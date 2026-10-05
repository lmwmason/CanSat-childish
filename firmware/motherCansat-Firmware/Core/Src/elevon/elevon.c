#include "elevon.h"
#include "../soft_pwm/soft_pwm.h"
#include "../crsf/crsf.h"

static float clamp1(float v)
{
    if (v > 1.0f) return 1.0f;
    if (v < -1.0f) return -1.0f;
    return v;
}

/* CRSF raw 172..1811 -> -1..1 */
static float stick(uint8_t channel)
{
    return clamp1(((float)crsf_get_channel(channel) - 992.0f) / 819.5f);
}

static void output(Elevon *e, float rollCmd, float pitchCmd)
{
    e->rollCmd = rollCmd;
    e->pitchCmd = pitchCmd;

    /* deflection + = trailing edge down. Roll right: left down, right up. Nose up: both up. */
    float defL = clamp1( rollCmd - pitchCmd);
    float defR = clamp1(-rollCmd - pitchCmd);
    if (ELEVON_REVERSE_L) defL = -defL;
    if (ELEVON_REVERSE_R) defR = -defR;

    e->leftUs  = (uint16_t)(ELEVON_CENTER_US_L + defL * ELEVON_RANGE_US);
    e->rightUs = (uint16_t)(ELEVON_CENTER_US_R + defR * ELEVON_RANGE_US);
    soft_pwm_set_us(0, e->leftUs);
    soft_pwm_set_us(1, e->rightUs);
}

void elevon_init(Elevon *e)
{
    pid_init(&e->rollPid, ELEVON_ROLL_KP, ELEVON_ROLL_KI, ELEVON_ROLL_KD, -1.0f, 1.0f);
    pid_init(&e->pitchPid, ELEVON_PITCH_KP, ELEVON_PITCH_KI, ELEVON_PITCH_KD, -1.0f, 1.0f);
    pid_set_derivative_filter(&e->rollPid, 0.3f);
    pid_set_derivative_filter(&e->pitchPid, 0.3f);
    e->mode = ELEVON_NEUTRAL;
    output(e, 0.0f, 0.0f);
}

void elevon_set_roll_gains(Elevon *e, float kp, float ki, float kd)
{
    pid_set_gains(&e->rollPid, kp, ki, kd);
}

void elevon_set_pitch_gains(Elevon *e, float kp, float ki, float kd)
{
    pid_set_gains(&e->pitchPid, kp, ki, kd);
}

const char *elevon_mode_name(ElevonMode m)
{
    switch (m) {
    case ELEVON_MANUAL: return "MAN";
    case ELEVON_AUTO:   return "AUTO";
    default:            return "OFF";
    }
}

void elevon_update(Elevon *e, float rollDeg, float pitchDeg, float rollTargetDeg, float dt,
                   uint32_t nowMs, uint8_t wingsOut)
{
    ElevonMode want;
    if (!wingsOut)                                          want = ELEVON_NEUTRAL;
    else if (crsf_switch_on(ELEVON_MODE_SWITCH_CH, nowMs))  want = ELEVON_MANUAL;
    else                                                    want = ELEVON_AUTO;   /* also on link loss */

    if (want != e->mode) {                                  /* no PID carry-over between modes */
        pid_reset(&e->rollPid);
        pid_reset(&e->pitchPid);
        e->mode = want;
    }

    switch (e->mode) {
    case ELEVON_MANUAL:
        output(e, stick(ELEVON_ROLL_CH), ELEVON_MANUAL_PITCH_SIGN * stick(ELEVON_PITCH_CH));
        break;
    case ELEVON_AUTO: {
        float roll  = pid_update(&e->rollPid, rollTargetDeg, rollDeg, dt);
        float pitch = pid_update(&e->pitchPid, ELEVON_AUTO_PITCH_DEG, pitchDeg, dt);
        output(e, roll, pitch);
        break;
    }
    default:
        output(e, 0.0f, 0.0f);
        break;
    }
}
