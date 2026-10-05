#ifndef WINGS_H
#define WINGS_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include "stm32f4xx_hal.h"

/* Wing ejection servos on TIM5 (1 MHz tick, 20 ms period): CCR = pulse in us.
 * Both servos are driven from ONE channel (wired in parallel to the same signal),
 * because TIM5 CH2 is the only free servo-capable output. If you give each servo
 * its own timer channel, split WING_SERVO_CH into two and set both in wings.c. */
#define WING_SERVO_CH        TIM_CHANNEL_2   /* PA1 */
#define WING_LOCKED_PULSE_US  1000u
#define WING_EJECT_PULSE_US   2000u

void    wings_init(TIM_HandleTypeDef *htim);   /* starts PWM, wings locked */
void    wings_eject(void);
void    wings_lock(void);
uint8_t wings_are_ejected(void);

#ifdef __cplusplus
}
#endif

#endif /* WINGS_H */
