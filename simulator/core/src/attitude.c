#include "attitude.h"
#include <math.h>
#include <stddef.h>

#define BAD_SAMPLE_FAULT_COUNT 10
#define COMP_FILTER_ALPHA 0.98f
#define RAD2DEG 57.2957795f

/* Keeps the gyro-integrated angle in (-180, 180] so it can't drift
 * unbounded: the filter only pulls it back toward the (already-wrapped)
 * accelerometer estimate by 2% per tick, which is far too weak a
 * correction to counter sustained fast gyro rates (e.g. a body
 * tumbling on the ground after landing) on its own. */
static float wrap_deg(float deg) {
    while (deg > 180.0f) deg -= 360.0f;
    while (deg <= -180.0f) deg += 360.0f;
    return deg;
}

void attitude_init(attitude_estimator_t *a) {
    a->roll_deg = 0.0f;
    a->pitch_deg = 0.0f;
    a->altitude_m = 0.0f;
    a->vspeed_mps = 0.0f;
    a->prev_altitude_m = 0.0f;
    a->initialized = false;
    a->fault = false;
    a->bad_imu_count = 0;
    a->bad_baro_count = 0;
}

void attitude_update(attitude_estimator_t *a,
                      const imu_sample_t *imu, bool imu_ok,
                      const baro_sample_t *baro, bool baro_ok,
                      float dt_s) {
    if (imu_ok && imu) {
        a->bad_imu_count = 0;
        float accel_roll = atan2f(imu->accel_y_g, imu->accel_z_g) * RAD2DEG;
        float denom = sqrtf(imu->accel_y_g * imu->accel_y_g + imu->accel_z_g * imu->accel_z_g);
        float accel_pitch = atan2f(-imu->accel_x_g, denom) * RAD2DEG;

        float gyro_roll = a->roll_deg + imu->gyro_x_dps * dt_s;
        float gyro_pitch = a->pitch_deg + imu->gyro_y_dps * dt_s;

        a->roll_deg = wrap_deg(COMP_FILTER_ALPHA * gyro_roll + (1.0f - COMP_FILTER_ALPHA) * accel_roll);
        a->pitch_deg = wrap_deg(COMP_FILTER_ALPHA * gyro_pitch + (1.0f - COMP_FILTER_ALPHA) * accel_pitch);
    } else {
        a->bad_imu_count++;
    }

    if (baro_ok && baro) {
        a->bad_baro_count = 0;
        if (!a->initialized) {
            a->altitude_m = baro->altitude_m;
            a->prev_altitude_m = baro->altitude_m;
            a->initialized = true;
        }
        float raw_vspeed = (baro->altitude_m - a->prev_altitude_m) / dt_s;
        a->vspeed_mps = 0.8f * a->vspeed_mps + 0.2f * raw_vspeed;
        a->altitude_m = baro->altitude_m;
        a->prev_altitude_m = baro->altitude_m;
    } else {
        a->bad_baro_count++;
    }

    a->fault = (a->bad_imu_count >= BAD_SAMPLE_FAULT_COUNT) ||
               (a->bad_baro_count >= BAD_SAMPLE_FAULT_COUNT);
}
