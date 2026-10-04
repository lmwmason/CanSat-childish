#include "mission.h"
#include "../comm/serial_cmd.h"
#include "../core/state.h"
#include "../sensors/sensors.h"
#include "../storage/flight_log.h"
#include "../ui/indicator.h"

Servo paraServo;

static void startDescent(uint32_t now)
{
  paraServo.write(paraServoReleasedAngle);
  baro.resetFlight();
  flightStartMs = now;
  lastLogMs = now - logIntervalMs;
  state = STATE_DESCENT;
  beepStart(patDeploy, false);
  Serial.println(F("===== CANSAT DEPLOY SUCCESS ====="));
  Serial.println(F("===== PARACHUTE DEPLOY SUCCESS ====="));
}

static void enterLanded(uint32_t now)
{
  logWrite(makeRecord(STATE_LANDED, now));
  paraServo.detach();
  state = STATE_LANDED;
  beepStart(patBeacon, true);
  Serial.println(F("===== CANSAT LANDED ====="));
}

void handleArmed(uint32_t now)
{
  static uint32_t highSince = 0;
  static bool wasHigh = false;
  static uint32_t lastWarn = 0;

  if ((baroFault || imuFault) && beepIdle() && now - lastWarn >= 5000)
  {
    lastWarn = now;
    beepStart(patFault, false);
  }

  if (!digitalRead(deploySensPin))
  {
    wasHigh = false;
    return;
  }

  if (!wasHigh)
  {
    wasHigh = true;
    highSince = now;
  }

  if (now - highSince >= deployConfirmMs) startDescent(now);
}

void handleDescent(uint32_t now)
{
  if (now - lastLogMs >= logIntervalMs)
  {
    lastLogMs = now;
    if (logWrite(makeRecord(STATE_DESCENT, now))) yellowFlashUntil = now + 80;
  }

  const uint32_t elapsed = now - flightStartMs;
  const bool baroLanded = !baroFault && baro.isLanded(landedHoldMs, landedMaxHeightM);

  if ((elapsed >= minDescentMs && baroLanded) || elapsed >= descentTimeoutMs) enterLanded(now);
}

bool resumeFlight(void)
{
  if (logCount == 0) return false;

  Record last;
  EEPROM.get(recordAddr(logCount - 1), last);
  if (last.state != STATE_DESCENT) return false;

  for (uint8_t i = 0; i < 10; i++)
  {
    if (!digitalRead(deploySensPin)) return false;
    delay(10);
  }

  flightStartMs = millis() - (uint32_t)last.t * 100UL;
  return true;
}

void warmUp(uint32_t ms)
{
  const uint32_t start = millis();
  while (millis() - start < ms)
  {
    const uint32_t now = millis();
    digitalWrite(yellowLed, now % 400 < 200);
    beepUpdate(now);
  }
  digitalWrite(yellowLed, LOW);
}
