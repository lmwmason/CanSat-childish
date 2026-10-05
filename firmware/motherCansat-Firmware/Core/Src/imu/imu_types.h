#ifndef IMU_TYPES_H
#define IMU_TYPES_H

/* One sample from an IMU. Accel in m/s^2 (includes gravity), gyro in deg/s. */
typedef struct {
    float ax, ay, az;
    float gx, gy, gz;
} ImuSample;

#define IMU_GRAVITY 9.80665f

#endif /* IMU_TYPES_H */
