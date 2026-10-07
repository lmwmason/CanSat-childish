# CanSat-childish

[![STM32](https://img.shields.io/badge/STM32-F410RB-03234B?logo=stmicroelectronics&logoColor=white)](https://www.st.com/en/microcontrollers-microprocessors/stm32f410rb.html)
[![PlatformIO](https://img.shields.io/badge/PlatformIO-ATmega328-F5822A?logo=platformio&logoColor=white)](https://platformio.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-Ground%20station-41CD52?logo=qt&logoColor=white)](https://www.riverbankcomputing.com/software/pyqt/)
[![KiCad](https://img.shields.io/badge/KiCad-PCB-314CB0?logo=kicad&logoColor=white)](https://www.kicad.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-D22128?logo=apache&logoColor=white)](./LICENSE)

<img src="./guiTool/cansat_gui/logo.png">

CanSat-childish is the open-source code and hardware for a two-tier CanSat
project by the Space Chamchu team: a **mother CanSat** that is dropped, steadies
itself with a reaction wheel, spins up, opens a door, ejects its wings and
glides back around the drop point, and small **child CanSats** that fall under a
parachute and record the descent. A **ground station** receives the mother's
telemetry over a TBS Crossfire link, shows it live and records it to CSV.

The repository holds every part of the system:

- **Mother firmware** — STM32F410RB. Fuses two IMUs, detects the drop, stabilizes
  and spins the body with a reaction wheel, opens the door, ejects the wings,
  flies the elevons (manual from the radio or automatic with GPS), detects the
  landing, and sends telemetry down the CRSF link.
- **Child firmware** — ATmega328 (Arduino Pro Mini). Reads barometer, IMU and
  humidity sensors, releases a parachute with a servo and logs the whole flight
  to EEPROM so it can be dumped over serial after landing.
- **Ground station** — a PyQt6 desktop app (Mission Planner style) that runs on a
  Raspberry Pi with a Crossfire Micro TX V2, or on a normal PC. Live flight view,
  ground track, CSV recording and the AUX switches of the mother.
- **Simulator** — the flight logic as a hardware-independent C core, run on a
  rigid-body physics engine, with a live 3D viewer.
- **PCB** — the KiCad project of the mother board.

## Mother mission

The mother's mission is a state machine on the STM32. Every number below is a
constant in the source and can be tuned.

1. **Drop detection** — the acceleration magnitude stays between 9.7 and
   9.9 m/s² for 300 ms **and** the AUX1 switch on the radio is on.
2. **2 s later** — the reaction wheel turns on and holds the current heading.
3. **Stable** (yaw rate under 8°/s and yaw error under 10° for 1 s) — the wheel
   spins the body up at full power.
4. **180°/s reached** — the servo opens the door.
5. **5 s at maximum speed**, then the wheel brakes and holds the heading again.
6. **Stable again** — the two wing servos eject the wings.
7. **Elevons** — the AUX2 switch selects manual (sticks) or automatic. Automatic
   mode levels the aircraft and circles around the point where the drop was
   detected (50 m radius) using the GPS.
8. **Landing** — motionless for 3 s (at least 10 s after the drop): the buzzer
   sounds and all LEDs blink.

## Tech stack

- **Mother firmware:** C, STM32 HAL, [STM32CubeMX](https://www.st.com/en/development-tools/stm32cubemx.html) project (`.ioc`) with IAR EWARM project files
- **Sensors on the mother:** MPU6050 + ICM-42688 (I2C), u-blox NEO-6M GPS (I2C / DDC), TBS Crossfire receiver (CRSF, UART)
- **Child firmware:** C++ / Arduino framework with [PlatformIO](https://platformio.org/); BMP280, MPU6050 (on-chip DMP), DHT11
- **Ground station:** Python 3, [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) (Qt Serial Port), [PyInstaller](https://pyinstaller.org/) and AppImage for releases
- **Simulator:** C11, [Open Dynamics Engine](https://www.ode.org/), Python with matplotlib / numpy for the viewer
- **Hardware design:** [KiCad](https://www.kicad.org/)

## Getting started

### Ground station

The easiest way is a build from the
[Releases](https://github.com/lmwmason/CanSat-childish/releases) page:

| File | For |
| ---- | --- |
| `CanSatGroundStation-aarch64.AppImage` | Raspberry Pi 4 / 5, 64-bit OS |
| `CanSatGroundStation-x86_64.AppImage` | Linux PC |
| `CanSatGroundStation-…-windows-x64.zip` | Windows PC |
| `CanSatGroundStation.pyz` + `run-on-pi.sh` | Any Raspberry Pi OS, if the AppImage does not work |

On a Raspberry Pi:

```bash
sudo apt install libfuse2 libxcb-cursor0
chmod +x CanSatGroundStation-aarch64.AppImage
./CanSatGroundStation-aarch64.AppImage
```

To run it from source:

```bash
cd guiTool
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m cansat_gui
```

Pick **Demo (synthetic flight)** in the Mother bar to try everything without
hardware. For the real link, choose the serial port and 400000 baud (CRSF). The
wiring between the Raspberry Pi and the Crossfire module is in
[`guiTool/pinmap.md`](./guiTool/pinmap.md). Telemetry is recorded to
`~/CanSat Logs/` (or `guiTool/logs/` when run from source).

Run the tests with `python -m unittest discover -s tests` inside `guiTool`.
To build a release locally:

```bash
pip install -r requirements-build.txt
pyinstaller cansat_gui.spec --noconfirm
tools/make_appimage.sh
```

Pushing a tag named `gui-vX.Y.Z` makes GitHub Actions
([`gui-release.yml`](./.github/workflows/gui-release.yml)) build the AppImages
for aarch64 and x86_64 and the Windows zip, and publish them as a release.

### Mother firmware

1. Open `firmware/motherCansat-Firmware/motherCansat-Firmware.ioc` in
   STM32CubeMX to inspect or regenerate the peripheral setup.
2. Build and flash with your STM32 toolchain (the `EWARM` folder contains the IAR
   project). Keep your own code inside the `USER CODE` blocks of `main.c`.
3. Check the wiring against
   [`firmware/motherCansat-Firmware/pinmap.md`](./firmware/motherCansat-Firmware/pinmap.md).
   Several pins (wheel motor, servos, buzzer, LEDs) are not labeled in the `.ioc`,
   so the pin map is the reference.

The mission constants live in the headers of the modules, for example
`mission.h`, `drop_detect.h`, `landing_detect.h`, `elevon.h` and `nav.h`.

### Child firmware

```bash
cd firmware/childCansat-Firmware
pio run -t upload
pio device monitor -b 115200
```

The serial monitor accepts `s` (status), `d` (dump the flight log as CSV) and
`e` (erase the log).

### Simulator

Needs `gcc`, `make`, the ODE development package (`ode-devel` on Fedora,
`libode-dev` on Debian / Ubuntu) and Python with `matplotlib` and `numpy` for the
viewer.

```bash
cd simulator
./run.sh              # build, then an interactive menu
./run.sh mother       # the mothership simulation
./run.sh child 1      # a child satellite simulation (1 to 3)
./run.sh test         # the headless failsafe test
./run.sh viz          # live 3D telemetry viewer
./run.sh all          # mother + 3 children + viewer together
```

## Project structure

```
firmware/
  childCansat-Firmware/    PlatformIO project of the child CanSat
    src/                   main, boot, mission, sensors, storage (EEPROM log), comm, ui, core, config
    lib/                   bmp280, dht11 and mpu6050 drivers
    pinmap.md              Pin assignments of the child
  motherCansat-Firmware/   STM32CubeMX project of the mother CanSat
    Core/Src/              main.c and the application modules:
                             imu, gps, nav, crsf, drop, mission, reaction_wheel, pid,
                             door, wings, elevon, soft_pwm, wheel_motor, landing, indicator
    pinmap.md              Pin assignments of the mother
guiTool/
  cansat_gui/              The PyQt6 ground station (CRSF decoder, CSV logger, pages)
  tests/                   Frame-format tests against the real firmware output
  tools/                   Packaging scripts (AppImage, .pyz, Raspberry Pi launcher)
  pinmap.md                Wiring Raspberry Pi <-> Crossfire TX module
simulator/
  core/                    Hardware-independent flight logic in C
  sim/                     Mothership and child simulations (physics)
  viz/                     Live 3D viewer (Python)
pcb/
  motherBoard/kicad-pcb/   KiCad project of the mother board
photos/                    Schematic and PCB exports
.github/workflows/         Ground station release build
```

## Status

The mother firmware and the ground station are verified on a PC: the telemetry
frames the firmware produces are decoded correctly by the ground station, and the
mission logic was simulated. They have **not yet been tested end to end on the
real hardware**. The mother's pin assignments are chosen in `pinmap.md`, and the
Crossfire module pins should be checked before powering anything.

## License

Licensed under the [Apache License 2.0](./LICENSE).
