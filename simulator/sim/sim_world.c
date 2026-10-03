#define _POSIX_C_SOURCE 200809L
#include "sim_world.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <math.h>
#include <time.h>
#include <unistd.h>
#include <termios.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#define DEG2RAD 0.017453293f
#define RAD2DEG 57.29577951f
#define PI_F 3.14159265358979323846f

/* Rotational "control" gains, now expressed as angular ACCELERATIONS
 * that get multiplied by the sphere's moment of inertia into a real
 * torque handed to ODE - ODE does the actual angular-velocity and
 * orientation (quaternion) integration from there. */
#define ACTUATOR_ANGACCEL_RADSS (40.0f * DEG2RAD) /* per unit actuator */
#define RATE_DAMPING 0.6f                          /* 1/s, dimensionless decay rate */

static float randf01_state(unsigned int *state) {
    return (float)rand_r(state) / (float)RAND_MAX;
}

static float randf01(sim_world_t *w) {
    return randf01_state(&w->rng_state);
}

/* Standard normal via Box-Muller, for a properly-distributed turbulence
 * process instead of uniform noise. */
static float randn(sim_world_t *w) {
    float u1 = randf01(w);
    if (u1 < 1e-6f) u1 = 1e-6f;
    float u2 = randf01(w);
    return sqrtf(-2.0f * logf(u1)) * cosf(2.0f * PI_F * u2);
}

/* ======================================================================
 * Randomized shared environment (wind + ground weather). See sim_world.h
 * for why this must be derived from a SHARED seed across all 4 processes
 * rather than each one rolling its own - they fly through the same air.
 * ==================================================================== */

typedef struct {
    bool ready;
    unsigned long seed;
    float wind_base_speed_mps;
    float wind_base_dir_deg;
    float wind_shear_per_100m;
    float wind_turn_deg_per_100m;
    float turbulence_sigma_mps;
    float ground_temp_c;
    float ground_humidity_pct;
    float sea_level_pressure_pa;
} sim_env_t;

static sim_env_t g_env;

void sim_env_init(void) {
    if (g_env.ready) return;

    unsigned long seed;
    const char *seed_str = getenv("CANSAT_WIND_SEED");
    if (seed_str && seed_str[0]) {
        seed = strtoul(seed_str, NULL, 10);
    } else {
        seed = 42; /* fixed, not time-based: unrelated processes must still agree */
        fprintf(stderr,
                "[env] CANSAT_WIND_SEED not set - defaulting to %lu so independently-launched\n"
                "      vehicles still share one wind field. Run via ./run.sh all (or export\n"
                "      CANSAT_WIND_SEED yourself before launching each terminal) for a fresh\n"
                "      random environment shared across all 4 processes.\n",
                seed);
    }
    g_env.seed = seed;

    unsigned int rng = (unsigned int)seed;
    g_env.wind_base_speed_mps = 1.0f + randf01_state(&rng) * 4.0f;        /* 1..5 m/s at the ground */
    g_env.wind_base_dir_deg = randf01_state(&rng) * 360.0f;
    g_env.wind_shear_per_100m = 0.3f + randf01_state(&rng) * 1.2f;        /* 0.3..1.5 (m/s)/100m */
    g_env.wind_turn_deg_per_100m = (randf01_state(&rng) - 0.5f) * 6.0f;   /* -3..+3 deg/100m, either way */
    g_env.turbulence_sigma_mps = 0.3f + randf01_state(&rng) * 1.2f;       /* gust intensity, 0.3..1.5 m/s */
    g_env.ground_temp_c = 5.0f + randf01_state(&rng) * 20.0f;             /* 5..25 C */
    g_env.ground_humidity_pct = 40.0f + randf01_state(&rng) * 50.0f;      /* 40..90 % */
    g_env.sea_level_pressure_pa = 100500.0f + randf01_state(&rng) * 1500.0f; /* 100500..102000 Pa */

    fprintf(stderr,
            "[env] seed=%lu wind=%.1fm/s@%.0fdeg shear=%.2f(m/s)/100m turn=%.2fdeg/100m "
            "turbulence=%.2fm/s ground=%.1fC %.0f%%RH %.0fPa\n",
            g_env.seed, g_env.wind_base_speed_mps, g_env.wind_base_dir_deg,
            g_env.wind_shear_per_100m, g_env.wind_turn_deg_per_100m, g_env.turbulence_sigma_mps,
            g_env.ground_temp_c, g_env.ground_humidity_pct, g_env.sea_level_pressure_pa);

    g_env.ready = true;
}

