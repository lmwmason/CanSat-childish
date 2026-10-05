#ifndef IMU_H
#define IMU_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include "stm32f4xx_hal.h"
#include "imu_types.h"
#include "mpu6050.h"
#include "icm42688.h"

/* Both sensors share I2C1, so they need different addresses:
 * MPU6050 AD0 low (0x68), ICM-42688 AD0 high (0x69). Change here if wired otherwise. */
#define IMU_MPU_ADDR       0x68
#define IMU_ICM_ADDR       0x69

#define IMU_ICM_WEIGHT     0.7f      /* ICM-42688 is the quieter sensor, so it counts more */
#define IMU_RETRY_MS       1000u     /* re-init a failed sensor this often */
#define IMU_DISAGREE_MS2   1.5f      /* accel magnitudes differing more than this -> flag */

typedef struct {
    Mpu6050  mpu;
    Icm42688 icm;
    I2C_HandleTypeDef *hi2c;

    uint8_t  mpuOk, icmOk;
    uint32_t mpuRetryAt, icmRetryAt;
    ImuSample mpuBias, icmBias;     /* gyro bias, set by imu_calibrate_gyro() */

    ImuSample fused;                /* accel m/s^2, gyro deg/s (bias removed) */
    float     accelMag;             /* |fused accel| in m/s^2 */
    float     yawDeg;               /* gyro-integrated yaw, -180..180, drifts (no magnetometer) */
    uint8_t   disagree;             /* 1 if the two accelerometers disagree */
    uint32_t  lastTickMs;
} Imu;

/* Initializes both sensors. Returns number of working sensors (0..2). */
uint8_t imu_init(Imu *imu, I2C_HandleTypeDef *hi2c);

/* Average gyro while the board is still, to remove bias. Blocks for durationMs. */
void    imu_calibrate_gyro(Imu *imu, uint32_t durationMs);

/* Read both sensors and fuse. Returns 1 if at least one sensor gave data. */
uint8_t imu_update(Imu *imu, uint32_t nowMs);

void    imu_reset_yaw(Imu *imu, float yawDeg);
uint8_t imu_sensor_count(const Imu *imu);

#ifdef __cplusplus
}
#endif

#endif /* IMU_H */
