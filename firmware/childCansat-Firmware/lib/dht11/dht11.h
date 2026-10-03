#ifndef CHILDCANSAT_FIRMWARE_DHT11_H
#define CHILDCANSAT_FIRMWARE_DHT11_H

#include <Arduino.h>

class dht11
{
public:
    enum Status : uint8_t
    {
        OK = 0,
        ERROR_CHECKSUM,
        ERROR_TIMEOUT
    };

    explicit dht11(uint8_t pin);

    // Configure the pin. Wait >= 1 s after power-up before the first read().
    void begin();

    // Blocking read (~25 ms). Do not call faster than once per second.
    // Interrupts are disabled for ~4 ms during the bit transfer.
    Status read();

    // Last successfully read values.
    uint8_t humidity() const { return _humidity; }       // %RH
    int8_t temperature() const { return _temperature; }  // degrees C

private:
    // Busy-wait while pin == level. Returns elapsed us, or 0 on timeout.
    uint16_t waitWhile(uint8_t level, uint16_t timeoutUs) const;

    uint8_t _pin;
    uint8_t _humidity;
    int8_t _temperature;
};

#endif