void sim_env_wind(float altitude_m, float *wind_x_mps, float *wind_y_mps) {
    sim_env_init();
    float hundreds = altitude_m * 0.01f;
    float speed = g_env.wind_base_speed_mps + g_env.wind_shear_per_100m * hundreds;
    float dir_deg = g_env.wind_base_dir_deg + g_env.wind_turn_deg_per_100m * hundreds;
    float dir_rad = dir_deg * DEG2RAD;
    *wind_x_mps = speed * cosf(dir_rad);
    *wind_y_mps = speed * sinf(dir_rad);
}

float sim_env_ground_temp_c(void) { sim_env_init(); return g_env.ground_temp_c; }
float sim_env_ground_humidity_pct(void) { sim_env_init(); return g_env.ground_humidity_pct; }
float sim_env_sea_level_pressure_pa(void) { sim_env_init(); return g_env.sea_level_pressure_pa; }

/* ======================================================================
 * ODE rigid-body setup. One free-falling sphere per vehicle, colliding
 * with a ground plane - the actual translational AND rotational motion
 * (including quaternion orientation integration and ground contact
 * response) is computed by ODE, not by us.
 * ==================================================================== */

static bool s_ode_ready = false;

static void ensure_ode_ready(void) {
    if (s_ode_ready) return;
    dInitODE2(0);
    s_ode_ready = true;
}

static void euler_to_quat(float roll_rad, float pitch_rad, dQuaternion out) {
    /* yaw is not modeled in this demo (fixed at 0) */
    float cr = cosf(roll_rad * 0.5f), sr = sinf(roll_rad * 0.5f);
    float cp = cosf(pitch_rad * 0.5f), sp = sinf(pitch_rad * 0.5f);
    out[0] = (dReal)(cr * cp);   /* w */
    out[1] = (dReal)(sr * cp);   /* x */
    out[2] = (dReal)(cr * sp);   /* y */
    out[3] = (dReal)(-sr * sp);  /* z */
}

static void quat_to_roll_pitch(const dReal *q, float *roll_rad, float *pitch_rad) {
    float qw = (float)q[0], qx = (float)q[1], qy = (float)q[2], qz = (float)q[3];
    *roll_rad = atan2f(2.0f * (qw * qx + qy * qz), 1.0f - 2.0f * (qx * qx + qy * qy));
    float sinp = 2.0f * (qw * qy - qz * qx);
    if (sinp > 1.0f) sinp = 1.0f;
    if (sinp < -1.0f) sinp = -1.0f;
    *pitch_rad = asinf(sinp);
}

static void near_callback(void *data, dGeomID o1, dGeomID o2) {
    sim_world_t *w = (sim_world_t *)data;
    dBodyID b1 = dGeomGetBody(o1);
    dBodyID b2 = dGeomGetBody(o2);

    dContact contact;
    memset(&contact, 0, sizeof(contact));
    contact.surface.mode = dContactBounce | dContactSoftCFM;
    /* Finite, not dInfinity: an "infinite friction" contact resists any
     * sliding by rolling instead, and a landed vehicle still has a
     * steady horizontal wind-drag force pushing on it - with no slip
     * allowed, that torques the sphere into an ever-accelerating spin
     * (nothing opposes rotation specifically, only translation). Real
     * friction sliding under load, not idealized rolling, is what
     * actually stops that. */
    contact.surface.mu = 0.6;
    contact.surface.bounce = 0.05;     /* almost no bounce - a soft touchdown */
    contact.surface.bounce_vel = 0.1;
    contact.surface.soft_cfm = 0.001;

    int n = dCollide(o1, o2, 1, &contact.geom, sizeof(dContact));
    if (n > 0) {
        dJointID j = dJointCreateContact(w->ode_world, w->ode_contacts, &contact);
        dJointAttach(j, b1, b2);
    }
}

/* Pushes the cached scalar state (position/velocity/roll/pitch) into
 * the ODE body as its new authoritative state - used once at the exact
 * moment a carried observer separates and starts flying under its own
 * dynamics (it was mirroring the mothership's telemetry, not simulating
 * anything, until this point). */
static void sync_cache_to_body(sim_world_t *w) {
    dBodySetPosition(w->ode_body, (dReal)w->x_m, (dReal)w->y_m, (dReal)w->altitude_m);
    dBodySetLinearVel(w->ode_body, (dReal)w->vx_mps, (dReal)w->vy_mps, (dReal)w->vspeed_mps);
    dQuaternion q;
    euler_to_quat(w->roll_deg * DEG2RAD, w->pitch_deg * DEG2RAD, q);
    dBodySetQuaternion(w->ode_body, q);
    dBodySetAngularVel(w->ode_body, 0, 0, 0);
}

