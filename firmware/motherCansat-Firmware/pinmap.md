# Mother CanSat Pin Map (STM32F410RB)

This is the pin map the firmware uses and the reference for the circuit design.
If you change one, update the file listed under "Code location" as well.

## Communication / sensors

| Pin | Function | Setting | Connected to | Code location |
|-----|----------|---------|--------------|---------------|
| PB6 | I2C1 SCL | 100 kHz | MPU6050 (0x68), ICM-42688 (0x69), NEO-6M GPS (0x42) | `imu/imu.h`, `gps/gps.h` |
| PB7 | I2C1 SDA | 100 kHz | same as above | |
| PC6 | USART6 TX | 420000 baud, 8N1 | CRSF receiver (Crossfire Nano RX) | `crsf/crsf.c` |
| PC7 | USART6 RX | 420000 baud, interrupt RX | same as above | |
| PA2 | USART2 TX | 115200 baud | Debug output (ST-Link VCP) | `main.c` |
| PA3 | USART2 RX | 115200 baud | same as above | |

- I2C address conflict avoided: MPU6050 has AD0 = low (0x68), ICM-42688 has AD0 = high (0x69).
- The NEO-6M breakout must expose its I2C (DDC) pins. Many boards only break out UART.

## Actuators

| Pin | Function | Timer / method | Code location |
|-----|----------|----------------|---------------|
| PA8 | Reaction wheel motor, forward PWM **(chosen)** | TIM1 CH1, 20 kHz | `wheel_motor/wheel_motor.h` |
| PA9 | Reaction wheel motor, reverse PWM **(chosen)** | TIM1 CH2, 20 kHz | same as above |
| PA0 | Door servo **(chosen)** | TIM5 CH1, 50 Hz, 1 us tick | `door/door.h` |
| PA1 | Wing ejection servos (2, signal wired in parallel) **(chosen)** | TIM5 CH2, 50 Hz | `wings/wings.h` |
| PC8 | Left elevon servo | Software PWM (TIM5 interrupt) | `soft_pwm/soft_pwm.c` |
| PC9 | Right elevon servo | Software PWM (TIM5 interrupt) | same as above |

Servo pulse widths (us):

| Servo | Default | Active |
|-------|---------|--------|
| Door | 1000 (closed) | 2000 (open) |
| Wings | 1000 (locked) | 2000 (ejected) |
| Elevons | 1500 (neutral) | neutral +/- 400 |

## Indicators

| Pin | Function | Code location |
|-----|----------|---------------|
| PA4 | Buzzer **(chosen)**, active buzzer (high = sound) | `indicator/indicator.h` |
| PA5 | LD2 (green onboard LED): on while a drop is detected, blinks after landing | same as above |
| PB12 | LED **(chosen)**: blinks after landing | same as above |
| PB13 | LED **(chosen)** | same as above |
| PB14 | LED **(chosen)** | same as above |
| PB15 | LED **(chosen)** | same as above |

## Controller (CRSF) channels

| Channel | Use | Code location |
|---------|-----|---------------|
| CH1 | Manual mode roll (aileron stick) | `elevon/elevon.h` |
| CH2 | Manual mode pitch (elevator stick) | same as above |
| CH5 (AUX1) | Drop detection switch (drop condition, mission start/reset) | `crsf/crsf.h` |
| CH6 (AUX2) | Elevon mode: on = manual, off = automatic (automatic if the link is lost) | `elevon/elevon.h` |

## Configured but not used by the code

| Pin | CubeMX setting | Note |
|-----|----------------|------|
| PC12 | TIM11 CH1 (50 Hz, 1 us tick) | Looks like a servo output. Could be used to split the two wing servos |
| PA10 | TIM1 CH3 (20 kHz) | Unused |
| PC0-PC4 | GPIO output | Unused |
| PC5 | Analog | Unused |
| PA12 | GPIO input | Unused |
| PC13 | B1 (blue button) | Unused |

## Reserved pins (do not use)

| Pin | Use |
|-----|-----|
| PA13 / PA14 / PB3 | SWD (SWDIO / SWCLK / SWO) |
| PC14 / PC15 | 32 kHz crystal |
| PH0 / PH1 | External crystal (HSE) |

## Timer summary

| Timer | Rate | Use |
|-------|------|-----|
| TIM1 | 20 kHz (ARR 4199, 84 MHz) | Wheel motor PWM |
| TIM5 | 50 Hz (PSC 83, ARR 19999) | Servo PWM (CH1, CH2) + elevon software PWM (CH3/CH4 compare interrupts, no pin output) |
| TIM11 | 50 Hz (PSC 83, ARR 19999) | CH1 configured (PC12), not used by the code |

## Electrical notes for the circuit

- **Servo power:** run the servos (door, wings, 2 elevons) from a separate 5 V supply (BEC) that can handle their stall current. Share GND with the MCU. Do not power them from the 3.3 V rail or the ST-Link 5 V.
- **Servo signal:** the 3.3 V PWM from the MCU works for most servos. Add about 1 kohm in series with each signal line.
- **Wing servos:** the 2 wing servos share PA1, so wire both signal lines to it (each with its own series resistor). The code drives them together.
- **Wheel motor driver:** use a dual-PWM H-bridge (for example DRV8833 or similar) with PA8 on IN1 and PA9 on IN2. Power the motor from the battery rail and add bulk capacitance close to the driver. A reaction wheel draws high current when braking.
- **Buzzer (PA4):** a GPIO can only source about 25 mA. Use an NPN transistor or logic MOSFET if the buzzer needs more, with a flyback diode if it is a magnetic type. It must be an active buzzer.
- **LEDs (PA5, PB12-PB15):** add a series resistor to each (330 ohm to 1 kohm). PA5 is already the onboard LD2.
- **I2C (PB6/PB7):** one bus with 3 devices. Use 4.7 kohm pull-ups to 3.3 V, and check that the breakout boards do not already add their own (several in parallel lowers the resistance too far).
- **Voltage levels:** MPU6050, ICM-42688 and NEO-6M must all be on the 3.3 V bus. Check that your breakout boards do not level-shift to 5 V.
- **GPS:** connect the NEO-6M DDC pins (SDA/SCL), not only TX/RX. Give it a clear view of the sky.
- **CRSF receiver (PC6/PC7):** wire the receiver TX to PC7 (MCU RX) and the receiver RX to PC6 (MCU TX). Power it from 5 V.
- **MCU I/O:** all of the pins above are 3.3 V logic. PA13, PA14 and PB3 stay free for the SWD connector.

## Notes

- `TIM5_IRQHandler` (in `soft_pwm.c`) and `USART6_IRQHandler` (in `crsf.c`) are defined directly in the code. If you enable those interrupts in CubeMX, you will get duplicate definitions, so delete one of each pair.
