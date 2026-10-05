#ifndef MPU6050_H
#define MPU6050_H

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32f4xx_hal.h"
#include "imu_types.h"

typedef struct {
    I2C_HandleTypeDef *hi2c;
    uint8_t addr;           /* 8-bit (7-bit address << 1) */
} Mpu6050;

/* addr7: 0x68 (AD0 low) or 0x69 (AD0 high). Range +-16 g, +-2000 dps, 44 Hz DLPF. */
HAL_StatusTypeDef mpu6050_init(Mpu6050 *dev, I2C_HandleTypeDef *hi2c, uint8_t addr7);
HAL_StatusTypeDef mpu6050_read(Mpu6050 *dev, ImuSample *out);

#ifdef __cplusplus
}
#endif

#endif /* MPU6050_H */