void sim_world_init(sim_world_t *w, const char *vehicle_name, float initial_altitude_m,
                     float terminal_vspeed_mps) {
    memset(w, 0, sizeof(*w));
    sim_env_init();
    ensure_ode_ready();

    w->vehicle_name = vehicle_name;
    w->altitude_m = initial_altitude_m;
    w->terminal_vspeed_mps = terminal_vspeed_mps;
    w->pi_link_enabled = true;
    w->rng_state = (unsigned int)time(NULL) ^ (unsigned int)(intptr_t)w;
    w->carry_sock = -1;
    w->humidity_pct = sim_env_ground_humidity_pct() - 0.03f * initial_altitude_m;

    w->mass_kg = 0.05f;   /* arbitrary but consistent - see header comment */
    w->radius_m = 0.05f;

    w->ode_world = dWorldCreate();
    dWorldSetGravity(w->ode_world, 0, 0, -9.81);
    /* Exactly 2 geoms live in this space (one body + the ground plane)
     * forever, so a naive O(n^2) simple space is both sufficient and
     * required: dHashSpaceCreate's bucket-level math chokes on a plane's
     * effectively-infinite AABB ("ODE INTERNAL ERROR 1: assertion
     * aabbBound..."), which a simple space never computes at all. */
    w->ode_space = dSimpleSpaceCreate(0);
    w->ode_contacts = dJointGroupCreate(0);
    w->ode_ground = dCreatePlane(w->ode_space, 0, 0, 1, 0);

    w->ode_body = dBodyCreate(w->ode_world);
    dMass m;
    dMassSetSphereTotal(&m, w->mass_kg, w->radius_m);
    dBodySetMass(w->ode_body, &m);
    w->ode_geom = dCreateSphere(w->ode_space, w->radius_m);
    dGeomSetBody(w->ode_geom, w->ode_body);

    dBodySetPosition(w->ode_body, 0, 0, (dReal)initial_altitude_m);
    dBodySetLinearVel(w->ode_body, 0, 0, 0);
    dBodySetAngularVel(w->ode_body, 0, 0, 0);

    /* Engine-native ANGULAR damping/cap as a safety net on top of the
     * explicit RATE_DAMPING torque term below - guards against a resting
     * body still being pushed by wind drag spinning up without bound
     * (see the mu comment in near_callback). Deliberately no linear
     * damping: it would multiplicatively bleed off velocity every step
     * on top of the drag force below, undermining the terminal-velocity
     * calibration that force is tuned for (this cost a lot of debugging
     * time to notice - do not re-add it). */
    dBodySetAngularDamping(w->ode_body, 0.3);
    dBodySetMaxAngularSpeed(w->ode_body, 30.0); /* rad/s hard cap, ~1720 deg/s */
}

void sim_world_shutdown(sim_world_t *w) {
    if (w->carry_sock >= 0) close(w->carry_sock);
    if (w->ode_geom) dGeomDestroy(w->ode_geom);
    if (w->ode_body) dBodyDestroy(w->ode_body);
    if (w->ode_contacts) dJointGroupDestroy(w->ode_contacts);
    if (w->ode_ground) dGeomDestroy(w->ode_ground);
    if (w->ode_space) dSpaceDestroy(w->ode_space);
    if (w->ode_world) dWorldDestroy(w->ode_world);
    /* dCloseODE() intentionally not called: one world per process, and
     * the process exits right after - no point risking a double-close. */
}

void sim_world_add_udp_target(sim_world_t *w, int port) {
    if (w->num_extra_udp_ports >= SIM_MAX_EXTRA_UDP_TARGETS) return;
    w->extra_udp_ports[w->num_extra_udp_ports++] = port;
}

void sim_inject_disturbance(sim_world_t *w) {
    const dReal *av = dBodyGetAngularVel(w->ode_body);
    float dwx = (randf01(w) - 0.5f) * 240.0f * DEG2RAD;
    float dwy = (randf01(w) - 0.5f) * 240.0f * DEG2RAD;
    dBodySetAngularVel(w->ode_body, av[0] + dwx, av[1] + dwy, av[2]);
}

