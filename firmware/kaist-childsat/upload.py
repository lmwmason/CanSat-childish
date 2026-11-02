#!/usr/bin/env python3
"""Upload the already-built HEX over the board's USB bootloader."""
import argparse
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--port', required=True, help='2nd-floor USB serial device, e.g. /dev/ttyUSB0')
parser.add_argument('--servo-pins', choices=['ta', 'at', 'dt'], help='upload the automatic bench sweep instead of the default firmware')
parser.add_argument('--dry-run', action='store_true', help='print the command without opening the device')
parser.add_argument('--bt-info', action='store_true', help='upload the temporary Bluetooth query firmware')
args = parser.parse_args()
if args.bt_info and args.servo_pins:
    parser.error('Choose --bt-info or --servo-pins')
# The user's original reference satellite must never be flashed by this tool.
protected_serial = 'A10NSP6U'
resolved = Path(args.port).resolve()
protected_path = Path('/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_' + protected_serial + '-if00-port0')
if protected_serial in args.port or (protected_path.exists() and resolved == protected_path.resolve()):
    parser.error('Original reference satellite protected: firmware upload is forbidden')
hexfile = root/'build/firmware.hex'
if args.servo_pins:
    hexfile = root/'build'/('servo-' + args.servo_pins)/'firmware.hex'
if args.bt_info:
    hexfile = root/'build/bt-info/firmware.hex'
if not hexfile.is_file():
    parser.error('Run python3 build.py first')
package = Path(os.environ.get('AVRDUDE_DIR', str(Path.home()/'.platformio/packages/tool-avrdude')))
config = package/'avrdude.conf'
if not config.exists():
    config = package/'etc/avrdude.conf'
command = [str(package/'avrdude'), '-C', str(config), '-p', 'atmega128', '-c', 'arduino', '-P', args.port, '-b', '115200', '-D', '-U', f'flash:w:{hexfile}:i']
if args.dry_run:
    import shlex
    print(shlex.join(command))
else:
    if not Path(args.port).exists():
        parser.error(f'Serial device does not exist: {args.port}')
    subprocess.run(command, check=True)
