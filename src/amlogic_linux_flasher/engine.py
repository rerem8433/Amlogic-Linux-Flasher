"""Moteur de flash : portage Python du script flash-tool de Khadas (aml-flash-tool).

Toutes les opérations USB passent par le binaire Amlogic « update ».
SoC pris en charge : g12a (S905X2/X3/Y2/D3, S922X), gxl (S905/S905X/W/D, S912), axg, txlx.
"""

from __future__ import annotations

import os
import pty
import re
import select
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import paths
from .i18n import tr_dyn
from .image import ImageInfo

PROGRESS_RE = re.compile(r"\[\s*(\d{1,3})%/\s*\d+MB\]")

SOCS = ("g12a", "gxl", "axg", "txlx")


class FlashError(Exception):
    pass


class Cancelled(FlashError):
    pass


@dataclass
class Options:
    soc: str = "g12a"
    wipe: bool = True             # « Effacer la flash »
    reset: bool = True            # « Réinitialiser après flash »
    password: Path | None = None  # fichier mot de passe USB (.bin)


class Flasher:
    """Flash « WorldCup » (outil update). Les callbacks sont appelés depuis le thread d'exécution."""

    progress_re = PROGRESS_RE

    def __init__(
        self,
        image: ImageInfo,
        opts: Options,
        on_status: Callable[[str, int], None],
        on_log: Callable[[str], None],
        log_file: Path | None = None,
    ):
        self.img = image
        self.opts = opts
        self.on_status = on_status
        self.on_log = on_log
        self.log_file = log_file
        self._cancel = False
        self._attempt = 1
        self._proc: subprocess.Popen | None = None
        self._pct = 0
        self._status = ""
        self._log_fh = open(log_file, "a", encoding="utf-8") if log_file else None

    # ------------------------------------------------------------------ outils
    def cancel(self) -> None:
        self._cancel = True
        p = self._proc
        if p and p.poll() is None:
            try:
                p.kill()
            except Exception:
                pass

    def log(self, line: str) -> None:
        if not line.startswith("$"):
            line = tr_dyn(line)
        if self._log_fh:
            self._log_fh.write(line.rstrip("\n") + "\n")
            self._log_fh.flush()
        self.on_log(line)

    def status(self, text: str, pct: int | None = None) -> None:
        if pct is not None:
            self._pct = max(0, min(100, int(pct)))
        self._status = text
        self.on_status(text, self._pct)

    def _check_cancel(self) -> None:
        if self._cancel:
            raise Cancelled("Arrêté par l'utilisateur")

    def wait(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self._check_cancel()
            time.sleep(0.1)

    def _build_cmd(self, sub: str, args: tuple[str, ...]) -> list[str]:
        # Reproduit le formatage de flash-tool : les arguments de bulkcmd/tplcmd
        # (et ceux qui contiennent des espaces) sont préfixés de 5 espaces.
        need_spaces = sub in ("bulkcmd", "tplcmd")
        cmd = [str(paths.UPDATE_BIN), sub]
        for a in args:
            a = str(a)
            cmd.append("     " + a if (need_spaces or " " in a) else a)
        return cmd

    def run(
        self,
        sub: str,
        *args: str,
        timeout: float | None = 60,
        progress: Callable[[int], None] | None = None,
    ) -> str:
        """Lance « update » et renvoie sa sortie standard (stderr va dans le journal)."""
        self._check_cancel()
        cmd = self._build_cmd(sub, args)
        self.log("$ " + " ".join(cmd[1:]))
        return self.spawn(cmd, timeout=timeout, progress=progress)

    def spawn(
        self,
        cmd: list[str],
        timeout: float | None = 60,
        progress: Callable[[int], None] | None = None,
    ) -> str:
        """Lance une commande dans un pseudo-terminal (sortie non bufferisée)."""
        self._check_cancel()
        master, slave = pty.openpty()
        err = tempfile.TemporaryFile()
        try:
            self._proc = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL, stdout=slave, stderr=err, close_fds=True
            )
        except OSError as e:
            os.close(master)
            os.close(slave)
            raise FlashError(f"Impossible de lancer {cmd[0]} : {e}") from e
        os.close(slave)

        chunks: list[str] = []
        buf = ""
        start = time.monotonic()
        try:
            while True:
                if self._cancel:
                    self._proc.kill()
                if timeout and time.monotonic() - start > timeout:
                    self._proc.kill()
                    self.log(f"  ! délai dépassé ({int(timeout)} s)")
                r, _, _ = select.select([master], [], [], 0.2)
                if r:
                    try:
                        data = os.read(master, 4096)
                    except OSError:
                        data = b""
                    if not data:
                        if self._proc.poll() is not None:
                            break
                        continue
                    text = data.decode("utf-8", "replace")
                    chunks.append(text)
                    buf += text
                    # découpage sur \r et \n pour suivre la progression en direct
                    parts = re.split(r"[\r\n]", buf)
                    buf = parts.pop()
                    for part in parts:
                        self._handle_line(part, progress)
                    if progress:
                        m = None
                        for m in self.progress_re.finditer(buf):
                            pass
                        if m:
                            progress(int(m.group(1)))
                elif self._proc.poll() is not None:
                    # vider ce qui reste
                    try:
                        while True:
                            r, _, _ = select.select([master], [], [], 0)
                            if not r:
                                break
                            data = os.read(master, 4096)
                            if not data:
                                break
                            t = data.decode("utf-8", "replace")
                            chunks.append(t)
                            buf += t
                    except OSError:
                        pass
                    break
            if buf:
                self._handle_line(buf, progress)
            self._proc.wait()
        finally:
            os.close(master)
            self._proc = None
            err.seek(0)
            e = err.read().decode("utf-8", "replace").strip()
            err.close()
            if e:
                for line in e.splitlines():
                    self.log("  [stderr] " + line)
        self._check_cancel()
        return "".join(chunks)

    def _handle_line(self, line: str, progress: Callable[[int], None] | None) -> None:
        line = line.strip()
        if not line:
            return
        m = self.progress_re.search(line)
        if m:
            if progress:
                progress(int(m.group(1)))
            # on ne journalise que la ligne finale de progression
            if int(m.group(1)) < 100:
                return
        self.log("  " + line)

    def run_ok(self, sub: str, *args: str, **kw) -> bool:
        return "ERR" not in self.run(sub, *args, **kw)

    def run_assert(self, what: str, sub: str, *args: str, **kw) -> str:
        out = self.run(sub, *args, **kw)
        if "ERR" in out:
            raise FlashError(f"{what} : échec de « update {sub} » (voir le journal)")
        return out

    # ------------------------------------------------------------- séquence
    def identify(self) -> str:
        return self.run("identify", "7", timeout=20)

    def wait_device(self, seconds: float = 20) -> str:
        end = time.monotonic() + seconds
        out = ""
        while time.monotonic() < end:
            out = self.identify()
            if "firmware" in out.lower():
                return out
            self.wait(1)
        return out

    def _unlock_password(self) -> None:
        out = self.identify()
        if "password check ng" not in out.lower():
            return
        if not self.opts.password:
            raise FlashError(
                "La box est verrouillée par mot de passe : indique le fichier "
                "mot de passe (menu Paramètres)."
            )
        self.status("Déverrouillage USB")
        # copie sans espace dans le chemin (formatage de update)
        pw = paths.CACHE_DIR / "password.bin"
        shutil.copyfile(self.opts.password, pw)
        self.run_assert("Déverrouillage", "password", str(pw))
        if "password check ok" not in self.identify().lower():
            raise FlashError("Mot de passe USB incorrect.")

    def _read_reg(self, addr: str) -> int:
        out = self.run("rreg", "4", addr, timeout=20)
        key = addr.lower().replace("0x", "")
        for line in out.splitlines():
            if key in line.lower() and ":" in line:
                tok = line.split(":", 1)[1].replace(" ", "")
                m = re.match(r"([0-9a-fA-F]+)", tok)
                if m:
                    return int(m.group(1), 16)
        return 0

    @staticmethod
    def _proto(identify_out: str) -> str:
        """4e champ de « This firmware version is a-b-c-d-… » (8 = nouveau protocole BL2)."""
        m = re.search(r"version is\s*([\d-]+)", identify_out)
        if not m:
            return ""
        f = m.group(1).split("-")
        return f[3] if len(f) > 3 else ""

    def _load_uboot(self, soc, bl2, tpl, ddr_load, ddr_run, uboot_load, uboot_run, bl2_params):
        # Initialisation DDR
        self.status("Initialisation DDR", 3)
        usb_protocol = ""
        if soc in ("gxl", "axg", "txlx"):
            ddr = paths.DATAS_DIR / "usbbl2runpara_ddrinit.bin"
            before = self._proto(self.identify())
            self.run_assert("DDR", "cwr", str(bl2), ddr_load)
            self.run_assert("DDR", "write", str(ddr), bl2_params)
            self.run_assert("DDR", "run", ddr_run)
            self.wait(8)
            out = self.identify()
            usb_protocol = self._proto(out)
            # le BL2 peut mettre plus de 8 s à reprendre la main : on attend qu'il réponde
            end = time.monotonic() + 10
            while usb_protocol != "8" and time.monotonic() < end:
                self.wait(1)
                out = self.identify()
                usb_protocol = self._proto(out)
            if "firmware" not in out.lower():
                raise FlashError("Initialisation DDR : la box ne répond plus.")
            if usb_protocol == "8":
                self.run_assert("DDR", "run", bl2_params)
            elif usb_protocol == before and self._attempt < 3:
                # le BL2 n'a pas pris la main : inutile d'envoyer U-Boot (la box planterait)
                raise FlashError("Initialisation DDR : le BL2 n'a pas démarré.")
            else:
                self.log(f"  protocole USB {usb_protocol or '?'} : séquence ancienne")
        else:  # g12a
            self.run_assert("DDR", "write", str(tpl), ddr_load, "0x10000")
            self.run_assert("DDR", "run", ddr_load)
            self.wait(8)

        # Lancement de U-Boot
        self.status("Lancement de U-Boot", 6)
        if soc in ("gxl", "axg", "txlx"):
            fip = paths.DATAS_DIR / "usbbl2runpara_runfipimg.bin"
            self.run_assert("U-Boot", "write", str(bl2), ddr_load)
            self.run_assert("U-Boot", "write", str(fip), bl2_params)
            self.run_assert("U-Boot", "write", str(tpl), uboot_load)
            self.run_assert("U-Boot", "run", bl2_params if usb_protocol == "8" else uboot_run)
        else:
            self.run_assert("U-Boot", "bl2_boot", str(tpl), timeout=120)
        self.wait(8)
        out = self.wait_device(20)
        if "firmware" not in out.lower():
            self.log("  ! U-Boot ne répond pas encore à identify, on continue")
        elif soc in ("gxl", "axg", "txlx") and self._proto(out) != "16" and "0-7-" not in out:
            self.log(f"  ! version inattendue après U-Boot : {out.strip().splitlines()[-1]}")

    def _prepare(self, soc: str):
        """Étapes 1 à 6 : rien n'est encore écrit sur l'eMMC, on peut tout recommencer."""
        img = self.img
        # 1. Détection
        self.status("Connexion", 0)
        if "firmware" not in self.identify().lower():
            raise FlashError("Box Amlogic non détectée (mode USB burn).")
        self._unlock_password()

        # 2. Redémarrage en mode mise à jour si la box est déjà sous U-Boot.
        # En ROM, cette commande échoue (normal) ; on la renvoie après le reset car
        # la ROM n'exécute le BL2 de façon fiable qu'après avoir reçu un bulkcmd.
        if self.run_ok("bulkcmd", "echo 12345", timeout=15):
            self.status("Redémarrage de la box", 1)
            self.run("bulkcmd", "bootloader_is_old", timeout=15)
            self.run_assert("Redémarrage", "bulkcmd", "erase_bootloader", timeout=15)
            self.run("bulkcmd", "reset", timeout=15)
            self.wait(8)
            if "firmware" not in self.wait_device(20).lower():
                raise FlashError("La box n'est pas revenue après le redémarrage.")
            self._unlock_password()
            self.run("bulkcmd", "echo 12345", timeout=15)
        self.status("Connexion", 2)

        # 3. Mode sécurisé ?
        secured = False
        if soc == "gxl":
            secured = bool(self._read_reg("0xc8100228") & 0x10)
        else:
            secured = bool(self._read_reg("0xff800228") & 0x10)
        if secured:
            self.log("Box en mode secure boot")

        # 4. Fichiers du bootloader
        bootloader = img.partition("bootloader")
        dtb_part = img.partition("_aml_dtb")
        if not bootloader:
            raise FlashError("Partition bootloader absente de l'image.")
        bootloader_file = img.workdir / bootloader.file
        dtb_file = img.workdir / dtb_part.file if dtb_part else None
        if secured:
            bl2, tpl = img.file_of("DDR_ENC"), img.file_of("UBOOT_ENC")
            if not bl2 or not tpl:
                raise FlashError(
                    "La box est en secure boot mais l'image ne contient pas "
                    "de bootloader signé."
                )
            meson1 = img.file_of("meson1_ENC")
        else:
            bl2 = img.file_of("DDR")
            tpl = img.file_of("UBOOT_COMP") or img.file_of("UBOOT")
            meson1 = img.file_of("meson1")
        for f in (bl2, tpl, meson1):
            if not f or not f.is_file():
                raise FlashError(f"Fichier manquant dans l'image : {f}")

        ddr_load = img.pconf("DDRLoad")
        ddr_run = img.pconf("DDRRun")
        uboot_load = img.pconf("UbootLoad")
        uboot_run = img.pconf("UbootRun")
        bl2_params = img.pconf("bl2ParaAddr")

        # 5-6. DDR + U-Boot en RAM
        self._load_uboot(soc, bl2, tpl, ddr_load, ddr_run, uboot_load, uboot_run, bl2_params)
        return bootloader_file, dtb_file, meson1


    def flash(self) -> None:
        img, o = self.img, self.opts
        soc = o.soc
        if soc not in SOCS:
            raise FlashError(f"SoC non pris en charge : {soc}")
        t0 = time.monotonic()
        self.log(f"Image : {img.path}")
        self.log(f"SoC : {soc} | effacement : {o.wipe} | reset : {o.reset}")

        # 1-6 avec jusqu'à 3 essais complets (la box redémarre seule en ROM si elle plante)
        for attempt in (1, 2, 3):
            self._attempt = attempt
            try:
                bootloader_file, dtb_file, meson1 = self._prepare(soc)
                break
            except Cancelled:
                raise
            except FlashError as e:
                if attempt == 3:
                    raise
                self.log(f"  ! {e} — nouvel essai complet ({attempt + 1}/3)")
                self.status("Reconnexion", 3)
                self.wait(3)
                if "firmware" not in self.wait_device(40).lower():
                    raise FlashError(
                        f"{e} La box ne revient pas : rebranche-la en mode USB burn.") from e
                self.wait(2)

        # évite de perdre 4 octets de commande après le reset (cf. flash-tool)
        self.run("bulkcmd", "echo 12345", timeout=15)

        # 7. DTB en mémoire, partitions, bootloader
        self.status("Écriture du device tree", 8)
        self.run_assert("DTB", "mwrite", str(meson1), "mem", "dtb", "normal")
        self.status("Création des partitions", 9)
        self.run_assert(
            "Partitions", "bulkcmd", "disk_initial 1" if o.wipe else "disk_initial 0",
            timeout=120,
        )
        if dtb_file:
            self.status("Écriture _aml_dtb", 10)
            self.run_assert("DTB", "partition", "_aml_dtb", str(dtb_file), timeout=120)
        self.status("Écriture bootloader", 11)
        self.run_assert(
            "Bootloader", "partition", "bootloader", str(bootloader_file), timeout=300,
            progress=lambda p: self.status("Écriture bootloader", 11 + p * 2 // 100),
        )
        self.run("bulkcmd", "setenv upgrade_step 1", timeout=15)
        self.run("bulkcmd", "save", timeout=30)

        # 8. Effacement data / cache
        if o.wipe:
            self.status("Effacement data / cache", 13)
            self.run("bulkcmd", "setenv firstboot 1", timeout=15)
            self.run("bulkcmd", "save", timeout=30)
            self.run("bulkcmd", "rpmb_reset", timeout=30)
            self.run("bulkcmd", "amlmmc erase data", timeout=600)
            self.run("bulkcmd", "nand erase.part data", timeout=600)
            self.run("bulkcmd", "amlmmc erase cache", timeout=300)
            self.run("bulkcmd", "nand erase.part cache", timeout=300)

        # 9. Partitions (pondérées par leur taille : 15 % → 99 %)
        parts = [p for p in img.partitions if p.sub_type not in ("bootloader", "_aml_dtb")]
        total = sum(max(p.size, 1) for p in parts) or 1
        done = 0
        for p in parts:
            f = img.workdir / p.file
            if not f.is_file():
                raise FlashError(f"Fichier de partition manquant : {p.file}")
            base, span = done, max(p.size, 1)

            def prog(pc: int, name=p.sub_type, base=base, span=span) -> None:
                overall = 15 + (base + span * pc / 100) * 84 / total
                self.status(f"Écriture {name}", overall)

            prog(0)
            self.run_assert(
                f"Partition {p.sub_type}", "partition", p.sub_type, str(f), p.file_type,
                timeout=None, progress=prog,
            )
            done += span
            self.log(f"  partition {p.sub_type} OK")

        # 10. Fin
        if o.reset:
            self.status("Redémarrage", 99)
            self.run("bulkcmd", "burn_complete 1", timeout=20)
        self.status("Flash réussi", 100)
        self.log(f"Flash réussi en {int(time.monotonic() - t0)} s")

    def close(self) -> None:
        if self._log_fh:
            self._log_fh.close()
            self._log_fh = None


ADNL_PROGRESS_RE = re.compile(r"\[([^\]]*)\]\s*%(\d{1,3})\.\.")


class AdnlFlasher(Flasher):
    """Flash ADNL (S905X4/Y4/W2, S905X5…) via adnl_burn_pkg.

    Le script de flash (usb_flow) est embarqué dans l'image elle-même :
    adnl_burn_pkg l'exécute et gère seul les redémarrages de la box.
    """

    progress_re = re.compile(r"%(\d{1,3})\.\.")

    def __init__(self, *a, check_crc: bool = False, **kw):
        super().__init__(*a, **kw)
        self.check_crc = check_crc
        self._step = ""

    def _handle_line(self, line: str, progress) -> None:
        line = line.strip()
        if not line:
            return
        m = ADNL_PROGRESS_RE.search(line)
        if m:
            step, pct = m.group(1).strip(), int(m.group(2))
            if step != self._step:
                self._step = step
                self.log(f"  étape : {step}")
            self.status(f"Écriture {step}" if step else "Écriture", pct)
            return
        # les traces DBG sont très bavardes : journal seulement
        self.log("  " + line)

    def flash(self) -> None:
        o = self.opts
        t0 = time.monotonic()
        cmd = [
            str(paths.ADNL_BIN), "-p", str(self.img.path),
            "-r", "1" if o.reset else "0",
            "-e", "1" if o.wipe else "0",
            "-c", "1" if self.check_crc else "0",
            "-t", "15",
        ]
        if o.password:
            cmd += ["-k", str(o.password)]
        self.log(f"Image : {self.img.path}")
        self.log("$ " + " ".join(cmd))
        self.status("Connexion", 0)
        out = self.spawn(cmd, timeout=None)
        if "burn successful" not in out:
            errs = [ln.strip() for ln in out.splitlines() if "ERR" in ln or "FAIL" in ln]
            raise FlashError(errs[-1] if errs else "adnl_burn_pkg a échoué (voir le journal).")
        self.status("Flash réussi", 100)
        self.log(f"Flash réussi en {int(time.monotonic() - t0)} s")


def make_flasher(protocol: str, image, opts: Options, check_crc: bool = False, **kw) -> Flasher:
    if protocol == "adnl":
        return AdnlFlasher(image, opts, check_crc=check_crc, **kw)
    return Flasher(image, opts, **kw)
