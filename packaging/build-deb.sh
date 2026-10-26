#!/bin/bash
# Construit les paquets .deb d'Amlogic Linux Flasher.
# Usage : ./packaging/build-deb.sh [9|11|14 ...]   (sans argument : les trois éditions)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ $# -eq 0 ]; then
    set -- 9 11 14
fi
if [ $# -gt 1 ]; then
    for ed in "$@"; do "$0" "$ed"; done
    exit 0
fi

ED="$1"
info() {
    AMLF_EDITION="$ED" PYTHONPATH="$ROOT/src" python3 -c \
        "import amlogic_linux_flasher as a; print($1)"
}
APP=$(info a.APP_ID)
VERSION=$(info a.VERSION)
TITLE=$(info a.APP_TITLE)
CHIPS=$(info "a.ED['chips']")
PROTO=$(info "a.ED['protocol']")

BUILD="$ROOT/build/deb"
PKG="$BUILD/${APP}_${VERSION}_amd64"
LIB="$PKG/usr/lib/$APP"

rm -rf "$PKG"
mkdir -p "$LIB" "$PKG/usr/bin" "$PKG/usr/share/applications" \
         "$PKG/usr/share/icons/hicolor/scalable/apps" "$PKG/usr/lib/udev/rules.d" \
         "$PKG/usr/share/doc/$APP" "$PKG/DEBIAN" "$ROOT/dist"

# Code Python + édition figée
cp -r "$ROOT/src/amlogic_linux_flasher" "$LIB/"
find "$LIB" -name "__pycache__" -type d -prune -exec rm -rf {} +
echo "EDITION = \"$ED\"" > "$LIB/amlogic_linux_flasher/_edition.py"

# Outils Amlogic : seulement ceux de l'édition
mkdir -p "$LIB/tools"
if [ "$PROTO" = "adnl" ]; then
    cp -r "$ROOT/tools/adnl" "$LIB/tools/"
    chmod 755 "$LIB/tools/adnl/adnl" "$LIB/tools/adnl/adnl_burn_pkg"
    chmod 644 "$LIB/tools/adnl/usb_flow/"*
    TOOL_DEPS="libudev1"
else
    cp -r "$ROOT/tools/update" "$ROOT/tools/aml_image_v2_packer" "$ROOT/tools/datas" "$LIB/tools/"
    chmod 755 "$LIB/tools/update" "$LIB/tools/aml_image_v2_packer"
    chmod 644 "$LIB/tools/datas/"*
    TOOL_DEPS="libusb-0.1-4"
fi

# Lanceur
cat > "$PKG/usr/bin/$APP" <<EOF
#!/bin/sh
export PYTHONPATH="/usr/lib/$APP\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m amlogic_linux_flasher "\$@"
EOF
chmod 755 "$PKG/usr/bin/$APP"

# Icône avec le numéro d'édition
python3 - "$ROOT/data/amlogic-linux-flasher.svg" "$PKG/usr/share/icons/hicolor/scalable/apps/$APP.svg" "$ED" <<'EOF'
import sys
src, dst, ed = sys.argv[1:]
svg = open(src).read()
badge = (f'<rect x="34" y="38" width="28" height="22" rx="6" fill="#ff6d00"/>'
         f'<text x="48" y="54" font-family="sans-serif" font-size="15" font-weight="bold" '
         f'fill="white" text-anchor="middle">{ed}</text>')
open(dst, "w").write(svg.replace("</svg>", badge + "\n</svg>"))
EOF

# Menu
cat > "$PKG/usr/share/applications/$APP.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$TITLE
GenericName=Amlogic USB Burning Tool
Comment=Flash Amlogic boxes over USB ($CHIPS)
Comment[fr]=Flasher une box Amlogic en USB ($CHIPS)
Exec=$APP %f
Icon=$APP
Terminal=false
Categories=Utility;System;
Keywords=amlogic;usb;burning;flash;firmware;android;tv;box;fastboot;adb;
StartupWMClass=$APP
EOF

# Règle udev : accès USB aux box en mode burn sans sudo
AMLF_EDITION="$ED" PYTHONPATH="$ROOT/src" python3 -c "
from amlogic_linux_flasher import paths
open('$PKG/usr/lib/udev/rules.d/' + paths.UDEV_RULE_NAME, 'w').write(
    '# $TITLE : box Amlogic en mode USB burn\n' + paths.UDEV_RULE)"

cp "$ROOT/README.md" "$PKG/usr/share/doc/$APP/README.md"

SIZE=$(du -sk "$PKG" | cut -f1)
# la v9 remplace l'ancien paquet « amlogic-linux-flasher » 1.0.0
EXTRA=""
if [ "$ED" = "9" ]; then
    EXTRA=$'Conflicts: amlogic-linux-flasher\nReplaces: amlogic-linux-flasher\n'
fi
cat > "$PKG/DEBIAN/control" <<EOF
Package: $APP
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Depends: python3 (>= 3.8), python3-pyqt5, $TOOL_DEPS, adb, fastboot, pkexec | policykit-1
${EXTRA}Installed-Size: $SIZE
Maintainer: ParadoxXx Squad
Description: $TITLE - USB flashing of Amlogic boxes ($CHIPS)
 Linux clone of Amlogic USB Burning Tool: burns .img files in
 USB Burning Tool format, plus an ADB / Fastboot tab (bootloader
 unlock, .cmd scripts shipped with firmwares). English / French UI.
 .
 Clone Linux d'Amlogic USB Burning Tool : flash des images .img
 au format USB Burning Tool, plus un onglet ADB / Fastboot
 (déverrouillage du bootloader, scripts .cmd fournis avec les
 firmwares). Interface en français et en anglais.
EOF

cat > "$PKG/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload-rules || true
    udevadm trigger --subsystem-match=usb --attr-match=idVendor=1b8e || true
fi
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -f /usr/share/icons/hicolor || true
exit 0
EOF
cat > "$PKG/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
command -v udevadm >/dev/null 2>&1 && udevadm control --reload-rules || true
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
exit 0
EOF
chmod 755 "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/postrm"

dpkg-deb --root-owner-group --build "$PKG" "$ROOT/dist/${APP}_${VERSION}_amd64.deb" >/dev/null
echo "OK : dist/${APP}_${VERSION}_amd64.deb"
