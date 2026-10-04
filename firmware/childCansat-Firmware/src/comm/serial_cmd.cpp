#include <Arduino.h>
#include "serial_cmd.h"
#include "../core/state.h"
#include "../sensors/sensors.h"
#include "../storage/flight_log.h"

void dumpLog(void)
{
  Serial.println(F("# childCansat flight log"));
  Serial.print(F("# records="));
  Serial.print(logCount);
  Serial.print('/');
  Serial.print(maxRecords);
  Serial.print(F(" ground_Pa="));
  Serial.println(groundPressure, 0);
  Serial.println(F("idx,state,t_s,rel_alt_m,pressure_hPa,temp_C,humidity_pct,accel_g"));

  for (uint16_t i = 0; i < logCount; i++)
  {
    Record r;
    EEPROM.get(recordAddr(i), r);
    Serial.print(i);
    Serial.print(',');
    Serial.print(r.state == STATE_LANDED ? F("LANDED") : F("DESCENT"));
    Serial.print(',');
    Serial.print(r.t / 10.0f, 1);
    Serial.print(',');
    Serial.print(r.alt / 10.0f, 1);
    Serial.print(',');
    Serial.print(r.pressure / 10.0f, 1);
    Serial.print(',');
    Serial.print(r.temp);
    Serial.print(',');
    Serial.print(r.hum);
    Serial.print(',');
    Serial.println(r.accel / 10.0f, 1);
  }
  Serial.println(F("# end"));
}

void printStatus(void)
{
  static const char* const names[] = {"BOOT", "ARMED", "DESCENT", "LANDED"};
  Serial.print(F("state="));
  Serial.print(names[state]);
  Serial.print(F(" log="));
  Serial.print(logCount);
  Serial.print('/');
  Serial.print(maxRecords);
  Serial.print(F(" fault(baro,imu,dht)="));
  Serial.print(baroFault);
  Serial.print(imuFault);
  Serial.println(dhtFault);
}

// serial (115200) and send:  d = dump CSV,  e = erase log,  s = status
void handleSerial(void)
{
  while (Serial.available())
  {
    const char c = Serial.read();
    if (c == 's') printStatus();
    else if (state == STATE_DESCENT) Serial.println(F("busy: descending"));
    else if (c == 'd') dumpLog();
    else if (c == 'e')
    {
      logErase();
      Serial.println(F("log erased"));
    }
  }
}
