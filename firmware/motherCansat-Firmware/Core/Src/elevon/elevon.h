#ifndef ELEVON_H
#define ELEVON_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include "../pid/pid.h"

/* Auto mode follows a roll target given by the caller (navigation); 0 = wings level.
 *
 * Two elevon servos (left = soft PWM ch0 / PC8, right = ch1 / PC9).
 *
 * Mode is picked by a switch on the controller:
 *   switch ON  (high)  -> MANUAL: sticks drive the elevons
 *   switch OFF (low)   -> AUTO:   PID levels the aircraft (roll 0, pitch trim)
 * If the radio link is lost the elevons go AUTO.
 *
 * Elevons only move once the wings are ejected; before that they stay neutral. */

#define ELEVON_MODE_SWITCH_CH   6      /* CRSF channel 1..16 (AUX2) */
#define ELEVON_ROLL_CH          1      /* aileron stick  */
#define ELEVON_PITCH_CH         2      /* elevator stick */
#define ELEVON_MANUAL_PITCH_SIGN (-1.0f) /* stick pulled back (low) = nose up */

#define ELEVON_CENTER_US_L      1500
#define ELEVON_CENTER_US_R      1500
#define ELEVON_RANGE_US         400    /* full deflection = center +- this */
#define ELEVON_REVERSE_L        0      /* set 1 if the left servo moves the wrong way */
#define ELEVON_REVERSE_R        0

#define ELEVON_AUTO_PITCH_DEG   0.0f   /* pitch the auto mode holds (glide trim) */
#define ELEVON_ROLL_KP          0.030f
#define ELEVON_ROLL_KI          0.002f
#define ELEVON_ROLL_KD          0.005f
#define ELEVON_PITCH_KP         0.030f
#define ELEVON_PITCH_KI         0.002f
#define ELEVON_PITCH_KD         0.005f

typedef enum { ELEVON_NEUTRAL = 0, ELEVON_MANUAL, ELEVON_AUTO } ElevonMode;

typedef struct {
    Pid        rollPid, pitchPid;
    ElevonMode mode;
    float      rollCmd, pitchCmd;     /* last commands, -1..1 (+ = roll right / nose up) */
    uint16_t   leftUs, rightUs;       /* last pulses sent */
} Elevon;

void elevon_init(Elevon *e);
void elevon_set_roll_gains(Elevon *e, float kp, float ki, float kd);
void elevon_set_pitch_gains(Elevon *e, float kp, float ki, float kd);

/* Call every control tick. rollDeg/pitchDeg from the IMU (+ = right wing down / nose up). */
void elevon_update(Elevon *e, float rollDeg, float pitchDeg, float rollTargetDeg, float dt,
                   uint32_t nowMs, uint8_t wingsOut);

const char *elevon_mode_name(ElevonMode m);

#ifdef __cplusplus
}
#endif

#endif /* ELEVON_H */
