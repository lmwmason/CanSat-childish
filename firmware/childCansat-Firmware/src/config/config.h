#pragma once

#include <Arduino.h>

const int dhtPin = 2;
const int deploySensPin = 3;
const int paraServoPin = 4;
const int buzzerForFinding = 5;
const int yellowLed = 6;
const int redLed = 7;
const int blueLed = 8;

const uint32_t deployConfirmMs = 1500;

const uint32_t imuPeriodMs = 10;
const uint32_t baroPeriodMs = 50;
const uint32_t dhtPeriodMs = 1000;

const uint8_t imuFailLimit = 50;
const uint8_t baroFailLimit = 20;
const uint8_t dhtFailLimit = 10;
const uint32_t reinitPeriodMs = 3000;

const int paraServoLockedAngle = 0;
const int paraServoReleasedAngle = 90;

const uint32_t logIntervalMs = 1000;
const uint32_t minDescentMs = 10000;
const uint32_t landedHoldMs = 5000;
const float landedMaxHeightM = 50.0f;
const uint32_t descentTimeoutMs = 600000UL;

const uint16_t beepFreqHz = 2700;

enum State : uint8_t { STATE_BOOT = 0, STATE_ARMED, STATE_DESCENT, STATE_LANDED };
