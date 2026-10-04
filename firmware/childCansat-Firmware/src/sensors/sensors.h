#pragma once

#include "../config/config.h"
#include "bmp280.h"
#include "dht11.h"
#include "mpu6050.h"

extern bmp280 baro;
extern dht11 dht;
extern mpu6050 imu;

extern float bmpTemperature;
extern float bmpPressure;
extern float bmpAltitude;
extern float bmpRelAltitude;

extern uint8_t dhtHumidity;
extern int8_t dhtTemperature;

extern float yaw, pitch, roll;
extern float accelX, accelY, accelZ;
extern float gyroX, gyroY, gyroZ;
extern float accelMag;

extern bool baroFault, imuFault, dhtFault;

void sampleSensors(uint32_t now);
