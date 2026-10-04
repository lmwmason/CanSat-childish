#pragma once

#include "../config/config.h"

extern const uint16_t patStart[];
extern const uint16_t patReady[];
extern const uint16_t patFault[];
extern const uint16_t patDeploy[];
extern const uint16_t patBeacon[];

bool beepIdle(void);
void beepStart(const uint16_t* pat, bool loop);
void beepUpdate(uint32_t now);
void setLeds(bool y, bool r, bool b);
void updateLeds(uint32_t now);
