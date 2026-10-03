#ifndef SIM_WORLD_H
#define SIM_WORLD_H

#include <stdint.h>
#include <stdbool.h>
#include <ode/ode.h>
#include "cansat_hal.h"
#include "cansat_types.h"
#include "cansat_fsm.h"

/*
 * Software stand-in for the real hardware: BNO055/BMP280/GPS, the two
 * DRV8874 actuator channels, the safety_io motor-power FET, the 3
 * deploy channels, and a byte-pipe standing in for the Pi UART link.
 *
 * The actual rigid-body mechanics (gravity, drag, wind force, actuator/
 * turbulence torque, ground contact) are simulated with the Open
 * Dynamics Engine (ODE) - a real, widely used rigid-body physics
 * library - rather than a hand-rolled integrator. This file only
 * supplies the forces/torques each tick and reads back ODE's resulting
 * position/velocity/orientation; ODE owns the actual integration and
 * ground-contact response.
 */
#define SIM_RX_QUEUE_SIZE 256
#define SIM_MAX_EXTRA_UDP_TARGETS 4

/* A child satellite listens for its mothership's telemetry on
 * SIM_CHILD_BASE_PORT + child_index (1, 2, 3). */
#define SIM_CHILD_BASE_PORT 41100

typedef struct {
    const char *vehicle_name;

    /* ODE rigid-body handles - one small free body (sphere) per vehicle,
     * falling under ODE's own gravity, plus a ground plane it actually
     * collides and settles on. mass_kg/radius_m are just enough to give
     * the body sane inertia; they don't need to be dimensionally
     * "correct" for a CanSat, only consistent. */
    dWorldID ode_world;
    dSpaceID ode_space;
    dJointGroupID ode_contacts;
    dGeomID ode_ground;
    dBodyID ode_body;
    dGeomID ode_geom;
    float mass_kg;
    float radius_m;

    /* Cached copy of the body's current state, refreshed from ODE right
     * after each dWorldStep - the rest of this file (HAL callbacks,
     * telemetry, the carry/UDP mirroring) reads/writes these plain
     * fields rather than calling ODE accessors everywhere. */
    float altitude_m;
    float vspeed_mps;
    float terminal_vspeed_mps;   /* negative = descending; sets the drag coefficient */
    float roll_deg, pitch_deg;
    float roll_rate_dps, pitch_rate_dps;
    float x_m, y_m;
    float vx_mps, vy_mps;
    float humidity_pct;

    /* Per-vehicle turbulence gust state (an Auto-Regressive AR(1)
     * filtered-noise process per axis - a simplified Dryden-style
     * atmospheric turbulence model), applied as an extra force/torque
     * on top of the shared mean wind field. Each vehicle gets its own
     * realization (real turbulence at this scale differs body to body
     * even under the same mean wind), seeded from rng_state below. */
    float gust_x_mps, gust_y_mps, gust_z_mps;
    float gust_roll_dps, gust_pitch_dps;

    /* actuator/motor state, written by the HAL callbacks */
    float actuator[2];
    bool motors_enabled;
    bool deployed[CANSAT_MAX_DEPLOY_CHANNELS];

    /* operator-controlled fault injection */
    bool pi_link_enabled;     /* 'p' toggles: is the (simulated) Pi alive */
    bool sensor_fault_inject; /* 'f' toggles: IMU/baro report failure */

    /* fake-Pi -> STM32 UART byte queue (loopback within the sim) */
    uint8_t rx_queue[SIM_RX_QUEUE_SIZE];
    int rx_head, rx_tail;
    uint32_t next_fake_pi_send_ms;

    unsigned int rng_state;
    bool launched;

    /* Extra UDP fan-out destinations for hal_lora_send, in addition to
     * the usual viz port - the mothership uses this to also reach each
     * carried child's listener (see sim_world_add_udp_target). */
    int extra_udp_ports[SIM_MAX_EXTRA_UDP_TARGETS];
    int num_extra_udp_ports;

    /* Carried-child state: while carried, this world's altitude/vspeed/
     * roll/pitch are mirrored directly from the mothership's telemetry
     * instead of being simulated - it's physically still riding inside
     * the mothership, not flying on its own. See sim_world_start_carried. */
    bool carried;
    int carry_sock;          /* UDP socket listening for mothership telemetry, or -1 */
    int carry_deploy_channel; /* which of the mothership's 3 deploy bits to watch (0-2) */
} sim_world_t;

void sim_world_init(sim_world_t *w, const char *vehicle_name, float initial_altitude_m,
                     float terminal_vspeed_mps);

