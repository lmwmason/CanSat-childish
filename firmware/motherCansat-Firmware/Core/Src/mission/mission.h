#ifndef MISSION_H
#define MISSION_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include "../reaction_wheel/reaction_wheel.h"

/* Sequence after the drop is detected:
 *   WAIT_WHEEL  -> wait MISSION_WHEEL_DELAY_MS
 *   STABILIZE   -> wheel on, hold yaw until the body is steady
 *   SPIN_UP     -> wheel spins the body fast
 *   DOOR_OPEN   -> yaw rate is high enough, servo opens the door, keep spinning
 *                  at max for MISSION_MAX_SPIN_MS
 *   RESTABILIZE -> wheel brakes the spin and holds yaw until steady
 *   WINGS_OUT   -> wing servos eject the wings
 * If the drop signal goes away (AUX1 off) everything is reset. */
#define MISSION_WHEEL_DELAY_MS     2000u
#define MISSION_STABLE_RATE_DPS    8.0f     /* |yaw rate| below this ... */
#define MISSION_STABLE_ERR_DEG     10.0f    /* ... and |yaw error| below this ... */
#define MISSION_STABLE_HOLD_MS     1000u    /* ... for this long = stabilized */
#define MISSION_SPIN_POWER         1.0f     /* wheel command while spinning up (sign = direction) */
#define MISSION_DOOR_RATE_DPS      180.0f   /* "fast enough" yaw rate to open the door */
#define MISSION_MAX_SPIN_MS        5000u    /* time at max speed after the door opens */
#define MISSION_RATE_FILTER_ALPHA  0.3f

typedef enum {
    MISSION_IDLE = 0,
    MISSION_WAIT_WHEEL,
    MISSION_STABILIZE,
    MISSION_SPIN_UP,
    MISSION_DOOR_OPEN,
    MISSION_RESTABILIZE,
    MISSION_WINGS_OUT
} MissionState;

typedef struct {
    MissionState state;
    uint32_t     dropStartMs;
    uint32_t     doorOpenMs;
    uint32_t     stableSinceMs;
    uint8_t      stableTiming;
    float        rateFiltered;   /* deg/s */
} Mission;

void mission_init(Mission *m);
/* Call every control tick (after the IMU update, before rw_update).
 * dropping from drop detector, yawDeg/yawRateDps from the IMU. */
void mission_update(Mission *m, ReactionWheel *rw, uint8_t dropping,
                    float yawDeg, float yawRateDps, uint32_t nowMs);
const char *mission_state_name(MissionState s);

#ifdef __cplusplus
}
#endif

#endif /* MISSION_H */
