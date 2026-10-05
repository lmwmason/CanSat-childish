#include "icm42688.h"

#define REG_DEVICE_CONFIG 0x11
#define REG_ACCEL_DATA_X1 0x1F
#define REG_PWR_MGMT0     0x4E
#define REG_GYRO_CONFIG0  0x4F
#define REG_ACCEL_CONFIG0 0x50
#define REG_WHO_AM_I      0x75

#define WHO_AM_I_ICM42688 0x47

#define ACCEL_LSB_PER_G   2048.0f   /* +-16 g */
#define GYRO_LSB_PER_DPS  16.4f     /* +-2000 dps */
#define I2C_TIMEOUT_MS    5

static HAL_StatusTypeDef wr(Icm42688 *d, uint8_t reg, uint8_t val)
{
    return HAL_I2C_Mem_Write(d->hi2c, d->addr, reg, I2C_MEMADD_SIZE_8BIT, &val, 1, I2C_TIMEOUT_MS);
}

HAL_StatusTypeDef icm42688_init(Icm42688 *d, I2C_HandleTypeDef *hi2c, uint8_t addr7)
{
    d->hi2c = hi2c;
    d->addr = (uint8_t)(addr7 << 1);

    if (wr(d, REG_DEVICE_CONFIG, 0x01) != HAL_OK) return HAL_ERROR;  /* soft reset */
    HAL_Delay(5);

    uint8_t who = 0;
    if (HAL_I2C_Mem_Read(hi2c, d->addr, REG_WHO_AM_I, I2C_MEMADD_SIZE_8BIT, &who, 1, I2C_TIMEOUT_MS) != HAL_OK)
        return HAL_ERROR;
    if (who != WHO_AM_I_ICM42688) return HAL_ERROR;

    if (wr(d, REG_GYRO_CONFIG0, 0x06) != HAL_OK) return HAL_ERROR;   /* 2000 dps, 1 kHz */
    if (wr(d, REG_ACCEL_CONFIG0, 0x06) != HAL_OK) return HAL_ERROR;  /* 16 g, 1 kHz */
    if (wr(d, REG_PWR_MGMT0, 0x0F) != HAL_OK) return HAL_ERROR;      /* accel + gyro low-noise */
    HAL_Delay(50);                                                   /* gyro start-up time */
    return HAL_OK;
}

HAL_StatusTypeDef icm42688_read(Icm42688 *d, ImuSample *out)
{
    uint8_t b[12];
    if (HAL_I2C_Mem_Read(d->hi2c, d->addr, REG_ACCEL_DATA_X1, I2C_MEMADD_SIZE_8BIT, b, 12, I2C_TIMEOUT_MS) != HAL_OK)
        return HAL_ERROR;

    int16_t ax = (int16_t)((b[0] << 8) | b[1]);
    int16_t ay = (int16_t)((b[2] << 8) | b[3]);
    int16_t az = (int16_t)((b[4] << 8) | b[5]);
    int16_t gx = (int16_t)((b[6] << 8) | b[7]);
    int16_t gy = (int16_t)((b[8] << 8) | b[9]);
    int16_t gz = (int16_t)((b[10] << 8) | b[11]);

    out->ax = ax / ACCEL_LSB_PER_G * IMU_GRAVITY;
    out->ay = ay / ACCEL_LSB_PER_G * IMU_GRAVITY;
    out->az = az / ACCEL_LSB_PER_G * IMU_GRAVITY;
    out->gx = gx / GYRO_LSB_PER_DPS;
    out->gy = gy / GYRO_LSB_PER_DPS;
    out->gz = gz / GYRO_LSB_PER_DPS;
    return HAL_OK;
}
