#include "deploy.h"
#include <string.h>

void deploy_init(deploy_sequencer_t *d) {
    memset(d, 0, sizeof(*d));
}

void deploy_on_descent_start(deploy_sequencer_t *d, uint32_t now_ms) {
    d->descent_start_ms = now_ms;
    d->descent_start_set = true;
    for (int i = 0; i < CANSAT_MAX_DEPLOY_CHANNELS; i++) {
        d->ch[i].armed = true;
        d->ch[i].fired = false;
    }
}

void deploy_update(deploy_sequencer_t *d, const cansat_config_t *cfg, const cansat_hal_t *hal,
                    float altitude_m, bool altitude_valid, uint32_t now_ms,
                    bool deployed_out[CANSAT_MAX_DEPLOY_CHANNELS]) {
    if (!d->descent_start_set) return;

    int n = cfg->num_deploy_channels;
    if (n > CANSAT_MAX_DEPLOY_CHANNELS) n = CANSAT_MAX_DEPLOY_CHANNELS;

    for (int i = 0; i < n; i++) {
        deploy_channel_state_t *c = &d->ch[i];
        if (!c->armed || c->fired) {
            if (deployed_out) deployed_out[i] = c->fired;
            continue;
        }

        uint32_t stagger_ready_ms = d->descent_start_ms + (uint32_t)i * cfg->deploy_stagger_ms;
        if (now_ms < stagger_ready_ms) {
            if (deployed_out) deployed_out[i] = false;
            continue;
        }

        bool primary_trigger = altitude_valid && (altitude_m <= cfg->deploy_altitude_m[i]);
        bool backup_trigger = (now_ms - d->descent_start_ms) >= cfg->deploy_backup_timer_ms[i];

        if (primary_trigger || backup_trigger) {
            if (hal->deploy_fire) hal->deploy_fire(hal->ctx, i);
            c->fired = true;
        }
        if (deployed_out) deployed_out[i] = c->fired;
    }
}