void sim_physics_step(sim_world_t *w, float dt_s) {
    if (!w->launched) return;

    float altitude = w->altitude_m; /* from the previous step's readback, used for this step's forces */

    /* Mean wind field (shared, randomized once per session) plus this
     * vehicle's own turbulence realization (Ornstein-Uhlenbeck / AR(1)
     * filtered noise - a simplified Dryden-style gust model, properly
     * random rather than a fixed constant). */
    float wind_x, wind_y;
    sim_env_wind(altitude, &wind_x, &wind_y);

    float tau_lin = 2.0f;
    float alpha_lin = expf(-dt_s / tau_lin);
    float sigma_lin = g_env.turbulence_sigma_mps;
    w->gust_x_mps = w->gust_x_mps * alpha_lin + sigma_lin * sqrtf(1.0f - alpha_lin * alpha_lin) * randn(w);
    w->gust_y_mps = w->gust_y_mps * alpha_lin + sigma_lin * sqrtf(1.0f - alpha_lin * alpha_lin) * randn(w);
    w->gust_z_mps = w->gust_z_mps * alpha_lin + (sigma_lin * 0.3f) * sqrtf(1.0f - alpha_lin * alpha_lin) * randn(w);

    float tau_rot = 0.3f;
    float alpha_rot = expf(-dt_s / tau_rot);
    float sigma_rot = sigma_lin * 0.02f; /* rad/s^2 - small: this is a torque disturbance,
                                           * and a correlated gust near the attitude loop's
                                           * own resonance drives a much bigger swing than
                                           * its raw sigma would suggest, so keep it modest */
    w->gust_roll_dps = w->gust_roll_dps * alpha_rot + sigma_rot * sqrtf(1.0f - alpha_rot * alpha_rot) * randn(w);
    w->gust_pitch_dps = w->gust_pitch_dps * alpha_rot + sigma_rot * sqrtf(1.0f - alpha_rot * alpha_rot) * randn(w);

    float total_wind_x = wind_x + w->gust_x_mps;
    float total_wind_y = wind_y + w->gust_y_mps;
    float total_wind_z = w->gust_z_mps; /* no mean vertical wind, gust only */

    const dReal *vel = dBodyGetLinearVel(w->ode_body);

    /* Linear drag calibrated so that, in still air, this vehicle settles
     * at exactly cfg's terminal_vspeed_mps: at steady state
     * drag_coeff * |Vt| = mass * g  =>  drag_coeff = mass*g/|Vt|. Applying
     * the SAME coefficient horizontally is what makes the vehicle "follow
     * the wind" (a bigger drag membrane means both a slower fall AND a
     * quicker, more pronounced response to wind - see the R&E plan). */
    float drag_coeff = w->mass_kg * 9.81f / fmaxf(0.1f, fabsf(w->terminal_vspeed_mps));
    float rel_x = (float)vel[0] - total_wind_x;
    float rel_y = (float)vel[1] - total_wind_y;
    float rel_z = (float)vel[2] - total_wind_z;
    dBodyAddForce(w->ode_body, -drag_coeff * rel_x, -drag_coeff * rel_y, -drag_coeff * rel_z);

    /* Rotational control/disturbance torque = I * desired angular accel,
     * so ODE integrates both angular velocity and orientation itself.
     * actuator[i] is already a corrective command (see failsafe_compute:
     * output = -kp*error), so it must add POSITIVE angular acceleration
     * here for negative feedback - do not flip this sign. */
    float inertia = (2.0f / 5.0f) * w->mass_kg * w->radius_m * w->radius_m;
    const dReal *avel = dBodyGetAngularVel(w->ode_body);
    float motor_scale = w->motors_enabled ? 1.0f : 0.0f;
    float angacc_x = ACTUATOR_ANGACCEL_RADSS * w->actuator[1] * motor_scale
                      - RATE_DAMPING * (float)avel[0] + w->gust_roll_dps;
    float angacc_y = ACTUATOR_ANGACCEL_RADSS * w->actuator[0] * motor_scale
                      - RATE_DAMPING * (float)avel[1] + w->gust_pitch_dps;
    dBodyAddTorque(w->ode_body, inertia * angacc_x, inertia * angacc_y, 0.0);

    dSpaceCollide(w->ode_space, w, near_callback);
    dWorldStep(w->ode_world, dt_s);
    dJointGroupEmpty(w->ode_contacts);

    /* Read the engine's result back into the plain cache fields the
     * rest of this file (HAL callbacks, telemetry, carry mirroring) uses. */
    const dReal *pos = dBodyGetPosition(w->ode_body);
    const dReal *vel2 = dBodyGetLinearVel(w->ode_body);
    const dReal *avel2 = dBodyGetAngularVel(w->ode_body);
    const dReal *quat = dBodyGetQuaternion(w->ode_body);

    w->x_m = (float)pos[0];
    w->y_m = (float)pos[1];
    w->altitude_m = fmaxf(0.0f, (float)pos[2]);
    w->vx_mps = (float)vel2[0];
    w->vy_mps = (float)vel2[1];
    w->vspeed_mps = (float)vel2[2];
    w->roll_rate_dps = (float)avel2[0] * RAD2DEG;
    w->pitch_rate_dps = (float)avel2[1] * RAD2DEG;

    float roll_rad, pitch_rad;
    quat_to_roll_pitch(quat, &roll_rad, &pitch_rad);
    w->roll_deg = roll_rad * RAD2DEG;
    w->pitch_deg = pitch_rad * RAD2DEG;

    /* environment: humidity falls off with altitude, matching the
     * observer's onboard temp/humidity sensor. */
    w->humidity_pct = sim_env_ground_humidity_pct() - 0.03f * w->altitude_m + (randf01(w) - 0.5f) * 2.0f;
    if (w->humidity_pct < 5.0f) w->humidity_pct = 5.0f;
    if (w->humidity_pct > 100.0f) w->humidity_pct = 100.0f;
}

