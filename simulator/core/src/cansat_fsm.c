#include "cansat_fsm.h"
#include <string.h>
#include <math.h>

/* core is ticked at a fixed 100 Hz by the caller (real IRQ/timer on
 * STM32, or the sim main loop) - attitude/vspeed filtering assumes this. */
#define DT_S 0.01f

static void enter_state(cansat_t *c, mission_state_t s, uint32_t now_ms) {
    c->state = s;
    c->state_enter_ms = now_ms;
}

void cansat_init(cansat_t *c, const cansat_config_t *cfg, const cansat_hal_t *hal, uint32_t now_ms) {
    memset(c, 0, sizeof(*c));
    c->cfg = *cfg;
    c->hal = *hal;

    pi_link_init(&c->pi_link);
    attitude_init(&c->att);
    failsafe_init(&c->failsafe);
    deploy_init(&c->deploy);
    telemetry_init(&c->telem);

    c->state = MISSION_BOOT;
    c->state_enter_ms = now_ms;
    c->boot_ms = now_ms;
    c->last_mode = CTRL_SAFE_DISARMED;
}

void cansat_request_launch(cansat_t *c, uint32_t now_ms) {
    if (c->state == MISSION_STANDBY) {
        enter_state(c, MISSION_DESCENT, now_ms);
        deploy_on_descent_start(&c->deploy, now_ms);
    }
}

