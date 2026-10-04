#ifndef CHILDCANSAT_FIRMWARE_BMP280_H
#define CHILDCANSAT_FIRMWARE_BMP280_H

#include <Arduino.h>

// BMP280 driver (pressure + temperature) with CanSat flight helpers. Uses only Wire, no heap.
// RAM use is ~90 bytes per object.
//
// Units: Pa, degrees C, metres, metres/second.
//
// Typical use:
//   bmp280 baro;
//   baro.begin();                    // FLIGHT preset, normal mode
//   baro.setGroundReference();       // call on the pad: altitudes become relative to here
//   loop: if (baro.update() == bmp280::OK) { baro.relativeAltitude(); baro.verticalSpeed(); ... }
//
// Call update() regularly (faster than ~10 Hz for the speed / apogee logic to make sense).
class bmp280
{
public:
    enum Status : uint8_t
    {
        OK = 0,
        ERROR_I2C,        // bus transaction failed
        ERROR_NOT_FOUND,  // no BMP280 at this address (or wrong chip ID)
        ERROR_NOT_INIT,   // begin() has not succeeded yet
        ERROR_TIMEOUT,    // measurement did not finish in time
        ERROR_BAD_DATA    // sensor returned "no measurement" or an out-of-range value
    };

    enum Mode : uint8_t
    {
        MODE_SLEEP = 0,
        MODE_FORCED = 1,  // one measurement, then back to sleep
        MODE_NORMAL = 3   // continuous measurements
    };

    enum Oversampling : uint8_t
    {
        OSRS_SKIP = 0,
        OSRS_X1 = 1,
        OSRS_X2 = 2,
        OSRS_X4 = 3,
        OSRS_X8 = 4,
        OSRS_X16 = 5
    };

    // IIR filter coefficient. Higher = smoother pressure, slower step response.
    enum Filter : uint8_t
    {
        FILTER_OFF = 0,
        FILTER_2 = 1,
        FILTER_4 = 2,
        FILTER_8 = 3,
        FILTER_16 = 4
    };

    // Idle time between measurements in normal mode.
    enum Standby : uint8_t
    {
        STANDBY_0_5_MS = 0,
        STANDBY_62_5_MS = 1,
        STANDBY_125_MS = 2,
        STANDBY_250_MS = 3,
        STANDBY_500_MS = 4,
        STANDBY_1000_MS = 5,
        STANDBY_2000_MS = 6,
        STANDBY_4000_MS = 7
    };

    // Ready-made settings (see datasheet chapter 3.5 for the recommended use cases).
    enum Preset : uint8_t
    {
        PRESET_FLIGHT,      // normal mode, P x4, T x1, filter 4, ~40 Hz. Fast, for ascent / descent.
        PRESET_HIGH_RES,    // normal mode, P x16, T x2, filter 16, ~25 Hz. Smooth, slower to react.
        PRESET_LOW_POWER,   // forced mode, P x1, T x1, no filter. Call readForced() to sample.
        PRESET_GROUND       // normal mode, P x16, T x2, filter 16, 1 s standby. Pad / idle waiting.
    };

    struct Reading
    {
        float temperature;  // degrees C
        float pressure;     // Pa
    };

    // I2C address: 0x76 (SDO low) or 0x77 (SDO high).
    explicit bmp280(uint8_t address = 0x76);

    // Check the chip ID, read the calibration data and apply a preset. Wire is started here (400 kHz).
    Status begin(Preset preset = PRESET_FLIGHT);

    // Soft reset. The chip is unconfigured afterwards, call begin() again.
    Status reset();

    bool isConnected();
    uint8_t chipId() const { return chipId_; }

    // ---- Configuration ----
    Status applyPreset(Preset preset);
    Status configure(Oversampling pressure, Oversampling temperature, Filter filter,
                     Standby standby, Mode mode);
    Status setMode(Mode mode);
    Status sleep() { return setMode(MODE_SLEEP); }  // ~0.2 uA, wake with setMode(MODE_NORMAL)

    // ---- Measuring ----
    // Normal mode: read the latest result and update every derived value (altitude, speed, apogee).
    // Returns OK on success. A failed read leaves the previous values untouched.
    Status update();

    // Forced mode: trigger one measurement, wait for it and update. Blocks for up to ~45 ms.
    Status readForced();

    // Plain read without any derived values (no altitude / speed / apogee tracking).
    Status read(Reading& out);

    // ---- Last values (from update() / readForced()) ----
    float temperature() const { return temperature_; }       // degrees C
    float pressure() const { return pressure_; }              // Pa
    float pressureHpa() const { return pressure_ / 100.0f; }  // hPa (mbar)
    uint32_t lastUpdateMs() const { return lastUpdateMs_; }

