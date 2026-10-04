#include "indicator.h"
#include "../core/state.h"
#include "../sensors/sensors.h"
#include "../storage/flight_log.h"

const uint16_t patStart[] = {60, 0};
const uint16_t patReady[] = {90, 90, 90, 0};
const uint16_t patFault[] = {400, 150, 400, 150, 400, 0};
const uint16_t patDeploy[] = {700, 0};
const uint16_t patBeacon[] = {150, 150, 150, 150, 150, 2000, 0};

static const uint16_t* beepPat = nullptr;
static bool beepLoop = false;
static uint8_t beepIdx = 0;
static uint32_t beepNext = 0;

bool beepIdle(void)
{
  return beepPat == nullptr;
}

void beepStart(const uint16_t* pat, bool loop)
{
  noTone(buzzerForFinding);
  beepPat = pat;
  beepLoop = loop;
  beepIdx = 0;
  beepNext = millis();
}

void beepUpdate(uint32_t now)
{
  if (beepPat == nullptr || (int32_t)(now - beepNext) < 0) return;

  uint16_t d = beepPat[beepIdx];
  if (d == 0)
  {
    noTone(buzzerForFinding);
    if (!beepLoop)
    {
      beepPat = nullptr;
      return;
    }
    beepIdx = 0;
    d = beepPat[0];
  }

  if (beepIdx % 2 == 0) tone(buzzerForFinding, beepFreqHz);
  else noTone(buzzerForFinding);
  beepNext = now + d;
  beepIdx++;
}

void setLeds(bool y, bool r, bool b)
{
  digitalWrite(yellowLed, y);
  digitalWrite(redLed, r);
  digitalWrite(blueLed, b);
}

void updateLeds(uint32_t now)
{
  const bool fault = baroFault || imuFault;
  const bool full = logCount >= maxRecords;

  switch (state)
  {
    case STATE_ARMED:
      setLeds(full ? (now % 200 < 100) : (logCount > 0), fault, now % 1000 < 60);
      break;
    case STATE_DESCENT:
      setLeds(full ? (now % 200 < 100) : ((int32_t)(yellowFlashUntil - now) > 0), fault, true);
      break;
    case STATE_LANDED:
      setLeds(now % 900 < 300, (now % 900 >= 300) && (now % 900 < 600), now % 900 >= 600);
      break;
    default:
      break;
  }
}
