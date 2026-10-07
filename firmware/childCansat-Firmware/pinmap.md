# Child CanSat Pin Map (Arduino Pro Mini, ATmega328P, 5 V / 16 MHz)

Every pin below is taken from the firmware (`src/config/config.h` and the code that uses it), so this file
matches what the program does. Change a pin in `config.h` and update this file as well.

The PlatformIO environment is `pro16MHzatmega328` (Pro Mini **5 V / 16 MHz**). If you build the circuit
around the 3.3 V / 8 MHz Pro Mini, the environment and the timings have to be changed too.

## Pins used by the firmware

| Arduino pin | Function | Mode | Notes | Code location |
|-------------|----------|------|-------|---------------|
| D2 | DHT11 data (temperature, humidity) | input with pull-up, driven as output while reading | `dhtPin` | `lib/dht11/dht11.cpp` |
| D3 | Deploy sensor | input with pull-up | **LOW = still stored in the mother, HIGH = released** (see below) | `src/mission/mission.cpp` |
| D4 | Parachute servo signal | Servo library | locked 0 deg, released 90 deg | `src/mission/boot.cpp` |
| D5 | Buzzer | `tone()` at 2700 Hz | a passive piezo buzzer is the intended type | `src/ui/indicator.cpp` |
| D6 | Yellow LED (**the only LED fitted**) | PWM with `analogWrite()`, level `yellowLedLevel` (25 of 255) | no series resistor, see the LED note below | `src/ui/indicator.cpp`, `src/config/config.h` |
| D7 | Red LED | output, high = on | not fitted in this build, the firmware still drives it | `src/ui/indicator.cpp` |
| D8 | Blue LED | output, high = on | not fitted in this build, the firmware still drives it | `src/ui/indicator.cpp` |
| A4 | I2C SDA | Wire, 400 kHz | BMP280 (0x76), MPU6050 (0x68) | `lib/bmp280`, `lib/mpu6050` |
| A5 | I2C SCL | Wire, 400 kHz | same bus | same as above |
| D0 (RX) / D1 (TX) | Serial, 115200 baud | UART | flight log commands and dump (`s`, `d`, `e`), also used for uploading | `src/comm/serial_cmd.cpp` |

I2C addresses: BMP280 `SDO` pin low = 0x76, MPU6050 `AD0` pin low = 0x68. They do not collide.

Not used by the firmware: D9 - D13, A0 - A3, A6, A7. D13 is the onboard LED.

## Deploy sensor (D3)

The pin has the internal pull-up enabled, so it reads HIGH when nothing is connected.

- While the child is stored in the mother, a contact (a micro switch, or a reed switch with a magnet)
  must connect **D3 to GND**.
- When the child is released, the contact opens and D3 goes HIGH. If it stays HIGH for 1.5 s while the
  state is ARMED, the firmware starts the descent (parachute release, logging).
- With nothing connected to D3 the child will start its descent 1.5 s after it is armed.
- After a reset in mid-flight the firmware checks D3 for 100 ms. If the last log record is DESCENT and the
  pin is HIGH, it resumes the flight instead of starting over.

## Indicators

| LED | ARMED | DESCENT | LANDED |
|-----|-------|---------|--------|
| Yellow | on once the log has records, fast blink when the log is full | short flash on every log write, fast blink when full | cycles with red and blue (900 ms) |
| Red | barometer or IMU fault | barometer or IMU fault | cycles with yellow and blue |
| Blue | short pulse every second | steady on | cycles with yellow and red |

At power-up the yellow LED is on, then blinks during the 9 s warm-up.

| Buzzer pattern | Meaning |
|----------------|---------|
| one 60 ms beep | start-up |
| two short beeps | sensors ready |
| three long beeps | sensor fault (repeats every 5 s while armed) |
| one 700 ms beep | descent started, parachute released |
| three beeps, 2 s pause, repeating | landed, find-me beacon |

## Serial and upload

The Pro Mini has no USB port. Connect a USB-serial adapter (3.3 V or 5 V to match the board) to the 6-pin header
(`GND`, `CTS`, `VCC`, `TXO`, `RXI`, `DTR`). The same connection is used for uploading and for the log dump.
Opening the serial port pulses `DTR` and resets the board. The firmware resumes a flight in progress after
such a reset (see above). The ground station's Data page works at 115200 baud.

## Electrical notes for the circuit

- **Supply:** the firmware does not measure the battery. Power the board through `RAW` (regulated on board)
  or `VCC` with a regulated 5 V, and share one GND with every module.
- **Logic level:** the board runs at 5 V. Check that the BMP280, MPU6050 and DHT11 breakout boards accept 5 V on
  the I2C and data lines. Many BMP280 boards are 3.3 V only, so use one with a regulator and level shifting, or
  a level shifter.
- **I2C pull-ups:** one bus with two devices. Breakout boards often have their own 4.7 kohm pull-ups. Do not stack
  so many that the combined value gets too low.
- **Servo:** power the parachute servo from a supply that can handle its stall current, with its GND tied to the
  board GND. Put about 1 kohm in series with the signal line.
- **Buzzer:** one ATmega pin should not source more than about 20 mA. Use a transistor if the buzzer needs more
  current.
- **Yellow LED without a resistor (D6):** the firmware dims it with PWM (`yellowLedLevel`, about 10 %), which keeps the
  *average* current near a normal LED current. PWM does not limit the current while the pin is on. A 5 V pin
  can push far more than 20 mA into a bare LED for those short pulses, which can shorten the life of the LED and
  of the pin. If there is any room, solder a 330 ohm resistor directly onto one LED leg. That takes no extra board
  space and makes the LED safe. Keep `yellowLedLevel` low, and leave D7 / D8 unconnected or use resistors.
- **DHT11:** needs a pull-up on the data line (4.7 - 10 kohm to VCC). Most modules already have one. Wait at least
  1 s after power-up before the first reading (the firmware does).
- **Timers:** the Servo library uses Timer1 (PWM on D9 / D10 is lost) and `tone()` uses Timer2 (PWM on D3 / D11).
  None of those pins is used for PWM here.
