#include "mpu6050.h"

#include <Wire.h>
#include "dmp_firmware.h"

namespace
{
    // Registers
    constexpr uint8_t REG_XG_OFFS_TC = 0x00;
    constexpr uint8_t REG_XA_OFFS_H = 0x06;     // X, Y, Z accel offsets, 2 bytes each, 2 apart
    constexpr uint8_t REG_XG_OFFS_USRH = 0x13;  // X, Y, Z gyro offsets, 2 bytes each
    constexpr uint8_t REG_SMPLRT_DIV = 0x19;
    constexpr uint8_t REG_CONFIG = 0x1A;
    constexpr uint8_t REG_GYRO_CONFIG = 0x1B;
    constexpr uint8_t REG_ACCEL_CONFIG = 0x1C;
    constexpr uint8_t REG_MOT_THR = 0x1F;
    constexpr uint8_t REG_MOT_DUR = 0x20;
    constexpr uint8_t REG_ZRMOT_THR = 0x21;
    constexpr uint8_t REG_ZRMOT_DUR = 0x22;
    constexpr uint8_t REG_I2C_SLV0_ADDR = 0x25;
    constexpr uint8_t REG_INT_ENABLE = 0x38;
    constexpr uint8_t REG_INT_STATUS = 0x3A;
    constexpr uint8_t REG_ACCEL_XOUT_H = 0x3B;
    constexpr uint8_t REG_TEMP_OUT_H = 0x41;
    constexpr uint8_t REG_SIGNAL_PATH_RESET = 0x68;
    constexpr uint8_t REG_USER_CTRL = 0x6A;
    constexpr uint8_t REG_PWR_MGMT_1 = 0x6B;
    constexpr uint8_t REG_BANK_SEL = 0x6D;
    constexpr uint8_t REG_MEM_START_ADDR = 0x6E;
    constexpr uint8_t REG_MEM_R_W = 0x6F;
    constexpr uint8_t REG_DMP_CFG_1 = 0x70;
    constexpr uint8_t REG_DMP_CFG_2 = 0x71;
    constexpr uint8_t REG_FIFO_COUNT_H = 0x72;
    constexpr uint8_t REG_FIFO_R_W = 0x74;
    constexpr uint8_t REG_WHO_AM_I = 0x75;

    // USER_CTRL bits
    constexpr uint8_t BIT_FIFO_RESET = 2;
    constexpr uint8_t BIT_I2C_MST_RESET = 1;
    constexpr uint8_t BIT_DMP_RESET = 3;
    constexpr uint8_t BIT_FIFO_EN = 6;
    constexpr uint8_t BIT_DMP_EN = 7;
    constexpr uint8_t BIT_I2C_MST_EN = 5;

    constexpr uint8_t PACKET_SIZE = 42;       // default MotionApps 2.0 packet
    constexpr uint8_t MEM_CHUNK = 16;         // fits easily in Wire's 32-byte buffer
    constexpr uint16_t FIFO_OVERFLOW_AT = 1000; // FIFO holds 1024 bytes

    // Scales (DMP is configured for +-2 g and +-2000 deg/s; +1 g = 8192 in the DMP packet)
    constexpr float QUAT_SCALE = 16384.0f;
    constexpr float ACCEL_PKT_SCALE = 8192.0f;
    constexpr float GYRO_SCALE = 16.4f;

    // Calibration
    constexpr uint8_t CAL_MAX_ITER = 15;
    constexpr uint8_t CAL_SAMPLES = 100;
    constexpr int16_t CAL_ONE_G = 16384;      // raw registers are +-2 g
    constexpr int16_t CAL_ACCEL_TOL = 16;     // ~1 mg
    constexpr int16_t CAL_GYRO_TOL = 2;       // ~0.12 deg/s

    inline int16_t s16(const uint8_t* p)
    {
        return (int16_t)(((uint16_t)p[0] << 8) | p[1]);
    }
}

mpu6050::mpu6050(uint8_t address)
    : _addr(address), _ready(false), _fail(false), _primed(false),
      _alpha(0.4f), _deadband(0.1f), _ffThreshold(0.35f), _ffPackets(10), _ffCount(0)
{
    _q[0] = 1.0f;
    _q[1] = _q[2] = _q[3] = 0.0f;
    _a[0] = _a[1] = _a[2] = 0.0f;
    _g[0] = _g[1] = _g[2] = 0.0f;
}

