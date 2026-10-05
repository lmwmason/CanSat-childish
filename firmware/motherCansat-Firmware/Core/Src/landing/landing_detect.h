#ifndef LANDING_DETECT_H
#define LANDING_DETECT_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

/* Landed = after a drop was detected, the CanSat has been motionless for
 * LANDING_STILL_MS: all gyro axes quiet, acceleration steady at 1 g and, when a GPS
 * fix exists, ground speed near zero. Ignored for the first LANDING_MIN_AFTER_DROP_MS
 * after the drop so a steady glide is not mistaken for landing.
 * Latched until the drop signal (AUX1) goes off. */
#define LANDING_MIN_AFTER_DROP_MS 10000u
#define LANDING_STILL_MS          3000u
#define LANDING_GYRO_MAX_DPS      5.0f     /* each axis */
#define LANDING_ACCEL_TOL_MS2     0.5f     /* |filtered accel - g| */
#define LANDING_ACCEL_JITTER_MS2  0.4f     /* |instant accel - filtered accel| */
#define LANDING_GPS_SPEED_MAX_MS  1.0f
#define LANDING_FILTER_ALPHA      0.1f

typedef struct {
    float    accelFiltered;
    uint8_t  filterInit;
    uint8_t  wasDropping;
    uint32_t dropStartMs;
    uint8_t  stillTiming;
    uint32_t stillSinceMs;
    uint8_t  landed;
} LandingDetect;

void    landing_init(LandingDetect *l);
/* gpsFix: 1 if the GPS has a valid fix (then gpsSpeedMs is checked too). Returns 1 once landed. */
uint8_t landing_update(LandingDetect *l, uint8_t dropping, float accelMag,
                       float gx, float gy, float gz,
                       uint8_t gpsFix, float gpsSpeedMs, uint32_t nowMs);
uint8_t landing_is_landed(const LandingDetect *l);

#ifdef __cplusplus
}
#endif

#endif /* LANDING_DETECT_H */
