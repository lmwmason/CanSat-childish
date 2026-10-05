#ifndef GPS_H
#define GPS_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include "stm32f4xx_hal.h"

/* u-blox NEO-6M over its DDC (I2C) port, address 0x42, default NMEA output.
 * Note: many NEO-6M breakout boards only wire the UART pins. The DDC pins
 * (SDA/SCL) must be connected for this to work. */
#define GPS_I2C_ADDR      0x42
#define GPS_POLL_MS       25u      /* poll the receiver this often */
#define GPS_CHUNK_BYTES   32       /* bytes read per poll (keeps I2C busy time short) */
#define GPS_RETRY_MS      1000u    /* re-probe a missing receiver this often */
#define GPS_FIX_TIMEOUT_MS 3000u   /* fix older than this is treated as lost */

typedef struct {
    I2C_HandleTypeDef *hi2c;
    uint8_t  present;
    uint32_t nextPollMs;

    /* NMEA line assembly */
    char     line[100];
    uint8_t  lineLen;

    /* latest data */
    uint8_t  fix;            /* RMC status A */
    uint8_t  satellites;
    double   lat, lon;       /* degrees, + = N / E */
    float    altM;
    float    speedMs;        /* ground speed */
    float    courseDeg;      /* course over ground, 0..360 (valid when speed is high enough) */
    uint32_t fixTimeMs;      /* tick of last valid RMC */
    uint32_t fixSeq;         /* increments on every valid RMC */
} Gps;

void    gps_init(Gps *g, I2C_HandleTypeDef *hi2c);
/* Call often (every loop). Reads pending bytes when GPS_POLL_MS has passed. */
void    gps_poll(Gps *g, uint32_t nowMs);
/* 1 if there is a valid, recent fix. */
uint8_t gps_has_fix(const Gps *g, uint32_t nowMs);

/* NMEA parser entry point (also usable from a UART). */
void    gps_feed_byte(Gps *g, char c, uint32_t nowMs);

#ifdef __cplusplus
}
#endif

#endif /* GPS_H */
