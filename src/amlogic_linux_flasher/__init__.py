"""Amlogic Linux Flasher — interface graphique de flash USB pour boîtiers Amlogic.

Une seule base de code, trois éditions (paquets distincts qui coexistent) :
  v9.0  : SoC « WorldCup » (S905X/X2/X3, S912, S922X…)  — outil update
  v11.0 : S905X4 / S905Y4 / S905W2 (ADNL)                — outil adnl_burn_pkg
  v14.0 : S905X5 / S905X5M (ADNL) + déverrouillage fastboot

ParadoxXx Squad.
"""

import os

try:  # écrit par packaging/build-deb.sh
    from ._edition import EDITION
except ImportError:
    EDITION = os.environ.get("AMLF_EDITION", "9")

EDITIONS = {
    "9": {
        "version": "9.0",
        "protocol": "worldcup",
        "products": {"c003"},
        "chips": "S905 / S905X / X2 / X3 / W / D / Y2, S912, S922X",
        "socs": [
            ("g12a", "S905X2/X3/Y2/D3 (g12a)", "S905X2, S905X3, S905Y2, S905D3, S922X, A311D"),
            ("gxl", "S905/X/W/D, S912 (gxl)", "S905, S905X, S905W, S905D, S905L, S912"),
            ("axg", "A113 (axg)", "A113"),
            ("txlx", "T962 (txlx)", "T962"),
        ],
    },
    "11": {
        "version": "11.0",
        "protocol": "adnl",
        "products": {"c004"},
        "chips": "S905X4, S905Y4, S905W2",
        "socs": [],
    },
    "14": {
        "version": "14.0",
        "protocol": "adnl",
        "products": {"c004"},
        "chips": "S905X5, S905X5M",
        "socs": [],
    },
}

if EDITION not in EDITIONS:
    EDITION = "9"
ED = EDITIONS[EDITION]

APP_NAME = "Amlogic Linux Flasher"
APP_ID = f"amlogic-linux-flasher-v{EDITION}"
VERSION = ED["version"]
APP_TITLE = f"{APP_NAME} v{VERSION}"
