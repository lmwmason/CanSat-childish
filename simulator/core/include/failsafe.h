#ifndef FAILSAFE_H
#define FAILSAFE_H

#include "attitude.h"

/*
 * Autonomous stabilization law used whenever there is no (or no
 * trustworthy) Pi guidance: nulls roll/pitch using only onboard
 * IMU/baro so the vehicle keeps a stable, non-tumbling descent by
 * itself. If the attitude estimator has a sensor fault, output is
 * forced to zero rather than acting on bad data.
 */
typedef struct {
    float kp; /* normalized actuator output per degree of attitude error */
} failsafe_controller_t;

void failsafe_init(failsafe_controller_t *f);
void failsafe_compute(const failsafe_controller_t *f, const attitude_estimator_t *att, float out[2]);

#endif /* FAILSAFE_H */
