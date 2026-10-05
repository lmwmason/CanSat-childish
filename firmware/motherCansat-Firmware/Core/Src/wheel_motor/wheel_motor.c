#include "wheel_motor.h"

static TIM_HandleTypeDef *g_tim;

void wheel_motor_init(TIM_HandleTypeDef *htim)
{
    g_tim = htim;
    __HAL_TIM_SET_COMPARE(g_tim, WHEEL_CH_FWD, 0);
    __HAL_TIM_SET_COMPARE(g_tim, WHEEL_CH_REV, 0);
    HAL_TIM_PWM_Start(g_tim, WHEEL_CH_FWD);
    HAL_TIM_PWM_Start(g_tim, WHEEL_CH_REV);
}

void wheel_motor_set(float command)
{
    if (!g_tim) return;
    if (command > 1.0f) command = 1.0f;
    if (command < -1.0f) command = -1.0f;

    uint32_t arr = __HAL_TIM_GET_AUTORELOAD(g_tim);
    uint32_t duty = (uint32_t)((command < 0.0f ? -command : command) * (float)arr);

    __HAL_TIM_SET_COMPARE(g_tim, WHEEL_CH_FWD, command > 0.0f ? duty : 0);
    __HAL_TIM_SET_COMPARE(g_tim, WHEEL_CH_REV, command < 0.0f ? duty : 0);
}
