#include "door.h"

static TIM_HandleTypeDef *g_tim;
static uint8_t g_open;

static void set_pulse(uint32_t us)
{
    if (g_tim) __HAL_TIM_SET_COMPARE(g_tim, DOOR_SERVO_CH, us);
}

void door_init(TIM_HandleTypeDef *htim)
{
    g_tim = htim;
    set_pulse(DOOR_CLOSED_PULSE_US);
    g_open = 0;
    HAL_TIM_PWM_Start(g_tim, DOOR_SERVO_CH);
}

void door_open(void)
{
    set_pulse(DOOR_OPEN_PULSE_US);
    g_open = 1;
}

void door_close(void)
{
    set_pulse(DOOR_CLOSED_PULSE_US);
    g_open = 0;
}

uint8_t door_is_open(void)
{
    return g_open;
}
