#include "bmp280.h"

#include <Wire.h>
#include <math.h>

namespace
{
    // Registers
    constexpr uint8_t REG_CALIB = 0x88;  // 24 bytes of calibration data
    constexpr uint8_t REG_ID = 0xD0;
    constexpr uint8_t REG_RESET = 0xE0;
    constexpr uint8_t REG_STATUS = 0xF3;
    constexpr uint8_t REG_CTRL_MEAS = 0xF4;
    constexpr uint8_t REG_CONFIG = 0xF5;
    constexpr uint8_t REG_PRESS_MSB = 0xF7;  // press[3], temp[3]

    constexpr uint8_t RESET_VALUE = 0xB6;
    constexpr uint8_t STATUS_MEASURING = 0x08;

    // 0x56 / 0x57 are engineering samples, 0x58 is the production chip
    constexpr uint8_t CHIP_ID_MIN = 0x56;
    constexpr uint8_t CHIP_ID_MAX = 0x58;

    constexpr int32_t ADC_SKIPPED = 0x80000;  // value the chip gives for a skipped measurement

    constexpr float STILL_SPEED_MPS = 1.0f;
    constexpr float SPEED_FILTER = 0.3f;  // low-pass weight of the newest speed sample
    constexpr uint32_t MIN_SPEED_DT_MS = 20;

    uint8_t osrsFactor(uint8_t osrs)
    {
        return osrs == 0 ? 0 : (uint8_t)(1 << (osrs - 1));
    }
}

bmp280::bmp280(uint8_t address) : address_(address)
{
}

bmp280::Status bmp280::begin(Preset preset)
{
    Wire.begin();
    Wire.setClock(400000);
    initialized_ = false;

    uint8_t id;
    Status s = readRegisters(REG_ID, &id, 1);
    if (s != OK) return s;
    if (id < CHIP_ID_MIN || id > CHIP_ID_MAX) return ERROR_NOT_FOUND;
    chipId_ = id;

    s = readCalibration();
    if (s != OK) return s;

    initialized_ = true;
    haveSample_ = false;
    resetFlight();
    groundPa_ = 0;

    s = applyPreset(preset);
    if (s != OK) initialized_ = false;
    return s;
}

bmp280::Status bmp280::reset()
{
    Status s = writeRegister(REG_RESET, RESET_VALUE);
    initialized_ = false;
    delay(5);
    return s;
}

bool bmp280::isConnected()
{
    uint8_t id;
    return readRegisters(REG_ID, &id, 1) == OK && id >= CHIP_ID_MIN && id <= CHIP_ID_MAX;
}

bmp280::Status bmp280::applyPreset(Preset preset)
{
    switch (preset)
    {
    case PRESET_FLIGHT:
        return configure(OSRS_X4, OSRS_X1, FILTER_4, STANDBY_0_5_MS, MODE_NORMAL);
    case PRESET_HIGH_RES:
        return configure(OSRS_X16, OSRS_X2, FILTER_16, STANDBY_0_5_MS, MODE_NORMAL);
    case PRESET_LOW_POWER:
        return configure(OSRS_X1, OSRS_X1, FILTER_OFF, STANDBY_0_5_MS, MODE_SLEEP);
    case PRESET_GROUND:
        return configure(OSRS_X16, OSRS_X2, FILTER_16, STANDBY_1000_MS, MODE_NORMAL);
    }
    return ERROR_BAD_DATA;
}

bmp280::Status bmp280::configure(Oversampling pressure, Oversampling temperature, Filter filter,
                                 Standby standby, Mode mode)
{
    if (!initialized_) return ERROR_NOT_INIT;

    osrsP_ = pressure;
    osrsT_ = temperature;
    filter_ = filter;
    standby_ = standby;
    mode_ = mode;

    // CONFIG is only writable while the chip sleeps, so always go through sleep first.
    Status s = writeRegister(REG_CTRL_MEAS, 0x00);
    if (s != OK) return s;
    s = writeRegister(REG_CONFIG, (uint8_t)((standby_ << 5) | (filter_ << 2)));
    if (s != OK) return s;
    return writeControl();
}

bmp280::Status bmp280::setMode(Mode mode)
{
    if (!initialized_) return ERROR_NOT_INIT;
    mode_ = mode;
    return writeControl();
}

bmp280::Status bmp280::writeControl()
{
    return writeRegister(REG_CTRL_MEAS, (uint8_t)((osrsT_ << 5) | (osrsP_ << 2) | mode_));
}

