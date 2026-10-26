import sys, time
from pathlib import Path
from amlogic_linux_flasher import image, engine
img = Path(sys.argv[1])
image.quick_check(img); print(image.crc_check(img)); image.unpack(img)
info = image.parse(img)
print([ (p.sub_type, p.size) for p in info.partitions ], info.platform)
engine.Flasher.wait = lambda self, s: None
seen = []
f = engine.Flasher(info, engine.Options(soc=sys.argv[2] if len(sys.argv)>2 else "g12a"),
    on_status=lambda s,p: seen.append((s,p)), on_log=lambda l: None, log_file=Path("/tmp/eng.log"))
f.flash()
print(len(seen), seen[:6], seen[-4:])
print("monotone:", all(b[1] >= a[1] for a, b in zip(seen, seen[1:])))
