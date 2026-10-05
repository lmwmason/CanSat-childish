#ifndef ICM42688_H
#define ICM42688_H

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32f4xx_hal.h"
#include "imu_types.h"

typedef struct {
    I2C_HandleTypeDef *hi2c;
    uint8_t addr;           /* 8-bit (7-bit address << 1) */
} Icm42688;

/* addr7: 0x68 (AD0 low) or 0x69 (AD0 high). Range +-16 g, +-2000 dps, 1 kHz ODR. */
HAL_StatusTypeDef icm42688_init(Icm42688 *dev, I2C_HandleTypeDef *hi2c, uint8_t addr7);
HAL_StatusTypeDef icm42688_read(Icm42688 *dev, ImuSample *out);

#ifdef __cplusplus
}
#endif

#endif /* ICM42688_H */
