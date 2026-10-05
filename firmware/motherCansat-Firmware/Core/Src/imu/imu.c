#include "imu.h"
#include <math.h>

#define RAD2DEG 57.2957795f

static void try_init_mpu(Imu *imu, uint32_t now)
{
    imu->mpuOk = (mpu6050_init(&imu->mpu, imu->hi2c, IMU_MPU_ADDR) == HAL_OK);
    imu->mpuRetryAt = now + IMU_RETRY_MS;
}

static void try_init_icm(Imu *imu, uint32_t now)
{
    imu->icmOk = (icm42688_init(&imu->icm, imu->hi2c, IMU_ICM_ADDR) == HAL_OK);
    imu->icmRetryAt = now + IMU_RETRY_MS;
}

uint8_t imu_init(Imu *imu, I2C_HandleTypeDef *hi2c)
{
    *imu = (Imu){0};
    imu->hi2c = hi2c;
    uint32_t now = HAL_GetTick();
    try_init_mpu(imu, now);
    try_init_icm(imu, now);
    imu->lastTickMs = now;
    return imu_sensor_count(imu);
}

uint8_t imu_sensor_count(const Imu *imu)
{
    return (uint8_t)(imu->mpuOk + imu->icmOk);
}

static void sub_gyro(ImuSample *s, const ImuSample *bias)
{
    s->gx -= bias->gx;
    s->gy -= bias->gy;
    s->gz -= bias->gz;
}

static float wrap180(float d)
{
    while (d >= 180.0f) d -= 360.0f;
    while (d < -180.0f) d += 360.0f;
    return d;
}

uint8_t imu_update(Imu *imu, uint32_t nowMs)
{
    ImuSample m, c;
    uint8_t haveM = 0, haveC = 0;

    if (imu->mpuOk) {
        if (mpu6050_read(&imu->mpu, &m) == HAL_OK) { sub_gyro(&m, &imu->mpuBias); haveM = 1; }
        else { imu->mpuOk = 0; imu->mpuRetryAt = nowMs + IMU_RETRY_MS; }
    } else if ((int32_t)(nowMs - imu->mpuRetryAt) >= 0) {
        try_init_mpu(imu, nowMs);
    }

    if (imu->icmOk) {
        if (icm42688_read(&imu->icm, &c) == HAL_OK) { sub_gyro(&c, &imu->icmBias); haveC = 1; }
        else { imu->icmOk = 0; imu->icmRetryAt = nowMs + IMU_RETRY_MS; }
    } else if ((int32_t)(nowMs - imu->icmRetryAt) >= 0) {
        try_init_icm(imu, nowMs);
    }

    float dt = (nowMs - imu->lastTickMs) * 0.001f;
    imu->lastTickMs = nowMs;

    if (!haveM && !haveC) return 0;

    if (haveM && haveC) {
        const float wc = IMU_ICM_WEIGHT, wm = 1.0f - IMU_ICM_WEIGHT;
        imu->fused.ax = wc * c.ax + wm * m.ax;
        imu->fused.ay = wc * c.ay + wm * m.ay;
        imu->fused.az = wc * c.az + wm * m.az;
        imu->fused.gx = wc * c.gx + wm * m.gx;
        imu->fused.gy = wc * c.gy + wm * m.gy;
        imu->fused.gz = wc * c.gz + wm * m.gz;

        float magM = sqrtf(m.ax * m.ax + m.ay * m.ay + m.az * m.az);
        float magC = sqrtf(c.ax * c.ax + c.ay * c.ay + c.az * c.az);
        imu->disagree = fabsf(magM - magC) > IMU_DISAGREE_MS2;
    } else {
        imu->fused = haveC ? c : m;
        imu->disagree = 0;
    }

    imu->accelMag = sqrtf(imu->fused.ax * imu->fused.ax +
                          imu->fused.ay * imu->fused.ay +
                          imu->fused.az * imu->fused.az);

    if (dt > 0.0f && dt < 0.5f)
        imu->yawDeg = wrap180(imu->yawDeg + imu->fused.gz * dt);

    /* roll / pitch: complementary filter (gyro integration + accel tilt) */
    const ImuSample *f = &imu->fused;
    float accRoll  = atan2f(f->ay, f->az) * RAD2DEG;
    float accPitch = atan2f(f->ax, sqrtf(f->ay * f->ay + f->az * f->az)) * RAD2DEG;
    if (!imu->tiltInit) {
        imu->rollDeg = accRoll;
        imu->pitchDeg = accPitch;
        imu->tiltInit = 1;
    } else if (dt > 0.0f && dt < 0.5f) {
        imu->rollDeg  += f->gx * dt;       /* roll rate  =  gx */
        imu->pitchDeg += -f->gy * dt;      /* pitch rate = -gy */
        if (fabsf(imu->accelMag - IMU_GRAVITY) < IMU_TILT_TRUST_MS2) {
            imu->rollDeg  = IMU_TILT_ALPHA * imu->rollDeg  + (1.0f - IMU_TILT_ALPHA) * accRoll;
            imu->pitchDeg = IMU_TILT_ALPHA * imu->pitchDeg + (1.0f - IMU_TILT_ALPHA) * accPitch;
        }
    }
    return 1;
}

void imu_calibrate_gyro(Imu *imu, uint32_t durationMs)
{
    ImuSample sumM = {0}, sumC = {0};
    uint32_t nM = 0, nC = 0;
    uint32_t start = HAL_GetTick();

    while (HAL_GetTick() - start < durationMs) {
        ImuSample s;
        if (imu->mpuOk && mpu6050_read(&imu->mpu, &s) == HAL_OK) {
            sumM.gx += s.gx; sumM.gy += s.gy; sumM.gz += s.gz; nM++;
        }
        if (imu->icmOk && icm42688_read(&imu->icm, &s) == HAL_OK) {
            sumC.gx += s.gx; sumC.gy += s.gy; sumC.gz += s.gz; nC++;
        }
        HAL_Delay(5);
    }
    if (nM) { imu->mpuBias.gx = sumM.gx / nM; imu->mpuBias.gy = sumM.gy / nM; imu->mpuBias.gz = sumM.gz / nM; }
    if (nC) { imu->icmBias.gx = sumC.gx / nC; imu->icmBias.gy = sumC.gy / nC; imu->icmBias.gz = sumC.gz / nC; }
    imu->yawDeg = 0.0f;
    imu->lastTickMs = HAL_GetTick();
}

void imu_reset_yaw(Imu *imu, float yawDeg)
{
    imu->yawDeg = wrap180(yawDeg);
}
