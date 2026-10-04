#include "state.h"

State state = STATE_BOOT;
float groundPressure = 0;
uint32_t flightStartMs = 0;
uint32_t lastLogMs = 0;
uint32_t yellowFlashUntil = 0;
