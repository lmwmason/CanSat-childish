#include "landing_detect.h"
#include "../imu/imu_types.h"

static float absf(float v) { return v < 0.0f ? -v : v; }

void landing_init(LandingDetect *l)
{
    *l = (LandingDetect){0};
}

uint8_t landing_is_landed(const LandingDetect *l)
{
    return l->landed;
}

uint8_t landing_update(LandingDetect *l, uint8_t dropping, float accelMag,
                       float gx, float gy, float gz,
                       uint8_t gpsFix, float gpsSpeedMs, uint32_t nowMs)
{
    if (!l->filterInit) {
        l->accelFiltered = accelMag;
        l->filterInit = 1;
    }
    float jitter = absf(accelMag - l->accelFiltered);
    l->accelFiltered += LANDING_FILTER_ALPHA * (accelMag - l->accelFiltered);

    if (!dropping) {                    /* disarm and clear */
        l->wasDropping = 0;
        l->stillTiming = 0;
        l->landed = 0;
        return 0;
    }
    if (!l->wasDropping) {
        l->wasDropping = 1;
        l->dropStartMs = nowMs;
    }
    if (l->landed) return 1;
    if ((nowMs - l->dropStartMs) < LANDING_MIN_AFTER_DROP_MS) return 0;

    uint8_t still = absf(gx) < LANDING_GYRO_MAX_DPS &&
                    absf(gy) < LANDING_GYRO_MAX_DPS &&
                    absf(gz) < LANDING_GYRO_MAX_DPS &&
                    absf(l->accelFiltered - IMU_GRAVITY) < LANDING_ACCEL_TOL_MS2 &&
                    jitter < LANDING_ACCEL_JITTER_MS2 &&
                    (!gpsFix || gpsSpeedMs < LANDING_GPS_SPEED_MAX_MS);

    if (!still) {
        l->stillTiming = 0;
    } else if (!l->stillTiming) {
        l->stillTiming = 1;
        l->stillSinceMs = nowMs;
    } else if ((nowMs - l->stillSinceMs) >= LANDING_STILL_MS) {
        l->landed = 1;
    }
    return l->landed;
}
