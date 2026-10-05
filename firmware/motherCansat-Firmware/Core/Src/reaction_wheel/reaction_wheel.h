#ifndef REACTION_WHEEL_H
#define REACTION_WHEEL_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include "../pid/pid.h"

/* Hardware hook: apply a wheel command in [-1.0, 1.0] (sign = spin direction,
 * magnitude = duty). Implement it with your PWM/DIR pins, e.g. TIM1 CH1. */
typedef void (*RwMotorFn)(float command);

typedef enum {
    RW_OFF = 0,      /* motor stopped, PID idle */
    RW_HOLD,         /* PID holds target yaw */
    RW_TURN_FAST     /* full-power fast yaw turn in progress */
} RwMode;

typedef struct {
    Pid       pid;
    RwMotorFn setMotor;
    RwMode    mode;
    float     targetYawDeg;
    float     outputSign;   /* +1 or -1, flip if the wheel pushes the wrong way */
    float     command;      /* last command sent to the motor */

    /* fast turn settings (tunable) */
    float     turnPower;       /* 0..1 wheel command during the fast phase */
    float     turnHandoverDeg; /* switch to PID braking when this close to target */
    float     turnDoneDeg;     /* turn counts as done inside this error */
    uint32_t  turnTimeoutMs;   /* give up fast phase after this long */
    uint32_t  turnElapsedMs;
    uint8_t   turnBraking;     /* 1 once PID has taken over */
} ReactionWheel;

/* Default gains, change here or at runtime with rw_set_gains(). */
#define RW_DEFAULT_KP 0.02f
#define RW_DEFAULT_KI 0.0005f
#define RW_DEFAULT_KD 0.01f

#define RW_TURN_DEFAULT_POWER       1.0f
#define RW_TURN_DEFAULT_HANDOVER    40.0f
#define RW_TURN_DEFAULT_DONE_DEG    3.0f
#define RW_TURN_DEFAULT_TIMEOUT_MS  3000u

void  rw_init(ReactionWheel *rw, RwMotorFn setMotor);
void  rw_set_gains(ReactionWheel *rw, float kp, float ki, float kd);

/* Turn the wheel on and hold the given yaw (deg). */
void  rw_on(ReactionWheel *rw, float holdYawDeg);
/* Turn the wheel off (motor stopped). */
void  rw_off(ReactionWheel *rw);
void  rw_set_target(ReactionWheel *rw, float targetYawDeg);
uint8_t rw_is_on(const ReactionWheel *rw);

/* Fast yaw turn: full power toward the target, then PID brakes and holds it.
 * Also turns the wheel on if it was off. */
void  rw_turn_by(ReactionWheel *rw, float currentYawDeg, float deltaDeg);
void  rw_turn_to(ReactionWheel *rw, float targetYawDeg);
/* 1 while a fast turn is still in progress. */
uint8_t rw_is_turning(const ReactionWheel *rw);

/* Call periodically. yawDeg from IMU, dt in seconds. Returns motor command. */
float rw_update(ReactionWheel *rw, float yawDeg, float dt);

/* Wrap an angle difference into [-180, 180). */
float rw_wrap_deg(float deg);

#ifdef __cplusplus
}
#endif

#endif /* REACTION_WHEEL_H */
