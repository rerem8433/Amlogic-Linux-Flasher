"""Onglet ADB / Fastboot : redémarrages, déverrouillage du bootloader, scripts .cmd/.bat/.sh."""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
from pathlib import Path

from PyQt5.QtCore import QProcess, QProcessEnvironment
from PyQt5.QtGui import QFont, QTextCursor
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from . import paths
from .i18n import tr

TOOLS = {"adb": lambda: paths.ADB_BIN, "fastboot": lambda: paths.FASTBOOT_BIN}

_SKIP = ("rem ", "rem\t", "::", "echo", "@echo", "pause", "cls", "title", "color",
         "set ", "goto", "exit", "chcp", "mode ", "timeout", "ping ", "cd ", "cd\t",
         "#", "if ", "for ", "call ", "start ", "setlocal", "endlocal", "prompt", ")", ":")
_STOP_TOKENS = ("|", "||", "&&", "&")


def _clean_token(tok: str) -> str:
    tok = tok.strip()
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "\"'":
        tok = tok[1:-1]
    tok = tok.replace("%~dp0", "").replace("%cd%\\", "").replace("%CD%\\", "")
    return tok.replace("\\", "/")


def parse_script(path: Path) -> tuple[list[list[str]], list[str]]:
    """Extrait les commandes adb / fastboot d'un script Windows (.cmd/.bat) ou shell (.sh).

    Renvoie (commandes, lignes ignorées). Chaque commande est ["adb"|"fastboot", args…].
    Les chemins Windows (bin\\fastboot.exe, images\\boot.img, %~dp0…) sont convertis ;
    les fichiers sont résolus par rapport au dossier du script.
    """
    cmds: list[list[str]] = []
    ignored: list[str] = []
    text = path.read_text(errors="replace")
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("@"):
            line = line[1:].strip()
        line = line.lstrip("( ").strip()
        low = line.lower()
        # un « if errorlevel … » ou « echo … » n'est pas exécuté, mais on le signale
        for part in re.split(r"\s*&&\s*|\s+&\s+|\s*\|\|\s*", line):
            part = part.strip()
            if not part:
                continue
            try:
                toks = shlex.split(part, posix=False)
            except ValueError:
                toks = part.split()
            if not toks:
                continue
            exe = _clean_token(toks[0]).rsplit("/", 1)[-1].lower()
            if exe.endswith(".exe"):
                exe = exe[:-4]
            if exe not in TOOLS:
                if not low.startswith(_SKIP) or "fastboot" in low or "adb" in low:
                    ignored.append(raw.strip())
                break
            args: list[str] = []
            for t in toks[1:]:
                if t.startswith((">", "2>", "1>", "<", ")")) or t in _STOP_TOKENS:
                    break
                args.append(_clean_token(t))
            cmds.append([exe, *args])
    return cmds, ignored


