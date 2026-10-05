#include "reaction_wheel.h"

float rw_wrap_deg(float deg)
{
    while (deg >= 180.0f) deg -= 360.0f;
    while (deg < -180.0f) deg += 360.0f;
    return deg;
}

static void apply(ReactionWheel *rw, float command)
{
    if (command > 1.0f) command = 1.0f;
    if (command < -1.0f) command = -1.0f;
    rw->command = command;
    if (rw->setMotor) rw->setMotor(command * rw->outputSign);
}

void rw_init(ReactionWheel *rw, RwMotorFn setMotor)
{
    rw->setMotor = setMotor;
    rw->mode = RW_OFF;
    rw->targetYawDeg = 0.0f;
    rw->outputSign = 1.0f;
    rw->command = 0.0f;
    rw->turnPower = RW_TURN_DEFAULT_POWER;
    rw->turnHandoverDeg = RW_TURN_DEFAULT_HANDOVER;
    rw->turnDoneDeg = RW_TURN_DEFAULT_DONE_DEG;
    rw->turnTimeoutMs = RW_TURN_DEFAULT_TIMEOUT_MS;
    rw->turnElapsedMs = 0;
    rw->turnBraking = 0;
    pid_init(&rw->pid, RW_DEFAULT_KP, RW_DEFAULT_KI, RW_DEFAULT_KD, -1.0f, 1.0f);
    pid_set_derivative_filter(&rw->pid, 0.3f);
    apply(rw, 0.0f);
}

void rw_set_gains(ReactionWheel *rw, float kp, float ki, float kd)
{
    pid_set_gains(&rw->pid, kp, ki, kd);
}

void rw_on(ReactionWheel *rw, float holdYawDeg)
{
    rw->targetYawDeg = holdYawDeg;
    pid_reset(&rw->pid);
    rw->mode = RW_HOLD;
}

void rw_off(ReactionWheel *rw)
{
    rw->mode = RW_OFF;
    pid_reset(&rw->pid);
    apply(rw, 0.0f);
}

void rw_set_target(ReactionWheel *rw, float targetYawDeg)
{
    rw->targetYawDeg = targetYawDeg;
}

uint8_t rw_is_on(const ReactionWheel *rw)
{
    return rw->mode != RW_OFF;
}

void rw_turn_to(ReactionWheel *rw, float targetYawDeg)
{
    rw->targetYawDeg = rw_wrap_deg(targetYawDeg);
    rw->turnElapsedMs = 0;
    rw->turnBraking = 0;
    pid_reset(&rw->pid);
    rw->mode = RW_TURN_FAST;
}

void rw_turn_by(ReactionWheel *rw, float currentYawDeg, float deltaDeg)
{
    rw_turn_to(rw, currentYawDeg + deltaDeg);
}

uint8_t rw_is_turning(const ReactionWheel *rw)
{
    return rw->mode == RW_TURN_FAST;
}

float rw_update(ReactionWheel *rw, float yawDeg, float dt)
{
    if (rw->mode == RW_OFF) return rw->command;

    float error = rw_wrap_deg(rw->targetYawDeg - yawDeg);
    float absErr = error < 0.0f ? -error : error;

    if (rw->mode == RW_TURN_FAST) {
        rw->turnElapsedMs += (uint32_t)(dt * 1000.0f);

        if (!rw->turnBraking) {
            if (absErr > rw->turnHandoverDeg && rw->turnElapsedMs < rw->turnTimeoutMs) {
                apply(rw, error > 0.0f ? rw->turnPower : -rw->turnPower);
                return rw->command;
            }
            rw->turnBraking = 1;        /* PID decelerates onto the target */
            pid_reset(&rw->pid);
        }
        if (absErr <= rw->turnDoneDeg || rw->turnElapsedMs >= rw->turnTimeoutMs * 2u) {
            rw->mode = RW_HOLD;         /* turn finished, keep holding */
        }
    }

    /* Work on the wrapped error so the +-180 boundary is continuous:
     * setpoint 0, measurement = -error (derivative then damps yaw rate). */
    float out = pid_update(&rw->pid, 0.0f, -error, dt);
    apply(rw, out);
    return rw->command;
}
