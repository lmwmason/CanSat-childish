// Three TA servos: boot at 0 degrees, command ID 71 sets 0 or 180.
#include <Arduino.h>
#include <Servo.h>

#if defined(SERVO_TEST_TA)
// PCB TA0/1/2 follow ADC channel 0/1/2: PF0/1/2.
// The CanSat variant reverses the Arduino A labels: A7/A6/A5.
static const uint8_t testPins[3] = {csA0, csA1, csA2};
#elif defined(SERVO_TEST_AT)
// Board labels AT0/1/2 map to PF0/1/2, Arduino A7/A6/A5.
static const uint8_t testPins[3] = {A7, A6, A5};
#elif defined(SERVO_TEST_DT)
// Board labels DT0/1/2 map to PA7/6/5, Arduino D7/D6/D5.
static const uint8_t testPins[3] = {D7, D6, D5};
#else
#error Select SERVO_TEST_AT or SERVO_TEST_DT explicitly
#endif

static const uint8_t testActiveChannels = 3; // TA0, TA1, TA2 together
static Servo testServos[3];
static int testAngle = 0;

static unsigned long testUpdated;
static bool sweepStarted = false;

void servoSweepSetup()
{
    // Restore the CanSat Arduino core Timer0 /64 timebase after legacy init.
    TCCR0 = _BV(CS02);
    // PF4..PF7 may be owned by JTAG. Disable it with two consecutive writes.
    const uint8_t savedSreg = SREG;
    cli();
    MCUCSR |= _BV(JTD);
    MCUCSR |= _BV(JTD);
    SREG = savedSreg;
    for (uint8_t i = testActiveChannels; i < 3; ++i) {
        pinMode(testPins[i], INPUT); // inactive, no pull-up or PWM
        digitalWrite(testPins[i], LOW);
    }
    for (uint8_t i = 0; i < testActiveChannels; ++i) {
        testServos[i].write(testAngle);
        testServos[i].attach(testPins[i], 1000, 2000);
        testServos[i].write(testAngle);
    }
    testUpdated = millis();
    sweepStarted = true;
}

// Only checksum-validated ID 71 values 0/180 are routed here by csGs.c.
void servoTrigger(uint8_t angle)
{
    if (!sweepStarted || (angle != 0 && angle != 180)) return;
    testAngle = angle;
    for (uint8_t i = 0; i < testActiveChannels; ++i) testServos[i].write(testAngle);
}

void servoSweepTick() {} // Compatibility hook: no autonomous movement.