static void rx_push(sim_world_t *w, uint8_t b) {
    int next = (w->rx_tail + 1) % SIM_RX_QUEUE_SIZE;
    if (next == w->rx_head) return; /* queue full, drop */
    w->rx_queue[w->rx_tail] = b;
    w->rx_tail = next;
}

static void rx_push_frame(sim_world_t *w, uint8_t type, const uint8_t *payload, uint8_t len) {
    rx_push(w, 0xAA);
    rx_push(w, type);
    rx_push(w, len);
    uint8_t chk = (uint8_t)(type ^ len);
    for (int i = 0; i < len; i++) { rx_push(w, payload[i]); chk ^= payload[i]; }
    rx_push(w, chk);
}

void sim_fake_pi_tick(sim_world_t *w, uint32_t now_ms) {
    if (!w->pi_link_enabled) return;
    if (now_ms < w->next_fake_pi_send_ms) return;
    w->next_fake_pi_send_ms = now_ms + 100;

    rx_push_frame(w, 0x01 /* PI_LINK_FRAME_HEARTBEAT */, NULL, 0);

    /* Stand-in for real Pi mission code (not implemented yet): a
     * trivial stabilizing command so CTRL_PI_GUIDED isn't a silent
     * no-op in the demo. Real Pi-side logic is a separate task. */
    int16_t cmd0 = (int16_t)(-30.0f * w->pitch_deg);
    int16_t cmd1 = (int16_t)(-30.0f * w->roll_deg);
    if (cmd0 > 1000) cmd0 = 1000;
    if (cmd0 < -1000) cmd0 = -1000;
    if (cmd1 > 1000) cmd1 = 1000;
    if (cmd1 < -1000) cmd1 = -1000;
    uint8_t payload[4];
    memcpy(&payload[0], &cmd0, 2);
    memcpy(&payload[2], &cmd1, 2);
    rx_push_frame(w, 0x02 /* PI_LINK_FRAME_ACTUATOR_CMD */, payload, 4);
}

/* ---- HAL callbacks ---- */

static bool hal_read_imu(void *ctx, imu_sample_t *out) {
    sim_world_t *w = (sim_world_t *)ctx;
    if (w->sensor_fault_inject) return false;

    float roll_r = w->roll_deg * DEG2RAD;
    float pitch_r = w->pitch_deg * DEG2RAD;
    out->roll_deg = w->roll_deg;
    out->pitch_deg = w->pitch_deg;
    out->yaw_deg = 0.0f;
    out->gyro_x_dps = w->roll_rate_dps;
    out->gyro_y_dps = w->pitch_rate_dps;
    out->gyro_z_dps = 0.0f;
    out->accel_x_g = -sinf(pitch_r);
    out->accel_y_g = sinf(roll_r) * cosf(pitch_r);
    out->accel_z_g = cosf(roll_r) * cosf(pitch_r);
    return true;
}

static bool hal_read_baro(void *ctx, baro_sample_t *out) {
    sim_world_t *w = (sim_world_t *)ctx;
    if (w->sensor_fault_inject) return false;
    float p0 = sim_env_sea_level_pressure_pa();
    out->altitude_m = w->altitude_m;
    out->pressure_pa = p0 * powf(1.0f - 2.25577e-5f * w->altitude_m, 5.25588f);
    out->temperature_c = sim_env_ground_temp_c() - 0.0065f * w->altitude_m; /* tropospheric lapse rate */
    out->humidity_pct = w->humidity_pct;
    return true;
}