// ---------------------------------------------------------------- I2C helpers

bool mpu6050::writeReg(uint8_t reg, uint8_t value)
{
    Wire.beginTransmission(_addr);
    Wire.write(reg);
    Wire.write(value);
    if (Wire.endTransmission() != 0)
    {
        _fail = true;
        return false;
    }
    return true;
}

bool mpu6050::readBytes(uint8_t reg, uint8_t* buf, uint8_t len)
{
    Wire.beginTransmission(_addr);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0 || Wire.requestFrom(_addr, len) != len)
    {
        _fail = true;
        return false;
    }
    for (uint8_t i = 0; i < len; i++)
        buf[i] = Wire.read();
    return true;
}

bool mpu6050::writeBit(uint8_t reg, uint8_t bit, bool value)
{
    uint8_t v;
    if (!readBytes(reg, &v, 1))
        return false;
    v = value ? (v | (1 << bit)) : (v & ~(1 << bit));
    return writeReg(reg, v);
}

// FIFO_R_W does not auto-increment, so every chunk re-addresses the same register.
bool mpu6050::readFifo(uint8_t* buf, uint8_t len)
{
    while (len)
    {
        const uint8_t n = len > 32 ? 32 : len;
        if (!readBytes(REG_FIFO_R_W, buf, n))
            return false;
        buf += n;
        len -= n;
    }
    return true;
}

// ---------------------------------------------------------------- DMP memory

bool mpu6050::selectMemory(uint8_t bank, uint8_t address)
{
    return writeReg(REG_BANK_SEL, bank & 0x1F) && writeReg(REG_MEM_START_ADDR, address);
}

// Write len bytes (RAM) into DMP memory.
bool mpu6050::writeMemory(const uint8_t* data, uint8_t len, uint8_t bank, uint8_t address)
{
    if (!selectMemory(bank, address))
        return false;
    Wire.beginTransmission(_addr);
    Wire.write(REG_MEM_R_W);
    Wire.write(data, len);
    if (Wire.endTransmission() != 0)
    {
        _fail = true;
        return false;
    }
    return true;
}

// Upload the DMP image from flash, verifying every chunk by reading it back.
bool mpu6050::writeDmpImage()
{
    uint8_t chunk[MEM_CHUNK];
    uint8_t check[MEM_CHUNK];
    uint8_t bank = 0;
    uint8_t address = 0;

    for (uint16_t i = 0; i < MPU6050_DMP_CODE_SIZE;)
    {
        uint8_t n = MEM_CHUNK;
        if (i + n > MPU6050_DMP_CODE_SIZE)
            n = MPU6050_DMP_CODE_SIZE - i;
        if (n > 256 - address)    // do not cross a 256-byte bank boundary
            n = 256 - address;

        memcpy_P(chunk, mpu6050DmpFirmware + i, n);
        if (!writeMemory(chunk, n, bank, address))
            return false;

        if (!selectMemory(bank, address) || !readBytes(REG_MEM_R_W, check, n))
            return false;
        if (memcmp(chunk, check, n) != 0)
            return false;

        i += n;
        address += n;              // wraps to 0 at 256
        if (address == 0)
            bank++;
    }
    return true;
}

// ---------------------------------------------------------------- start-up

