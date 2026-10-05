#include "wings.h"

static TIM_HandleTypeDef *g_tim;
static uint8_t g_ejected;

static void set_pulse(uint32_t us)
{
    if (g_tim) __HAL_TIM_SET_COMPARE(g_tim, WING_SERVO_CH, us);
}

void wings_init(TIM_HandleTypeDef *htim)
{
    g_tim = htim;
    set_pulse(WING_LOCKED_PULSE_US);
    g_ejected = 0;
    HAL_TIM_PWM_Start(g_tim, WING_SERVO_CH);
}

void wings_eject(void)
{
    set_pulse(WING_EJECT_PULSE_US);
    g_ejected = 1;
}

void wings_lock(void)
{
    set_pulse(WING_LOCKED_PULSE_US);
    g_ejected = 0;
}

uint8_t wings_are_ejected(void)
{
    return g_ejected;
}