void cansat_tick(cansat_t *c, uint32_t now_ms) {
    imu_sample_t imu;
    bool imu_ok = c->hal.read_imu ? c->hal.read_imu(c->hal.ctx, &imu) : false;

    baro_sample_t baro;
    bool baro_ok = c->hal.read_baro ? c->hal.read_baro(c->hal.ctx, &baro) : false;

    attitude_update(&c->att, &imu, imu_ok, &baro, baro_ok, DT_S);
    if (baro_ok) c->last_humidity_pct = baro.humidity_pct;

    gps_sample_t gps;
    if (c->hal.read_gps && c->hal.read_gps(c->hal.ctx, &gps)) {
        c->last_gps_fix = gps.fix;
        c->last_pos_x_m = gps.local_x_m;
        c->last_pos_y_m = gps.local_y_m;
    }

    bool pi_alive = false;
    if (c->cfg.has_pi_link) {
        pi_link_poll(&c->pi_link, &c->hal, now_ms);
        pi_alive = pi_link_is_alive(&c->pi_link, now_ms, c->cfg.pi_link_timeout_ms);
    }

    /* --- Phase 1: evaluate transitions out of the CURRENT state. --- */
    bool altitude_valid = c->att.initialized && !c->att.fault;

    switch (c->state) {
    case MISSION_BOOT:
        if (now_ms - c->state_enter_ms > 500) enter_state(c, MISSION_STANDBY, now_ms);
        break;

    case MISSION_STANDBY:
        /* Waits for cansat_request_launch(): ground command, RC arm
         * switch, or - for a child satellite - the physical separation
         * event off the mothership. */
        break;

    case MISSION_DESCENT: {
        deploy_update(&c->deploy, &c->cfg, &c->hal, c->att.altitude_m, altitude_valid, now_ms, c->deployed);

        bool stable = altitude_valid &&
                      fabsf(c->att.vspeed_mps) < c->cfg.landing_vspeed_thresh_mps &&
                      c->att.altitude_m <= c->cfg.landing_altitude_m;
        if (stable) {
            if (!c->landing_stable_timer_running) {
                c->landing_stable_timer_running = true;
                c->landing_stable_since_ms = now_ms;
            } else if (now_ms - c->landing_stable_since_ms >= c->cfg.landing_confirm_ms) {
                c->landing_stable_timer_running = false;
                enter_state(c, MISSION_LANDED, now_ms);
            }
        } else {
            c->landing_stable_timer_running = false;
        }
        break;
    }

    case MISSION_LANDED:
        break;
    }

    /* --- Phase 2: compute outputs for the (possibly just-updated)
     * state, so a same-tick DESCENT->LANDED transition is disarmed
     * immediately instead of one tick late. --- */
    control_mode_t mode = CTRL_SAFE_DISARMED;
    bool motors_enabled = false;
    float actuator_out[2] = {0.0f, 0.0f};

    if (c->state == MISSION_DESCENT && c->cfg.has_actuators) {
        /* Deliberately requires an actual actuator command, not just a
         * live heartbeat: a Pi that is up but not yet actively steering
         * should not silently zero out the stabilization loop. */
        if (c->cfg.has_pi_link && pi_alive && c->pi_link.have_actuator_cmd) {
            mode = CTRL_PI_GUIDED;
            actuator_out[0] = c->pi_link.actuator_cmd[0];
            actuator_out[1] = c->pi_link.actuator_cmd[1];
        } else {
            mode = CTRL_FAILSAFE_AUTONOMOUS;
            failsafe_compute(&c->failsafe, &c->att, actuator_out);
        }
        motors_enabled = true;
    } else if (c->state == MISSION_DESCENT) {
        /* No actuators fitted at all (every small observer): passive
         * fall under the drag membrane. Nothing to command - just keep
         * logging GPS/baro/IMU/humidity for the wind vector field. */
    } else if (c->state == MISSION_LANDED && c->cfg.has_actuators) {
        if (c->cfg.has_pi_link && pi_alive) {
            /* Post-landing mission handoff (e.g. rover drive-away). */
            mode = CTRL_PI_GUIDED;
            motors_enabled = true;
            if (c->pi_link.have_actuator_cmd) {
                actuator_out[0] = c->pi_link.actuator_cmd[0];
                actuator_out[1] = c->pi_link.actuator_cmd[1];
            }
        } else {
            /* No Pi (or it died): stay landed, motors physically cut,
             * beacon only. This is the required safe end state when
             * there is no Pi code at all. */
            mode = CTRL_SAFE_DISARMED;
            motors_enabled = false;
        }
    }
    /* BOOT/STANDBY: stays CTRL_SAFE_DISARMED, motors off, zero output. */

    if (c->hal.set_actuator) {
        c->hal.set_actuator(c->hal.ctx, 0, actuator_out[0]);
        c->hal.set_actuator(c->hal.ctx, 1, actuator_out[1]);
    }
    if (c->hal.set_motor_power) c->hal.set_motor_power(c->hal.ctx, motors_enabled);

    c->last_mode = mode;
    c->last_pi_alive = pi_alive;
    c->last_motors_enabled = motors_enabled;
    c->last_actuator_out[0] = actuator_out[0];
    c->last_actuator_out[1] = actuator_out[1];
    c->last_now_ms = now_ms;

    cansat_status_t status;
    cansat_get_status(c, &status);
    telemetry_update(&c->telem, &c->hal, &status, c->cfg.telemetry_period_ms, now_ms, c->cfg.vehicle_name);
}

void cansat_get_status(const cansat_t *c, cansat_status_t *out) {
    out->state = c->state;
    out->mode = c->last_mode;
    out->pi_alive = c->last_pi_alive;
    out->sensor_fault = c->att.fault;
    out->motors_enabled = c->last_motors_enabled;
    out->actuator_out[0] = c->last_actuator_out[0];
    out->actuator_out[1] = c->last_actuator_out[1];
    out->altitude_m = c->att.altitude_m;
    out->vspeed_mps = c->att.vspeed_mps;
    out->roll_deg = c->att.roll_deg;
    out->pitch_deg = c->att.pitch_deg;
    for (int i = 0; i < CANSAT_MAX_DEPLOY_CHANNELS; i++) out->deployed[i] = c->deployed[i];
    out->uptime_ms = c->last_now_ms - c->boot_ms;
    out->gps_fix = c->last_gps_fix;
    out->pos_x_m = c->last_pos_x_m;
    out->pos_y_m = c->last_pos_y_m;
    out->humidity_pct = c->last_humidity_pct;
}