mpu6050::Status mpu6050::begin(uint8_t fifoDivisor)
{
    _ready = false;
    _primed = false;
    _fail = false;
    _ffCount = 0;

    Wire.begin();
    Wire.setClock(400000UL);
#ifdef WIRE_HAS_TIMEOUT
    Wire.setWireTimeout(3000, true); // never hang the flight code on a stuck bus
#endif

    uint8_t id = 0;
    if (!readBytes(REG_WHO_AM_I, &id, 1) || id != 0x68)
        return ERROR_NOT_FOUND;

    // Reset, wake, then follow the InvenSense DMP start-up sequence.
    writeReg(REG_PWR_MGMT_1, 0x80);
    delay(100);
    writeReg(REG_SIGNAL_PATH_RESET, 0x07);
    delay(100);
    writeReg(REG_PWR_MGMT_1, 0x00);
    delay(10);

    writeReg(REG_I2C_SLV0_ADDR, 0x7F);
    writeBit(REG_USER_CTRL, BIT_I2C_MST_EN, false);
    writeReg(REG_I2C_SLV0_ADDR, 0x68);
    writeBit(REG_USER_CTRL, BIT_I2C_MST_RESET, true);
    delay(20);

    writeReg(REG_PWR_MGMT_1, 0x03);        // clock from Z gyro PLL
    writeReg(REG_INT_ENABLE, 0x12);        // FIFO overflow + DMP interrupt flags
    writeReg(REG_SMPLRT_DIV, 4);           // 1 kHz / 5 = 200 Hz, DMP base rate
    writeReg(REG_CONFIG, 0x0B);            // ext sync TEMP_OUT_L, DLPF 42 Hz
    writeReg(REG_GYRO_CONFIG, 0x18);       // +-2000 deg/s
    writeReg(REG_ACCEL_CONFIG, 0x00);      // +-2 g
    if (_fail)
        return ERROR_I2C;

    if (!writeDmpImage())
        return _fail ? ERROR_I2C : ERROR_DMP_LOAD;

    // FIFO rate divisor lives inside the DMP image: bank 2, offset 0x16.
    const uint8_t rate[2] = {0x00, fifoDivisor};
    writeMemory(rate, 2, 0x02, 0x16);

    writeReg(REG_DMP_CFG_1, 0x03);         // DMP start address 0x0300
    writeReg(REG_DMP_CFG_2, 0x00);
    writeBit(REG_XG_OFFS_TC, 0, false);    // clear OTP bank valid

    writeReg(REG_MOT_THR, 2);
    writeReg(REG_ZRMOT_THR, 156);
    writeReg(REG_MOT_DUR, 80);
    writeReg(REG_ZRMOT_DUR, 0);
    if (_fail)
        return ERROR_I2C;

    startDmp();
    if (_fail)
        return ERROR_I2C;

    _ready = true;
    return OK;
}

void mpu6050::startDmp()
{
    writeBit(REG_USER_CTRL, BIT_FIFO_EN, true);
    writeBit(REG_USER_CTRL, BIT_DMP_RESET, true);
    writeBit(REG_USER_CTRL, BIT_DMP_EN, true);
    resetFifo();
    _primed = false;
    _ffCount = 0;
}

void mpu6050::stopDmp()
{
    writeBit(REG_USER_CTRL, BIT_DMP_EN, false);
    writeBit(REG_USER_CTRL, BIT_FIFO_EN, false);
}

void mpu6050::resetFifo()
{
    uint8_t status;
    writeBit(REG_USER_CTRL, BIT_FIFO_RESET, true);
    readBytes(REG_INT_STATUS, &status, 1); // reading clears the interrupt flags
}

// ---------------------------------------------------------------- calibration

void mpu6050::getOffsets(Offsets& out)
{
    uint8_t a[6], g[6];
    if (!readBytes(REG_XA_OFFS_H, a, 6) || !readBytes(REG_XG_OFFS_USRH, g, 6))
        return;
    out.ax = s16(a);
    out.ay = s16(a + 2);
    out.az = s16(a + 4);
    out.gx = s16(g);
    out.gy = s16(g + 2);
    out.gz = s16(g + 4);
}

void mpu6050::setOffsets(const Offsets& in)
{
    const int16_t acc[3] = {in.ax, in.ay, in.az};
    const int16_t gyr[3] = {in.gx, in.gy, in.gz};
    for (uint8_t set = 0; set < 2; set++)
    {
        const int16_t* v = set ? gyr : acc;
        Wire.beginTransmission(_addr);
        Wire.write(set ? REG_XG_OFFS_USRH : REG_XA_OFFS_H);
        for (uint8_t i = 0; i < 3; i++)
        {
            Wire.write((uint8_t)((uint16_t)v[i] >> 8));
            Wire.write((uint8_t)v[i]);
        }
        if (Wire.endTransmission() != 0)
            _fail = true;
    }
}

bool mpu6050::readRaw(int16_t v[6])
{
    uint8_t b[14];
    if (!readBytes(REG_ACCEL_XOUT_H, b, 14))
        return false;
    v[0] = s16(b);
    v[1] = s16(b + 2);
    v[2] = s16(b + 4);
    v[3] = s16(b + 8);   // skip temperature at b[6..7]
    v[4] = s16(b + 10);
    v[5] = s16(b + 12);
    return true;
}

