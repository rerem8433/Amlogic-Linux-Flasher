#!/usr/bin/env python3
"""Faux binaire « update » : simule ROM → BL2 (protocole 8) → U-Boot."""
import os, sys, time
args = sys.argv[1:]
st = "/tmp/fake_state"
state = open(st).read() if os.path.exists(st) else "uboot_old"
def setst(x): open(st, "w").write(x)
with open(os.environ.get("FAKE_UPDATE_LOG", "/tmp/fake_update.log"), "a") as f:
    f.write(f"{state:10s} {args!r}\n")
cmd = args[0] if args else ""
speed = float(os.environ.get("FAKE_SPEED", "0.02"))
ver = {"rom": "2-4-0-0-0-1-0", "bl2": "2-2-0-8-0-1-0"}.get(state, "0-7-0-16-0-0-0")
if cmd == "identify":
    print("AmlUsbIdentifyHost\nThis firmware version is " + ver)
elif cmd == "bulkcmd":
    a = args[1].strip()
    if state in ("rom", "bl2"):
        open("/tmp/fake_echo", "w").close()
        print("[AmlUsbRom]Err:return len=0 < strLenBusy 11\nERR: AmlUsbBulkCmd failed!")
    else:
        if a == "reset":
            setst("rom")
            if os.path.exists("/tmp/fake_echo"): os.remove("/tmp/fake_echo")
        print("[AmlUsbRom]Inf:bulkInReply success")
elif cmd == "run":
    if state == "rom":
        if os.environ.get("FAKE_RUN_FAIL_ONCE") and not os.path.exists("/tmp/fake_runfail"):
            open("/tmp/fake_runfail", "w").close()
        elif not os.environ.get("FAKE_NEED_ECHO") or os.path.exists("/tmp/fake_echo"):
            setst("bl2")
    elif state == "bl2" and os.path.exists("/tmp/fake_tpl"):
        setst("uboot"); os.remove("/tmp/fake_tpl")
    print("[update]Run at Addr " + args[1])
elif cmd == "write" and args[1].endswith("UBOOT.USB") and state == "rom" and args[2] == "0x200c000":
    setst("rom")  # DDR non initialisée : la box plante et revient en ROM
    print("usbWriteFile len=4096,ret=-19 error_msg=error submitting URB: No such device\nERR: write data to device failed")
elif cmd == "write" and args[1].endswith("UBOOT.USB"):
    if os.environ.get("FAKE_FAIL_ONCE") and not os.path.exists("/tmp/fake_failed"):
        open("/tmp/fake_failed", "w").close(); setst("rom")
        print("usbWriteFile len=4096,ret=-19 error_msg=error submitting URB: No such device\nERR: write data to device failed")
    else:
        open("/tmp/fake_tpl", "w").close(); print("Transfer Complete!")
elif cmd == "bl2_boot":
    setst("uboot"); print("[LUSB]BL2 END, waiting TPL plug-in...")
elif cmd == "chipid":
    if state == "rom":
        print("ChipID is:0x" + os.environ.get("FAKE_CHIP", "AMLGXL0123456789").encode().hex())
    else:
        print("romStage not bl1/bl2, cannot support chipid")
elif cmd == "rreg":
    print(f"{args[2][2:]}: 00000000")
elif cmd == "partition":
    size = os.path.getsize(args[2]) // 2**20 or 1
    for p in range(0, 101, 5):
        sys.stdout.write(f"\r[{p:3d}%/{size:5d}MB]"); sys.stdout.flush(); time.sleep(speed)
    print("\n[update]mwrite success")
else:
    print("Transfer Complete!")
