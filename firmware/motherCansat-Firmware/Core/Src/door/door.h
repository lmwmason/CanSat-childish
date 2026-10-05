#ifndef DOOR_H
#define DOOR_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include "stm32f4xx_hal.h"

/* Door servo on TIM5 (1 MHz tick, 20 ms period): CCR = pulse width in us. */
#define DOOR_SERVO_CH        TIM_CHANNEL_1   /* PA0 */
#define DOOR_CLOSED_PULSE_US 1000u
#define DOOR_OPEN_PULSE_US   2000u

void    door_init(TIM_HandleTypeDef *htim);   /* starts PWM, door closed */
void    door_open(void);
void    door_close(void);
uint8_t door_is_open(void);

#ifdef __cplusplus
}
#endif

#endif /* DOOR_H */
