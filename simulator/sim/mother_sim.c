#include <stdio.h>
#include "cansat_fsm.h"
#include "sim_world.h"

/*
 * Mothership ("모체 캔위성") demo, per the R&E plan: dropped from a
 * drone at 600 m, hands control to a (simulated) Pi over UART while the
 * Pi link is alive, fires its CO2 ejection device to release all 3
 * small wind-observer satellites SIMULTANEOUS in 3 directions
 * (deploy_stagger_ms=0) at ~300 m AGL, and - if the Pi link ever drops
 * out - falls back to onboard-only wing/attitude stabilization and
 * disarms its own actuators once landed with no Pi present.
 */
int main(void) {
    cansat_config_t cfg = {
        .vehicle_name = "mothership",
        .has_pi_link = true,
        .pi_link_timeout_ms = 500,
        .has_actuators = true, /* folding-wing / attitude control surfaces */
        .num_deploy_channels = 3,
        .deploy_altitude_m = {300.0f, 300.0f, 300.0f},
        /* Backup net only if the barometer dies: must sit safely beyond
         * the ~50 s the primary altitude trigger normally takes to reach
         * 300 m from a 600 m start at -6 m/s, or it fires prematurely. */
        .deploy_backup_timer_ms = {90000, 90000, 90000},
        .deploy_stagger_ms = 0, /* CO2 3방향 동시 사출: all 3 fire together */
        .landing_altitude_m = 5.0f,
        .landing_vspeed_thresh_mps = 1.0f,
        .landing_confirm_ms = 1000,
        .telemetry_period_ms = 150, /* fast enough for smooth live-3D viz */
    };

    sim_world_t world;
    sim_world_init(&world, cfg.vehicle_name, 600.0f, -6.0f);

    /* Fan out our telemetry to each carried child's listener too, so
     * they can ride along at our altitude/attitude and see the instant
     * we actually fire their deploy channel - see sim_world_start_carried
     * in child_sim.c. */
    for (int i = 1; i <= 3; i++) sim_world_add_udp_target(&world, SIM_CHILD_BASE_PORT + i);

    cansat_hal_t hal;
    sim_world_bind_hal(&world, &hal);

    cansat_t cansat;
    cansat_init(&cansat, &cfg, &hal, 0);

    sim_run_loop(&world, &cansat, cfg.has_pi_link, /*use_fake_pi=*/true,
                 /*auto_launch=*/true, /*auto_launch_delay_ms=*/1500);
    sim_world_shutdown(&world);
    return 0;
}
