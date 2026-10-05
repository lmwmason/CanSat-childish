# Ground Station Pin Map: Raspberry Pi 4 <-> Crossfire Micro TX V2

Wiring for the ground station (`guiTool`). The Raspberry Pi acts as the transmitter: it sends RC frames
(AUX1 / AUX2) to the Crossfire module and reads the telemetry the module returns.

The mother CanSat side is in the firmware `pinmap.md`. This file only covers the ground side.

**Read the "Verify before powering" section first.** The module's JR-bay pin numbers come from community
documentation, not from a TBS pinout drawing for the Micro TX V2.

## What the module is

- The Crossfire Micro TX V2 is a JR-bay module (it plugs into the external module bay of a radio).
- Input voltage: 6.0 - 13 V.
- Its USB-C port is documented for power and firmware update (TBS Agent). It is **not** documented as a
  CRSF serial port, so the Pi talks to the module through the JR-bay signal pin, not through USB.

## JR module bay pins (standard, top to bottom)

| JR pin | Name | Use here |
|--------|------|----------|
| 1 | PPM | not connected |
| 2 | +6V (regulated, output of a radio) | not connected (see "Verify") |
| 3 | +BAT (raw battery voltage) | module power, 6 - 13 V |
| 4 | GND | ground (shared with the Pi) |
| 5 | ANT / S.Port | **CRSF data**, single-wire half-duplex |

## Wiring

| From | To | Notes |
|------|----|-------|
| Pi pin 8 (GPIO14, TXD0) | diode anode (Schottky, e.g. BAT54 / 1N5819) | transmit path |
| diode cathode | JR pin 5 (CRSF data) | the diode lets the Pi pull the line low but never drive it high |
| JR pin 5 (CRSF data) | Pi pin 10 (GPIO15, RXD0) | receive path, connected directly |
| Pi pin 1 (3V3) | 4.7 kohm resistor -> JR pin 5 | pull-up so the line idles high |
| Pi pin 6 (GND) | JR pin 4 (GND) | common ground, required |
| battery / supply (6 - 13 V) | JR pin 3 (+BAT) | module power. Share its ground with JR pin 4 |

```
 Pi TXD (pin 8) ----|>|----+---- JR pin 5 (CRSF data, half-duplex)
                           |
 Pi RXD (pin 10) ----------+
                           |
 Pi 3V3 (pin 1) --[4.7k]---+

 Pi GND (pin 6) ------------------ JR pin 4 (GND) ---- supply GND
                                   JR pin 3 (+BAT) --- supply + (6 - 13 V)
```

- Everything on the Pi side is 3.3 V logic. Do not connect a 5 V signal to the Pi.
- The Pi receives its own transmitted bytes (half-duplex echo). The software ignores them.
- The diode + pull-up circuit is a standard way to run a single-wire UART from a push-pull Pi pin. It is
  a starting design for 400 kbaud, so check the waveform with a scope or logic analyser.
- Size the supply for the module's transmit current (check the TBS specification). Do not power the module
  from the Pi's 5 V pins.

## Raspberry Pi setup

1. In `/boot/firmware/config.txt` (older images: `/boot/config.txt`) add:
   ```
   enable_uart=1
   dtoverlay=disable-bt
   ```
   This gives the full PL011 UART (`/dev/serial0` -> `ttyAMA0`) on GPIO14/15. The mini-UART is not suitable
   for a precise 400 kbaud.
2. `sudo raspi-config` -> Interface Options -> Serial Port -> login shell over serial: **No**, serial
   hardware: **Yes**. Reboot.
3. `sudo usermod -aG dialout $USER`, then log out and in.
4. Check the baud rate can be set: `stty -F /dev/serial0 400000`.
5. Make a new virtual environment on the Pi (the `.venv` in this repo was built on x86 and does not work on
   the Pi):
   ```
   cd guiTool
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/python -m cansat_gui
   ```
   Use a 64-bit Raspberry Pi OS so a PyQt6 wheel is available.
6. In the Mother connection bar choose `serial0` and **400000 baud** (the default).

## Baud rates

| Link | Baud |
|------|------|
| Pi <-> Crossfire TX module (JR bay) | 400000 (default in the app) |
| Crossfire receiver <-> mother CanSat (firmware USART6) | 420000 (the receiver speaks about 416666; the 0.8 % difference is within UART tolerance) |

The app treats 400000, 416666 and 420000 as CRSF. Any other baud rate is the old text-line protocol.

## Verify before powering

These were **not** confirmed from a TBS document for the Micro TX V2:

1. The physical order and orientation of the module's JR pins. Check with a multimeter (continuity to the
   radio-bay drawing, or the supply pins) before applying power. A wrong connection on +BAT / GND can
   destroy the module.
2. That the CRSF data pin is JR pin 5. This is the common convention (it is the S.Port / antenna pin), but
   confirm it for this module.
3. Whether the module needs the +6V pin (JR pin 2) or accepts power on +BAT alone.
4. Whether the module needs the handset to hold the data line high (the pull-up above covers this) and
   that its logic level is 3.3 V.
5. The handset <-> module baud rate (400000 is the usual default; try 416666 / 420000 if no frames arrive).

If no telemetry shows up, the Actions tab shows the CRSF frame and CRC error counters. Zero frames means a
wiring, baud or half-duplex problem. Frames with CRC errors usually mean a wrong baud rate or a noisy line.

## Sources

- [TBS Crossfire Micro TX quick-start guide](https://www.team-blacksheep.com/media/files/tbs-crossfire-micro-tx-quickstart.pdf): JR form factor, CRSF output.
- [Transmitter external module pinout (Stavros' Notes)](https://notes.stavros.io/drone-stuff/transmitter-external-module-pinout/): JR bay pins 1 - 5.
- [ExpressLRS radio preparation](https://www.expresslrs.org/quick-start/transmitters/tx-prep/): modules need VBAT, GND and S.Port/data; 400000 / 921000 / 1.87M baud options.
- [Oscar Liang: TBS Crossfire Micro TX V2](https://oscarliang.com/tbs-crossfire-micro-tx-v2/): 6 - 13 V input, USB-C for power and firmware.
