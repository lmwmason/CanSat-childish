#ifndef DROP_DETECT_H
#define DROP_DETECT_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

/* Drop is detected when BOTH are true continuously for DROP_HOLD_MS:
 *   - filtered acceleration magnitude is within [DROP_ACCEL_MIN, DROP_ACCEL_MAX] m/s^2
 *   - the CRSF AUX1 switch is on
 * Once detected it stays latched until AUX1 goes off (or drop_reset()). */
#define DROP_ACCEL_MIN   9.7f
#define DROP_ACCEL_MAX   9.9f
#define DROP_HOLD_MS     300u
#define DROP_FILTER_ALPHA 0.2f   /* low-pass on the magnitude, 1 = off */

typedef struct {
    float    accelFiltered;
    uint8_t  filterInit;
    uint8_t  inBand;
    uint32_t bandSinceMs;
    uint8_t  dropping;
} DropDetect;

void    drop_init(DropDetect *d);
void    drop_reset(DropDetect *d);
/* accelMag in m/s^2. Returns 1 while dropping is detected. */
uint8_t drop_update(DropDetect *d, float accelMag, uint8_t aux1On, uint32_t nowMs);
uint8_t drop_is_dropping(const DropDetect *d);

#ifdef __cplusplus
}
#endif

#endif /* DROP_DETECT_H */
