#ifndef WHEEL_MOTOR_H
#define WHEEL_MOTOR_H

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32f4xx_hal.h"

/* Reaction wheel motor on TIM1 (20 kHz PWM), dual-PWM H-bridge:
 * forward = PWM on WHEEL_CH_FWD, reverse = PWM on WHEEL_CH_REV.
 * Change the channels here if the driver is wired differently. */
#define WHEEL_CH_FWD  TIM_CHANNEL_1   /* PA8 */
#define WHEEL_CH_REV  TIM_CHANNEL_2   /* PA9 */

void wheel_motor_init(TIM_HandleTypeDef *htim);
/* command -1..1, matches RwMotorFn */
void wheel_motor_set(float command);

#ifdef __cplusplus
}
#endif

#endif /* WHEEL_MOTOR_H */
