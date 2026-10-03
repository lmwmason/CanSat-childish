/*
 * Automated regression test for the control core, run headless (no
 * keyboard, no wall-clock pacing) so the Pi-link-loss failsafe path is
 * verified on every build instead of only when someone manually
 * presses 'p' in the interactive sim.
 *
 * Three scenarios against a mothership-shaped config:
 *   A. No Pi ever appears           -> autonomous descent, all 3
 *                                       children deploy on schedule,
 *                                       lands with motors disarmed.
 *   B. Pi alive the whole flight    -> PI_GUIDED descent, lands with
 *                                       motors still enabled (handoff).
 *   C. Pi alive, then lost mid-air  -> switches to
 *                                       CTRL_FAILSAFE_AUTONOMOUS within
 *                                       pi_link_timeout_ms, still
 *                                       deploys + lands safely disarmed.
 */
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "cansat_fsm.h"

typedef struct {
    float altitude_m;
    float descent_rate_mps;
    bool launched;
    bool pi_alive_enabled;
    int deploy_fire_count;
    control_mode_t last_descent_mode;
    bool saw_pi_guided_descent;
    bool saw_failsafe_descent;
    bool ever_motors_enabled;
    bool ever_nonzero_actuator;
    float imu_tilt_deg; /* nonzero in scenario D, to prove a passive vehicle ignores it */
} mock_ctx_t;

static bool mock_read_imu(void *ctx, imu_sample_t *out) {
    mock_ctx_t *m = (mock_ctx_t *)ctx;
    memset(out, 0, sizeof(*out));
    float r = m->imu_tilt_deg * 0.017453293f;
    out->accel_x_g = sinf(r);
    out->accel_z_g = cosf(r);
    return true;
}

static bool mock_read_baro(void *ctx, baro_sample_t *out) {
    mock_ctx_t *m = (mock_ctx_t *)ctx;
    out->altitude_m = m->altitude_m;
    out->pressure_pa = 101325.0f;
    out->temperature_c = 15.0f;
    return true;
}

static bool mock_read_gps(void *ctx, gps_sample_t *out) {
    (void)ctx;
    memset(out, 0, sizeof(*out));
    return true;
}

static int mock_pi_uart_read(void *ctx, uint8_t *buf, int max_len) {
    mock_ctx_t *m = (mock_ctx_t *)ctx;
    if (!m->pi_alive_enabled) return 0;
    /* HEARTBEAT (4 bytes) + ACTUATOR_CMD with zero command (8 bytes) = 12 bytes */
    static const uint8_t frame[] = {
        0xAA, 0x01, 0x00, 0x01,                         /* heartbeat, chk=type^len */
        0xAA, 0x02, 0x04, 0x00, 0x00, 0x00, 0x00, 0x06, /* actuator cmd {0,0}, chk=type^len */
    };
    int n = (int)sizeof(frame);
    if (n > max_len) n = max_len;
    memcpy(buf, frame, (size_t)n);
    return n;
}

static void mock_set_actuator(void *ctx, int channel, float value_norm) {
    mock_ctx_t *m = (mock_ctx_t *)ctx;
    (void)channel;
    if (fabsf(value_norm) > 1e-6f) m->ever_nonzero_actuator = true;
}

static void mock_set_motor_power(void *ctx, bool enable) {
    mock_ctx_t *m = (mock_ctx_t *)ctx;
    if (enable) m->ever_motors_enabled = true;
}

static void mock_deploy_fire(void *ctx, int channel) {
    mock_ctx_t *m = (mock_ctx_t *)ctx;
    (void)channel;
    m->deploy_fire_count++;
}

static void mock_lora_send(void *ctx, const uint8_t *buf, int len) {
    (void)ctx; (void)buf; (void)len;
}

static void mock_hal(mock_ctx_t *m, cansat_hal_t *hal) {
    memset(hal, 0, sizeof(*hal));
    hal->read_imu = mock_read_imu;
    hal->read_baro = mock_read_baro;
    hal->read_gps = mock_read_gps;
    hal->pi_uart_read = mock_pi_uart_read;
    hal->set_actuator = mock_set_actuator;
    hal->set_motor_power = mock_set_motor_power;
    hal->deploy_fire = mock_deploy_fire;
    hal->lora_send = mock_lora_send;
    hal->ctx = m;
}