static bool hal_read_gps(void *ctx, gps_sample_t *out) {
    sim_world_t *w = (sim_world_t *)ctx;
    if (w->sensor_fault_inject) return false;
    out->lat_deg = 37.5665;  /* stub reference point - only the local_x/y offsets are used */
    out->lon_deg = 126.9780;
    out->alt_m = w->altitude_m;
    out->fix = true;
    out->local_x_m = w->x_m;
    out->local_y_m = w->y_m;
    return true;
}

static int hal_pi_uart_read(void *ctx, uint8_t *buf, int max_len) {
    sim_world_t *w = (sim_world_t *)ctx;
    int n = 0;
    while (w->rx_head != w->rx_tail && n < max_len) {
        buf[n++] = w->rx_queue[w->rx_head];
        w->rx_head = (w->rx_head + 1) % SIM_RX_QUEUE_SIZE;
    }
    return n;
}

static void hal_set_actuator(void *ctx, int channel, float value_norm) {
    sim_world_t *w = (sim_world_t *)ctx;
    if (channel < 0 || channel > 1) return;
    w->actuator[channel] = value_norm;
}

static void hal_set_motor_power(void *ctx, bool enable) {
    ((sim_world_t *)ctx)->motors_enabled = enable;
}

static void hal_deploy_fire(void *ctx, int channel) {
    sim_world_t *w = (sim_world_t *)ctx;
    if (channel < 0 || channel >= CANSAT_MAX_DEPLOY_CHANNELS) return;
    w->deployed[channel] = true;
    fprintf(stderr, "\n>>> [%s] DEPLOY channel %d fired at altitude %.1f m <<<\n",
            w->vehicle_name, channel, w->altitude_m);
}

/* Best-effort UDP fan-out of every LoRa telemetry line, so the Python
 * live-3D viewer (firmware/viz/visualize.py) can render mother + all 3
 * children in real time. Purely additive: if nothing's listening on
 * 127.0.0.1:<CANSAT_VIZ_PORT|41000>, sendto() just drops the packet. */
static int s_udp_sock = -1;
static struct sockaddr_in s_udp_addr;

static void udp_viz_ensure_init(void) {
    if (s_udp_sock >= 0) return;
    s_udp_sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (s_udp_sock < 0) return;
    int port = 41000;
    const char *p = getenv("CANSAT_VIZ_PORT");
    if (p) {
        int v = atoi(p);
        if (v > 0 && v < 65536) port = v;
    }
    memset(&s_udp_addr, 0, sizeof(s_udp_addr));
    s_udp_addr.sin_family = AF_INET;
    s_udp_addr.sin_port = htons((uint16_t)port);
    inet_pton(AF_INET, "127.0.0.1", &s_udp_addr.sin_addr);
}

static void hal_lora_send(void *ctx, const uint8_t *buf, int len) {
    sim_world_t *w = (sim_world_t *)ctx;
    printf("[LORA %-10s] %.*s\n", w->vehicle_name, len, (const char *)buf);
    fflush(stdout);

    udp_viz_ensure_init();
    if (s_udp_sock >= 0) {
        (void)sendto(s_udp_sock, buf, (size_t)len, 0,
                      (struct sockaddr *)&s_udp_addr, sizeof(s_udp_addr));

        for (int i = 0; i < w->num_extra_udp_ports; i++) {
            struct sockaddr_in extra;
            memset(&extra, 0, sizeof(extra));
            extra.sin_family = AF_INET;
            extra.sin_port = htons((uint16_t)w->extra_udp_ports[i]);
            inet_pton(AF_INET, "127.0.0.1", &extra.sin_addr);
            (void)sendto(s_udp_sock, buf, (size_t)len, 0,
                          (struct sockaddr *)&extra, sizeof(extra));
        }
    }
}

static uint32_t hal_millis(void *ctx) {
    (void)ctx;
    return sim_millis_now();
}

void sim_world_bind_hal(sim_world_t *w, cansat_hal_t *hal) {
    memset(hal, 0, sizeof(*hal));
    hal->read_imu = hal_read_imu;
    hal->read_baro = hal_read_baro;
    hal->read_gps = hal_read_gps;
    hal->pi_uart_read = hal_pi_uart_read;
    hal->set_actuator = hal_set_actuator;
    hal->set_motor_power = hal_set_motor_power;
    hal->deploy_fire = hal_deploy_fire;
    hal->lora_send = hal_lora_send;
    hal->millis = hal_millis;
    hal->ctx = w;
}

