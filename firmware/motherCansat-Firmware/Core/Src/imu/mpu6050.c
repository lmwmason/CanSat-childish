#include "mpu6050.h"

#define REG_SMPLRT_DIV   0x19
#define REG_CONFIG       0x1A
#define REG_GYRO_CONFIG  0x1B
#define REG_ACCEL_CONFIG 0x1C
#define REG_ACCEL_XOUT_H 0x3B
#define REG_PWR_MGMT_1   0x6B
#define REG_WHO_AM_I     0x75

#define ACCEL_LSB_PER_G   2048.0f   /* +-16 g */
#define GYRO_LSB_PER_DPS  16.4f     /* +-2000 dps */
#define I2C_TIMEOUT_MS    5

static HAL_StatusTypeDef wr(Mpu6050 *d, uint8_t reg, uint8_t val)
{
    return HAL_I2C_Mem_Write(d->hi2c, d->addr, reg, I2C_MEMADD_SIZE_8BIT, &val, 1, I2C_TIMEOUT_MS);
}

HAL_StatusTypeDef mpu6050_init(Mpu6050 *d, I2C_HandleTypeDef *hi2c, uint8_t addr7)
{
    d->hi2c = hi2c;
    d->addr = (uint8_t)(addr7 << 1);

    uint8_t who = 0;
    if (HAL_I2C_Mem_Read(hi2c, d->addr, REG_WHO_AM_I, I2C_MEMADD_SIZE_8BIT, &who, 1, I2C_TIMEOUT_MS) != HAL_OK)
        return HAL_ERROR;
    if ((who & 0x7E) != 0x68) return HAL_ERROR;

    if (wr(d, REG_PWR_MGMT_1, 0x80) != HAL_OK) return HAL_ERROR;  /* reset */
    HAL_Delay(100);
    if (wr(d, REG_PWR_MGMT_1, 0x01) != HAL_OK) return HAL_ERROR;  /* wake, PLL gyro X */
    HAL_Delay(10);
    if (wr(d, REG_SMPLRT_DIV, 4) != HAL_OK) return HAL_ERROR;     /* 1 kHz / 5 = 200 Hz */
    if (wr(d, REG_CONFIG, 3) != HAL_OK) return HAL_ERROR;         /* DLPF 44 Hz */
    if (wr(d, REG_GYRO_CONFIG, 0x18) != HAL_OK) return HAL_ERROR;
    if (wr(d, REG_ACCEL_CONFIG, 0x18) != HAL_OK) return HAL_ERROR;
    return HAL_OK;
}

HAL_StatusTypeDef mpu6050_read(Mpu6050 *d, ImuSample *out)
{
    uint8_t b[14];
    if (HAL_I2C_Mem_Read(d->hi2c, d->addr, REG_ACCEL_XOUT_H, I2C_MEMADD_SIZE_8BIT, b, 14, I2C_TIMEOUT_MS) != HAL_OK)
        return HAL_ERROR;

    int16_t ax = (int16_t)((b[0] << 8) | b[1]);
    int16_t ay = (int16_t)((b[2] << 8) | b[3]);
    int16_t az = (int16_t)((b[4] << 8) | b[5]);
    /* b[6..7] = temperature */
    int16_t gx = (int16_t)((b[8] << 8) | b[9]);
    int16_t gy = (int16_t)((b[10] << 8) | b[11]);
    int16_t gz = (int16_t)((b[12] << 8) | b[13]);

    out->ax = ax / ACCEL_LSB_PER_G * IMU_GRAVITY;
    out->ay = ay / ACCEL_LSB_PER_G * IMU_GRAVITY;
    out->az = az / ACCEL_LSB_PER_G * IMU_GRAVITY;
    out->gx = gx / GYRO_LSB_PER_DPS;
    out->gy = gy / GYRO_LSB_PER_DPS;
    out->gz = gz / GYRO_LSB_PER_DPS;
    return HAL_OK;
}
