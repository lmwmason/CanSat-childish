#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "cansat_fsm.h"
#include "sim_world.h"

/*
 * Small wind-observer satellite demo ("소형 관측기"), per the R&E plan:
 * GPS + baro + temp/humidity + IMU + comms, but NO actuators at all - it
 * has no DRV8874, no control surfaces, nothing to steer with. It just
 * falls passively under a Y-Zipper drag membrane, following the wind so
 * its GPS track (combined with baro altitude) can be turned into a
 * low-altitude wind vector field. By default it starts "carried" inside
 * the mothership (see sim_world_start_carried): it rides at the
 * mothership's own altitude/attitude, doing nothing of its own, until
 * the mothership's telemetry reports THIS channel deployed (the CO2
 * 3-direction simultaneous ejection) - at which point it inherits that
 * exact altitude/velocity/attitude, gets a brief outward ejection kick
 * in its assigned direction, and then just drifts with the wind.
 *
 * Run all 3 side by side, e.g. in separate terminals, together with
 * ./build/mother_sim (order doesn't matter - it just waits):
 *   ./build/child_sim 1
 *   ./build/child_sim 2
 *   ./build/child_sim 3
 *
 * Pass --standalone to instead free-fall on a fixed timer from ~300 m
 * without needing a mothership running (useful for testing this sim in
 * isolation - not how a real flight behaves).
 */
int main(int argc, char **argv) {
    int idx = 1;
    bool standalone = false;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--standalone") == 0) {
            standalone = true;
        } else {
            int v = atoi(argv[i]);
            if (v >= 1 && v <= 3) idx = v;
        }
    }

    static char name_buf[16];
    snprintf(name_buf, sizeof(name_buf), "child-%d", idx);

    cansat_config_t cfg = {
        .vehicle_name = name_buf,
        .has_pi_link = false, /* observers never have a Pi/ELRS */
        .pi_link_timeout_ms = 0,
        .has_actuators = false, /* passive drag-membrane fall - nothing to steer with */
        .num_deploy_channels = 0, /* nothing further for an observer to deploy */
        .deploy_stagger_ms = 0,
        .landing_altitude_m = 3.0f,
        .landing_vspeed_thresh_mps = 1.0f,
        .landing_confirm_ms = 800,
        .telemetry_period_ms = 150, /* fast enough for smooth live-3D viz */
    };

    sim_world_t world;
    if (standalone) {
        /* Old isolated-testing behavior: just free-fall from ~300 m on a
         * fixed timer, no mothership needed. */
        sim_world_init(&world, cfg.vehicle_name, 300.0f - (idx - 1) * 3.0f, -8.0f);
    } else {
        /* Rides at the mothership's start altitude (600 m in mother_sim.c)
         * until the real separation event arrives over the network. */
        sim_world_init(&world, cfg.vehicle_name, 600.0f, -8.0f);
    }

    cansat_hal_t hal;
    sim_world_bind_hal(&world, &hal);

    cansat_t cansat;
    cansat_init(&cansat, &cfg, &hal, 0);

    if (!standalone) {
        sim_world_start_carried(&world, SIM_CHILD_BASE_PORT + idx, /*deploy_channel=*/idx - 1);
    }

    sim_run_loop(&world, &cansat, cfg.has_pi_link, /*use_fake_pi=*/false,
                 /*auto_launch=*/standalone,
                 /*auto_launch_delay_ms=*/(uint32_t)(500 + (idx - 1) * 800));
    sim_world_shutdown(&world);
    return 0;
}
