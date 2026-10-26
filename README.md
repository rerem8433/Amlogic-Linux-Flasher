# Amlogic Linux Flasher

*ParadoxXx Squad* — [Français](#français) · [English](#english)

---

## Français

Flash USB des box Android TV Amlogic depuis Linux (Mint, Ubuntu…), avec une interface calquée sur **Amlogic USB Burning Tool**. Plus besoin de redémarrer sous Windows.

L'interface est disponible en **français** et en **anglais** (menu *Langue*). Au premier lancement, la langue du système est choisie automatiquement.

### Éditions

Trois paquets indépendants, installables ensemble :

| Édition | Puces | Mode USB de la box | Outil Amlogic |
|---|---|---|---|
| **v9.0** | S905, S905X/X2/X3, S905W/D/Y2, S912, S922X, A113, T962 | WorldCup `1b8e:c003` | `update` |
| **v11.0** | S905X4, S905Y4, S905W2 | ADNL `1b8e:c004` | `adnl_burn_pkg` |
| **v14.0** | S905X5, S905X5M | ADNL `1b8e:c004` | `adnl_burn_pkg` |

Chaque édition reconnaît une image ou une box de la mauvaise génération et indique laquelle utiliser.

### Installation

```bash
sudo apt install ./amlogic-linux-flasher-v9_9.0_amd64.deb
```

Le paquet installe la règle udev (accès à la box sans `sudo`), `adb` et `fastboot`. Si la box était branchée pendant l'installation, débranche-la et rebranche-la.

### Onglet Flash USB

1. **Paramètres > Importer une image** (ou glisser-déposer un `.img`).
2. Cliquer **Démarrer**.
3. Brancher la box en mode USB burn (bouton reset enfoncé + câble USB). Le flash démarre tout seul.

Tant que **Démarrer** est actif, chaque nouvelle box branchée est flashée à la suite (une box à la fois). Une box qui vient d'être flashée et qui redémarre sur le même port n'est pas reflashée.

En v9, la famille de la puce est lue dans la ROM dès le branchement (ex. « S905X / S905W / S905D / S905L (gxl) ») et le SoC est réglé automatiquement. Le modèle commercial (x96mini, HK1…) n'est pas lisible en mode burn.

| Option | Effet |
|---|---|
| Effacer la flash | *Erase Flash* |
| Réinitialiser après flash | *Reset After Burn* |
| SoC (v9) | `g12a` : S905X2/X3/Y2/D3, S922X — `gxl` : S905/X/W/D, S912 — `axg` : A113 — `txlx` : T962 |
| Vérifier l'image (v11/v14) | Contrôle CRC de l'image avant le flash |
| Fichier mot de passe | Box verrouillées (menu Paramètres) |

Si la box décroche pendant le chargement de DDR / U-Boot (avant toute écriture sur l'eMMC), la v9 recommence automatiquement, jusqu'à 3 fois.

### Onglet ADB / Fastboot

- Redémarrages : fastboot, recovery, **mode USB burn** (`adb reboot update`).
- **Déverrouiller le bootloader** : vérifie que la box est en bootloader (pas en fastbootd), puis `fastboot flashing unlock`.
- **Exécuter un script** : charge le `.cmd` / `.bat` fourni avec le firmware (ex. `Unlock_Bootloader.cmd` de SlimboxTV), en extrait les lignes `adb` / `fastboot` (chemins Windows convertis) et les exécute avec les outils Linux, après aperçu.
- Ligne de commande libre `adb …` / `fastboot …`.

Exemple S905X5 (procédure SlimboxTV) : Recovery > *Reboot to bootloader* → onglet ADB / Fastboot → *Déverrouiller le bootloader* → puis flash dans l'onglet Flash USB.

### Fichiers de l'utilisateur

`apt purge` ne touche pas au dossier personnel. Pour tout remettre à zéro :

| Contenu | Emplacement |
|---|---|
| Réglages | `~/.config/ParadoxXx Squad/amlogic-linux-flasher-vXX.conf` |
| Image décompressée | `~/.cache/amlogic-linux-flasher-vXX/` (menu *Vider le cache de l'image*) |
| Journaux | `~/.local/share/amlogic-linux-flasher-vXX/logs/` |

### Lancer depuis les sources

```bash
sudo apt install python3-pyqt5 libusb-0.1-4 adb fastboot
AMLF_EDITION=9 PYTHONPATH=src python3 -m amlogic_linux_flasher
```

### Construire les .deb

```bash
./packaging/build-deb.sh          # les trois éditions
./packaging/build-deb.sh 14       # une seule
```

---

## English

USB flashing of Amlogic Android TV boxes from Linux (Mint, Ubuntu…), with an interface modelled on **Amlogic USB Burning Tool**. No more rebooting into Windows.

The interface is available in **English** and **French** (*Language* menu). On first launch, the system language is picked automatically.

### Editions

Three independent packages that can be installed side by side:

| Edition | Chips | Box USB mode | Amlogic tool |
|---|---|---|---|
| **v9.0** | S905, S905X/X2/X3, S905W/D/Y2, S912, S922X, A113, T962 | WorldCup `1b8e:c003` | `update` |
| **v11.0** | S905X4, S905Y4, S905W2 | ADNL `1b8e:c004` | `adnl_burn_pkg` |
| **v14.0** | S905X5, S905X5M | ADNL `1b8e:c004` | `adnl_burn_pkg` |

Each edition recognises an image or a box from the wrong generation and tells you which one to use.

### Installation

```bash
sudo apt install ./amlogic-linux-flasher-v9_9.0_amd64.deb
```

The package installs the udev rule (box access without `sudo`), `adb` and `fastboot`. If the box was plugged in during installation, unplug it and plug it back.

### USB Burn tab

1. **Setting > Import image** (or drag and drop an `.img`).
2. Click **Start**.
3. Plug the box in USB burning mode (reset button held + USB cable). Burning starts on its own.

While **Start** is active, every newly plugged box is burned in turn (one box at a time). A box that has just been burned and reboots on the same port is not burned again.

In v9, the chip family is read from the ROM as soon as the box is plugged (e.g. "S905X / S905W / S905D / S905L (gxl)") and the SoC is selected automatically. The retail model (x96mini, HK1…) cannot be read in burning mode.

| Option | Effect |
|---|---|
| Erase Flash | *Erase Flash* |
| Reset After Burn | *Reset After Burn* |
| SoC (v9) | `g12a`: S905X2/X3/Y2/D3, S922X — `gxl`: S905/X/W/D, S912 — `axg`: A113 — `txlx`: T962 |
| Check image (v11/v14) | CRC check of the image before burning |
| Password file | Locked boxes (Setting menu) |

If the box drops off USB while DDR / U-Boot is being loaded (before anything is written to the eMMC), v9 retries automatically, up to 3 times.

### ADB / Fastboot tab

- Reboots: fastboot, recovery, **USB burning mode** (`adb reboot update`).
- **Unlock bootloader**: checks the box is in bootloader mode (not fastbootd), then `fastboot flashing unlock`.
- **Run a script**: loads the `.cmd` / `.bat` shipped with the firmware (e.g. SlimboxTV's `Unlock_Bootloader.cmd`), extracts the `adb` / `fastboot` lines (Windows paths converted) and runs them with the Linux tools, after a preview.
- Free command line `adb …` / `fastboot …`.

S905X5 example (SlimboxTV procedure): Recovery > *Reboot to bootloader* → ADB / Fastboot tab → *Unlock bootloader* → then burn in the USB Burn tab.

### User files

`apt purge` does not touch the home folder. To reset everything:

| Content | Location |
|---|---|
| Settings | `~/.config/ParadoxXx Squad/amlogic-linux-flasher-vXX.conf` |
| Unpacked image | `~/.cache/amlogic-linux-flasher-vXX/` (*Clear image cache* menu) |
| Logs | `~/.local/share/amlogic-linux-flasher-vXX/logs/` |

### Run from source

```bash
sudo apt install python3-pyqt5 libusb-0.1-4 adb fastboot
AMLF_EDITION=9 PYTHONPATH=src python3 -m amlogic_linux_flasher
```

### Build the .deb packages

```bash
./packaging/build-deb.sh          # all three editions
./packaging/build-deb.sh 14       # a single one
```

---

## Crédits / Credits

- `update`, `aml_image_v2_packer` and `adnl_burn_pkg`: Amlogic, redistributed by Khadas in [khadas/utils](https://github.com/khadas/utils).
- v9 burning sequence ported from Khadas' `aml-flash-tool` script.