bmp280::Status bmp280::read(Reading& out)
{
    if (!initialized_) return ERROR_NOT_INIT;

    uint8_t b[6];
    Status s = readRegisters(REG_PRESS_MSB, b, sizeof(b));
    if (s != OK) return s;

    int32_t adcP = ((int32_t)b[0] << 12) | ((int32_t)b[1] << 4) | (b[2] >> 4);
    int32_t adcT = ((int32_t)b[3] << 12) | ((int32_t)b[4] << 4) | (b[5] >> 4);
    if (adcP == ADC_SKIPPED || adcT == ADC_SKIPPED) return ERROR_BAD_DATA;

    float t, p;
    compensate(adcT, adcP, t, p);
    // Valid range from the datasheet: 300..1100 hPa, -40..85 C. Anything else is a bad read.
    if (p < 30000.0f || p > 110000.0f || t < -40.0f || t > 85.0f) return ERROR_BAD_DATA;

    out.temperature = t;
    out.pressure = p;
    return OK;
}

bmp280::Status bmp280::update()
{
    Reading r;
    Status s = read(r);
    if (s != OK) return s;

    temperature_ = r.temperature;
    pressure_ = r.pressure;
    haveSample_ = true;
    lastUpdateMs_ = millis();
    track(lastUpdateMs_);
    return OK;
}

bmp280::Status bmp280::readForced()
{
    if (!initialized_) return ERROR_NOT_INIT;

    Status s = setMode(MODE_FORCED);
    if (s != OK) return s;

    // Mode returns to sleep by itself once the measurement is done.
    uint32_t start = millis();
    delay(measurementTimeMs() / 2);
    while (true)
    {
        uint8_t status;
        s = readRegisters(REG_STATUS, &status, 1);
        if (s != OK) return s;
        if (!(status & STATUS_MEASURING)) break;
        if (millis() - start > (uint32_t)measurementTimeMs() + 20) return ERROR_TIMEOUT;
        delay(1);
    }
    mode_ = MODE_SLEEP;
    return update();
}

uint16_t bmp280::measurementTimeMs() const
{
    float ms = 1.25f;
    if (osrsT_ != OSRS_SKIP) ms += 2.3f * osrsFactor(osrsT_);
    if (osrsP_ != OSRS_SKIP) ms += 2.3f * osrsFactor(osrsP_) + 0.575f;
    return (uint16_t)ceilf(ms);
}

// ---- Altitude ----

float bmp280::altitudeFromPressure(float pa, float seaLevelPa)
{
    if (pa <= 0.0f || seaLevelPa <= 0.0f) return 0.0f;
    return 44330.0f * (1.0f - powf(pa / seaLevelPa, 0.19029495f));
}

float bmp280::seaLevelFromAltitude(float pa, float altitudeM)
{
    return pa / powf(1.0f - altitudeM / 44330.0f, 5.255f);
}

void bmp280::calibrateSeaLevel(float knownAltitudeM)
{
    if (!haveSample_) return;
    seaLevelPa_ = seaLevelFromAltitude(pressure_, knownAltitudeM);
}

bmp280::Status bmp280::setGroundReference(uint8_t samples)
{
    if (!initialized_) return ERROR_NOT_INIT;
    if (samples == 0) samples = 1;

    float sum = 0;
    uint8_t got = 0;
    for (uint8_t i = 0; i < samples; i++)
    {
        Status s = (mode_ == MODE_NORMAL) ? update() : readForced();
        if (s == OK)
        {
            sum += pressure_;
            got++;
        }
        delay(20);
    }
    if (got == 0) return ERROR_BAD_DATA;

    setGroundPressure(sum / got);
    return OK;
}

void bmp280::setGroundPressure(float pa)
{
    groundPa_ = pa;
    resetFlight();
}

float bmp280::relativeAltitude() const
{
    if (groundPa_ <= 0.0f || !haveSample_) return 0.0f;
    return altitudeFromPressure(pressure_, seaLevelPa_) - altitudeFromPressure(groundPa_, seaLevelPa_);
}

// ---- Flight tracking ----

void bmp280::setApogeeParams(float dropM, uint8_t confirmSamples, float minClimbM)
{
    apogeeDropM_ = dropM;
    apogeeConfirm_ = confirmSamples ? confirmSamples : 1;
    apogeeMinClimbM_ = minClimbM;
}

void bmp280::resetFlight()
{
    havePrevAltitude_ = false;
    verticalSpeed_ = 0;
    maxAltitude_ = 0;
    minAltitude_ = 0;
    apogee_ = false;
    apogeeCount_ = 0;
    stillSinceMs_ = 0;
}

bool bmp280::isLanded(uint32_t holdMs, float maxHeightM) const
{
    if (stillSinceMs_ == 0 || !haveSample_) return false;
    if (relativeAltitude() > maxHeightM) return false;
    return millis() - stillSinceMs_ >= holdMs;
}

