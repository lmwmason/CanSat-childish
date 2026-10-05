#include "gps.h"
#include <stdlib.h>
#include <string.h>

#define REG_BYTES_AVAIL_H 0xFD
#define REG_STREAM        0xFF
#define I2C_TIMEOUT_MS    5
#define KNOTS_TO_MS       0.514444f

static uint8_t hex(char c)
{
    if (c >= '0' && c <= '9') return (uint8_t)(c - '0');
    if (c >= 'A' && c <= 'F') return (uint8_t)(c - 'A' + 10);
    if (c >= 'a' && c <= 'f') return (uint8_t)(c - 'a' + 10);
    return 0;
}

/* ddmm.mmmm (or dddmm.mmmm) -> degrees */
static double nmea_to_deg(const char *s)
{
    double v = atof(s);
    double deg = (double)((int)(v / 100.0));
    return deg + (v - deg * 100.0) / 60.0;
}

/* Splits in place on ',' (and the '*' before the checksum). Returns field count. */
static int split(char *s, char *f[], int max)
{
    int n = 0;
    f[n++] = s;
    for (; *s && n < max; s++) {
        if (*s == ',' || *s == '*') {
            *s = 0;
            f[n++] = s + 1;
        }
    }
    return n;
}

static void parse_line(Gps *g, char *line, uint32_t nowMs)
{
    /* line starts with '$', checksum is XOR of everything between '$' and '*' */
    char *star = strchr(line, '*');
    if (!star || line[0] != '$' || strlen(star) < 3) return;

    uint8_t sum = 0;
    for (char *p = line + 1; p < star; p++) sum ^= (uint8_t)*p;
    if (sum != (uint8_t)((hex(star[1]) << 4) | hex(star[2]))) return;

    char *f[20];
    int n = split(line, f, 20);
    if (n < 7 || strlen(f[0]) < 6) return;
    const char *type = f[0] + 3;          /* skip "$GP" / "$GN" */

    if (strncmp(type, "RMC", 3) == 0 && n >= 9) {
        if (f[2][0] == 'A' && f[3][0] && f[5][0]) {
            g->fix = 1;
            g->lat = nmea_to_deg(f[3]) * (f[4][0] == 'S' ? -1.0 : 1.0);
            g->lon = nmea_to_deg(f[5]) * (f[6][0] == 'W' ? -1.0 : 1.0);
            g->speedMs = (float)atof(f[7]) * KNOTS_TO_MS;
            g->courseDeg = (float)atof(f[8]);
            g->fixTimeMs = nowMs;
            g->fixSeq++;
        } else {
            g->fix = 0;
        }
    } else if (strncmp(type, "GGA", 3) == 0 && n >= 10) {
        g->satellites = (uint8_t)atoi(f[7]);
        if (f[9][0]) g->altM = (float)atof(f[9]);
    }
}

void gps_feed_byte(Gps *g, char c, uint32_t nowMs)
{
    if (c == '$') {
        g->lineLen = 0;
    }
    if (c == '\n' || c == '\r') {
        if (g->lineLen > 0) {
            g->line[g->lineLen] = 0;
            parse_line(g, g->line, nowMs);
        }
        g->lineLen = 0;
        return;
    }
    if (g->lineLen < sizeof(g->line) - 1) g->line[g->lineLen++] = c;
    else g->lineLen = 0;                  /* overlong garbage, resync */
}

static uint8_t probe(Gps *g)
{
    uint8_t b[2];
    return HAL_I2C_Mem_Read(g->hi2c, GPS_I2C_ADDR << 1, REG_BYTES_AVAIL_H,
                            I2C_MEMADD_SIZE_8BIT, b, 2, I2C_TIMEOUT_MS) == HAL_OK;
}

void gps_init(Gps *g, I2C_HandleTypeDef *hi2c)
{
    memset(g, 0, sizeof(*g));
    g->hi2c = hi2c;
    g->present = probe(g);
}

void gps_poll(Gps *g, uint32_t nowMs)
{
    if ((int32_t)(nowMs - g->nextPollMs) < 0) return;

    if (!g->present) {
        g->nextPollMs = nowMs + GPS_RETRY_MS;
        g->present = probe(g);
        return;
    }
    g->nextPollMs = nowMs + GPS_POLL_MS;

    uint8_t cnt[2];
    if (HAL_I2C_Mem_Read(g->hi2c, GPS_I2C_ADDR << 1, REG_BYTES_AVAIL_H,
                         I2C_MEMADD_SIZE_8BIT, cnt, 2, I2C_TIMEOUT_MS) != HAL_OK) {
        g->present = 0;
        return;
    }
    uint16_t avail = (uint16_t)((cnt[0] << 8) | cnt[1]);
    if (avail == 0 || avail == 0xFFFF) return;
    if (avail > GPS_CHUNK_BYTES) avail = GPS_CHUNK_BYTES;

    uint8_t buf[GPS_CHUNK_BYTES];
    if (HAL_I2C_Mem_Read(g->hi2c, GPS_I2C_ADDR << 1, REG_STREAM,
                         I2C_MEMADD_SIZE_8BIT, buf, avail, I2C_TIMEOUT_MS) != HAL_OK) {
        g->present = 0;
        return;
    }
    for (uint16_t i = 0; i < avail; i++) {
        if (buf[i] == 0xFF) continue;     /* DDC pads with 0xFF when empty */
        gps_feed_byte(g, (char)buf[i], nowMs);
    }
}

uint8_t gps_has_fix(const Gps *g, uint32_t nowMs)
{
    return g->fix && (nowMs - g->fixTimeMs) < GPS_FIX_TIMEOUT_MS;
}
