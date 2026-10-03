#ifndef TELEMETRY_H
#define TELEMETRY_H

#include <stdint.h>
#include "cansat_types.h"
#include "cansat_hal.h"

typedef struct {
    uint32_t last_send_ms;
} telemetry_t;

void telemetry_init(telemetry_t *t);
void telemetry_update(telemetry_t *t, const cansat_hal_t *hal, const cansat_status_t *status,
                       uint32_t period_ms, uint32_t now_ms, const char *vehicle_name);

#endif /* TELEMETRY_H */
