#ifndef PID_H
#define PID_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

typedef struct {
    float kp;
    float ki;
    float kd;

    float outMin;
    float outMax;

    float derivAlpha;   /* derivative low-pass, 0..1 (1 = no filtering) */

    float integral;
    float prevMeasurement;
    float derivative;
    float output;
    uint8_t primed;     /* 0 until first update, avoids derivative kick */
} Pid;

void  pid_init(Pid *pid, float kp, float ki, float kd, float outMin, float outMax);
void  pid_set_gains(Pid *pid, float kp, float ki, float kd);
void  pid_set_limits(Pid *pid, float outMin, float outMax);
void  pid_set_derivative_filter(Pid *pid, float alpha);
void  pid_reset(Pid *pid);

/* dt in seconds. Returns output clamped to [outMin, outMax]. */
float pid_update(Pid *pid, float setpoint, float measurement, float dt);

#ifdef __cplusplus
}
#endif

#endif /* PID_H */
