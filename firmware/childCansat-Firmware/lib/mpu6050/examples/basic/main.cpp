// Example: copy into src/main.cpp. Wiring: SDA=A4, SCL=A5, VCC=3.3V/5V (GY-521), GND.
#include <Arduino.h>
#include "mpu6050.h"

mpu6050 imu;

void setup() {
  Serial.begin(115200);

  if (imu.begin() != mpu6050::OK) {
    Serial.println(F("MPU6050 init failed (check wiring)"));
    while (true) {}
  }

  Serial.println(F("Keep the board still and flat, calibrating..."));
  if (imu.calibrate() != mpu6050::OK) {
    Serial.println(F("Calibration failed (moving or not flat), using defaults"));
  }

  imu.setFilter(0.4f);        // 1.0 = no smoothing
  imu.setGyroDeadband(0.1f);  // deg/s
}

void loop() {
  if (imu.update() != mpu6050::OK) return;  // no new packet yet

  float ypr[3];
  imu.ypr(ypr);
  const mpu6050::Vec3 up = imu.worldAccel();

  Serial.print(F("yaw "));   Serial.print(ypr[0], 1);
  Serial.print(F(" pitch ")); Serial.print(ypr[1], 1);
  Serial.print(F(" roll "));  Serial.print(ypr[2], 1);
  Serial.print(F(" | |a| ")); Serial.print(imu.accelMagnitude(), 2);
  Serial.print(F(" g, world z ")); Serial.print(up.z, 2);
  Serial.println(imu.freeFall() ? F(" FREEFALL") : F(""));
}
