"""Emplacements des outils embarqués et des dossiers utilisateur."""

import os
from pathlib import Path

from . import APP_ID

_HERE = Path(__file__).resolve().parent


def _tools_dir() -> Path:
    env = os.environ.get("AMLF_TOOLS_DIR")
    if env:
        return Path(env)
    for cand in (
        _HERE.parent.parent / "tools",          # dépôt source
        _HERE.parent / "tools",                 # /usr/lib/amlogic-linux-flasher/tools
        Path("/usr/lib") / APP_ID / "tools",
    ):
        if cand.is_dir():
            return cand
    return Path("/usr/lib") / APP_ID / "tools"


TOOLS_DIR = _tools_dir()
UPDATE_BIN = Path(os.environ.get("AMLF_UPDATE", TOOLS_DIR / "update"))
PACKER_BIN = Path(os.environ.get("AMLF_PACKER", TOOLS_DIR / "aml_image_v2_packer"))
ADNL_BIN = Path(os.environ.get("AMLF_ADNL", TOOLS_DIR / "adnl" / "adnl_burn_pkg"))
DATAS_DIR = TOOLS_DIR / "datas"
ADB_BIN = os.environ.get("AMLF_ADB", "adb")
FASTBOOT_BIN = os.environ.get("AMLF_FASTBOOT", "fastboot")

_xdg_cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
_xdg_data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

CACHE_DIR = _xdg_cache / APP_ID
WORK_DIR = CACHE_DIR / "image"
LOG_DIR = _xdg_data / APP_ID / "logs"

UDEV_RULE_NAME = f"70-{APP_ID}.rules"
UDEV_RULE_DIRS = (Path("/lib/udev/rules.d"), Path("/usr/lib/udev/rules.d"), Path("/etc/udev/rules.d"))
UDEV_RULE = (
    'SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", ATTR{idVendor}=="1b8e", '
    'ATTR{idProduct}=="c003", MODE="0666", TAG+="uaccess"\n'
    'SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", ATTR{idVendor}=="1b8e", '
    'ATTR{idProduct}=="c004", MODE="0666", TAG+="uaccess"\n'
)


def ensure_dirs() -> None:
    for d in (CACHE_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


def udev_rule_installed() -> bool:
    for d in UDEV_RULE_DIRS:
        if list(d.glob("70-amlogic-linux-flasher*.rules")) or \
                (d / "70-persistent-usb-ubuntu14.rules").exists():  # règle Khadas
            return True
    return False
