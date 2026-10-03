#ifndef CANSAT_HAL_H
#define CANSAT_HAL_H

/*
 * Hardware abstraction the control core depends on. Nothing in core/
 * includes an STM32 or POSIX header directly - only this struct of
 * function pointers. sim/ implements it in software; a real firmware
 * port later implements the exact same struct on top of STM32 HAL
 * (I2C for BNO055/BMP280, UART for GPS/NEO-M8N and the Pi link, SPI
 * for the SX1262/RA-01SH LoRa module, PWM+GPIO for the DRV8874
 * channels, GPIO for the safety_io FET and deploy triggers).
 */

#include <stdint.h>
#include <stdbool.h>
#include "cansat_types.h"

typedef struct {
    bool (*read_imu)(void *ctx, imu_sample_t *out);
    bool (*read_baro)(void *ctx, baro_sample_t *out);
    bool (*read_gps)(void *ctx, gps_sample_t *out);

    /* Non-blocking: returns number of bytes copied into buf (0 if none). */
    int (*pi_uart_read)(void *ctx, uint8_t *buf, int max_len);

    /* channel 0/1 map to the two DRV8874 outputs; value_norm in [-1, 1]. */
    void (*set_actuator)(void *ctx, int channel, float value_norm);

    /* Master safety cutoff (the safety_io NMOS FET). */
    void (*set_motor_power)(void *ctx, bool enable);

    /* One-shot pyro/servo/pusher fire for deploy channel `channel`. */
    void (*deploy_fire)(void *ctx, int channel);

    void (*lora_send)(void *ctx, const uint8_t *buf, int len);

    uint32_t (*millis)(void *ctx);

    void *ctx;
} cansat_hal_t;

#endif /* CANSAT_HAL_H */
