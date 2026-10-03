#include "telemetry.h"
#include <stdio.h>

void telemetry_init(telemetry_t *t) {
    t->last_send_ms = 0;
}

void telemetry_update(telemetry_t *t, const cansat_hal_t *hal, const cansat_status_t *status,
                       uint32_t period_ms, uint32_t now_ms, const char *vehicle_name) {
    if (t->last_send_ms != 0 && (now_ms - t->last_send_ms) < period_ms) return;
    t->last_send_ms = now_ms;

    char buf[224];
    int n = snprintf(buf, sizeof(buf),
        "%s,t=%u,state=%d,mode=%d,pi=%d,fault=%d,alt=%.1f,vs=%.2f,roll=%.1f,pitch=%.1f,motors=%d,dep=%d%d%d,"
        "x=%.1f,y=%.1f,fix=%d,hum=%.1f",
        vehicle_name, status->uptime_ms, status->state, status->mode,
        status->pi_alive, status->sensor_fault, status->altitude_m, status->vspeed_mps,
        status->roll_deg, status->pitch_deg, status->motors_enabled,
        status->deployed[0], status->deployed[1], status->deployed[2],
        status->pos_x_m, status->pos_y_m, status->gps_fix, status->humidity_pct);

    if (hal->lora_send && n > 0) hal->lora_send(hal->ctx, (const uint8_t *)buf, n);
}