void sim_world_shutdown(sim_world_t *w);

/*
 * Randomized environment shared by every vehicle in one flight.
 *
 * Reads CANSAT_WIND_SEED from the environment once per process and uses
 * it to deterministically draw a mean wind profile (base speed/direction
 * at the ground, how much each grows/rotates with altitude), ground
 * temperature/humidity/pressure, and a turbulence intensity - all
 * "external conditions" per the request that nothing here be a fixed
 * constant. Because mother_sim and all 3 child_sim processes read the
 * SAME seed (./run.sh exports one shared value before launching all 4),
 * they independently compute the IDENTICAL mean wind field, which is
 * physically required - they are falling through the same air at the
 * same time. Per-vehicle turbulence (gusts) still differs, seeded from
 * each vehicle's own rng_state instead (see gust_* fields above).
 *
 * Safe/idempotent to call multiple times per process; only the first
 * call does anything.
 */
void sim_env_init(void);

/* Local wind (mean field only, no turbulence) at a given altitude,
 * using the randomized profile from sim_env_init(). */
void sim_env_wind(float altitude_m, float *wind_x_mps, float *wind_y_mps);

/* Ground-level values from the randomized environment, for logging
 * or printing at startup. */
float sim_env_ground_temp_c(void);
float sim_env_ground_humidity_pct(void);
float sim_env_sea_level_pressure_pa(void);

/* Advance the physics model by dt_s seconds. */
void sim_physics_step(sim_world_t *w, float dt_s);

/* One-shot attitude disturbance kick ('d' key), to watch failsafe recover. */
void sim_inject_disturbance(sim_world_t *w);

/* Only meaningful on the mothership: emits a HEARTBEAT (+ small
 * stabilizing ACTUATOR_CMD, standing in for real Pi mission code that
 * doesn't exist yet) into the sim UART queue while pi_link_enabled. */
void sim_fake_pi_tick(sim_world_t *w, uint32_t now_ms);

/* Populates a cansat_hal_t bound to this world (ctx = w). */
void sim_world_bind_hal(sim_world_t *w, cansat_hal_t *hal);

uint32_t sim_millis_now(void);

/* Triggers cansat_request_launch() and marks the physics model "in flight". */
void sim_do_launch(sim_world_t *w, cansat_t *c, uint32_t now_ms);

/* Mothership only: also fan out every telemetry line to 127.0.0.1:port
 * (in addition to the usual CANSAT_VIZ_PORT target). Used to reach each
 * carried child's listener socket. */
void sim_world_add_udp_target(sim_world_t *w, int port);

/* Child satellite only: call once before the run loop instead of
 * launching. Puts the world in "carried" mode (still riding inside the
 * mothership) and opens a listener on 127.0.0.1:my_port for the
 * mothership's telemetry, watching deploy channel `deploy_channel`
 * (0-2) to know when *this* child has actually been released. */
void sim_world_start_carried(sim_world_t *w, int my_port, int deploy_channel);

/*
 * Call once per loop tick (harmless no-op unless sim_world_start_carried
 * was used). While carried, mirrors altitude/vspeed/roll/pitch straight
 * from the mothership's telemetry - it hasn't separated yet, so it has
 * no flight of its own. The instant the mothership reports this child's
 * deploy channel as fired, it inherits that exact altitude/vspeed/
 * attitude as its own initial conditions, calls cansat_request_launch(),
 * and hands control to its own independent physics from then on.
 */
void sim_world_poll_carry(sim_world_t *w, cansat_t *c, uint32_t now_ms);

/*
 * Runs the interactive 100 Hz demo loop (fixed 10 ms sim steps, real-time
 * paced) shared by mother_sim and child_sim. Handles common keys:
 *   p = toggle simulated Pi link (only meaningful if has_pi_link)
 *   f = toggle IMU/baro fault injection
 *   d = inject a one-shot attitude disturbance
 *   l = force launch now (from STANDBY)
 *   q = quit
 * When use_fake_pi is true, a stand-in "fake Pi" heartbeat/command
 * generator feeds the sim UART queue while w->pi_link_enabled.
 */
void sim_run_loop(sim_world_t *w, cansat_t *c, bool has_pi_link, bool use_fake_pi,
                   bool auto_launch, uint32_t auto_launch_delay_ms);

/* Non-blocking single-key keyboard input, Linux/POSIX only. */
void kbd_raw_mode_enable(void);
void kbd_raw_mode_disable(void);
int kbd_getch_nonblock(void); /* returns -1 if nothing pending */

#endif /* SIM_WORLD_H */
