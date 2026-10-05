#ifndef SOFT_PWM_H
#define SOFT_PWM_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include "stm32f4xx_hal.h"

/* Software servo PWM on PC8 (channel 0) and PC9 (channel 1).
 * Uses the TIM5 interrupts: update event (every 20 ms) sets both pins high,
 * compare CC3 / CC4 match sets each pin low after its pulse width in us.
 * TIM5 CH3/CH4 are never routed to pins, so this does not disturb TIM5 CH1/CH2 PWM.
 * TIM5_IRQHandler is defined here; if you enable the TIM5 global interrupt in
 * CubeMX, remove it from this file (or merge the two). */
#define SOFT_PWM_CHANNELS 2

void soft_pwm_init(TIM_HandleTypeDef *htim);
/* Pulse width 500..2500 us, channel 0 = PC8, 1 = PC9 */
void soft_pwm_set_us(uint8_t channel, uint16_t us);

#ifdef __cplusplus
}
#endif

#endif /* SOFT_PWM_H */