uint32_t sim_millis_now(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint32_t)(ts.tv_sec * 1000L + ts.tv_nsec / 1000000L);
}

/* ---- keyboard ---- */

static struct termios s_orig_termios;
static bool s_raw_enabled = false;

void kbd_raw_mode_enable(void) {
    if (!isatty(STDIN_FILENO)) return;
    tcgetattr(STDIN_FILENO, &s_orig_termios);
    struct termios raw = s_orig_termios;
    raw.c_lflag &= (tcflag_t)~(ICANON | ECHO);
    raw.c_cc[VMIN] = 0;
    raw.c_cc[VTIME] = 0;
    tcsetattr(STDIN_FILENO, TCSANOW, &raw);
    int flags = fcntl(STDIN_FILENO, F_GETFL, 0);
    fcntl(STDIN_FILENO, F_SETFL, flags | O_NONBLOCK);
    s_raw_enabled = true;
}

void kbd_raw_mode_disable(void) {
    if (!s_raw_enabled) return;
    tcsetattr(STDIN_FILENO, TCSANOW, &s_orig_termios);
    s_raw_enabled = false;
}

int kbd_getch_nonblock(void) {
    unsigned char c;
    ssize_t n = read(STDIN_FILENO, &c, 1);
    if (n == 1) return c;
    return -1;
}

/* ---- shared run loop ---- */

void sim_do_launch(sim_world_t *w, cansat_t *c, uint32_t now_ms) {
    (void)w;
    /* No-op unless the FSM is actually in MISSION_STANDBY; sim_run_loop
     * confirms the transition afterwards from cansat_get_status() rather
     * than assuming this call succeeded (it may be requested slightly
     * before the BOOT->STANDBY self-test delay elapses). */
    cansat_request_launch(c, now_ms);
}

