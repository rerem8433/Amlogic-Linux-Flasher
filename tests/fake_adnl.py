#!/usr/bin/env python3
"""Faux adnl_burn_pkg."""
import os, sys, time
with open("/tmp/fake_adnl.log", "a") as f:
    f.write(repr(sys.argv[1:]) + "\n")
sp = float(os.environ.get("FAKE_SPEED", "0.02"))
print("MSG[TLS]pkg path " + sys.argv[2])
for step in ("BL2", "TPL", "boot", "system", "vendor"):
    for p in range(0, 101, 10):
        sys.stdout.write(f"\r[{step}] %{p}.."); sys.stdout.flush(); time.sleep(sp)
    print()
print("[Hub3-2]burn successful^_^")
