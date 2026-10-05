#ifndef CRSF_TELEMETRY_H
#define CRSF_TELEMETRY_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

/* Telemetry sent down the CRSF link (receiver -> Crossfire module -> radio / ground PC).
 *
 * Frames (all big-endian, standard CRSF framing):
 *   0x1E attitude    : pitch, roll, yaw  int16 each, rad * 10000
 *   0x02 GPS         : lat, lon int32 (deg * 1e7), speed uint16 (km/h * 10),
 *                      heading uint16 (deg * 100), altitude uint16 (m + 1000), sats uint8
 *   0x21 flight mode : text, e.g. "SPIN AUTO LAND"  (mission state, elevon mode, landed)
 *   0x7F mother status (custom, layout below)
 *
 * Custom 0x7F payload (big-endian):
 *   [0]  u8   version (1)
 *   [1]  u8   mission state   (MissionState enum)
 *   [2]  u8   elevon mode     (ElevonMode enum)
 *   [3]  u8   flags: b0 dropping, b1 landed, b2 wings ejected, b3 door open,
 *                    b4 gps fix, b5 AUX1 on, b6 IMUs disagree, b7 nav active
 *   [4]  u8   working IMU count
 *   [5]  u16  accel magnitude, m/s^2 * 100
 *   [7]  i16  yaw rate, deg/s * 10
 *   [9]  i8   wheel command * 100  (-100..100)
 *   [10] i8   roll target, deg
 *   [11] u16  distance to home, m
 *   [13] u16  desired course, deg * 10
 *   [15] u16  left elevon pulse, us
 *   [17] u16  right elevon pulse, us
 *   [19] u32  uptime, ms
 *
 * Bandwidth of the link is small (about 100 B/s depending on the link mode).
 * If your link drops the custom frame, the three standard frames still arrive. */

#define CRSF_TLM_CUSTOM_TYPE     0x7F
#define CRSF_TLM_ATTITUDE_MS     250u
#define CRSF_TLM_GPS_MS          1000u
#define CRSF_TLM_MODE_MS         1000u
#define CRSF_TLM_STATUS_MS       500u

#define CRSF_TLM_FLAG_DROPPING   (1u << 0)
#define CRSF_TLM_FLAG_LANDED     (1u << 1)
#define CRSF_TLM_FLAG_WINGS      (1u << 2)
#define CRSF_TLM_FLAG_DOOR       (1u << 3)
#define CRSF_TLM_FLAG_GPS_FIX    (1u << 4)
#define CRSF_TLM_FLAG_AUX1       (1u << 5)
#define CRSF_TLM_FLAG_IMU_DISAGREE (1u << 6)
#define CRSF_TLM_FLAG_NAV_ACTIVE (1u << 7)

/* Latest values, filled by the main loop. */
typedef struct {
    float    rollDeg, pitchDeg, yawDeg;
    double   lat, lon;
    float    altM, speedMs, courseDeg;
    uint8_t  satellites;
    uint8_t  missionState, elevonMode;
    const char *missionName;
    const char *elevonName;
    uint8_t  flags;
    uint8_t  imuCount;
    float    accelMag, yawRateDps;
    float    wheelCmd, rollTargetDeg;
    float    navDistM, desiredCourseDeg;
    uint16_t leftUs, rightUs;
} CrsfTelemetryData;

/* Call every main-loop iteration. Sends at most one frame per call (the most overdue one). */
void crsf_telemetry_update(const CrsfTelemetryData *d, uint32_t nowMs);

#ifdef __cplusplus
}
#endif

#endif /* CRSF_TELEMETRY_H */