void sim_world_start_carried(sim_world_t *w, int my_port, int deploy_channel) {
    w->carried = true;
    w->carry_deploy_channel = deploy_channel;

    w->carry_sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (w->carry_sock < 0) return;

    int opt = 1;
    setsockopt(w->carry_sock, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons((uint16_t)my_port);
    inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);

    if (bind(w->carry_sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        close(w->carry_sock);
        w->carry_sock = -1;
        return;
    }
    int flags = fcntl(w->carry_sock, F_GETFL, 0);
    fcntl(w->carry_sock, F_SETFL, flags | O_NONBLOCK);
}

static bool parse_float_field(const char *line, const char *key, float *out) {
    const char *p = strstr(line, key);
    if (!p) return false;
    return sscanf(p + strlen(key), "%f", out) == 1;
}

void sim_world_poll_carry(sim_world_t *w, cansat_t *c, uint32_t now_ms) {
    if (w->carry_sock < 0 || !w->carried) return;

    char buf[256];
    bool released = false;

    for (;;) {
        ssize_t n = recv(w->carry_sock, buf, sizeof(buf) - 1, 0);
        if (n <= 0) break;
        buf[n] = '\0';
        if (strncmp(buf, "mothership,", 11) != 0) continue;

        /* Still riding inside the mothership: our altitude/attitude/
         * position ARE its altitude/attitude/position, not something we
         * simulate ourselves. */
        parse_float_field(buf, "alt=", &w->altitude_m);
        parse_float_field(buf, "vs=", &w->vspeed_mps);
        parse_float_field(buf, "roll=", &w->roll_deg);
        parse_float_field(buf, "pitch=", &w->pitch_deg);
        parse_float_field(buf, "x=", &w->x_m);
        parse_float_field(buf, "y=", &w->y_m);

        const char *dep = strstr(buf, "dep=");
        if (dep && strlen(dep + 4) >= 3) {
            char bit = dep[4 + w->carry_deploy_channel];
            if (bit == '1') released = true;
        }
    }

    if (released) {
        w->carried = false;
        w->launched = true; /* now flying on our own, seeded from the separation state above */

        /* CO2 3-direction simultaneous ejection: each of the 3 channels
         * is fired outward ~120 degrees apart, giving each observer a
         * distinct starting point before it settles into following the
         * local wind (see sim_env_wind()/sim_physics_step). */
        float eject_speed_mps = 6.0f;
        float dir_rad = (float)w->carry_deploy_channel * 120.0f * DEG2RAD;
        w->vx_mps = eject_speed_mps * cosf(dir_rad);
        w->vy_mps = eject_speed_mps * sinf(dir_rad);

        sync_cache_to_body(w); /* hand the inherited + kicked state to ODE */

        cansat_request_launch(c, now_ms);
        printf(">>> [%s] SEPARATED from mothership at alt=%.1f m vs=%.2f roll=%.1f pitch=%.1f (ejected @ %.0f deg)\n",
               w->vehicle_name, w->altitude_m, w->vspeed_mps, w->roll_deg, w->pitch_deg,
               (float)w->carry_deploy_channel * 120.0f);
    }
}

void sim_run_loop(sim_world_t *w, cansat_t *c, bool has_pi_link, bool use_fake_pi,
                   bool auto_launch, uint32_t auto_launch_delay_ms) {
    printf("== %s sim ==  keys: [l]aunch  [p]i-link toggle  [f]ault inject toggle  [d]isturb  [q]uit\n",
           w->vehicle_name);
    if (!has_pi_link) {
        printf("(%s has no Pi link at all - always autonomous failsafe once launched)\n", w->vehicle_name);
    }
    if (w->carried) {
        printf("(%s is riding inside the mothership - waiting for real separation on deploy channel %d;"
               " press 'l' to override manually)\n", w->vehicle_name, w->carry_deploy_channel);
    }

    kbd_raw_mode_enable();
    uint32_t sim_time_ms = 0;
    bool launch_requested = false;
    bool running = true;

    while (running) {
        int key = kbd_getch_nonblock();
        switch (key) {
        case 'q': case 'Q':
            running = false;
            break;
        case 'l': case 'L':
            if (w->carried) {
                w->carried = false; /* manual override of the network-driven separation */
                sync_cache_to_body(w);
                printf(">>> [%s] manual launch overrides carried mode\n", w->vehicle_name);
            }
            sim_do_launch(w, c, sim_time_ms);
            launch_requested = true;
            break;
        case 'p': case 'P':
            if (has_pi_link) {
                w->pi_link_enabled = !w->pi_link_enabled;
                printf(">>> [%s] Pi link %s\n", w->vehicle_name,
                       w->pi_link_enabled ? "RESTORED" : "CUT (simulating no Pi code / crash)");
            } else {
                printf("(%s: no Pi link to toggle)\n", w->vehicle_name);
            }
            break;
        case 'f': case 'F':
            w->sensor_fault_inject = !w->sensor_fault_inject;
            printf(">>> [%s] sensor fault injection %s\n", w->vehicle_name,
                   w->sensor_fault_inject ? "ON" : "OFF");
            break;
        case 'd': case 'D':
            sim_inject_disturbance(w);
            printf(">>> [%s] disturbance injected\n", w->vehicle_name);
            break;
        default:
            break;
        }

        if (auto_launch && !launch_requested && sim_time_ms >= auto_launch_delay_ms) {
            sim_do_launch(w, c, sim_time_ms);
            launch_requested = true;
        } else if (launch_requested && !w->launched) {
            /* First attempt may have landed while still MISSION_BOOT
             * (self-test not finished yet) - keep retrying; this is a
             * no-op once the FSM is out of MISSION_STANDBY. */
            cansat_request_launch(c, sim_time_ms);
        }

        sim_world_poll_carry(w, c, sim_time_ms);
        if (use_fake_pi) sim_fake_pi_tick(w, sim_time_ms);

        cansat_tick(c, sim_time_ms);
        sim_physics_step(w, 0.01f);

        cansat_status_t st;
        cansat_get_status(c, &st);

        if (!w->launched && (st.state == MISSION_DESCENT || st.state == MISSION_LANDED)) {
            w->launched = true;
            printf(">>> [%s] LAUNCH confirmed at t=%u ms\n", w->vehicle_name, sim_time_ms);
        }

        if (st.state == MISSION_LANDED && !st.motors_enabled && st.mode == CTRL_SAFE_DISARMED) {
            static bool announced = false; /* per-process; fine, one vehicle per process */
            if (!announced) {
                printf(">>> [%s] SAFE LANDED (pi_alive=%d) - motors disarmed, beacon only\n",
                       w->vehicle_name, st.pi_alive);
                announced = true;
            }
        }

        sim_time_ms += 10;
        struct timespec req = {0, 10L * 1000000L};
        nanosleep(&req, NULL);
    }

    kbd_raw_mode_disable();
    printf("\n[%s] sim stopped.\n", w->vehicle_name);
}
