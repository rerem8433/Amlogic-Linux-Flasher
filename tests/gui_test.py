import sys, os
from pathlib import Path
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication
from amlogic_linux_flasher import ui, engine
engine.Flasher.wait = lambda self, s: None
out = Path(sys.argv[2]); img = Path(sys.argv[1])
app = QApplication([])
w = ui.MainWindow(); w.resize(1180, 680); w.show()
w.settings.remove("last_image")
def shot(name): w.grab().save(str(out / name)); print("shot", name, w.devices and {k:(v['state'],v['text'],v['pct']) for k,v in w.devices.items()})
steps = [
  (300, lambda: w.load_image(img)),
  (2500, lambda: shot("1_charge.png")),
  (100, lambda: w.toggle_start()),
  (1800, lambda: shot("2_flash.png")),
  (6000, lambda: shot("3_fini.png")),
  (100, lambda: (w.set_language("en"), shot("4_en.png"))),
  (100, lambda: app.quit()),
]
t = 0
for d, fn in steps:
    t += d; QTimer.singleShot(t, fn)
app.exec_()
