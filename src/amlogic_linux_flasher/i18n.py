"""Traductions minimalistes : le français est la langue source, l'anglais est traduit."""

import re

_lang = "fr"

EN = {
    # menus
    "Paramètres": "Setting",
    "Aide": "Help",
    "Langue": "Language",
    "Importer une image…": "Import image…",
    "Fichier mot de passe…": "Password file…",
    "Retirer le mot de passe": "Clear password",
    "Installer la règle udev…": "Install udev rule…",
    "Vider le cache de l'image": "Clear image cache",
    "Quitter": "Quit",
    "Ouvrir le dossier des journaux": "Open log folder",
    "À propos": "About",
    # colonnes
    "Appareil": "DeviceID",
    "État": "Status",
    "Temps": "Time",
    "Statistique": "Statistic",
    "Heure": "Time",
    "Message (double-clic pour ouvrir)": "Message (double click open)",
    "Partition": "Partition",
    "Taille": "Size",
    # panneau droit
    "Démarrer": "Start",
    "Arrêter": "Stop",
    "Actualiser": "Refresh",
    "Configuration": "Configuration",
    "Effacer la flash": "Erase Flash",
    "Réinitialiser après flash": "Reset After Burn",
    "SoC :": "SoC:",
    "Contenu de l'image": "Image content",
    # barre d'état
    "Aucune image": "No image",
    "Total : {t}  Réussis : {s}  Échecs : {f}": "Total: {t}  Success: {s}  Failed: {f}",
    # états
    "Connecté": "Connect",
    "Déconnecté": "Disconnect",
    "En attente": "Waiting",
    "Connexion": "Connecting",
    "Déverrouillage USB": "Unlocking USB",
    "Redémarrage de la box": "Rebooting board",
    "Initialisation DDR": "Initializing DDR",
    "Lancement de U-Boot": "Running U-Boot",
    "Écriture du device tree": "Writing device tree",
    "Création des partitions": "Creating partitions",
    "Effacement data / cache": "Erasing data / cache",
    "Redémarrage": "Resetting",
    "Reconnexion": "Reconnecting",
    " : ": ": ",
    "Flash réussi": "Burn Success",
    "Échec": "Failed",
    "Arrêté": "Stopped",
    # dialogues
    "Vérification de l'image": "Checking image",
    "Vérification de l'image…": "Checking image…",
    "Préparation de l'image…": "Unpacking image…",
    "Lecture de l'image…": "Reading image…",
    "Images Amlogic (*.img);;Tous les fichiers (*)": "Amlogic images (*.img);;All files (*)",
    "Fichiers mot de passe (*.bin);;Tous les fichiers (*)": "Password files (*.bin);;All files (*)",
    "Image chargée : {name} ({n} partitions)": "Image loaded: {name} ({n} partitions)",
    "Image invalide": "Invalid image",
    "Importe d'abord une image (Paramètres > Importer une image).":
        "Import an image first (Setting > Import image).",
    "Arrêter le flash en cours ? La box devra être reflashée.":
        "Stop the current burn? The box will need to be flashed again.",
    "Plusieurs box sont connectées : une seule à la fois est prise en charge.":
        "Several boxes are connected: only one at a time is supported.",
    "Pas d'accès USB à la box : installe la règle udev (menu Paramètres), puis rebranche la box.":
        "No USB access to the box: install the udev rule (Setting menu), then replug the box.",
    "Règle udev installée. Rebranche la box.": "udev rule installed. Replug the box.",
    "Installation de la règle udev annulée ou impossible.": "udev rule installation cancelled or failed.",
    "Cache vidé.": "Cache cleared.",
    "Mot de passe : {name}": "Password: {name}",
    "Mot de passe retiré.": "Password cleared.",
    "Prêt : branche la box en mode USB burn.": "Ready: plug the box in USB burning mode.",
    "Journal": "Log",
    "Fermer": "Close",
    "Outil manquant : {p}": "Missing tool: {p}",
    # éditions
    "Flash USB": "USB Burn",
    "Vérifier l'image (CRC)": "Check image (CRC)",
    "Puces : {c}": "Chips: {c}",
    "Box en mode ADNL (S905X4/Y4/X5…) : utilise Amlogic Linux Flasher v11.0 / v14.0.":
        "Box in ADNL mode (S905X4/Y4/X5…): use Amlogic Linux Flasher v11.0 / v14.0.",
    "Box en mode WorldCup (S905X/X2/X3…) : utilise Amlogic Linux Flasher v9.0.":
        "Box in WorldCup mode (S905X/X2/X3…): use Amlogic Linux Flasher v9.0.",
    "Boîtier détecté en mode flash : identification…": "Box detected in burning mode: identifying…",
    "prêt à démarrer le flash": "ready to start burning",
    "flash imminent": "burning about to start",
    "{chip} détecté en mode flash : {ready}": "{chip} detected in burning mode: {ready}",
    "Boîtier détecté en mode flash (U-Boot) : {ready}": "Box detected in burning mode (U-Boot): {ready}",
    "Boîtier détecté en mode flash : {ready}": "Box detected in burning mode: {ready}",
    "Puce détectée : {chip}": "Chip detected: {chip}",
    "Flash USB des box Android TV Amlogic depuis Linux, à la manière d’Amlogic USB Burning Tool.":
        "USB flashing of Amlogic Android TV boxes from Linux, in the style of Amlogic USB Burning Tool.",
    "Moteur : outils Amlogic update / adnl_burn_pkg (redistribués par Khadas), séquence du script aml-flash-tool.":
        "Engine: Amlogic update / adnl_burn_pkg tools (redistributed by Khadas), aml-flash-tool script sequence.",
    "Box flashée revenue en mode USB après redémarrage : débranche-la.":
        "Flashed box came back in USB mode after reboot: unplug it.",
    "Flash réussi : débranche la box avant d'en brancher une autre.":
        "Burn successful: unplug the box before plugging another one.",
    "SoC réglé sur {soc}": "SoC set to {soc}",
    "attention, SoC choisi : {soc}": "warning, selected SoC: {soc}",
    # ADB / Fastboot
    "Appareils": "Devices",
    "Lister les appareils": "List devices",
    "Redémarrer en fastboot": "Reboot to fastboot",
    "Exécuter un script…": "Run a script…",
    "Redémarrer en recovery": "Reboot to recovery",
    "Redémarrer en mode USB burn": "Reboot to USB burning mode",
    "Redémarrer": "Reboot",
    "Infos (getvar all)": "Info (getvar all)",
    "Déverrouiller le bootloader": "Unlock bootloader",
    "Verrouiller le bootloader": "Lock bootloader",
    "Redémarrer en bootloader": "Reboot to bootloader",
    "Script du firmware": "Firmware script",
    "Exécuter un script (.cmd / .bat / .sh)…": "Run a script (.cmd / .bat / .sh)…",
    "Ex. : Unlock_Bootloader.cmd fourni avec le firmware. Seules les lignes adb / fastboot sont exécutées, avec les outils Linux.":
        "E.g. Unlock_Bootloader.cmd shipped with the firmware. Only adb / fastboot lines are run, with the Linux tools.",
    "Commande : fastboot getvar unlocked": "Command: fastboot getvar unlocked",
    "Exécuter": "Run",
    "Annuler": "Cancel",
    "Effacer": "Clear",
    "Commandes qui vont être exécutées (dossier : {d}) :": "Commands to run (folder: {d}):",
    "Lignes ignorées (ni adb ni fastboot) :": "Ignored lines (neither adb nor fastboot):",
    "Scripts (*.cmd *.bat *.sh);;Tous les fichiers (*)": "Scripts (*.cmd *.bat *.sh);;All files (*)",
    "Aucune commande adb / fastboot dans ce script.": "No adb / fastboot command in this script.",
    "Seules les commandes adb et fastboot sont acceptées.": "Only adb and fastboot commands are accepted.",
    "Outil introuvable : {t}. Installe-le : sudo apt install adb fastboot":
        "Tool not found: {t}. Install it: sudo apt install adb fastboot",
    "(code de sortie {c})": "(exit code {c})",
    "Aucune box en mode fastboot : Recovery > Reboot to bootloader, câble USB A-A sur le port le plus proche de l'arrière.":
        "No box in fastboot mode: Recovery > Reboot to bootloader, USB A-A cable on the port closest to the back.",
    "La box est en fastbootd (userspace), pas en bootloader : fais « Redémarrer en bootloader ».":
        "The box is in fastbootd (userspace), not bootloader: use \"Reboot to bootloader\".",
    "La box doit être en mode fastboot (Recovery > Reboot to bootloader, ou bouton « Redémarrer en bootloader »).\n\nLe déverrouillage peut effacer les données de la box. Continuer ?":
        "The box must be in fastboot mode (Recovery > Reboot to bootloader, or the \"Reboot to bootloader\" button).\n\nUnlocking may wipe the box data. Continue?",
    "Reverrouiller le bootloader ? Avec un firmware non officiel, la box risque de ne plus démarrer.":
        "Lock the bootloader again? With an unofficial firmware the box may no longer boot.",
}

