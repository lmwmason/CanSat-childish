#include "mission.h"
#include "../door/door.h"
#include "../wings/wings.h"

void mission_init(Mission *m)
{
    m->state = MISSION_IDLE;
    m->dropStartMs = 0;
    m->doorOpenMs = 0;
    m->stableSinceMs = 0;
    m->stableTiming = 0;
    m->rateFiltered = 0.0f;
}

const char *mission_state_name(MissionState s)
{
    switch (s) {
    case MISSION_IDLE:       return "IDLE";
    case MISSION_WAIT_WHEEL: return "WAIT";
    case MISSION_STABILIZE:  return "STAB";
    case MISSION_SPIN_UP:    return "SPIN";
    case MISSION_DOOR_OPEN:  return "OPEN";
    case MISSION_RESTABILIZE: return "REST";
    case MISSION_WINGS_OUT:  return "WING";
    default:                 return "?";
    }
}

static float absf(float v) { return v < 0.0f ? -v : v; }

/* Returns 1 once the body has been steady for MISSION_STABLE_HOLD_MS. */
static uint8_t stable_for_hold(Mission *m, const ReactionWheel *rw, float yawDeg, uint32_t nowMs)
{
    uint8_t steady = absf(m->rateFiltered) < MISSION_STABLE_RATE_DPS &&
                     absf(rw_wrap_deg(rw->targetYawDeg - yawDeg)) < MISSION_STABLE_ERR_DEG;
    if (!steady) {
        m->stableTiming = 0;
        return 0;
    }
    if (!m->stableTiming) {
        m->stableTiming = 1;
        m->stableSinceMs = nowMs;
        return 0;
    }
    return (nowMs - m->stableSinceMs) >= MISSION_STABLE_HOLD_MS;
}

void mission_update(Mission *m, ReactionWheel *rw, uint8_t dropping,
                    float yawDeg, float yawRateDps, uint32_t nowMs)
{
    m->rateFiltered += MISSION_RATE_FILTER_ALPHA * (yawRateDps - m->rateFiltered);

    if (!dropping) {
        if (m->state != MISSION_IDLE) {
            rw_off(rw);
            door_close();
            wings_lock();
            m->state = MISSION_IDLE;
        }
        return;
    }

    switch (m->state) {
    case MISSION_IDLE:
        m->dropStartMs = nowMs;
        m->state = MISSION_WAIT_WHEEL;
        break;

    case MISSION_WAIT_WHEEL:
        if ((nowMs - m->dropStartMs) >= MISSION_WHEEL_DELAY_MS) {
            rw_on(rw, yawDeg);              /* hold the heading we have now */
            m->stableTiming = 0;
            m->state = MISSION_STABILIZE;
        }
        break;

    case MISSION_STABILIZE:
        if (stable_for_hold(m, rw, yawDeg, nowMs)) {
            rw_spin(rw, MISSION_SPIN_POWER);
            m->state = MISSION_SPIN_UP;
        }
        break;

    case MISSION_SPIN_UP:
        if (absf(m->rateFiltered) >= MISSION_DOOR_RATE_DPS) {
            door_open();
            m->doorOpenMs = nowMs;
            m->state = MISSION_DOOR_OPEN;
        }
        break;

    case MISSION_DOOR_OPEN:             /* wheel keeps spinning at max */
        if ((nowMs - m->doorOpenMs) >= MISSION_MAX_SPIN_MS) {
            rw_on(rw, yawDeg);          /* PID brakes the spin and holds yaw */
            m->stableTiming = 0;
            m->state = MISSION_RESTABILIZE;
        }
        break;

    case MISSION_RESTABILIZE:
        if (stable_for_hold(m, rw, yawDeg, nowMs)) {
            wings_eject();
            m->state = MISSION_WINGS_OUT;
        }
        break;

    case MISSION_WINGS_OUT:
        break;
    }
}
