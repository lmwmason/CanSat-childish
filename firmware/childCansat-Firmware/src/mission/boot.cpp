#include <Wire.h>
#include "boot.h"
#include "mission.h"
#include "../comm/serial_cmd.h"
#include "../core/state.h"
#include "../sensors/sensors.h"
#include "../storage/flight_log.h"
#include "../ui/indicator.h"

void bootSystem(void)
{
  Serial.begin(115200);
  pinMode(deploySensPin, INPUT_PULLUP);
  pinMode(buzzerForFinding, OUTPUT);
  pinMode(yellowLed, OUTPUT);
  pinMode(redLed, OUTPUT);
  pinMode(blueLed, OUTPUT);
  setLeds(true, false, false);

  logScan();
  const bool resumed = resumeFlight();

  paraServo.attach(paraServoPin);
  paraServo.write(resumed ? paraServoReleasedAngle : paraServoLockedAngle);

  dht.begin();
  baroFault = (baro.begin() != bmp280::OK);
  imuFault = (imu.begin() != mpu6050::OK);
#ifdef WIRE_HAS_TIMEOUT
  Wire.setWireTimeout(25000, true);
#endif

  beepStart(patStart, false);
  if (!resumed) warmUp(9000);

  if (!baroFault)
  {
    if (resumed) EEPROM.get(eepromGroundAddr, groundPressure);
    if (!(groundPressure > 30000.0f && groundPressure < 110000.0f))
    {
      baroFault = (baro.setGroundReference() != bmp280::OK);
      groundPressure = baro.groundPressure();
      if (!baroFault) EEPROM.put(eepromGroundAddr, groundPressure);
    }
    else
    {
      baro.setGroundPressure(groundPressure);
    }
  }

  if (resumed)
  {
    state = STATE_DESCENT;
    lastLogMs = millis();
    Serial.println(F("===== RESUMED IN DESCENT ====="));
  }
  else
  {
    state = STATE_ARMED;
    beepStart((baroFault || imuFault) ? patFault : patReady, false);
  }

  Serial.println(F("===== END SENSOR SETUP ====="));
  printStatus();
}
