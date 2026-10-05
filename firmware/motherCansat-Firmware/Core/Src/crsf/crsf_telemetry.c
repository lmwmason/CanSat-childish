#include "crsf_telemetry.h"
#include "crsf.h"
#include <stdio.h>
#include <math.h>

#define DEG2RAD 0.01745329252f

typedef enum { TLM_ATTITUDE = 0, TLM_GPS, TLM_MODE, TLM_STATUS, TLM_COUNT } TlmFrame;

static uint32_t g_nextMs[TLM_COUNT];
static const uint32_t g_periodMs[TLM_COUNT] = {
    CRSF_TLM_ATTITUDE_MS, CRSF_TLM_GPS_MS, CRSF_TLM_MODE_MS, CRSF_TLM_STATUS_MS
};

static uint8_t *put16(uint8_t *p, uint16_t v) { *p++ = (uint8_t)(v >> 8); *p++ = (uint8_t)v; return p; }
static uint8_t *put32(uint8_t *p, uint32_t v)
{
    *p++ = (uint8_t)(v >> 24); *p++ = (uint8_t)(v >> 16); *p++ = (uint8_t)(v >> 8); *p++ = (uint8_t)v;
    return p;
}

static int16_t clamp16(float v)
{
    if (v > 32767.0f) return 32767;
    if (v < -32768.0f) return -32768;
    return (int16_t)lroundf(v);
}

static uint16_t clampu16(float v)
{
    if (v < 0.0f) return 0;
    if (v > 65535.0f) return 65535;
    return (uint16_t)lroundf(v);
}

static int8_t clamp8(float v)
{
    if (v > 127.0f) return 127;
    if (v < -128.0f) return -128;
    return (int8_t)lroundf(v);
}

static void send_attitude(const CrsfTelemetryData *d)
{
    uint8_t b[6], *p = b;
    p = put16(p, (uint16_t)clamp16(d->pitchDeg * DEG2RAD * 10000.0f));
    p = put16(p, (uint16_t)clamp16(d->rollDeg * DEG2RAD * 10000.0f));
    p = put16(p, (uint16_t)clamp16(d->yawDeg * DEG2RAD * 10000.0f));
    crsf_send_frame(0x1E, b, (uint8_t)(p - b));
}

static void send_gps(const CrsfTelemetryData *d)
{
    uint8_t b[15], *p = b;
    p = put32(p, (uint32_t)(int32_t)lround(d->lat * 1e7));
    p = put32(p, (uint32_t)(int32_t)lround(d->lon * 1e7));
    p = put16(p, clampu16(d->speedMs * 3.6f * 10.0f));
    p = put16(p, clampu16(d->courseDeg * 100.0f));
    p = put16(p, clampu16(d->altM + 1000.0f));
    *p++ = d->satellites;
    crsf_send_frame(0x02, b, (uint8_t)(p - b));
}

static void send_mode(const CrsfTelemetryData *d)
{
    uint8_t b[24];
    int n = snprintf((char *)b, sizeof(b), "%s %s%s",
                     d->missionName ? d->missionName : "?",
                     d->elevonName ? d->elevonName : "?",
                     (d->flags & CRSF_TLM_FLAG_LANDED) ? " LAND" : "");
    if (n < 0) return;
    if (n > (int)sizeof(b) - 1) n = (int)sizeof(b) - 1;
    b[n] = 0;
    crsf_send_frame(0x21, b, (uint8_t)(n + 1));   /* includes the terminating NUL */
}

static void send_status(const CrsfTelemetryData *d, uint32_t nowMs)
{
    uint8_t b[23], *p = b;
    *p++ = 1;
    *p++ = d->missionState;
    *p++ = d->elevonMode;
    *p++ = d->flags;
    *p++ = d->imuCount;
    p = put16(p, clampu16(d->accelMag * 100.0f));
    p = put16(p, (uint16_t)clamp16(d->yawRateDps * 10.0f));
    *p++ = (uint8_t)clamp8(d->wheelCmd * 100.0f);
    *p++ = (uint8_t)clamp8(d->rollTargetDeg);
    p = put16(p, clampu16(d->navDistM));
    p = put16(p, clampu16(d->desiredCourseDeg * 10.0f));
    p = put16(p, d->leftUs);
    p = put16(p, d->rightUs);
    p = put32(p, nowMs);
    crsf_send_frame(CRSF_TLM_CUSTOM_TYPE, b, (uint8_t)(p - b));
}

void crsf_telemetry_update(const CrsfTelemetryData *d, uint32_t nowMs)
{
    /* pick the most overdue frame, send only that one */
    int pick = -1;
    int32_t worst = 0;
    for (int i = 0; i < TLM_COUNT; i++) {
        int32_t late = (int32_t)(nowMs - g_nextMs[i]);
        if (late >= 0 && (pick < 0 || late > worst)) { pick = i; worst = late; }
    }
    if (pick < 0) return;
    g_nextMs[pick] = nowMs + g_periodMs[pick];

    switch (pick) {
    case TLM_ATTITUDE: send_attitude(d); break;
    case TLM_GPS:      send_gps(d); break;
    case TLM_MODE:     send_mode(d); break;
    default:           send_status(d, nowMs); break;
    }
}