    // ---- Altitude ----
    // Pressure at sea level for the absolute altitude. Default 101325 Pa (standard atmosphere).
    void setSeaLevelPressure(float pa) { seaLevelPa_ = pa; }
    float seaLevelPressure() const { return seaLevelPa_; }

    // Work out sea level pressure from a known altitude (e.g. launch site) and use it.
    void calibrateSeaLevel(float knownAltitudeM);

    // Absolute altitude above sea level from the last pressure and the sea level pressure.
    float altitude() const { return altitudeFromPressure(pressure_, seaLevelPa_); }

    // Average `samples` readings (blocking, ~20 ms apart) and take them as altitude zero.
    // Resets speed and apogee tracking. Call this on the launch pad.
    Status setGroundReference(uint8_t samples = 16);
    void setGroundPressure(float pa);
    float groundPressure() const { return groundPa_; }

    // Altitude above the ground reference (metres). 0 if no reference was set yet.
    float relativeAltitude() const;

    // Pure helpers, no sensor needed.
    static float altitudeFromPressure(float pa, float seaLevelPa);
    static float seaLevelFromAltitude(float pa, float altitudeM);

    // ---- Flight tracking ----
    // Smoothed vertical speed in m/s, positive = climbing. Needs update() to be called regularly.
    float verticalSpeed() const { return verticalSpeed_; }

    // Highest relative altitude seen since the ground reference / resetFlight().
    float maxAltitude() const { return maxAltitude_; }

    // Lowest relative altitude seen (useful when launched from above the ground reference).
    float minAltitude() const { return minAltitude_; }

    // True once the CanSat climbed at least `minClimbM` and then dropped `dropM` below the peak
    // for `confirmSamples` updates in a row. Stays true until resetFlight().
    bool apogeeDetected() const { return apogee_; }
    void setApogeeParams(float dropM = 3.0f, uint8_t confirmSamples = 5, float minClimbM = 10.0f);

    // True when the vertical speed has stayed within +-1 m/s for holdMs (default 5 s) and
    // the CanSat is below `maxHeightM` above the ground reference. Good "landed" check.
    bool isLanded(uint32_t holdMs = 5000, float maxHeightM = 15.0f) const;

    // Speed below -thresholdMps (default 2 m/s), i.e. falling / under parachute.
    bool isDescending(float thresholdMps = 2.0f) const { return verticalSpeed_ < -thresholdMps; }
    bool isAscending(float thresholdMps = 2.0f) const { return verticalSpeed_ > thresholdMps; }

    // Forget max / min altitude, speed and the apogee flag. Ground reference is kept.
    void resetFlight();

    // ---- Low-level ----
    // Worst-case time of one measurement with the current oversampling (datasheet 3.8.1).
    uint16_t measurementTimeMs() const;

private:
    Status writeRegister(uint8_t reg, uint8_t value);
    Status readRegisters(uint8_t reg, uint8_t* buf, uint8_t len);
    Status readCalibration();
    Status writeControl();
    void compensate(int32_t adcT, int32_t adcP, float& tempC, float& pressurePa);
    void track(uint32_t now);

    uint8_t address_;
    uint8_t chipId_ = 0;
    bool initialized_ = false;

    // Settings kept so the registers can be rewritten
    Oversampling osrsP_ = OSRS_X4;
    Oversampling osrsT_ = OSRS_X1;
    Filter filter_ = FILTER_4;
    Standby standby_ = STANDBY_0_5_MS;
    Mode mode_ = MODE_NORMAL;

    // Factory calibration
    uint16_t digT1_ = 0;
    int16_t digT2_ = 0, digT3_ = 0;
    uint16_t digP1_ = 0;
    int16_t digP2_ = 0, digP3_ = 0, digP4_ = 0, digP5_ = 0, digP6_ = 0, digP7_ = 0, digP8_ = 0, digP9_ = 0;
    int32_t tFine_ = 0;

    // Latest values
    float temperature_ = 0;
    float pressure_ = 0;
    uint32_t lastUpdateMs_ = 0;
    bool haveSample_ = false;

    // Altitude
    float seaLevelPa_ = 101325.0f;
    float groundPa_ = 0;  // 0 = not set

    // Flight tracking
    float prevAltitude_ = 0;
    uint32_t prevAltitudeMs_ = 0;
    bool havePrevAltitude_ = false;
    float verticalSpeed_ = 0;
    float maxAltitude_ = 0;
    float minAltitude_ = 0;
    bool apogee_ = false;
    uint8_t apogeeCount_ = 0;
    float apogeeDropM_ = 3.0f;
    uint8_t apogeeConfirm_ = 5;
    float apogeeMinClimbM_ = 10.0f;
    uint32_t stillSinceMs_ = 0;  // 0 = not still (a millis() of 0 is nudged to 1)
};

#endif //CHILDCANSAT_FIRMWARE_BMP280_H
