#include "nav.h"
#include <math.h>

#define DEG2RAD 0.01745329252
#define RAD2DEG 57.29577951
#define EARTH_M_PER_DEG 111320.0

static float wrap360(float d)
{
    while (d >= 360.0f) d -= 360.0f;
    while (d < 0.0f) d += 360.0f;
    return d;
}

static float wrap180(float d)
{
    while (d >= 180.0f) d -= 360.0f;
    while (d < -180.0f) d += 360.0f;
    return d;
}

void nav_init(Nav *n)
{
    *n = (Nav){0};
}

void nav_set_home(Nav *n, double lat, double lon)
{
    n->homeLat = lat;
    n->homeLon = lon;
    n->homeSet = 1;
}

void nav_clear_home(Nav *n)
{
    n->homeSet = 0;
    n->active = 0;
    n->rollTargetDeg = 0.0f;
}

void nav_update(Nav *n, const Gps *g, float yawRateDps, float dt, uint32_t nowMs)
{
    /* propagate heading with the gyro (yaw rate + = CCW, compass heading + = CW) */
    if (n->headingValid && dt > 0.0f && dt < 0.5f)
        n->headingDeg = wrap360(n->headingDeg - yawRateDps * dt);

    uint8_t fixOk = gps_has_fix(g, nowMs);

    if (fixOk && g->fixSeq != n->lastSeq) {
        n->lastSeq = g->fixSeq;

        if (g->speedMs >= NAV_MIN_SPEED_MS) {
            if (!n->headingValid) {
                n->headingDeg = g->courseDeg;
                n->headingValid = 1;
            } else {
                n->headingDeg = wrap360(n->headingDeg +
                                        NAV_HEADING_GPS_ALPHA * wrap180(g->courseDeg - n->headingDeg));
            }
        }

        if (n->homeSet) {
            double north = (n->homeLat - g->lat) * EARTH_M_PER_DEG;
            double east  = (n->homeLon - g->lon) * EARTH_M_PER_DEG * cos(g->lat * DEG2RAD);
            n->distM = (float)sqrt(north * north + east * east);
            n->bearingDeg = wrap360((float)(atan2(east, north) * RAD2DEG));
        }
    }

    if (!fixOk || !n->homeSet || !n->headingValid) {
        n->active = 0;
        n->rollTargetDeg = 0.0f;
        return;
    }

    /* far away: head for home. At the radius: fly tangent. Inside: turn away. */
    float d = n->distM < 1.0f ? 1.0f : n->distM;
    float offset = 90.0f * NAV_LOITER_RADIUS_M / d;
    if (offset > 135.0f) offset = 135.0f;
    n->desiredCourseDeg = wrap360(n->bearingDeg + (NAV_LOITER_CW ? -offset : offset));

    float err = wrap180(n->desiredCourseDeg - n->headingDeg);    /* + = turn right */
    float roll = NAV_HEADING_KP * err;
    if (roll > NAV_MAX_BANK_DEG) roll = NAV_MAX_BANK_DEG;
    if (roll < -NAV_MAX_BANK_DEG) roll = -NAV_MAX_BANK_DEG;
    n->rollTargetDeg = roll;
    n->active = 1;
}
