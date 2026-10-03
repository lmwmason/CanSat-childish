#include "failsafe.h"

void failsafe_init(failsafe_controller_t *f) {
    f->kp = 0.03f; /* normalized actuator output per degree of attitude error */
}

static float clampf(float v, float lo, float hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

void failsafe_compute(const failsafe_controller_t *f, const attitude_estimator_t *att, float out[2]) {
    if (att->fault || !att->initialized) {
        out[0] = 0.0f;
        out[1] = 0.0f;
        return;
    }
    out[0] = clampf(-f->kp * att->pitch_deg, -1.0f, 1.0f);
    out[1] = clampf(-f->kp * att->roll_deg, -1.0f, 1.0f);
}