// Iteratively trims the hardware offset registers until the averaged readings are zero
// (gyro) and 1 g on the axis pointing along gravity (accel). Offset units differ from the
// readings: accel offsets are 1/8 of a +-2 g LSB, gyro offsets 1/2 of a +-2000 deg/s LSB.
mpu6050::Status mpu6050::calibrate()
{
    if (!_ready)
        return ERROR_NOT_INIT;
    _fail = false;

    Offsets start = {0, 0, 0, 0, 0, 0};
    getOffsets(start);
    if (_fail)
        return ERROR_I2C;

    Offsets o = start;
    stopDmp();

    Status result = ERROR_NOT_STILL;
    int8_t axis = -1;   // axis carrying gravity, found on the first pass
    int16_t target = 0; // +-1 g in raw units for that axis

    for (uint8_t iter = 0; iter < CAL_MAX_ITER && !_fail; iter++)
    {
        int32_t sum[6] = {0, 0, 0, 0, 0, 0};
        int16_t gmin[3] = {32767, 32767, 32767};
        int16_t gmax[3] = {-32768, -32768, -32768};

        for (uint8_t n = 0; n < CAL_SAMPLES; n++)
        {
            int16_t v[6];
            if (!readRaw(v))
                break;
            for (uint8_t i = 0; i < 6; i++)
                sum[i] += v[i];
            for (uint8_t i = 0; i < 3; i++)
            {
                gmin[i] = min(gmin[i], v[3 + i]);
                gmax[i] = max(gmax[i], v[3 + i]);
            }
            delay(5); // new sample every 5 ms (200 Hz)
        }
        if (_fail)
            break;

        int16_t mean[6];
        for (uint8_t i = 0; i < 6; i++)
            mean[i] = sum[i] / CAL_SAMPLES;

        // Moving: a gyro axis swung more than ~18 deg/s within one pass.
        if (gmax[0] - gmin[0] > 300 || gmax[1] - gmin[1] > 300 || gmax[2] - gmin[2] > 300)
            break;

        if (axis < 0)
        {
            axis = 0;
            for (uint8_t i = 1; i < 3; i++)
                if (abs(mean[i]) > abs(mean[axis]))
                    axis = i;
            // Gravity must lie almost exactly along one axis (within ~14 degrees).
            for (uint8_t i = 0; i < 3; i++)
            {
                if (i == axis ? abs(mean[i]) < 12000 : abs(mean[i]) > 4000)
                {
                    axis = -2;
                    break;
                }
            }
            if (axis < 0)
                break;
            target = mean[axis] > 0 ? CAL_ONE_G : -CAL_ONE_G;
        }

        int16_t err[3];
        bool done = true;
        for (uint8_t i = 0; i < 3; i++)
        {
            err[i] = mean[i] - (i == axis ? target : 0);
            if (abs(err[i]) > CAL_ACCEL_TOL || abs(mean[3 + i]) > CAL_GYRO_TOL)
                done = false;
        }
        if (done)
        {
            result = OK;
            break;
        }

        o.ax -= err[0] / 8;
        o.ay -= err[1] / 8;
        o.az -= err[2] / 8;
        o.gx -= mean[3] / 2;
        o.gy -= mean[4] / 2;
        o.gz -= mean[5] / 2;
        setOffsets(o);
        delay(30); // let the 42 Hz filter settle on the new offsets
    }

    if (_fail)
        result = ERROR_I2C;
    if (result != OK)
        setOffsets(start);
    startDmp();
    return _fail ? ERROR_I2C : result;
}

// ---------------------------------------------------------------- reading data

mpu6050::Status mpu6050::update()
{
    if (!_ready)
        return ERROR_NOT_INIT;
    _fail = false;

    uint8_t cb[2];
    if (!readBytes(REG_FIFO_COUNT_H, cb, 2))
        return ERROR_I2C;
    uint16_t count = ((uint16_t)cb[0] << 8) | cb[1];

    if (count >= FIFO_OVERFLOW_AT)
    {
        resetFifo();
        return _fail ? ERROR_I2C : ERROR_FIFO_OVERFLOW;
    }
    if (count < PACKET_SIZE)
        return ERROR_NO_DATA;

    // Several packets may be queued if the main loop was slow: keep only the newest.
    uint8_t pkt[PACKET_SIZE];
    for (;;)
    {
        if (!readFifo(pkt, PACKET_SIZE))
        {
            resetFifo();
            return ERROR_I2C;
        }
        count -= PACKET_SIZE;
        if (count < PACKET_SIZE)
            break;
    }
    return decode(pkt);
}