void bmp280::track(uint32_t now)
{
    if (groundPa_ <= 0.0f) return;  // nothing to track against until the pad reference is set

    float alt = relativeAltitude();

    if (!havePrevAltitude_)
    {
        havePrevAltitude_ = true;
        maxAltitude_ = minAltitude_ = alt;
    }
    else
    {
        uint32_t dt = now - prevAltitudeMs_;
        if (dt < MIN_SPEED_DT_MS) return;  // too close to the last sample, speed would be noise

        float raw = (alt - prevAltitude_) * 1000.0f / (float)dt;
        verticalSpeed_ += SPEED_FILTER * (raw - verticalSpeed_);

        if (alt > maxAltitude_)
        {
            maxAltitude_ = alt;
            apogeeCount_ = 0;
        }
        if (alt < minAltitude_) minAltitude_ = alt;

        if (!apogee_ && maxAltitude_ - minAltitude_ >= apogeeMinClimbM_)
        {
            if (alt <= maxAltitude_ - apogeeDropM_)
            {
                if (++apogeeCount_ >= apogeeConfirm_) apogee_ = true;
            }
            else
            {
                apogeeCount_ = 0;
            }
        }
    }

    if (fabsf(verticalSpeed_) <= STILL_SPEED_MPS)
    {
        if (stillSinceMs_ == 0) stillSinceMs_ = now ? now : 1;
    }
    else
    {
        stillSinceMs_ = 0;
    }

    prevAltitude_ = alt;
    prevAltitudeMs_ = now;
}

// ---- Low-level ----

bmp280::Status bmp280::writeRegister(uint8_t reg, uint8_t value)
{
    Wire.beginTransmission(address_);
    Wire.write(reg);
    Wire.write(value);
    return Wire.endTransmission() == 0 ? OK : ERROR_I2C;
}

bmp280::Status bmp280::readRegisters(uint8_t reg, uint8_t* buf, uint8_t len)
{
    Wire.beginTransmission(address_);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0) return ERROR_I2C;
    if (Wire.requestFrom(address_, len) != len) return ERROR_I2C;
    for (uint8_t i = 0; i < len; i++) buf[i] = Wire.read();
    return OK;
}

bmp280::Status bmp280::readCalibration()
{
    uint8_t c[24];
    Status s = readRegisters(REG_CALIB, c, sizeof(c));
    if (s != OK) return s;

    auto u16 = [&c](uint8_t i) { return (uint16_t)(c[i] | (c[i + 1] << 8)); };
    digT1_ = u16(0);
    digT2_ = (int16_t)u16(2);
    digT3_ = (int16_t)u16(4);
    digP1_ = u16(6);
    digP2_ = (int16_t)u16(8);
    digP3_ = (int16_t)u16(10);
    digP4_ = (int16_t)u16(12);
    digP5_ = (int16_t)u16(14);
    digP6_ = (int16_t)u16(16);
    digP7_ = (int16_t)u16(18);
    digP8_ = (int16_t)u16(20);
    digP9_ = (int16_t)u16(22);

    // An unprogrammed chip reads all zeros or all ones
    if (digT1_ == 0 || digT1_ == 0xFFFF || digP1_ == 0) return ERROR_NOT_FOUND;
    return OK;
}

// Integer compensation from the datasheet (chapter 3.11.3), 64-bit variant for pressure.
void bmp280::compensate(int32_t adcT, int32_t adcP, float& tempC, float& pressurePa)
{
    int32_t v1 = ((((adcT >> 3) - ((int32_t)digT1_ << 1))) * (int32_t)digT2_) >> 11;
    int32_t v2 = (((((adcT >> 4) - (int32_t)digT1_) * ((adcT >> 4) - (int32_t)digT1_)) >> 12)
                  * (int32_t)digT3_) >> 14;
    tFine_ = v1 + v2;
    tempC = (float)((tFine_ * 5 + 128) >> 8) / 100.0f;

    int64_t p1 = (int64_t)tFine_ - 128000;
    int64_t p2 = p1 * p1 * (int64_t)digP6_;
    p2 += (p1 * (int64_t)digP5_) << 17;
    p2 += (int64_t)digP4_ << 35;
    p1 = ((p1 * p1 * (int64_t)digP3_) >> 8) + ((p1 * (int64_t)digP2_) << 12);
    p1 = (((int64_t)1 << 47) + p1) * (int64_t)digP1_ >> 33;
    if (p1 == 0)
    {
        pressurePa = 0;  // would divide by zero, read() rejects it as out of range
        return;
    }

    int64_t p = 1048576 - adcP;
    p = (((p << 31) - p2) * 3125) / p1;
    p1 = ((int64_t)digP9_ * (p >> 13) * (p >> 13)) >> 25;
    p2 = ((int64_t)digP8_ * p) >> 19;
    p = ((p + p1 + p2) >> 8) + ((int64_t)digP7_ << 4);
    pressurePa = (float)p / 256.0f;
}
