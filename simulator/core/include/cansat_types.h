#ifndef CANSAT_TYPES_H
#define CANSAT_TYPES_H

#include <stdint.h>
#include <stdbool.h>

#define CANSAT_MAX_DEPLOY_CHANNELS 3

typedef struct {
    float roll_deg, pitch_deg, yaw_deg;
    float gyro_x_dps, gyro_y_dps, gyro_z_dps;
    float accel_x_g, accel_y_g, accel_z_g;
} imu_sample_t;

typedef struct {
    float pressure_pa;
    float altitude_m;
    float temperature_c;
    float humidity_pct; /* small observers carry a temp/humidity sensor */
} baro_sample_t;

typedef struct {
    double lat_deg, lon_deg;
    float alt_m;
    bool fix;
    /* Flat-earth East/North offset in meters from the launch point. A
     * real port would derive this from lat/lon via a local reference;
     * this sim reports it directly so wind-drift trajectories (the
     * actual R&E deliverable - a low-altitude wind vector field built
     * from observer GPS tracks) are easy to log/plot without redoing
     * geodesy for a demo. */
    float local_x_m, local_y_m;
} gps_sample_t;

typedef enum {
    MISSION_BOOT = 0,
    MISSION_STANDBY,
    MISSION_DESCENT,
    MISSION_LANDED
} mission_state_t;

typedef enum {
    CTRL_SAFE_DISARMED = 0,
    CTRL_PI_GUIDED,
    CTRL_FAILSAFE_AUTONOMOUS
} control_mode_t;

/* Snapshot of everything the outside world (telemetry, sim UI, ...) needs. */
typedef struct {
    mission_state_t state;
    control_mode_t mode;
    bool pi_alive;
    bool sensor_fault;
    bool motors_enabled;
    float actuator_out[2];
    float altitude_m;
    float vspeed_mps;
    float roll_deg, pitch_deg;
    bool deployed[CANSAT_MAX_DEPLOY_CHANNELS];
    uint32_t uptime_ms;
    bool gps_fix;
    float pos_x_m, pos_y_m; /* see gps_sample_t.local_x_m/local_y_m */
    float humidity_pct;
} cansat_status_t;

#endif /* CANSAT_TYPES_H */
