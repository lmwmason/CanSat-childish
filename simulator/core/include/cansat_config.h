#ifndef CANSAT_CONFIG_H
#define CANSAT_CONFIG_H

#include <stdint.h>
#include <stdbool.h>
#include "cansat_types.h"

/*
 * Per-vehicle configuration. The mothership ("모체 캔위성") and each of
 * the 3 small wind-observer satellites ("소형 관측기") run the exact
 * same core/ code, just with a different cansat_config_t - see
 * sim/mother_sim.c vs sim/child_sim.c. Per the R&E plan: the mothership
 * carries IMU/GPS/baro/comm + a CO2 ejection device + folding wings; the
 * observers carry GPS/baro/temp-humidity/IMU/comm but NO actuators - they
 * fall passively under a drag membrane, following the wind so their GPS
 * tracks can be turned into a low-altitude wind vector field.
 */
typedef struct {
    const char *vehicle_name;

    /* Only the mothership has a Pi link + ELRS; the observers never do,
     * so has_pi_link=false pins them permanently in autonomous failsafe. */
    bool has_pi_link;
    uint32_t pi_link_timeout_ms;

    /* The observers have no DRV8874/control surfaces at all (passive
     * drag-membrane fall) - has_actuators=false skips stabilization
     * output entirely instead of computing a command nothing can act on. */
    bool has_actuators;

    /* Deployment sequencer (3 observer-release channels on the
     * mothership - the CO2 "3방향 동시 사출", 0 channels on an observer
     * since it has nothing further to deploy on its own). */
    int num_deploy_channels;
    float deploy_altitude_m[CANSAT_MAX_DEPLOY_CHANNELS];      /* primary trigger */
    uint32_t deploy_backup_timer_ms[CANSAT_MAX_DEPLOY_CHANNELS]; /* failsafe trigger if baro is unusable */
    uint32_t deploy_stagger_ms;                                /* 0 = simultaneous 3-direction ejection */

    float landing_altitude_m;
    float landing_vspeed_thresh_mps;
    uint32_t landing_confirm_ms;

    uint32_t telemetry_period_ms;
} cansat_config_t;

#endif /* CANSAT_CONFIG_H */
