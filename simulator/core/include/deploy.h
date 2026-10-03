#ifndef DEPLOY_H
#define DEPLOY_H

#include <stdint.h>
#include <stdbool.h>
#include "cansat_types.h"
#include "cansat_config.h"
#include "cansat_hal.h"

/*
 * Deployment sequencer: releases each channel once, at whichever
 * comes first of:
 *   - primary trigger: measured altitude has dropped to
 *     cfg->deploy_altitude_m[i] ("safe altitude"), or
 *   - backup trigger: cfg->deploy_backup_timer_ms[i] has elapsed
 *     since descent start, regardless of sensor state.
 *
 * The backup timer is itself a failsafe: if the barometer is dead
 * (altitude_valid stays false), channels still fire on schedule
 * instead of staying stuck inside the mothership forever.
 * Channels are staggered by cfg->deploy_stagger_ms so the 3 child
 * satellites don't separate on top of each other.
 */
typedef struct {
    bool armed;
    bool fired;
} deploy_channel_state_t;

typedef struct {
    deploy_channel_state_t ch[CANSAT_MAX_DEPLOY_CHANNELS];
    uint32_t descent_start_ms;
    bool descent_start_set;
} deploy_sequencer_t;

void deploy_init(deploy_sequencer_t *d);
void deploy_on_descent_start(deploy_sequencer_t *d, uint32_t now_ms);
void deploy_update(deploy_sequencer_t *d, const cansat_config_t *cfg, const cansat_hal_t *hal,
                    float altitude_m, bool altitude_valid, uint32_t now_ms,
                    bool deployed_out[CANSAT_MAX_DEPLOY_CHANNELS]);

#endif /* DEPLOY_H */
