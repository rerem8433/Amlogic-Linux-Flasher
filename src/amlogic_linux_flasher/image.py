"""Lecture des images Amlogic au format USB Burning Tool (aml_upgrade_package v2)."""

from __future__ import annotations

import json
import re
import shutil
import struct
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import paths

MAGIC = b"\x56\x19\xb5\x27"  # 0x27b51956, petit-boutiste, à l'offset 8
_KV = re.compile(r'(\w+)="([^"]*)"')


class ImageError(Exception):
    pass


@dataclass
class Item:
    file: str
    main_type: str
    sub_type: str
    file_type: str = "normal"
    size: int = 0


@dataclass
class ImageInfo:
    path: Path
    workdir: Path | None
    size: int
    items: list[Item] = field(default_factory=list)
    platform: dict[str, str] = field(default_factory=dict)

    # ---- accès pratiques -------------------------------------------------
    def sub(self, sub_type: str) -> Item | None:
        for it in self.items:
            if it.sub_type == sub_type and it.main_type != "PARTITION":
                return it
        return None

    def file_of(self, sub_type: str) -> Path | None:
        it = self.sub(sub_type)
        return self.workdir / it.file if it else None

    @property
    def partitions(self) -> list[Item]:
        return [it for it in self.items if it.main_type == "PARTITION"]

    def partition(self, name: str) -> Item | None:
        for it in self.partitions:
            if it.sub_type == name:
                return it
        return None

    def pconf(self, key: str) -> str:
        return self.platform.get(key, "")


def quick_check(path: Path) -> None:
    """Contrôle rapide de l'en-tête (avant le contrôle CRC complet)."""
    if not path.is_file():
        raise ImageError(f"Fichier introuvable : {path}")
    with open(path, "rb") as f:
        head = f.read(16)
    if len(head) < 12 or head[8:12] != MAGIC:
        raise ImageError(
            "Ce fichier n'est pas une image Amlogic USB Burning Tool "
            "(en-tête 0x27b51956 absent)."
        )


HEADER_SIZE = 64
ITEM_V2_SIZE = 576  # itemId, fileType, 3×u64, main[256], sub[256], verify, backup…


def list_items(path: Path) -> list[Item]:
    """Lit la table des éléments directement dans l'en-tête (sans décompresser).

    Renvoie une liste vide si le format n'est pas reconnu (v1, v3…).
    """
    try:
        with open(path, "rb") as f:
            head = f.read(HEADER_SIZE)
            if len(head) < HEADER_SIZE or head[8:12] != MAGIC:
                return []
            version, = struct.unpack_from("<I", head, 4)
            count, = struct.unpack_from("<I", head, 24)
            if version != 2 or not 0 < count < 512:
                return []
            table = f.read(count * ITEM_V2_SIZE)
    except OSError:
        return []
    items: list[Item] = []
    for i in range(count):
        off = i * ITEM_V2_SIZE
        if off + ITEM_V2_SIZE > len(table):
            break
        rec = table[off:off + ITEM_V2_SIZE]
        file_type, = struct.unpack_from("<I", rec, 4)
        size, = struct.unpack_from("<Q", rec, 24)
        main = rec[32:288].split(b"\0", 1)[0].decode("ascii", "replace")
        sub = rec[288:544].split(b"\0", 1)[0].decode("ascii", "replace")
        items.append(Item(file="", main_type=main, sub_type=sub,
                          file_type=str(file_type), size=size))
    return items


def is_adnl(items: list[Item]) -> bool:
    """Les images ADNL (S905X4/Y4/X5…) embarquent leur propre script de flash."""
    return any(it.main_type == "aml" and it.sub_type == "usb_flow" for it in items)


def crc_check(path: Path) -> tuple[bool, str]:
    """Contrôle CRC complet via aml_image_v2_packer -c."""
    proc = subprocess.run(
        [str(paths.PACKER_BIN), "-c", str(path)],
        capture_output=True, text=True, errors="replace",
    )
    out = (proc.stdout + proc.stderr).strip()
    return ("Image check OK" in out and proc.returncode == 0), out


def _stamp_for(path: Path) -> dict:
    st = path.stat()
    return {"path": str(path.resolve()), "size": st.st_size, "mtime": st.st_mtime_ns}


def cached(path: Path) -> bool:
    stamp = paths.WORK_DIR / ".stamp.json"
    try:
        return json.loads(stamp.read_text()) == _stamp_for(path)
    except Exception:
        return False


def unpack(path: Path) -> str:
    """Décompresse l'image dans le cache (réutilisé si l'image n'a pas changé)."""
    paths.ensure_dirs()
    if cached(path):
        return "cache"
    work = paths.WORK_DIR
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    need = path.stat().st_size * 1.05
    free = shutil.disk_usage(work).free
    if free < need:
        raise ImageError(
            f"Espace disque insuffisant dans {paths.CACHE_DIR} : "
            f"{free // 2**20} Mo libres, {int(need) // 2**20} Mo nécessaires."
        )
    proc = subprocess.run(
        [str(paths.PACKER_BIN), "-d", str(path), str(work)],
        capture_output=True, text=True, errors="replace",
    )
    out = proc.stdout + proc.stderr
    if "Image unpack OK!" not in out:
        shutil.rmtree(work, ignore_errors=True)
        raise ImageError("Échec de la décompression de l'image :\n" + out[-2000:])
    (work / ".stamp.json").write_text(json.dumps(_stamp_for(path)))
    return out


def parse(path: Path) -> ImageInfo:
    work = paths.WORK_DIR
    cfg = work / "image.cfg"
    if not cfg.is_file():
        raise ImageError("image.cfg absent de l'image décompressée.")
    info = ImageInfo(path=path, workdir=work, size=path.stat().st_size)
    for line in cfg.read_text(errors="replace").splitlines():
        kv = dict(_KV.findall(line))
        if "file" not in kv:
            continue
        it = Item(
            file=kv["file"],
            main_type=kv.get("main_type", ""),
            sub_type=kv.get("sub_type", ""),
            file_type=kv.get("file_type", "normal") or "normal",
        )
        fp = work / it.file
        it.size = fp.stat().st_size if fp.is_file() else 0
        info.items.append(it)

    plat = info.file_of("platform")
    if plat and plat.is_file():
        for line in plat.read_text(errors="replace").splitlines():
            m = re.match(r"\s*(\w+)\s*[:=]\s*(\S+)", line)
            if m:
                info.platform[m.group(1)] = m.group(2)
    if not info.partitions:
        raise ImageError("Aucune partition trouvée dans l'image.")
    return info


def clear_cache() -> None:
    shutil.rmtree(paths.WORK_DIR, ignore_errors=True)


def load_header(path: Path) -> ImageInfo:
    """Chargement léger (éditions ADNL) : pas de décompression, adnl_burn_pkg lit l'image."""
    quick_check(path)
    items = list_items(path)
    return ImageInfo(path=path, workdir=None, size=path.stat().st_size, items=items)
