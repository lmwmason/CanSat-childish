#ifndef CHILDCANSAT_FIRMWARE_MPU6050_H
#define CHILDCANSAT_FIRMWARE_MPU6050_H

#include <Arduino.h>

// MPU6050 driver using the on-chip DMP (MotionApps 2.0 firmware).
// The DMP fuses gyro + accel on the chip into a quaternion at 100 Hz (default), so the
// ATmega only reads a 42-byte FIFO packet. Uses only Wire. RAM use is ~70 bytes per object,
// no heap. Flash use is ~2 KB for the DMP image plus the driver code.
//
// Axes follow the chip's silkscreen. Units: g, deg/s, degrees.
// The sensor has no magnetometer, so yaw is relative to the start-up heading and drifts slowly.
class mpu6050
{
public:
    enum Status : uint8_t
    {
        OK = 0,
        ERROR_I2C,            // bus transaction failed
        ERROR_NOT_FOUND,      // no MPU6050 at this address (or wrong WHO_AM_I)
        ERROR_DMP_LOAD,       // DMP image failed read-back verification
        ERROR_NOT_INIT,       // begin() has not succeeded yet
        ERROR_NO_DATA,        // no complete DMP packet yet, just try again
        ERROR_FIFO_OVERFLOW,  // loop was too slow, FIFO was reset
        ERROR_BAD_PACKET,     // corrupt packet dropped, FIFO was reset
        ERROR_NOT_STILL       // calibrate(): board was moving or not lying flat
    };

    struct Vec3
    {
        float x, y, z;
    };

    // Hardware offset registers, in the chip's own units. Save these (e.g. to EEPROM)
    // after calibrate() to skip the calibration at the next power-up.
    struct Offsets
    {
        int16_t ax, ay, az, gx, gy, gz;
    };

    // I2C address: 0x68 (AD0 low) or 0x69 (AD0 high).
    explicit mpu6050(uint8_t address = 0x68);

    // Reset the chip, load the DMP and start it. Takes ~0.7 s. Wire is started here (400 kHz).
    // fifoDivisor sets the output rate: 200 / (1 + fifoDivisor) Hz. 1 = 100 Hz, 3 = 50 Hz.
    // The DMP needs ~10 s of standing still after this to settle its own gyro bias.
    Status begin(uint8_t fifoDivisor = 1);

    // Zero the gyro and accel offsets. Call after begin() with the board still and flat
    // (any one axis pointing up or down). Takes ~5 s and resets the DMP.
    // On ERROR_NOT_STILL the previous offsets are kept.
    Status calibrate();
    void getOffsets(Offsets& out);
    void setOffsets(const Offsets& in);

    // Poll the FIFO and decode the newest packet. Call at least every ~200 ms.
    // OK means new data is available; older packets that piled up are dropped.
    Status update();

    // ---- Noise reduction (applied to accel() and gyro() only) ----
    // Low-pass filter: out += alpha * (in - out). 1.0 = off, smaller = smoother but laggier.
    void setFilter(float alpha) { _alpha = constrain(alpha, 0.01f, 1.0f); }
    // Gyro rates smaller than this are reported as 0, hiding residual drift while at rest.
    void setGyroDeadband(float dps) { _deadband = dps; }

    // ---- Orientation (from the DMP, already fused and normalised) ----
    float qw() const { return _q[0]; }
    float qx() const { return _q[1]; }
    float qy() const { return _q[2]; }
    float qz() const { return _q[3]; }
    // out = {yaw, pitch, roll} in degrees.
    void ypr(float out[3]) const;
    Vec3 gravity() const;       // unit gravity vector in sensor frame

    // ---- Motion ----
    Vec3 accel() const;         // g, filtered, includes gravity
    Vec3 gyro() const;          // deg/s, filtered
    Vec3 linearAccel() const;   // g, gravity removed, sensor frame
    Vec3 worldAccel() const;    // g, gravity removed, world frame (z = up)
    float accelMagnitude() const; // g, ~1.0 at rest, ~0 in free fall

    // True after accelMagnitude() stayed under the threshold for enough consecutive packets.
    // Defaults: 0.35 g for 10 packets (100 ms at 100 Hz).
    void setFreeFall(float thresholdG, uint8_t packets)
    {
        _ffThreshold = thresholdG;
        _ffPackets = packets;
    }
    bool freeFall() const { return _ffCount >= _ffPackets; }

    // Die temperature in degrees C, or NAN if the read failed. Blocking I2C read.
    float temperature();

private:
    bool writeReg(uint8_t reg, uint8_t value);
    bool writeBit(uint8_t reg, uint8_t bit, bool value);
    bool readBytes(uint8_t reg, uint8_t* buf, uint8_t len);
    bool readFifo(uint8_t* buf, uint8_t len);
    bool selectMemory(uint8_t bank, uint8_t address);
    bool writeDmpImage();
    bool writeMemory(const uint8_t* data, uint8_t len, uint8_t bank, uint8_t address);
    void startDmp();
    void stopDmp();
    void resetFifo();
    bool readRaw(int16_t v[6]);
    Status decode(const uint8_t* pkt);

    uint8_t _addr;
    bool _ready;
    bool _fail;    // set by any failed I2C transaction
    bool _primed;  // filters hold a first sample

    float _q[4];   // w x y z
    float _a[3];   // filtered accel, g
    float _g[3];   // filtered gyro, deg/s
    float _alpha;
    float _deadband;
    float _ffThreshold;
    uint8_t _ffPackets;
    uint8_t _ffCount;
};

#endif
