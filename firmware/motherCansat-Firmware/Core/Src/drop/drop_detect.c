#include "drop_detect.h"

void drop_init(DropDetect *d)
{
    drop_reset(d);
}

void drop_reset(DropDetect *d)
{
    d->accelFiltered = 0.0f;
    d->filterInit = 0;
    d->inBand = 0;
    d->bandSinceMs = 0;
    d->dropping = 0;
}

uint8_t drop_update(DropDetect *d, float accelMag, uint8_t aux1On, uint32_t nowMs)
{
    if (!d->filterInit) {
        d->accelFiltered = accelMag;
        d->filterInit = 1;
    } else {
        d->accelFiltered += DROP_FILTER_ALPHA * (accelMag - d->accelFiltered);
    }

    if (!aux1On) {              /* switch off: disarm and clear */
        d->inBand = 0;
        d->dropping = 0;
        return 0;
    }

    uint8_t inBand = d->accelFiltered >= DROP_ACCEL_MIN && d->accelFiltered <= DROP_ACCEL_MAX;
    if (!inBand) {
        d->inBand = 0;
    } else if (!d->inBand) {
        d->inBand = 1;
        d->bandSinceMs = nowMs;
    } else if ((nowMs - d->bandSinceMs) >= DROP_HOLD_MS) {
        d->dropping = 1;
    }
    return d->dropping;
}

uint8_t drop_is_dropping(const DropDetect *d)
{
    return d->dropping;
}