static cansat_config_t mothership_cfg(void) {
    cansat_config_t cfg = {
        .vehicle_name = "test-mothership",
        .has_pi_link = true,
        .pi_link_timeout_ms = 500,
        .has_actuators = true,
        .num_deploy_channels = 3,
        .deploy_altitude_m = {300.0f, 300.0f, 300.0f},
        .deploy_backup_timer_ms = {90000, 90800, 91600},
        .deploy_stagger_ms = 800,
        .landing_altitude_m = 5.0f,
        .landing_vspeed_thresh_mps = 1.0f,
        .landing_confirm_ms = 1000,
        .telemetry_period_ms = 1000000,
    };
    return cfg;
}

static cansat_config_t observer_cfg(void) {
    cansat_config_t cfg = {
        .vehicle_name = "test-observer",
        .has_pi_link = false,
        .has_actuators = false, /* no DRV8874 at all - passive drag-membrane fall */
        .num_deploy_channels = 0,
        .landing_altitude_m = 3.0f,
        .landing_vspeed_thresh_mps = 1.0f,
        .landing_confirm_ms = 800,
        .telemetry_period_ms = 1000000,
    };
    return cfg;
}

static int g_failures = 0;

#define CHECK(cond, msg) do { \
    if (!(cond)) { printf("  FAIL: %s\n", msg); g_failures++; } \
    else { printf("  ok:   %s\n", msg); } \
} while (0)

/* Runs up to max_ms of simulated flight, calling on_tick(m, c, now_ms)
 * before each cansat_tick so the test can drive pi_alive_enabled and
 * altitude. Stops early once MISSION_LANDED is reached. */
static void run_flight(mock_ctx_t *m, cansat_t *c, uint32_t max_ms,
                        void (*on_tick)(mock_ctx_t *, cansat_t *, uint32_t)) {
    for (uint32_t now_ms = 0; now_ms < max_ms; now_ms += 10) {
        cansat_status_t st;
        cansat_get_status(c, &st);

        if (st.state == MISSION_STANDBY && !m->launched) {
            cansat_request_launch(c, now_ms);
            m->launched = true;
        }
        if (on_tick) on_tick(m, c, now_ms);
        if (m->launched && m->altitude_m > 0.0f) {
            m->altitude_m -= m->descent_rate_mps * 0.01f;
            if (m->altitude_m < 0.0f) m->altitude_m = 0.0f;
        }

        cansat_tick(c, now_ms);

        cansat_get_status(c, &st);
        if (st.state == MISSION_DESCENT) {
            m->last_descent_mode = st.mode;
            if (st.mode == CTRL_PI_GUIDED) m->saw_pi_guided_descent = true;
            if (st.mode == CTRL_FAILSAFE_AUTONOMOUS) m->saw_failsafe_descent = true;
        }
        if (st.state == MISSION_LANDED) return;
    }
}

static void scenario_a_no_pi_ever(void) {
    printf("Scenario A: no Pi ever appears\n");
    mock_ctx_t m = {0};
    m.altitude_m = 600.0f;
    m.descent_rate_mps = 6.0f;
    m.pi_alive_enabled = false;

    cansat_hal_t hal; mock_hal(&m, &hal);
    cansat_config_t cfg = mothership_cfg();
    cansat_t c; cansat_init(&c, &cfg, &hal, 0);

    run_flight(&m, &c, 200000, NULL);

    cansat_status_t st; cansat_get_status(&c, &st);
    CHECK(st.state == MISSION_LANDED, "reached MISSION_LANDED");
    CHECK(!m.saw_pi_guided_descent, "descent was never PI_GUIDED");
    CHECK(m.saw_failsafe_descent, "descent used CTRL_FAILSAFE_AUTONOMOUS");
    CHECK(m.deploy_fire_count == 3, "all 3 child satellites deployed");
    CHECK(st.deployed[0] && st.deployed[1] && st.deployed[2], "deployed[] flags all set");
    CHECK(!st.motors_enabled, "motors disarmed at landing with no Pi");
    CHECK(st.mode == CTRL_SAFE_DISARMED, "final mode is CTRL_SAFE_DISARMED");
    CHECK(fabsf(st.roll_deg) < 5.0f && fabsf(st.pitch_deg) < 5.0f, "attitude stayed bounded (stable descent)");
}

