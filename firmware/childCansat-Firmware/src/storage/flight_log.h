#pragma once

#include <EEPROM.h>
#include "../config/config.h"

struct __attribute__((packed)) Record
{
  uint8_t state;
  uint16_t t;
  int16_t alt;
  uint16_t pressure;
  int8_t temp;
  uint8_t hum;
  uint8_t accel;
};

const uint16_t eepromGroundAddr = 0;
const uint16_t eepromLogStart = 4;
const uint16_t maxRecords = (E2END + 1 - eepromLogStart) / sizeof(Record);

extern uint16_t logCount;

uint16_t recordAddr(uint16_t i);
void logScan(void);
bool logWrite(const Record& r);
void logErase(void);
Record makeRecord(State s, uint32_t now);