_STATUS_PCT = re.compile(r"^(Écriture) (\S+) (\d+%)$")


def system_lang() -> str:
    import locale
    import os
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(var)
        if v:
            return "fr" if v.lower().startswith("fr") else "en"
    loc = (locale.getlocale()[0] or "").lower()
    return "fr" if loc.startswith("fr") else "en"


def set_lang(lang: str) -> None:
    global _lang
    _lang = "en" if lang == "en" else "fr"


def lang() -> str:
    return _lang


def tr(text: str, **kw) -> str:
    out = text if _lang == "fr" else EN.get(text, text)
    return out.format(**kw) if kw else out


def tr_status(text: str) -> str:
    """Traduit les états du moteur, y compris « Écriture system 45% »."""
    if _lang == "fr":
        return text
    if text in EN:
        return EN[text]
    m = _STATUS_PCT.match(text)
    if m:
        return f"Downloading {m.group(2)} {m.group(3)}"
    if text.startswith("Écriture "):
        return "Downloading " + text[len("Écriture "):]
    if text.startswith("Échec : "):
        return "Failed: " + text[len("Échec : "):]
    return EN.get(text, text)


# Messages dynamiques (erreurs du moteur, journal) : regex française → modèle anglais
_DYN = [
    (r"Impossible de lancer (.+) : (.+)", r"Cannot run \1: \2"),
    (r"(.+) : échec de « update (\S+) » \(voir le journal\)", r"\1: « update \2 » failed (see log)"),
    (r"Initialisation DDR : la box ne répond plus\.", "DDR init: the box no longer responds."),
    (r"Initialisation DDR : le BL2 n'a pas démarré\.", "DDR init: BL2 did not start."),
    (r"La box est verrouillée par mot de passe : indique le fichier mot de passe \(menu Paramètres\)\.",
     "The box is password-locked: set the password file (Setting menu)."),
    (r"Mot de passe USB incorrect\.", "Wrong USB password."),
    (r"Box Amlogic non détectée \(mode USB burn\)\.", "Amlogic box not detected (USB burning mode)."),
    (r"La box n'est pas revenue après le redémarrage\.", "The box did not come back after reboot."),
    (r"Partition bootloader absente de l'image\.", "No bootloader partition in the image."),
    (r"La box est en secure boot mais l'image ne contient pas de bootloader signé\.",
     "The box uses secure boot but the image has no signed bootloader."),
    (r"Fichier manquant dans l'image : (.+)", r"Missing file in image: \1"),
    (r"SoC non pris en charge : (.+)", r"Unsupported SoC: \1"),
    (r"(.+) La box ne revient pas : rebranche-la en mode USB burn\.",
     r"\1 The box does not come back: replug it in USB burning mode."),
    (r"Fichier de partition manquant : (.+)", r"Missing partition file: \1"),
    (r"adnl_burn_pkg a échoué \(voir le journal\)\.", "adnl_burn_pkg failed (see log)."),
    (r"Arrêté", "Stopped"),
    # images
    (r"Fichier introuvable : (.+)", r"File not found: \1"),
    (r"Ce fichier n'est pas une image Amlogic USB Burning Tool \(en-tête 0x27b51956 absent\)\.",
     "This file is not an Amlogic USB Burning Tool image (0x27b51956 header missing)."),
    (r"Espace disque insuffisant dans (.+) : (\d+) Mo libres, (\d+) Mo nécessaires\.",
     r"Not enough disk space in \1: \2 MB free, \3 MB needed."),
    (r"Échec de la décompression de l'image :", "Image unpacking failed:"),
    (r"image\.cfg absent de l'image décompressée\.", "image.cfg missing from the unpacked image."),
    (r"Aucune partition trouvée dans l'image\.", "No partition found in the image."),
    (r"Contrôle CRC échoué\.", "CRC check failed."),
    (r"Cette image n'est pas au format ADNL \(S905X4/X5…\) : utilise Amlogic Linux Flasher v9\.0\.",
     "This image is not in ADNL format (S905X4/X5…): use Amlogic Linux Flasher v9.0."),
    (r"Cette image est au format ADNL \(S905X4/Y4/W2, S905X5…\) : utilise Amlogic Linux Flasher v11\.0 ou v14\.0\.",
     "This image is in ADNL format (S905X4/Y4/W2, S905X5…): use Amlogic Linux Flasher v11.0 or v14.0."),
    # journal
    (r"(\s*)! délai dépassé \((\d+) s\)", r"\1! timeout (\2 s)"),
    (r"(\s*)protocole USB (\S+) : séquence ancienne", r"\1USB protocol \2: legacy sequence"),
    (r"(\s*)! U-Boot ne répond pas encore à identify, on continue",
     r"\1! U-Boot does not answer identify yet, continuing"),
    (r"(\s*)! version inattendue après U-Boot : (.+)", r"\1! unexpected version after U-Boot: \2"),
    (r"Box en mode secure boot", "Box in secure boot mode"),
    (r"Image : (.+)", r"Image: \1"),
    (r"SoC : (\S+) \| effacement : (\S+) \| reset : (\S+)", r"SoC: \1 | erase: \2 | reset: \3"),
    (r"(\s*)! (.+) — nouvel essai complet \((\d)/3\)", None),  # traité à part
    (r"(\s*)partition (\S+) OK", r"\1partition \2 OK"),
    (r"Flash réussi en (\d+) s", r"Burn successful in \1 s"),
    (r"(\s*)étape : (.+)", r"\1step: \2"),
    (r"Arrêté par l'utilisateur", "Stopped by user"),
    (r"ERREUR : (.+)", None),  # traité à part
]
_DYN = [(re.compile(p + r"$", re.S), t) for p, t in _DYN]


def tr_dyn(text: str) -> str:
    """Traduit un message produit à l'exécution (erreurs, journal)."""
    if _lang == "fr" or not text:
        return text
    if text in EN:
        return EN[text]
    first, nl, rest = text.partition("\n")
    for rx, tpl in _DYN:
        m = rx.match(first)
        if not m:
            continue
        if rx.pattern.startswith(r"(\s*)! (.+) — nouvel essai"):
            out = f"{m.group(1)}! {tr_dyn(m.group(2))} — full retry ({m.group(3)}/3)"
        elif rx.pattern.startswith("ERREUR"):
            out = "ERROR: " + tr_dyn(m.group(1))
        else:
            out = m.expand(tpl)
        return out + nl + rest
    return text
