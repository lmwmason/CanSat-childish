#!/usr/bin/env bash
# Starts the ground station on a Raspberry Pi (Raspberry Pi OS, 32 or 64 bit). Keep this file next to
# CanSatGroundStation.pyz. The first run installs PyQt6 from Raspberry Pi OS (needs internet + sudo).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
if ! python3 -c "import PyQt6.QtSerialPort" 2>/dev/null; then
    echo "Installing PyQt6 (python3-pyqt6, python3-pyqt6.qtserialport) ..."
    sudo apt-get update
    sudo apt-get install -y python3-pyqt6 python3-pyqt6.qtserialport
fi
if ! id -nG | tr ' ' '\n' | grep -qx dialout; then
    echo "Note: your user is not in the 'dialout' group, so serial ports may be denied:"
    echo "      sudo usermod -aG dialout \$USER   (then log out and in)"
fi
exec python3 "$HERE/CanSatGroundStation.pyz" "$@"