def fastboot_preflight() -> tuple[bool, str]:
    """Vérifie qu'une box est en mode bootloader (fastboot) et pas en fastbootd.

    Reproduit le contrôle des scripts SlimboxTV : « getvar is-userspace » doit valoir « no ».
    """
    fb = paths.FASTBOOT_BIN
    if not shutil.which(fb):
        return False, tr("Outil introuvable : {t}. Installe-le : sudo apt install adb fastboot", t="fastboot")
    try:
        out = subprocess.run([fb, "devices"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        out = ""
    if not out.strip():
        return False, tr("Aucune box en mode fastboot : Recovery > Reboot to bootloader, "
                         "câble USB A-A sur le port le plus proche de l'arrière.")
    try:
        p = subprocess.run([fb, "getvar", "is-userspace"], capture_output=True,
                           text=True, timeout=10)
        var = (p.stdout + p.stderr).lower()
    except (OSError, subprocess.TimeoutExpired):
        var = ""
    if "is-userspace: yes" in var:
        return False, tr("La box est en fastbootd (userspace), pas en bootloader : "
                         "fais « Redémarrer en bootloader ».")
    return True, ""


class ScriptPreview(QDialog):
    def __init__(self, parent, path: Path, cmds: list[list[str]], ignored: list[str]):
        super().__init__(parent)
        self.setWindowTitle(path.name)
        self.resize(720, 440)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(tr("Commandes qui vont être exécutées (dossier : {d}) :", d=path.parent)))
        view = QPlainTextEdit("\n".join(" ".join(shlex.quote(a) for a in c) for c in cmds))
        view.setReadOnly(True)
        view.setFont(QFont("Monospace", 9))
        lay.addWidget(view, 3)
        if ignored:
            lay.addWidget(QLabel(tr("Lignes ignorées (ni adb ni fastboot) :")))
            v2 = QPlainTextEdit("\n".join(ignored))
            v2.setReadOnly(True)
            v2.setFont(QFont("Monospace", 9))
            lay.addWidget(v2, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(tr("Exécuter"))
        bb.button(QDialogButtonBox.Cancel).setText(tr("Annuler"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


class AdbFastbootWidget(QWidget):
    """Interface ADB / Fastboot avec console et file d'attente de commandes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue: list[tuple[list[str], str | None]] = []
        self.proc: QProcess | None = None
        self._build()
        self.retranslate()

    # ------------------------------------------------------------- interface
    def _build(self) -> None:
        root = QHBoxLayout(self)
        left = QVBoxLayout()

        self.grp_dev = QGroupBox()
        gd = QVBoxLayout(self.grp_dev)
        self.btn_devices = QPushButton(clicked=self.list_devices)
        gd.addWidget(self.btn_devices)
        left.addWidget(self.grp_dev)

        self.grp_adb = QGroupBox()
        ga = QGridLayout(self.grp_adb)
        self.b_adb_fb = QPushButton(clicked=lambda: self.run_many([["adb", "reboot", "bootloader"]]))
        self.b_adb_rec = QPushButton(clicked=lambda: self.run_many([["adb", "reboot", "recovery"]]))
        self.b_adb_upd = QPushButton(clicked=lambda: self.run_many([["adb", "reboot", "update"]]))
        self.b_adb_reboot = QPushButton(clicked=lambda: self.run_many([["adb", "reboot"]]))
        for i, b in enumerate((self.b_adb_fb, self.b_adb_rec, self.b_adb_upd, self.b_adb_reboot)):
            ga.addWidget(b, i, 0)
        left.addWidget(self.grp_adb)

        self.grp_fb = QGroupBox()
        gf = QGridLayout(self.grp_fb)
        self.b_fb_info = QPushButton(clicked=lambda: self.run_many([["fastboot", "getvar", "all"]]))
        self.b_fb_unlock = QPushButton(clicked=self.unlock)
        self.b_fb_lock = QPushButton(clicked=self.lock)
        self.b_fb_reboot = QPushButton(clicked=lambda: self.run_many([["fastboot", "reboot"]]))
        self.b_fb_rbl = QPushButton(clicked=lambda: self.run_many([["fastboot", "reboot", "bootloader"]]))
        self.b_fb_unlock.setStyleSheet("font-weight: bold;")
        for i, b in enumerate((self.b_fb_info, self.b_fb_unlock, self.b_fb_lock,
                               self.b_fb_reboot, self.b_fb_rbl)):
            gf.addWidget(b, i, 0)
        left.addWidget(self.grp_fb)

        self.grp_script = QGroupBox()
        gs = QVBoxLayout(self.grp_script)
        self.b_script = QPushButton(clicked=self.run_script)
        self.lbl_script = QLabel(wordWrap=True)
        self.lbl_script.setStyleSheet("color: #666;")
        gs.addWidget(self.b_script)
        gs.addWidget(self.lbl_script)
        left.addWidget(self.grp_script)
        left.addStretch(1)

        left_w = QWidget()
        left_w.setLayout(left)
        left_w.setFixedWidth(320)
        root.addWidget(left_w)

        right = QVBoxLayout()
        self.console = QPlainTextEdit(readOnly=True)
        self.console.setFont(QFont("Monospace", 9))
        self.console.setStyleSheet("QPlainTextEdit { background: #101418; color: #d8e0e8; }")
        right.addWidget(self.console, 1)
        row = QHBoxLayout()
        self.cmd_edit = QLineEdit()
        self.cmd_edit.returnPressed.connect(self.run_typed)
        self.b_run = QPushButton(clicked=self.run_typed)
        self.b_stop = QPushButton(clicked=self.stop, enabled=False)
        self.b_clear = QPushButton(clicked=self.console.clear)
        row.addWidget(self.cmd_edit, 1)
        row.addWidget(self.b_run)
        row.addWidget(self.b_stop)
        row.addWidget(self.b_clear)
        right.addLayout(row)
        root.addLayout(right, 1)

    def retranslate(self) -> None:
        self.grp_dev.setTitle(tr("Appareils"))
        self.btn_devices.setText(tr("Lister les appareils"))
        self.grp_adb.setTitle("ADB")
        self.b_adb_fb.setText(tr("Redémarrer en fastboot"))
        self.b_adb_rec.setText(tr("Redémarrer en recovery"))
        self.b_adb_upd.setText(tr("Redémarrer en mode USB burn"))
        self.b_adb_reboot.setText(tr("Redémarrer"))
        self.grp_fb.setTitle("Fastboot")
        self.b_fb_info.setText(tr("Infos (getvar all)"))
        self.b_fb_unlock.setText(tr("Déverrouiller le bootloader"))
        self.b_fb_lock.setText(tr("Verrouiller le bootloader"))
        self.b_fb_reboot.setText(tr("Redémarrer"))
        self.b_fb_rbl.setText(tr("Redémarrer en bootloader"))
        self.grp_script.setTitle(tr("Script du firmware"))
        self.b_script.setText(tr("Exécuter un script…"))
        self.lbl_script.setText(tr(
            "Ex. : Unlock_Bootloader.cmd fourni avec le firmware. Seules les lignes "
            "adb / fastboot sont exécutées, avec les outils Linux."))
        self.cmd_edit.setPlaceholderText(tr("Commande : fastboot getvar unlocked"))
        self.b_run.setText(tr("Exécuter"))
        self.b_stop.setText(tr("Arrêter"))
        self.b_clear.setText(tr("Effacer"))

    # ------------------------------------------------------------- actions
    def list_devices(self) -> None:
        self.run_many([["adb", "devices", "-l"], ["fastboot", "devices", "-l"]])

    def unlock(self) -> None:
        if QMessageBox.warning(
            self, tr("Déverrouiller le bootloader"),
            tr("La box doit être en mode fastboot (Recovery > Reboot to bootloader, "
               "ou bouton « Redémarrer en bootloader »).\n\n"
               "Le déverrouillage peut effacer les données de la box. Continuer ?"),
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        if not self._preflight():
            return
        self.run_many([
            ["fastboot", "flashing", "unlock"],
            ["fastboot", "getvar", "unlocked"],
            ["fastboot", "reboot"],
        ])

    def _preflight(self) -> bool:
        ok, msg = fastboot_preflight()
        if not ok:
            self._print(msg + "\n", "#ff8a80")
            QMessageBox.warning(self, "Fastboot", msg)
        return ok

    def lock(self) -> None:
        if QMessageBox.question(
            self, tr("Verrouiller le bootloader"),
            tr("Reverrouiller le bootloader ? Avec un firmware non officiel, "
               "la box risque de ne plus démarrer."),
        ) != QMessageBox.Yes:
            return
        if self._preflight():
            self.run_many([["fastboot", "flashing", "lock"]])

    def run_script(self) -> None:
        fn, _ = QFileDialog.getOpenFileName(
            self, tr("Exécuter un script (.cmd / .bat / .sh)…"), str(Path.home()),
            tr("Scripts (*.cmd *.bat *.sh);;Tous les fichiers (*)"))
        if not fn:
            return
        path = Path(fn)
        cmds, ignored = parse_script(path)
        if not cmds:
            QMessageBox.information(self, path.name, tr("Aucune commande adb / fastboot dans ce script."))
            return
        if ScriptPreview(self, path, cmds, ignored).exec_() != QDialog.Accepted:
            return
        if any(c[0] == "fastboot" and c[1:2] == ["flashing"] for c in cmds) and not self._preflight():
            return
        self.run_many(cmds, cwd=str(path.parent))

    def run_typed(self) -> None:
        text = self.cmd_edit.text().strip()
        if not text:
            return
        try:
            toks = shlex.split(text)
        except ValueError:
            toks = text.split()
        if not toks or toks[0] not in TOOLS:
            self._print(tr("Seules les commandes adb et fastboot sont acceptées.") + "\n", "#ff8a80")
            return
        self.cmd_edit.clear()
        self.run_many([toks])

    # ------------------------------------------------------------- exécution
    def run_many(self, cmds: list[list[str]], cwd: str | None = None) -> None:
        missing = {c[0] for c in cmds if not shutil.which(TOOLS[c[0]]())}
        if missing:
            self._print(tr("Outil introuvable : {t}. Installe-le : sudo apt install adb fastboot",
                           t=", ".join(sorted(missing))) + "\n", "#ff8a80")
            return
        self.queue.extend((c, cwd) for c in cmds)
        if not self.proc:
            self._next()

    def _next(self) -> None:
        if not self.queue:
            self.proc = None
            self.b_stop.setEnabled(False)
            return
        cmd, cwd = self.queue.pop(0)
        self._print("$ " + " ".join(shlex.quote(a) for a in cmd) + "\n", "#80d8ff")
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.MergedChannels)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("LC_ALL", "C")
        p.setProcessEnvironment(env)
        if cwd:
            p.setWorkingDirectory(cwd)
        p.readyReadStandardOutput.connect(
            lambda: self._print(bytes(p.readAllStandardOutput()).decode("utf-8", "replace")))
        p.finished.connect(self._finished)
        p.errorOccurred.connect(lambda _e: self._print(p.errorString() + "\n", "#ff8a80"))
        self.proc = p
        self.b_stop.setEnabled(True)
        p.start(TOOLS[cmd[0]](), cmd[1:])

    def _finished(self, code: int, _status) -> None:
        if code != 0:
            self._print(tr("(code de sortie {c})", c=code) + "\n", "#ffd180")
        if self.proc:
            self.proc.deleteLater()
        self.proc = None
        self._next()

    def stop(self) -> None:
        self.queue.clear()
        if self.proc:
            self.proc.kill()

    def _print(self, text: str, color: str | None = None) -> None:
        cur = self.console.textCursor()
        cur.movePosition(QTextCursor.End)
        fmt = cur.charFormat()
        if color:
            from PyQt5.QtGui import QColor
            fmt.setForeground(QColor(color))
        else:
            fmt.clearForeground()
        cur.insertText(text.replace("\r\n", "\n"), fmt)
        self.console.setTextCursor(cur)
        self.console.ensureCursorVisible()
