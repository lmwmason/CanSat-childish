#!/usr/bin/env python3
"""Build the official CanSat default sketch without uploading to hardware."""
import argparse
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--servo-pins', choices=['ta', 'at', 'dt'], help='build the automatic bench sweep for the indicated board labels')
parser.add_argument('--bt-info', action='store_true', help='temporary read-only Bluetooth UART inventory firmware')
args = parser.parse_args()
if args.bt_info and args.servo_pins:
    parser.error('Choose --bt-info or --servo-pins')
BUILD = ROOT / 'build'
if args.servo_pins:
    BUILD = BUILD / ('servo-' + args.servo_pins)
if args.bt_info:
    BUILD = ROOT/'build/bt-info'
BUILD.mkdir(parents=True, exist_ok=True)
TOOLS = Path(os.environ.get('AVR_TOOLCHAIN', str(Path.home() / '.platformio/packages/toolchain-atmelavr/bin')))
CORE = ROOT / 'vendor/arduino/cores/arduino'
VARIANT = ROOT / 'vendor/arduino/variants/cansat'
LIBS = [ROOT / ('vendor/' + n + '/src') for n in ('Servo', 'SD', 'SPI', 'EEPROM')]
FLAGS = ['-mmcu=atmega128', '-DF_CPU=11059200L', '-DARDUINO=10819', '-DARDUINO_ARCH_AVR', '-DARDUINO_AVR_ATMEGA128', '-Os', '-ffunction-sections', '-fdata-sections']
if args.bt_info:
    FLAGS.append('-DBT_RX_DIAG')
if args.servo_pins:
    FLAGS.append('-DSERVO_TEST_' + args.servo_pins.upper())
INCLUDES = [arg for p in [CORE, VARIANT, ROOT/'src', *LIBS] for arg in ['-I', str(p)]]

def run(args):
    subprocess.run([str(x) for x in args], check=True)

sources = [ROOT/('src/bt_info_probe.cpp' if args.bt_info else 'src/main.cpp')]
sources += [p for p in CORE.iterdir() if p.suffix in ('.c', '.cpp', '.S')]
for lib in LIBS:
    for p in lib.rglob('*'):
        if p.suffix in ('.c', '.cpp', '.S') and not any(x in p.parts for x in ('sam', 'samd', 'megaavr', 'mbed', 'nrf52', 'renesas', 'esp32', 'stm32f4', 'xmc')):
            sources.append(p)
objects = []
for i, source in enumerate(sources):
    target = BUILD / (str(i) + '_' + source.name + '.o')
    cpp = source.suffix == '.cpp'
    extra = ['-std=gnu++11', '-fpermissive', '-fno-exceptions', '-fno-threadsafe-statics'] if cpp else ['-std=gnu11']
    run([TOOLS/('avr-g++' if cpp else 'avr-gcc'), *FLAGS, *extra, *INCLUDES, '-c', source, '-o', target])
    objects.append(target)
elf = BUILD/'firmware.elf'
run([TOOLS/'avr-gcc', '-mmcu=atmega128', '-Wl,--gc-sections', '-o', elf, *objects, '-lm'])
run([TOOLS/'avr-objcopy', '-O', 'ihex', '-R', '.eeprom', elf, BUILD/'firmware.hex'])
run([TOOLS/'avr-size', '-C', '--mcu=atmega128', elf])
print('HEX:', BUILD/'firmware.hex')
