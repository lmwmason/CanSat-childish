#!/usr/bin/env bash
# Builds CanSatGroundStation-<arch>.AppImage from the PyInstaller one-folder build.
# It must run on the same CPU architecture it builds for (x86_64 or aarch64 = Raspberry Pi 64-bit).
#
#   cd guiTool && pyinstaller cansat_gui.spec --noconfirm && tools/make_appimage.sh
#
# Env: DIST (default dist/CanSatGroundStation)  OUT (default build)  ARCH (default uname -m)
set -euo pipefail
cd "$(dirname "$0")/.."
ARCH="${ARCH:-$(uname -m)}"
DIST="${DIST:-dist/CanSatGroundStation}"
OUT="${OUT:-build}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
APPDIR="$WORK/AppDir"

mkdir -p "$APPDIR/usr/bin" "$OUT"
cp -r "$DIST" "$APPDIR/usr/bin/CanSatGroundStation"

cat > "$APPDIR/AppRun" <<'RUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/CanSatGroundStation/CanSatGroundStation" "$@"
RUN
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/cansat.desktop" <<'DESK'
[Desktop Entry]
Type=Application
Name=Space Chamchu Ground Station
Exec=CanSatGroundStation
Icon=cansat
Categories=Utility;
Terminal=false
DESK

python3 - "$APPDIR/cansat.png" <<'PY'
import sys
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage
img = QImage("cansat_gui/logo.png").copy(330, 80, 700, 640)
img = img.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
assert img.save(sys.argv[1]), "could not write icon"
PY

TOOL="$WORK/appimagetool"
curl -fsSL -o "$TOOL" "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
chmod +x "$TOOL"
ARCH="$ARCH" "$TOOL" --appimage-extract-and-run "$APPDIR" "$OUT/CanSatGroundStation-${ARCH}.AppImage"
echo "built $OUT/CanSatGroundStation-${ARCH}.AppImage"
