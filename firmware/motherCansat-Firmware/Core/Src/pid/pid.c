#include "pid.h"

static float clampf(float v, float lo, float hi)
{
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

void pid_init(Pid *pid, float kp, float ki, float kd, float outMin, float outMax)
{
    pid->kp = kp;
    pid->ki = ki;
    pid->kd = kd;
    pid->outMin = outMin;
    pid->outMax = outMax;
    pid->derivAlpha = 1.0f;
    pid_reset(pid);
}

void pid_set_gains(Pid *pid, float kp, float ki, float kd)
{
    pid->kp = kp;
    pid->ki = ki;
    pid->kd = kd;
}

void pid_set_limits(Pid *pid, float outMin, float outMax)
{
    pid->outMin = outMin;
    pid->outMax = outMax;
    pid->integral = clampf(pid->integral, outMin, outMax);
}

void pid_set_derivative_filter(Pid *pid, float alpha)
{
    pid->derivAlpha = clampf(alpha, 0.0f, 1.0f);
}

void pid_reset(Pid *pid)
{
    pid->integral = 0.0f;
    pid->prevMeasurement = 0.0f;
    pid->derivative = 0.0f;
    pid->output = 0.0f;
    pid->primed = 0;
}

float pid_update(Pid *pid, float setpoint, float measurement, float dt)
{
    if (dt <= 0.0f) return pid->output;

    float error = setpoint - measurement;

    /* derivative on measurement (no kick on setpoint change), low-pass filtered */
    if (pid->primed) {
        float raw = -(measurement - pid->prevMeasurement) / dt;
        pid->derivative += pid->derivAlpha * (raw - pid->derivative);
    } else {
        pid->derivative = 0.0f;
        pid->primed = 1;
    }
    pid->prevMeasurement = measurement;

    /* integrate with clamping anti-windup */
    pid->integral += pid->ki * error * dt;
    pid->integral = clampf(pid->integral, pid->outMin, pid->outMax);

    float out = pid->kp * error + pid->integral + pid->kd * pid->derivative;
    pid->output = clampf(out, pid->outMin, pid->outMax);
    return pid->output;
}
