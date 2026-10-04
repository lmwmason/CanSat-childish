#include "sensors.h"
#include "../core/state.h"

bmp280 baro;
dht11 dht(dhtPin);
mpu6050 imu;

float bmpTemperature = 0;
float bmpPressure = 0;
float bmpAltitude = 0;
float bmpRelAltitude = 0;

uint8_t dhtHumidity = 0;
int8_t dhtTemperature = 0;

float yaw = 0, pitch = 0, roll = 0;
float accelX = 0, accelY = 0, accelZ = 0;
float gyroX = 0, gyroY = 0, gyroZ = 0;
float accelMag = 0;

bool baroFault = false, imuFault = false, dhtFault = false;
static uint8_t baroFails = 0, imuFails = 0, dhtFails = 0;

static void barometerReading(void)
{
  if (baro.update() == bmp280::OK)
  {
    bmpTemperature = baro.temperature();
    bmpPressure = baro.pressure();
    bmpAltitude = baro.altitude();
    bmpRelAltitude = baro.relativeAltitude();
    baroFails = 0;
  }
  else if (++baroFails >= baroFailLimit)
  {
    baroFails = baroFailLimit;
    baroFault = true;
  }
}

static void dhtReading(void)
{
  if (dht.read() == dht11::OK)
  {
    dhtHumidity = dht.humidity();
    dhtTemperature = dht.temperature();
    dhtFails = 0;
    dhtFault = false;
  }
  else if (++dhtFails >= dhtFailLimit)
  {
    dhtFails = dhtFailLimit;
    dhtFault = true;
  }
}

static void imuReading(void)
{
  const mpu6050::Status s = imu.update();

  if (s == mpu6050::OK) {
    float ypr[3];
    imu.ypr(ypr);
    yaw = ypr[0];
    pitch = ypr[1];
    roll = ypr[2];

    const mpu6050::Vec3 a = imu.accel();
    accelX = a.x;
    accelY = a.y;
    accelZ = a.z;
    accelMag = imu.accelMagnitude();

    const mpu6050::Vec3 g = imu.gyro();
    gyroX = g.x;
    gyroY = g.y;
    gyroZ = g.z;
    imuFails = 0;
  }
  else if (s == mpu6050::ERROR_I2C || s == mpu6050::ERROR_NOT_FOUND || s == mpu6050::ERROR_NOT_INIT)
  {
    if (++imuFails >= imuFailLimit)
    {
      imuFails = imuFailLimit;
      imuFault = true;
    }
  }
}

void sampleSensors(uint32_t now)
{
  static uint32_t lastBaro = 0, lastDht = 0, lastImu = 0, lastReinit = 0;

  if (now - lastImu >= imuPeriodMs)
  {
    lastImu = now;
    imuReading();
  }

  if (now - lastBaro >= baroPeriodMs)
  {
    lastBaro = now;
    barometerReading();
  }

  if (now - lastDht >= dhtPeriodMs)
  {
    lastDht = now;
    dhtReading();
  }

  if ((baroFault || imuFault) && now - lastReinit >= reinitPeriodMs)
  {
    lastReinit = now;
    if (baroFault && baro.begin() == bmp280::OK)
    {
      if (groundPressure > 0) baro.setGroundPressure(groundPressure);
      baroFault = false;
      baroFails = 0;
    }
    if (imuFault && state != STATE_DESCENT && imu.begin() == mpu6050::OK)
    {
      imuFault = false;
      imuFails = 0;
    }
  }
}
