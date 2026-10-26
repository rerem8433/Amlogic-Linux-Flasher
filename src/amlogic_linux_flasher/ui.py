"""Fenêtre principale, calquée sur Amlogic USB Burning Tool."""

from __future__ import annotations

import datetime as dt
import subprocess
import time
from pathlib import Path

from PyQt5.QtCore import QSettings, Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QFont, QIcon
from PyQt5.QtWidgets import (
    QAbstractItemView, QAction, QActionGroup, QApplication, QCheckBox, QComboBox,
    QDialog, QDialogButtonBox, QFileDialog, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QSplitter, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import APP_ID, APP_NAME, APP_TITLE, ED, image, paths, usbwatch
from . import chipinfo
from .adbtools import AdbFastbootWidget
from .engine import Cancelled, Options, make_flasher
from .i18n import lang, set_lang, system_lang, tr, tr_dyn, tr_status

CREAM = "#fffde7"
BLUE = "#1e90ff"
GREEN = "#00e676"
RED = "#ff5252"
GRAY = "#e0e0e0"

SOC_CHOICES = ED["socs"]
ADNL = ED["protocol"] == "adnl"


def _icon() -> QIcon:
    for p in (
        Path("/usr/share/icons/hicolor/scalable/apps") / f"{APP_ID}.svg",
        Path(__file__).resolve().parent.parent.parent / "data" / "amlogic-linux-flasher.svg",
    ):
        if p.is_file():
            return QIcon.fromTheme(APP_ID, QIcon(str(p)))
    return QIcon.fromTheme(APP_ID)


def _human(n: int) -> str:
    units = ("o", "Ko", "Mo", "Go") if lang() == "fr" else ("B", "KB", "MB", "GB")
    for i, unit in enumerate(units):
        if n < 1024 or i == len(units) - 1:
            return f"{n:.0f} {unit}" if i == 0 else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def _mmss(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}"


# ---------------------------------------------------------------- threads
class LoaderThread(QThread):
    stage = pyqtSignal(str)
    done = pyqtSignal(object, str)  # ImageInfo | None, message d'erreur

    def __init__(self, path: Path):
        super().__init__()
        self.path = path

    def run(self) -> None:
        try:
            self.stage.emit("Lecture de l'image…")
            image.quick_check(self.path)
            items = image.list_items(self.path)
            if ADNL:
                if items and not image.is_adnl(items):
                    raise image.ImageError(
                        "Cette image n'est pas au format ADNL (S905X4/X5…) : "
                        "utilise Amlogic Linux Flasher v9.0.")
                self.done.emit(image.load_header(self.path), "")
                return
            if image.is_adnl(items):
                raise image.ImageError(
                    "Cette image est au format ADNL (S905X4/Y4/W2, S905X5…) : "
                    "utilise Amlogic Linux Flasher v11.0 ou v14.0.")
            self.stage.emit("Vérification de l'image…")
            ok, out = image.crc_check(self.path)
            if not ok:
                raise image.ImageError(out or "Contrôle CRC échoué.")
            self.stage.emit("Préparation de l'image…")
            image.unpack(self.path)
            info = image.parse(self.path)
            self.done.emit(info, "")
        except Exception as e:  # noqa: BLE001
            self.done.emit(None, str(e))


class ProbeThread(QThread):
    done = pyqtSignal(str, dict)

    def __init__(self, dev_id: str):
        super().__init__()
        self.dev_id = dev_id

    def run(self) -> None:
        self.done.emit(self.dev_id, chipinfo.probe())


class FlashThread(QThread):
    status = pyqtSignal(str, int)
    log = pyqtSignal(str)
    done = pyqtSignal(bool, str)

    def __init__(self, info, opts: Options, log_file: Path, check_crc: bool = False):
        super().__init__()
        self.flasher = make_flasher(
            ED["protocol"], info, opts, check_crc=check_crc,
            on_status=lambda s, p: self.status.emit(s, p),
            on_log=lambda line: self.log.emit(line),
            log_file=log_file,
        )

    def cancel(self) -> None:
        self.flasher.cancel()

    def run(self) -> None:
        try:
            self.flasher.flash()
            self.done.emit(True, "")
        except Cancelled:
            self.flasher.log("Arrêté par l'utilisateur")
            self.done.emit(False, "Arrêté")
        except Exception as e:  # noqa: BLE001
            self.flasher.log(f"ERREUR : {e}")
            self.done.emit(False, str(e))
        finally:
            self.flasher.close()


# ---------------------------------------------------------------- dialogues
class BusyDialog(QDialog):
    def __init__(self, parent: QWidget):
        super().__init__(parent, Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setWindowTitle(tr("Vérification de l'image"))
        self.setModal(True)
        self.setFixedWidth(340)
        lay = QVBoxLayout(self)
        self.label = QLabel(tr("Vérification de l'image…"))
        bar = QProgressBar()
        bar.setRange(0, 0)
        bar.setTextVisible(False)
        lay.addWidget(self.label)
        lay.addWidget(bar)

    def set_stage(self, text: str) -> None:
        self.label.setText(tr(text))


class LogDialog(QDialog):
    def __init__(self, parent: QWidget, title: str, text: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(820, 520)
        lay = QVBoxLayout(self)
        view = QPlainTextEdit(text)
        view.setReadOnly(True)
        view.setFont(QFont("Monospace", 9))
        lay.addWidget(view)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.button(QDialogButtonBox.Close).setText(tr("Fermer"))
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        view.moveCursor(view.textCursor().End)


# ---------------------------------------------------------------- fenêtre
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("ParadoxXx Squad", APP_ID)
        if not self.settings.contains("lang"):
            self.settings.setValue("lang", system_lang())
        set_lang(self.settings.value("lang", "fr"))
        paths.ensure_dirs()

        self.info = None              # ImageInfo chargée
        self.loader: LoaderThread | None = None
        self.busy: BusyDialog | None = None
        self.worker: FlashThread | None = None
        self.worker_dev: str | None = None
        self.armed = False
        self.devices: dict[str, dict] = {}   # id -> état de la ligne
        self.stats = {"total": 0, "ok": 0, "ko": 0}
        self._warned_multi = False
        self._warned_access: set[str] = set()
        self._warned_mode: set[str] = set()

        self.setWindowIcon(_icon())
        self.setAcceptDrops(True)
        self._build()
        self.retranslate()
        self._restore()

        self.timer = QTimer(self, interval=1000, timeout=self._tick)
        self.timer.start()
        QTimer.singleShot(0, self._startup)

    # ---------------------------------------------------------- construction
    def _build(self) -> None:
        mb = self.menuBar()
        self.m_set = mb.addMenu("")
        self.a_import = QAction(self, shortcut="Ctrl+O", triggered=self.import_image)
        self.a_pwd = QAction(self, triggered=self.choose_password)
        self.a_pwd_clear = QAction(self, triggered=self.clear_password)
        self.a_udev = QAction(self, triggered=self.install_udev)
        self.a_cache = QAction(self, triggered=self.clear_cache)
        self.a_quit = QAction(self, shortcut="Ctrl+Q", triggered=self.close)
        for a in (self.a_import, None, self.a_pwd, self.a_pwd_clear, None,
                  self.a_udev, self.a_cache, None, self.a_quit):
            self.m_set.addSeparator() if a is None else self.m_set.addAction(a)
        self.m_help = mb.addMenu("")
        self.a_logs = QAction(self, triggered=self.open_logs)
        self.a_about = QAction(self, triggered=self.about)
        self.m_help.addAction(self.a_logs)
        self.m_help.addAction(self.a_about)
        self.m_lang = mb.addMenu("")
        grp = QActionGroup(self)
        self.a_fr = QAction("Français", self, checkable=True, triggered=lambda: self.set_language("fr"))
        self.a_en = QAction("English", self, checkable=True, triggered=lambda: self.set_language("en"))
        for a in (self.a_fr, self.a_en):
            grp.addAction(a)
            self.m_lang.addAction(a)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        central = QWidget()
        self.tabs.addTab(central, "")
        self.adb_tab = AdbFastbootWidget()
        self.tabs.addTab(self.adb_tab, "")
        root = QHBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)

        table_css = (
            f"QTableWidget {{ background: {CREAM}; gridline-color: #d7d2b0; }}"
            "QHeaderView::section { background: white; font-weight: bold; padding: 4px;"
            " border: 1px solid #c8c8c8; }"
        )
        split = QSplitter(Qt.Vertical)
        self.dev_table = QTableWidget(0, 4)
        self.dev_table.setStyleSheet(table_css)
        self.dev_table.verticalHeader().hide()
        self.dev_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.dev_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        h = self.dev_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.Fixed)
        h.setSectionResizeMode(3, QHeaderView.Fixed)
        self.dev_table.setColumnWidth(2, 90)
        self.dev_table.setColumnWidth(3, 110)
        self.dev_table.setMinimumWidth(560)

        self.msg_table = QTableWidget(0, 3)
        self.msg_table.setStyleSheet(table_css)
        self.msg_table.verticalHeader().hide()
        self.msg_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.msg_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        mh = self.msg_table.horizontalHeader()
        mh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        mh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        mh.setSectionResizeMode(2, QHeaderView.Stretch)
        self.msg_table.cellDoubleClicked.connect(self._open_message)
        split.addWidget(self.dev_table)
        split.addWidget(self.msg_table)
        split.setSizes([420, 200])
        root.addWidget(split, 1)

        side = QVBoxLayout()
        side.setSpacing(8)
        self.btn_start = QPushButton(minimumHeight=42, clicked=self.toggle_start)
        self.btn_refresh = QPushButton(minimumHeight=36, clicked=self.refresh)
        side.addWidget(self.btn_start)
        side.addWidget(self.btn_refresh)

        self.grp_conf = QGroupBox()
        g = QVBoxLayout(self.grp_conf)
        self.chk_wipe = QCheckBox(checked=True)
        self.chk_reset = QCheckBox(checked=True)
        self.lbl_soc = QLabel()
        self.cmb_soc = QComboBox()
        for i, (soc, label, tip) in enumerate(SOC_CHOICES):
            self.cmb_soc.addItem(label, soc)
            self.cmb_soc.setItemData(i, tip, Qt.ToolTipRole)
        g.addWidget(self.chk_wipe)
        g.addWidget(self.chk_reset)
        self.chk_crc = QCheckBox(checked=False)
        self.lbl_chips = QLabel(wordWrap=True)
        self.lbl_chips.setStyleSheet("color: #555;")
        if SOC_CHOICES:
            g.addWidget(self.lbl_soc)
            g.addWidget(self.cmb_soc)
        else:
            self.lbl_soc.hide()
            self.cmb_soc.hide()
            g.addWidget(self.chk_crc)
            g.addWidget(self.lbl_chips)
        side.addWidget(self.grp_conf)

        self.grp_img = QGroupBox()
        gi = QVBoxLayout(self.grp_img)
        self.part_table = QTableWidget(0, 2)
        self.part_table.setStyleSheet("QTableWidget { background: white; }")
        self.part_table.verticalHeader().hide()
        self.part_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.part_table.setSelectionMode(QAbstractItemView.NoSelection)
        ph = self.part_table.horizontalHeader()
        ph.setSectionResizeMode(0, QHeaderView.Stretch)
        ph.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        gi.addWidget(self.part_table)
        side.addWidget(self.grp_img, 1)

        side_w = QWidget()
        side_w.setLayout(side)
        side_w.setFixedWidth(260)
        root.addWidget(side_w)

        sb = self.statusBar()
        self.lbl_image = QLabel()
        self.lbl_size = QLabel()
        self.lbl_stats = QLabel()
        sb.addWidget(self.lbl_image, 1)
        sb.addPermanentWidget(self.lbl_size)
        sb.addPermanentWidget(self.lbl_stats)

        for w in (self.chk_wipe, self.chk_reset, self.chk_crc):
            w.toggled.connect(self._save_opts)
        self.cmb_soc.currentIndexChanged.connect(self._save_opts)

    def retranslate(self) -> None:
        self.setWindowTitle(APP_TITLE)
        self.tabs.setTabText(0, tr("Flash USB"))
        self.tabs.setTabText(1, "ADB / Fastboot")
        self.adb_tab.retranslate()
        self.chk_crc.setText(tr("Vérifier l'image (CRC)"))
        self.lbl_chips.setText(tr("Puces : {c}", c=ED["chips"]))
        self.m_set.setTitle(tr("Paramètres"))
        self.m_help.setTitle(tr("Aide"))
        self.m_lang.setTitle(tr("Langue"))
        self.a_import.setText(tr("Importer une image…"))
        self.a_pwd.setText(tr("Fichier mot de passe…"))
        self.a_pwd_clear.setText(tr("Retirer le mot de passe"))
        self.a_udev.setText(tr("Installer la règle udev…"))
        self.a_cache.setText(tr("Vider le cache de l'image"))
        self.a_quit.setText(tr("Quitter"))
        self.a_logs.setText(tr("Ouvrir le dossier des journaux"))
        self.a_about.setText(tr("À propos"))
        self.dev_table.setHorizontalHeaderLabels(
            [tr("Appareil"), tr("État"), tr("Temps"), tr("Statistique")])
        self.msg_table.setHorizontalHeaderLabels(
            [tr("Appareil"), tr("Heure"), tr("Message (double-clic pour ouvrir)")])
        self.part_table.setHorizontalHeaderLabels([tr("Partition"), tr("Taille")])
        self.btn_start.setText(tr("Arrêter") if self.armed else tr("Démarrer"))
        self.btn_refresh.setText(tr("Actualiser"))
        self.grp_conf.setTitle(tr("Configuration"))
        self.chk_wipe.setText(tr("Effacer la flash"))
        self.chk_reset.setText(tr("Réinitialiser après flash"))
        self.lbl_soc.setText(tr("SoC :"))
        self.grp_img.setTitle(tr("Contenu de l'image"))
        self._update_statusbar()
        for dev_id, d in self.devices.items():
            self._paint_row(dev_id)

    def _restore(self) -> None:
        self._restoring = True
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        else:
            self.resize(1180, 700)
        self.chk_wipe.setChecked(self.settings.value("wipe", True, type=bool))
        self.chk_reset.setChecked(self.settings.value("reset", True, type=bool))
        self.chk_crc.setChecked(self.settings.value("crc", False, type=bool))
        soc = self.settings.value("soc", "g12a")
        idx = self.cmb_soc.findData(soc)
        self.cmb_soc.setCurrentIndex(max(idx, 0))
        (self.a_en if self.settings.value("lang", "fr") == "en" else self.a_fr).setChecked(True)
        self._restoring = False

    def _save_opts(self) -> None:
        if getattr(self, "_restoring", False):
            return
        self.settings.setValue("wipe", self.chk_wipe.isChecked())
        self.settings.setValue("reset", self.chk_reset.isChecked())
        self.settings.setValue("crc", self.chk_crc.isChecked())
        if SOC_CHOICES:
            self.settings.setValue("soc", self.cmb_soc.currentData())

    def _startup(self) -> None:
        for tool in ((paths.ADNL_BIN,) if ADNL else (paths.UPDATE_BIN, paths.PACKER_BIN)):
            if not Path(tool).exists():
                self.add_message("-", tr("Outil manquant : {p}", p=tool))
        last = self.settings.value("last_image", "")
        if last and Path(last).is_file():
            self.load_image(Path(last))
        else:
            self.add_message("-", tr("Prêt : branche la box en mode USB burn."))
        self._tick()

    # ---------------------------------------------------------- image
    def import_image(self) -> None:
        start = self.settings.value("last_dir", str(Path.home()))
        fn, _ = QFileDialog.getOpenFileName(
            self, tr("Importer une image…"), start,
            tr("Images Amlogic (*.img);;Tous les fichiers (*)"))
        if fn:
            self.settings.setValue("last_dir", str(Path(fn).parent))
            self.load_image(Path(fn))

    def load_image(self, path: Path) -> None:
        if self.worker or self.loader:
            return
        self.busy = BusyDialog(self)
        self.loader = LoaderThread(path)
        self.loader.stage.connect(self.busy.set_stage)
        self.loader.done.connect(self._image_loaded)
        self.loader.start()
        # la fenêtre n'apparaît que si la lecture dure (évite un affichage/fermeture
        # trop rapides que certains gestionnaires de fenêtres gèrent mal)
        QTimer.singleShot(400, self._show_busy)

    def _show_busy(self) -> None:
        if self.busy and self.loader:
            self.busy.show()

    def _image_loaded(self, info, err: str) -> None:
        loader, self.loader = self.loader, None
        if loader:
            loader.wait()          # le thread doit être terminé avant d'être libéré
            loader.deleteLater()
        busy, self.busy = self.busy, None
        if busy:
            busy.hide()
            busy.deleteLater()
        if info is None:
            QTimer.singleShot(0, lambda: self._image_error(err))
            return
        self.info = info
        self.settings.setValue("last_image", str(info.path))
        self.part_table.setRowCount(0)
        for p in info.partitions:
            r = self.part_table.rowCount()
            self.part_table.insertRow(r)
            self.part_table.setItem(r, 0, QTableWidgetItem(p.sub_type))
            it = QTableWidgetItem(_human(p.size))
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.part_table.setItem(r, 1, it)
        self._update_statusbar()
        self.add_message("-", tr("Image chargée : {name} ({n} partitions)",
                                 name=info.path.name, n=len(info.partitions)))

    def _image_error(self, err: str) -> None:
        err = tr_dyn(err)
        self.add_message("-", tr('Image invalide') + tr(' : ') + (err.splitlines()[0] if err else ''))
        QMessageBox.critical(self, tr("Image invalide"), err)

    def clear_cache(self) -> None:
        if self.worker:
            return
        image.clear_cache()
        self.info = None
        self.part_table.setRowCount(0)
        self.settings.remove("last_image")
        self._update_statusbar()
        self.add_message("-", tr("Cache vidé."))

    # ---------------------------------------------------------- mot de passe
    def choose_password(self) -> None:
        fn, _ = QFileDialog.getOpenFileName(
            self, tr("Fichier mot de passe…"), str(Path.home()),
            tr("Fichiers mot de passe (*.bin);;Tous les fichiers (*)"))
        if fn:
            self.settings.setValue("password", fn)
            self.add_message("-", tr("Mot de passe : {name}", name=Path(fn).name))

    def clear_password(self) -> None:
        self.settings.remove("password")
        self.add_message("-", tr("Mot de passe retiré."))

    # ---------------------------------------------------------- udev
    def install_udev(self) -> None:
        target = f"/etc/udev/rules.d/{paths.UDEV_RULE_NAME}"
        script = (
            f"printf '%s' '{paths.UDEV_RULE}' > {target} && "
            "udevadm control --reload-rules && udevadm trigger"
        )
        try:
            rc = subprocess.run(["pkexec", "sh", "-c", script]).returncode
        except OSError:
            rc = 1
        if rc == 0:
            self.add_message("-", tr("Règle udev installée. Rebranche la box."))
        else:
            QMessageBox.warning(self, APP_NAME, tr("Installation de la règle udev annulée ou impossible."))

    # ---------------------------------------------------------- appareils
    def _ensure_row(self, dev_id: str) -> dict:
        d = self.devices.get(dev_id)
        if d:
            return d
        r = self.dev_table.rowCount()
        self.dev_table.insertRow(r)
        self.dev_table.setRowHeight(r, 30)
        self.dev_table.setItem(r, 0, QTableWidgetItem(dev_id))
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.dev_table.setCellWidget(r, 1, bar)
        for c in (2, 3):
            it = QTableWidgetItem("")
            it.setTextAlignment(Qt.AlignCenter)
            self.dev_table.setItem(r, c, it)
        d = {"row": r, "bar": bar, "state": "connected", "text": "Connecté", "pct": 0,
             "flashed": False, "ok": 0, "total": 0, "t0": None, "elapsed": None,
             "present": True, "probe": None, "chip": ""}
        self.devices[dev_id] = d
        return d

    def _paint_row(self, dev_id: str) -> None:
        d = self.devices[dev_id]
        color = {"flashing": BLUE, "success": GREEN, "failed": RED}.get(d["state"], GRAY)
        bar: QProgressBar = d["bar"]
        bar.setStyleSheet(
            "QProgressBar { border: 1px solid #c0c0c0; background: #f0f0f0; padding-left: 4px;"
            " font-weight: bold; font-size: 11px; }"
            f"QProgressBar::chunk {{ background: {color}; }}"
        )
        pct = d["pct"] if d["state"] != "success" else 100
        bar.setValue(pct)
        if d["state"] == "connected":
            bar.setValue(0)
            bar.setFormat("  " + self._idle_text(d))
        else:
            bar.setFormat(f"  {tr_status(d['text'])} {pct}%")
        r = d["row"]
        t = d["elapsed"]
        if d["state"] == "flashing" and d["t0"]:
            t = time.monotonic() - d["t0"]
        self.dev_table.item(r, 2).setText(_mmss(t) if t is not None else "")
        self.dev_table.item(r, 3).setText(f"{d['ok']}/{d['total']}" if d["total"] else "")

    def _idle_text(self, d: dict) -> str:
        if d["text"] == "Déconnecté":
            return tr("Déconnecté")
        if d.get("probe") == "running":
            return tr("Boîtier détecté en mode flash : identification…")
        chip = d.get("chip")
        ready = tr("prêt à démarrer le flash") if not self.armed else tr("flash imminent")
        if chip:
            return tr("{chip} détecté en mode flash : {ready}", chip=chip, ready=ready)
        if d.get("stage") == "uboot":
            return tr("Boîtier détecté en mode flash (U-Boot) : {ready}", ready=ready)
        return tr("Boîtier détecté en mode flash : {ready}", ready=ready)

    def _start_probe(self, dev_id: str) -> None:
        d = self.devices[dev_id]
        if d.get("probe") or self.worker:
            return
        d["probe"] = "running"
        t = ProbeThread(dev_id)
        t.done.connect(self._probe_done)
        t.finished.connect(t.deleteLater)
        d["probe_thread"] = t
        t.start()

    def _probe_done(self, dev_id: str, info: dict) -> None:
        d = self.devices.get(dev_id)
        if not d:
            return
        d["probe"] = "done"
        d.pop("probe_thread", None)
        d["stage"] = info.get("stage", "")
        d["chip"] = chipinfo.describe(info)
        if d["chip"]:
            msg = tr("Puce détectée : {chip}", chip=d["chip"])
            soc = info.get("soc")
            if SOC_CHOICES and soc and not self.armed and not self.worker:
                idx = self.cmb_soc.findData(soc)
                if idx >= 0 and idx != self.cmb_soc.currentIndex():
                    self.cmb_soc.setCurrentIndex(idx)
                    msg += " — " + tr("SoC réglé sur {soc}", soc=soc)
            elif SOC_CHOICES and soc and soc != self.cmb_soc.currentData():
                msg += " — " + tr("attention, SoC choisi : {soc}", soc=self.cmb_soc.currentData())
            self.add_message(dev_id, msg)
        self._paint_row(dev_id)
        self._tick()

    def refresh(self) -> None:
        # retire les lignes des box débranchées qui ne flashent pas
        keep = {k: v for k, v in self.devices.items()
                if v["present"] or k == self.worker_dev}
        self.devices = {}
        self.dev_table.setRowCount(0)
        for dev_id, old in keep.items():
            d = self._ensure_row(dev_id)
            for k in ("state", "text", "pct", "flashed", "ok", "total", "t0", "elapsed", "present"):
                d[k] = old[k]
            self._paint_row(dev_id)
        self._tick()

    def _tick(self) -> None:
        allf = usbwatch.scan()
        found = {k: v for k, v in allf.items() if v["product"] in ED["products"]}
        for dev_id, info in allf.items():
            if dev_id not in found and dev_id not in self._warned_mode:
                self._warned_mode.add(dev_id)
                self.add_message(dev_id, tr(
                    "Box en mode ADNL (S905X4/Y4/X5…) : utilise Amlogic Linux Flasher v11.0 / v14.0."
                    if info["product"] == "c004" else
                    "Box en mode WorldCup (S905X/X2/X3…) : utilise Amlogic Linux Flasher v9.0."))
        self._warned_mode &= set(allf)
        for dev_id, info in found.items():
            d = self.devices.get(dev_id)
            if d is not None and not d["present"] and d.get("cooldown_until", 0) > time.monotonic():
                # la box vient d'être flashée et redémarre sur le port : pas de nouveau flash
                d["present"] = True
                if not d.get("cooldown_warned"):
                    d["cooldown_warned"] = True
                    self.add_message(dev_id, tr(
                        "Box flashée revenue en mode USB après redémarrage : débranche-la."))
                self._paint_row(dev_id)
                continue
            if d is None or (not d["present"] and dev_id != self.worker_dev):
                d = self._ensure_row(dev_id)
                d.update(state="connected", text="Connecté", pct=0, flashed=False,
                         elapsed=None, t0=None, probe=None, chip="", stage="")
            d["present"] = True
            if (d["state"] == "connected" and not d.get("probe") and not ADNL
                    and usbwatch.accessible(info) and dev_id != self.worker_dev):
                self._start_probe(dev_id)
            if not usbwatch.accessible(info) and dev_id not in self._warned_access:
                self._warned_access.add(dev_id)
                self.add_message(dev_id, tr(
                    "Pas d'accès USB à la box : installe la règle udev (menu Paramètres), "
                    "puis rebranche la box."))
            self._paint_row(dev_id)
        for dev_id, d in self.devices.items():
            if dev_id not in found and d["present"]:
                d["present"] = False
                if dev_id == self.worker_dev:
                    continue  # la box redémarre pendant le flash : normal
                self._warned_access.discard(dev_id)
                if d.get("cooldown_until", 0) > time.monotonic():
                    continue  # redémarrage après flash : on garde « Flash réussi »
                if d["state"] == "connected":
                    d["text"] = "Déconnecté"
                elif d["state"] in ("success", "failed"):
                    d["text"] = "Déconnecté"
                    d["state"] = "connected"
                    d["pct"] = 0
                self._paint_row(dev_id)
        if self.worker_dev in self.devices:
            self._paint_row(self.worker_dev)
        self._maybe_start(found)

    def _maybe_start(self, found: dict) -> None:
        if not self.armed or self.worker or self.loader or not self.info:
            return
        present = [k for k in found]
        if len(present) > 1:
            if not self._warned_multi:
                self._warned_multi = True
                self.add_message("-", tr(
                    "Plusieurs box sont connectées : une seule à la fois est prise en charge."))
            return
        self._warned_multi = False
        for dev_id in present:
            d = self.devices[dev_id]
            if d.get("probe") == "running":
                return  # on attend la fin de l'identification (un seul accès USB à la fois)
            if not d["flashed"] and d["state"] == "connected":
                self._start_flash(dev_id)
                return

    # ---------------------------------------------------------- flash
    def toggle_start(self) -> None:
        if self.armed:
            if self.worker:
                if QMessageBox.question(
                        self, APP_NAME,
                        tr("Arrêter le flash en cours ? La box devra être reflashée.")
                ) != QMessageBox.Yes:
                    return
                self.worker.cancel()
            self.armed = False
        else:
            if not self.info:
                QMessageBox.information(
                    self, APP_NAME, tr("Importe d'abord une image (Paramètres > Importer une image)."))
                return
            self.armed = True
        self.btn_start.setText(tr("Arrêter") if self.armed else tr("Démarrer"))
        locked = self.armed
        for w in (self.grp_conf, self.a_import, self.a_cache, self.a_pwd, self.a_pwd_clear):
            w.setEnabled(not locked)
        self._tick()

    def _options(self) -> Options:
        pw = self.settings.value("password", "")
        return Options(
            soc=self.cmb_soc.currentData() or "",
            wipe=self.chk_wipe.isChecked(),
            reset=self.chk_reset.isChecked(),
            password=Path(pw) if pw and Path(pw).is_file() else None,
        )

    def _start_flash(self, dev_id: str) -> None:
        d = self.devices[dev_id]
        d.update(state="flashing", text="Connexion", pct=0, flashed=True,
                 t0=time.monotonic(), elapsed=None)
        d["total"] += 1
        self.stats["total"] += 1
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        log_file = paths.LOG_DIR / f"{stamp}_{dev_id}.log"
        d["log"] = log_file
        self.worker_dev = dev_id
        self.worker = FlashThread(self.info, self._options(), log_file,
                                  check_crc=self.chk_crc.isChecked())
        self.worker.status.connect(self._on_status)
        self.worker.done.connect(self._on_done)
        self.worker.start()
        self._paint_row(dev_id)
        self._update_statusbar()

    def _on_status(self, text: str, pct: int) -> None:
        d = self.devices.get(self.worker_dev)
        if d:
            d["text"], d["pct"] = text, pct
            self._paint_row(self.worker_dev)

    def _on_done(self, ok: bool, err: str) -> None:
        dev_id = self.worker_dev
        d = self.devices.get(dev_id)
        self.worker.wait()
        self.worker = None
        self.worker_dev = None
        if d:
            d["elapsed"] = time.monotonic() - d["t0"] if d["t0"] else None
            d["t0"] = None
            if ok:
                d.update(state="success", text="Flash réussi", pct=100,
                         cooldown_until=time.monotonic() + 90, cooldown_warned=False)
                d["ok"] += 1
                self.stats["ok"] += 1
                msg = tr("Flash réussi : débranche la box avant d'en brancher une autre.")
            else:
                d["state"] = "failed"
                d["text"] = "Arrêté" if err == "Arrêté" else "Échec"
                self.stats["ko"] += 1
                msg = tr('Échec') + tr(' : ') + tr_dyn(err)
            self._paint_row(dev_id)
            self.add_message(dev_id, msg, d.get("log"))
        self._update_statusbar()
        self._tick()

    # ---------------------------------------------------------- messages
    def add_message(self, dev_id: str, text: str, log: Path | None = None) -> None:
        r = self.msg_table.rowCount()
        self.msg_table.insertRow(r)
        self.msg_table.setItem(r, 0, QTableWidgetItem(dev_id))
        self.msg_table.setItem(r, 1, QTableWidgetItem(dt.datetime.now().strftime("%H:%M:%S")))
        it = QTableWidgetItem(text)
        it.setToolTip(text)
        if log:
            it.setData(Qt.UserRole, str(log))
        self.msg_table.setItem(r, 2, it)
        self.msg_table.scrollToBottom()

    def _open_message(self, row: int, _col: int) -> None:
        it = self.msg_table.item(row, 2)
        if not it:
            return
        log = it.data(Qt.UserRole)
        if log and Path(log).is_file():
            text = Path(log).read_text(errors="replace")
            title = f"{tr('Journal')} — {Path(log).name}"
        else:
            text, title = it.text(), tr("Journal")
        LogDialog(self, title, text).exec_()

    def open_logs(self) -> None:
        paths.ensure_dirs()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.LOG_DIR)))

    # ---------------------------------------------------------- divers
    def _update_statusbar(self) -> None:
        if self.info:
            self.lbl_image.setText(str(self.info.path))
            self.lbl_size.setText(f"{self.info.size // 1024:,} KB".replace(",", " "))
        else:
            self.lbl_image.setText(tr("Aucune image"))
            self.lbl_size.setText("")
        s = self.stats
        self.lbl_stats.setText(tr("Total : {t}  Réussis : {s}  Échecs : {f}",
                                  t=s["total"], s=s["ok"], f=s["ko"]))

    def set_language(self, code: str) -> None:
        self.settings.setValue("lang", code)
        set_lang(code)
        self.retranslate()
        if self.info:
            for r, p in enumerate(self.info.partitions):
                it = self.part_table.item(r, 1)
                if it:
                    it.setText(_human(p.size))

    def about(self) -> None:
        QMessageBox.about(
            self, tr("À propos"),
            f"<h3>{APP_TITLE}</h3>"
            f"<p>{tr('Puces : {c}', c=ED['chips'])}</p>"
            f"<p>{tr('Flash USB des box Android TV Amlogic depuis Linux, à la manière d’Amlogic USB Burning Tool.')}</p>"
            "<p><b>ParadoxXx Squad</b></p>"
            f"<p>{tr('Moteur : outils Amlogic update / adnl_burn_pkg (redistribués par Khadas), séquence du script aml-flash-tool.')}</p>"
        )

    def dragEnterEvent(self, e) -> None:  # noqa: N802
        if e.mimeData().hasUrls() and not self.armed:
            e.acceptProposedAction()

    def dropEvent(self, e) -> None:  # noqa: N802
        urls = e.mimeData().urls()
        if urls and urls[0].isLocalFile():
            self.load_image(Path(urls[0].toLocalFile()))

    def closeEvent(self, e) -> None:  # noqa: N802
        if self.worker:
            if QMessageBox.question(
                    self, APP_NAME,
                    tr("Arrêter le flash en cours ? La box devra être reflashée.")
            ) != QMessageBox.Yes:
                e.ignore()
                return
            self.worker.cancel()
            self.worker.wait(5000)
        self.settings.setValue("geometry", self.saveGeometry())
        e.accept()


def main() -> int:
    import sys
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName(APP_ID)
    w = MainWindow()
    w.show()
    if len(sys.argv) > 1 and Path(sys.argv[1]).is_file():
        QTimer.singleShot(300, lambda: w.load_image(Path(sys.argv[1])))
    return app.exec_()
