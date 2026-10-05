#ifndef NAV_H
#define NAV_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include "../gps/gps.h"

/* Circles around a home point (the GPS position where the drop was detected).
 * Output is a roll target (deg) for the elevon roll PID: bank toward the desired
 * course. Heading comes from GPS course over ground, propagated by the gyro
 * between 1 Hz fixes. Without a fix / home / heading the target is 0 (wings level). */
#define NAV_LOITER_RADIUS_M     50.0f
#define NAV_LOITER_CW           1        /* 1 = clockwise, 0 = counter-clockwise */
#define NAV_MIN_SPEED_MS        2.0f     /* GPS course is trusted above this ground speed */
#define NAV_HEADING_GPS_ALPHA   0.6f     /* pull of each GPS course fix on the heading estimate */
#define NAV_HEADING_KP          0.6f     /* roll target deg per deg of course error */
#define NAV_MAX_BANK_DEG        25.0f

typedef struct {
    uint8_t  homeSet;
    double   homeLat, homeLon;

    float    distM;          /* distance to home */
    float    bearingDeg;     /* bearing from aircraft to home, 0..360 */
    float    headingDeg;     /* estimated heading, 0..360 */
    uint8_t  headingValid;
    uint32_t lastSeq;

    float    desiredCourseDeg;
    float    rollTargetDeg;
    uint8_t  active;         /* 1 = rollTargetDeg comes from navigation */
} Nav;

void nav_init(Nav *n);
void nav_set_home(Nav *n, double lat, double lon);
void nav_clear_home(Nav *n);
/* Call every control tick. yawRateDps = gyro z (+ = counter-clockwise seen from above). */
void nav_update(Nav *n, const Gps *g, float yawRateDps, float dt, uint32_t nowMs);

#ifdef __cplusplus
}
#endif

#endif /* NAV_H */
