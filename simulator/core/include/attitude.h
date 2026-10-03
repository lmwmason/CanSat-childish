#ifndef ATTITUDE_H
#define ATTITUDE_H

#include <stdbool.h>
#include "cansat_types.h"

/*
 * Complementary-filter attitude + altitude/vertical-speed estimator.
 * Also doubles as the sensor-health monitor: if the IMU or baro HAL
 * calls report "not ok" for too many consecutive ticks, `fault`
 * latches so failsafe_compute() can force actuators to zero instead
 * of steering on garbage data. This is the sensor-level failsafe
 * that applies equally to the mothership and every child satellite.
 */
typedef struct {
    float roll_deg, pitch_deg;
    float altitude_m, vspeed_mps;
    float prev_altitude_m;
    bool initialized;
    bool fault;
    int bad_imu_count, bad_baro_count;
} attitude_estimator_t;

void attitude_init(attitude_estimator_t *a);
void attitude_update(attitude_estimator_t *a,
                      const imu_sample_t *imu, bool imu_ok,
                      const baro_sample_t *baro, bool baro_ok,
                      float dt_s);

#endif /* ATTITUDE_H */