mpu6050::Status mpu6050::decode(const uint8_t* pkt)
{
    float q[4];
    float norm = 0.0f;
    for (uint8_t i = 0; i < 4; i++)
    {
        q[i] = s16(pkt + i * 4) / QUAT_SCALE;
        norm += q[i] * q[i];
    }
    norm = sqrt(norm);
    if (norm < 0.9f || norm > 1.1f) // a valid unit quaternion; anything else is corruption
    {
        resetFifo();
        return ERROR_BAD_PACKET;
    }
    for (uint8_t i = 0; i < 4; i++)
        _q[i] = q[i] / norm;

    const float gyro[3] = {s16(pkt + 16) / GYRO_SCALE, s16(pkt + 20) / GYRO_SCALE, s16(pkt + 24) / GYRO_SCALE};
    const float acc[3] = {s16(pkt + 28) / ACCEL_PKT_SCALE, s16(pkt + 32) / ACCEL_PKT_SCALE,
                          s16(pkt + 36) / ACCEL_PKT_SCALE};

    for (uint8_t i = 0; i < 3; i++)
    {
        if (_primed)
        {
            _a[i] += _alpha * (acc[i] - _a[i]);
            _g[i] += _alpha * (gyro[i] - _g[i]);
        }
        else
        {
            _a[i] = acc[i];
            _g[i] = gyro[i];
        }
    }
    _primed = true;

    if (accelMagnitude() < _ffThreshold)
    {
        if (_ffCount < 255)
            _ffCount++;
    }
    else
    {
        _ffCount = 0;
    }
    return OK;
}

// ---------------------------------------------------------------- derived values

mpu6050::Vec3 mpu6050::gravity() const
{
    const float w = _q[0], x = _q[1], y = _q[2], z = _q[3];
    return {2.0f * (x * z - w * y), 2.0f * (w * x + y * z), w * w - x * x - y * y + z * z};
}

void mpu6050::ypr(float out[3]) const
{
    const float w = _q[0], x = _q[1], y = _q[2], z = _q[3];
    const Vec3 g = gravity();

    float yaw = atan2(2.0f * (x * y - w * z), 2.0f * (w * w + x * x) - 1.0f);
    float pitch = atan2(g.x, sqrt(g.y * g.y + g.z * g.z));
    const float roll = atan2(g.y, g.z);
    if (g.z < 0.0f) // upside down: keep pitch continuous instead of folding back
        pitch = pitch > 0.0f ? PI - pitch : -PI - pitch;

    out[0] = yaw * RAD_TO_DEG;
    out[1] = pitch * RAD_TO_DEG;
    out[2] = roll * RAD_TO_DEG;
}

mpu6050::Vec3 mpu6050::accel() const
{
    return {_a[0], _a[1], _a[2]};
}

mpu6050::Vec3 mpu6050::gyro() const
{
    Vec3 r = {_g[0], _g[1], _g[2]};
    if (fabs(r.x) < _deadband) r.x = 0.0f;
    if (fabs(r.y) < _deadband) r.y = 0.0f;
    if (fabs(r.z) < _deadband) r.z = 0.0f;
    return r;
}

mpu6050::Vec3 mpu6050::linearAccel() const
{
    const Vec3 g = gravity();
    return {_a[0] - g.x, _a[1] - g.y, _a[2] - g.z};
}

// Rotate the sensor-frame linear acceleration by the orientation quaternion: v' = q v q*.
mpu6050::Vec3 mpu6050::worldAccel() const
{
    const Vec3 v = linearAccel();
    const float w = _q[0], qx = _q[1], qy = _q[2], qz = _q[3];

    const float tx = 2.0f * (qy * v.z - qz * v.y);
    const float ty = 2.0f * (qz * v.x - qx * v.z);
    const float tz = 2.0f * (qx * v.y - qy * v.x);
    return {v.x + w * tx + (qy * tz - qz * ty),
            v.y + w * ty + (qz * tx - qx * tz),
            v.z + w * tz + (qx * ty - qy * tx)};
}

float mpu6050::accelMagnitude() const
{
    return sqrt(_a[0] * _a[0] + _a[1] * _a[1] + _a[2] * _a[2]);
}

float mpu6050::temperature()
{
    uint8_t b[2];
    _fail = false;
    if (!readBytes(REG_TEMP_OUT_H, b, 2))
        return NAN;
    return s16(b) / 340.0f + 36.53f;
}
