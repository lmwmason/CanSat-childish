#include "flight_log.h"
#include "../core/state.h"
#include "../sensors/sensors.h"

uint16_t logCount = 0;

uint16_t recordAddr(uint16_t i)
{
  return eepromLogStart + i * sizeof(Record);
}

void logScan(void)
{
  logCount = 0;
  while (logCount < maxRecords && EEPROM.read(recordAddr(logCount)) != 0xFF) logCount++;
}

bool logWrite(const Record& r)
{
  if (logCount >= maxRecords) return false;

  const uint16_t addr = recordAddr(logCount);
  const uint8_t* p = (const uint8_t*)&r;
  for (uint8_t i = 1; i < sizeof(Record); i++) EEPROM.update(addr + i, p[i]);
  EEPROM.update(addr, p[0]);
  logCount++;
  return true;
}

void logErase(void)
{
  for (uint16_t i = 0; i < maxRecords; i++) EEPROM.update(recordAddr(i), 0xFF);
  logCount = 0;
}

Record makeRecord(State s, uint32_t now)
{
  Record r;
  r.state = s;
  r.t = (uint16_t)min((now - flightStartMs) / 100UL, 65535UL);
  r.alt = (int16_t)constrain(lroundf(bmpRelAltitude * 10.0f), -32768L, 32767L);
  r.pressure = (uint16_t)constrain(lroundf(bmpPressure / 10.0f), 0L, 65535L);
  r.temp = (int8_t)constrain(lroundf(bmpTemperature), -128L, 127L);
  r.hum = dhtHumidity;
  r.accel = (uint8_t)constrain(lroundf(accelMag * 10.0f), 0L, 255L);
  return r;
}
