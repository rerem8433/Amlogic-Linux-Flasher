"""Détection des box Amlogic en mode USB burn (1b8e:c003 / 1b8e:c004) via sysfs."""

from __future__ import annotations

import os
from pathlib import Path

SYSFS = Path(os.environ.get("AMLF_SYSFS", "/sys/bus/usb/devices"))
VENDOR = "1b8e"
PRODUCTS = {"c003", "c004"}


def _read(p: Path) -> str:
    try:
        return p.read_text().strip().lower()
    except OSError:
        return ""


def scan() -> dict[str, dict]:
    """Renvoie {device_id: infos} ; device_id ressemble à « Hub3-2 »."""
    found: dict[str, dict] = {}
    try:
        entries = list(SYSFS.iterdir())
    except OSError:
        return found
    for d in entries:
        if ":" in d.name:  # interfaces, pas des périphériques
            continue
        if _read(d / "idVendor") != VENDOR:
            continue
        prod = _read(d / "idProduct")
        if prod not in PRODUCTS:
            continue
        busnum = _read(d / "busnum")
        devnum = _read(d / "devnum")
        found[f"Hub{d.name}"] = {
            "sysname": d.name,
            "product": prod,
            "bus": busnum,
            "dev": devnum,
            "devnode": f"/dev/bus/usb/{int(busnum):03d}/{int(devnum):03d}"
            if busnum.isdigit() and devnum.isdigit() else "",
        }
    return found


def accessible(info: dict) -> bool:
    node = info.get("devnode")
    return bool(node) and os.access(node, os.R_OK | os.W_OK)
