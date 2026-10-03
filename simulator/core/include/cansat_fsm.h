#ifndef CANSAT_FSM_H
#define CANSAT_FSM_H

#include <stdint.h>
#include "cansat_types.h"
#include "cansat_hal.h"
#include "cansat_config.h"
#include "pi_link.h"
#include "attitude.h"
#include "failsafe.h"
#include "deploy.h"
#include "telemetry.h"

/*
 * Top-level mission state machine, shared by the mothership and every
 * small observer satellite (each instance gets its own cansat_config_t).
 *
 *   BOOT -> STANDBY -> DESCENT -> LANDED
 *
 * During DESCENT, if cfg.has_actuators: control is CTRL_PI_GUIDED while
 * the Pi heartbeat is alive (mothership only), else
 * CTRL_FAILSAFE_AUTONOMOUS - the core stabilizes attitude itself using
 * only onboard IMU/baro. If !cfg.has_actuators (every observer - no
 * DRV8874/control surfaces at all), this is skipped entirely: it just
 * falls passively under its drag membrane while GPS/baro/IMU/humidity
 * keep being logged for the wind vector field. The deploy sequencer
 * runs unconditionally in DESCENT and never depends on the Pi link.
 *
 * At LANDED: motors stay live under CTRL_PI_GUIDED (e.g. a post-landing
 * mission) only while the Pi is alive; otherwise the vehicle goes
 * CTRL_SAFE_DISARMED - actuators zeroed and motor power physically cut.
 * An observer (has_pi_link=false) always lands into CTRL_SAFE_DISARMED
 * and just beacons telemetry.
 */
typedef struct {
    cansat_config_t cfg;
    cansat_hal_t hal;

    pi_link_t pi_link;
    attitude_estimator_t att;
    failsafe_controller_t failsafe;
    deploy_sequencer_t deploy;
    telemetry_t telem;

    mission_state_t state;
    uint32_t state_enter_ms;

    bool landing_stable_timer_running;
    uint32_t landing_stable_since_ms;

    bool deployed[CANSAT_MAX_DEPLOY_CHANNELS];

    /* last computed outputs, exposed via cansat_get_status() */
    control_mode_t last_mode;
    bool last_pi_alive;
    bool last_motors_enabled;
    float last_actuator_out[2];
    bool last_gps_fix;
    float last_pos_x_m, last_pos_y_m;
    float last_humidity_pct;

    uint32_t boot_ms;
    uint32_t last_now_ms;
} cansat_t;

void cansat_init(cansat_t *c, const cansat_config_t *cfg, const cansat_hal_t *hal, uint32_t now_ms);

/* Call at a fixed 100 Hz (dt = 10 ms) - attitude/vspeed filtering assumes this rate. */
void cansat_tick(cansat_t *c, uint32_t now_ms);

/* External launch/separation trigger (ground command, RC switch, or -
 * for a child satellite - the physical separation event from the
 * mothership). Only takes effect from MISSION_STANDBY. */
void cansat_request_launch(cansat_t *c, uint32_t now_ms);

void cansat_get_status(const cansat_t *c, cansat_status_t *out);

#endif /* CANSAT_FSM_H */
