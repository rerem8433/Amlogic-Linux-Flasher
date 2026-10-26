"""Identification de la puce d'une box en mode USB burn (WorldCup, 1b8e:c003).

Le VID/PID est le même pour toutes les puces Amlogic : il ne dit rien du modèle.
On interroge donc la ROM :
  - « update identify 7 » : mode de la box (ROM / U-Boot)
  - « update chipid »     : identifiant de puce, qui commence par « AML<famille> »
                            (ex. AMLGXL…), comme dans le code commenté d'aml-flash-tool.
Le modèle commercial (x96mini, HK1…) n'est pas lisible en mode burn.
"""

from __future__ import annotations

import re
import subprocess

from . import paths

# famille → (puces, valeur du choix SoC dans l'interface ou None)
FAMILIES = {
    "GXBB": ("S905", None),
    "GXL": ("S905X / S905W / S905D / S905L", "gxl"),
    "GXM": ("S912", "gxl"),
    "GXLX": ("S905L / S805X", "gxl"),
    "TXL": ("T950 / T960", None),
    "TXLX": ("T962", "txlx"),
    "AXG": ("A113", "axg"),
    "G12A": ("S905X2 / S905Y2 / S905D2", "g12a"),
    "G12B": ("S922X / A311D", "g12a"),
    "SM1": ("S905X3 / S905D3", "g12a"),
    "TL1": ("T962X2", None),
    "TM2": ("T962E2", None),
}


def _run(*args: str, timeout: float = 6) -> str:
    try:
        p = subprocess.run(
            [str(paths.UPDATE_BIN), *args], capture_output=True, text=True,
            errors="replace", timeout=timeout, stdin=subprocess.DEVNULL,
        )
        return p.stdout + p.stderr
    except (OSError, subprocess.TimeoutExpired):
        return ""


def stage(identify_out: str) -> str:
    """« rom », « uboot » ou « » d'après « This firmware version is a-b-c-d… »."""
    m = re.search(r"version is\s*(\d+)-(\d+)", identify_out)
    if not m:
        return ""
    return "uboot" if m.group(1) == "0" else "rom"


def family_from_chipid(out: str) -> str:
    m = re.search(r"ChipID is:\s*0x([0-9a-fA-F]+)", out)
    if not m:
        return ""
    hexs = m.group(1)
    if len(hexs) % 2:
        hexs = hexs[:-1]
    try:
        text = bytes.fromhex(hexs).decode("ascii", "replace")
    except ValueError:
        return ""
    if not text.startswith("AML"):
        return ""
    rest = text[3:]
    # la plus longue famille connue qui correspond (GXLX avant GXL…)
    for fam in sorted(FAMILIES, key=len, reverse=True):
        if rest.upper().startswith(fam):
            return fam
    m2 = re.match(r"[A-Z0-9]+", rest.upper())
    return m2.group(0)[:4] if m2 else ""


def probe() -> dict:
    """Interroge la box. Renvoie {stage, family, chips, soc}. Ne lève jamais d'exception."""
    info = {"stage": "", "family": "", "chips": "", "soc": None}
    out = _run("identify", "7")
    info["stage"] = stage(out)
    if info["stage"] == "rom":
        fam = family_from_chipid(_run("chipid"))
        if fam:
            info["family"] = fam
            chips, soc = FAMILIES.get(fam, ("", None))
            info["chips"] = chips
            info["soc"] = soc
    return info


def describe(info: dict) -> str:
    """Texte court pour la colonne État."""
    if info.get("chips"):
        return f"{info['chips']} ({info['family'].lower()})"
    if info.get("family"):
        return info["family"]
    return ""
