#include "dht11.h"

dht11::dht11(uint8_t pin) : _pin(pin), _humidity(0), _temperature(0)
{
}

void dht11::begin()
{
    pinMode(_pin, INPUT_PULLUP);
}

uint16_t dht11::waitWhile(uint8_t level, uint16_t timeoutUs) const
{
    const uint32_t start = micros();
    while (digitalRead(_pin) == level)
    {
        if (micros() - start > timeoutUs)
            return 0;
    }
    const uint16_t elapsed = (uint16_t)(micros() - start);
    return elapsed ? elapsed : 1;
}

dht11::Status dht11::read()
{
    uint8_t data[5] = {0, 0, 0, 0, 0};

    // Start signal: pull low >= 18 ms, then release and let the pull-up raise the line.
    pinMode(_pin, OUTPUT);
    digitalWrite(_pin, LOW);
    delay(20);
    digitalWrite(_pin, HIGH);
    delayMicroseconds(30);
    pinMode(_pin, INPUT_PULLUP);

    noInterrupts();

    // Sensor response: ~80 us low, ~80 us high.
    bool ok = waitWhile(HIGH, 100) != 0   // wait for sensor to pull low
              && waitWhile(LOW, 120) != 0  // response low
              && waitWhile(HIGH, 120) != 0; // response high

    // 40 data bits: each is ~50 us low, then high for ~26 us (0) or ~70 us (1).
    for (uint8_t i = 0; ok && i < 40; i++)
    {
        if (waitWhile(LOW, 100) == 0)
        {
            ok = false;
            break;
        }
        const uint16_t high = waitWhile(HIGH, 120);
        if (high == 0)
        {
            ok = false;
            break;
        }
        data[i / 8] <<= 1;
        if (high > 40)
            data[i / 8] |= 1;
    }

    interrupts();

    if (!ok)
        return ERROR_TIMEOUT;

    if ((uint8_t)(data[0] + data[1] + data[2] + data[3]) != data[4])
        return ERROR_CHECKSUM;

    _humidity = data[0];
    // DHT11 temperature: integer in data[2]; bit 7 of data[3] marks negative on newer units.
    _temperature = (int8_t)data[2];
    if (data[3] & 0x80)
        _temperature = -_temperature;

    return OK;
}
