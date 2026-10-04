#pragma once

#include <Servo.h>
#include "../config/config.h"

extern Servo paraServo;

void handleArmed(uint32_t now);
void handleDescent(uint32_t now);
bool resumeFlight(void);
void warmUp(uint32_t ms);
