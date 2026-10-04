#include <Arduino.h>
#include "comm/serial_cmd.h"
#include "core/state.h"
#include "mission/boot.h"
#include "mission/mission.h"
#include "sensors/sensors.h"
#include "ui/indicator.h"

void setup()
{
  bootSystem();
}

void loop()
{
  const uint32_t now = millis();

  if (state != STATE_LANDED) sampleSensors(now);

  switch (state)
  {
    case STATE_ARMED:   handleArmed(now);   break;
    case STATE_DESCENT: handleDescent(now); break;
    default: break;
  }

  updateLeds(now);
  beepUpdate(now);
  handleSerial();
}
