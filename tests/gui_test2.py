import sys
from pathlib import Path
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication
from amlogic_linux_flasher import ui, engine
engine.Flasher.wait = lambda self, s: None
img, out, script = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
app = QApplication([])
w = ui.MainWindow(); w.resize(1180, 680); w.show()
w.settings.remove("last_image")
def shot(name): w.grab().save(str(out / name)); print("shot", name, {k:(v['state'],v['text'],v['pct']) for k,v in w.devices.items()})
def adb():
    w.tabs.setCurrentIndex(1)
    from amlogic_linux_flasher.adbtools import parse_script
    c, _ = parse_script(script)
    w.adb_tab.list_devices(); w.adb_tab.run_many(c, cwd=str(script.parent))
steps = [(300, lambda: w.load_image(img)), (1500, lambda: shot("a_charge.png")),
  (100, w.toggle_start), (900, lambda: shot("b_flash.png")), (3000, lambda: shot("c_fini.png")),
  (100, adb), (1500, lambda: shot("d_adb.png")), (100, app.quit)]
t = 0
for d, fn in steps:
    t += d; QTimer.singleShot(t, fn)
app.exec_()