static void scenario_b_pi_alive_throughout(void) {
    printf("Scenario B: Pi alive the whole flight\n");
    mock_ctx_t m = {0};
    m.altitude_m = 600.0f;
    m.descent_rate_mps = 6.0f;
    m.pi_alive_enabled = true;

    cansat_hal_t hal; mock_hal(&m, &hal);
    cansat_config_t cfg = mothership_cfg();
    cansat_t c; cansat_init(&c, &cfg, &hal, 0);

    run_flight(&m, &c, 200000, NULL);

    cansat_status_t st; cansat_get_status(&c, &st);
    CHECK(st.state == MISSION_LANDED, "reached MISSION_LANDED");
    CHECK(m.saw_pi_guided_descent, "descent used CTRL_PI_GUIDED");
    CHECK(m.deploy_fire_count == 3, "all 3 child satellites deployed");
    CHECK(st.motors_enabled, "motors stay enabled at landing (post-landing Pi handoff)");
    CHECK(st.mode == CTRL_PI_GUIDED, "final mode is CTRL_PI_GUIDED");
}

static void on_tick_kill_pi_below_450(mock_ctx_t *m, cansat_t *c, uint32_t now_ms) {
    (void)c; (void)now_ms;
    if (m->altitude_m <= 450.0f) m->pi_alive_enabled = false;
}

static void scenario_c_pi_lost_mid_descent(void) {
    printf("Scenario C: Pi alive, then lost mid-descent\n");
    mock_ctx_t m = {0};
    m.altitude_m = 600.0f;
    m.descent_rate_mps = 6.0f;
    m.pi_alive_enabled = true;

    cansat_hal_t hal; mock_hal(&m, &hal);
    cansat_config_t cfg = mothership_cfg();
    cansat_t c; cansat_init(&c, &cfg, &hal, 0);

    run_flight(&m, &c, 200000, on_tick_kill_pi_below_450);

    cansat_status_t st; cansat_get_status(&c, &st);
    CHECK(st.state == MISSION_LANDED, "reached MISSION_LANDED");
    CHECK(m.saw_pi_guided_descent, "descent started CTRL_PI_GUIDED");
    CHECK(m.saw_failsafe_descent, "descent fell back to CTRL_FAILSAFE_AUTONOMOUS after Pi loss");
    CHECK(m.deploy_fire_count == 3, "all 3 child satellites still deployed (deploy is Pi-independent)");
    CHECK(!st.motors_enabled, "motors disarmed at landing (Pi stayed dead)");
}

static void scenario_d_passive_observer(void) {
    printf("Scenario D: passive observer (no actuators) ignores a tilted attitude\n");
    mock_ctx_t m = {0};
    m.altitude_m = 300.0f;
    m.descent_rate_mps = 8.0f;
    m.pi_alive_enabled = false;
    m.imu_tilt_deg = 25.0f; /* would produce a real correction if failsafe ran */

    cansat_hal_t hal; mock_hal(&m, &hal);
    cansat_config_t cfg = observer_cfg();
    cansat_t c; cansat_init(&c, &cfg, &hal, 0);

    run_flight(&m, &c, 100000, NULL);

    cansat_status_t st; cansat_get_status(&c, &st);
    CHECK(st.state == MISSION_LANDED, "reached MISSION_LANDED");
    CHECK(!m.saw_pi_guided_descent && !m.saw_failsafe_descent, "descent never entered any control mode");
    CHECK(!m.ever_motors_enabled, "motor power was never enabled");
    CHECK(!m.ever_nonzero_actuator, "actuator output stayed zero despite a tilted attitude");
    CHECK(st.mode == CTRL_SAFE_DISARMED, "final mode is CTRL_SAFE_DISARMED");
}

int main(void) {
    scenario_a_no_pi_ever();
    scenario_b_pi_alive_throughout();
    scenario_c_pi_lost_mid_descent();
    scenario_d_passive_observer();

    if (g_failures == 0) {
        printf("\nALL TESTS PASSED\n");
        return 0;
    }
    printf("\n%d CHECK(S) FAILED\n", g_failures);
    return 1;
}
