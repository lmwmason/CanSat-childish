#include "soft_pwm.h"

#define SPWM_MIN_US 500u
#define SPWM_MAX_US 2500u

static TIM_HandleTypeDef *g_tim;

void soft_pwm_init(TIM_HandleTypeDef *htim)
{
    g_tim = htim;

    __HAL_RCC_GPIOC_CLK_ENABLE();
    GPIO_InitTypeDef gi = {0};
    gi.Pin = GPIO_PIN_8 | GPIO_PIN_9;
    gi.Mode = GPIO_MODE_OUTPUT_PP;
    gi.Pull = GPIO_NOPULL;
    gi.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOC, &gi);
    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_8 | GPIO_PIN_9, GPIO_PIN_RESET);

    htim->Instance->CCR3 = 1500;
    htim->Instance->CCR4 = 1500;
    htim->Instance->SR = 0;
    htim->Instance->DIER |= TIM_DIER_UIE | TIM_DIER_CC3IE | TIM_DIER_CC4IE;

    HAL_NVIC_SetPriority(TIM5_IRQn, 2, 0);
    HAL_NVIC_EnableIRQ(TIM5_IRQn);
}

void soft_pwm_set_us(uint8_t channel, uint16_t us)
{
    if (!g_tim) return;
    if (us < SPWM_MIN_US) us = SPWM_MIN_US;
    if (us > SPWM_MAX_US) us = SPWM_MAX_US;
    if (channel == 0) g_tim->Instance->CCR3 = us;       /* TIM5 ticks are 1 us */
    else if (channel == 1) g_tim->Instance->CCR4 = us;
}

void TIM5_IRQHandler(void)
{
    if (!g_tim) return;
    TIM_TypeDef *t = g_tim->Instance;
    uint32_t flags = t->SR & t->DIER;

    t->SR = ~(flags & (TIM_SR_UIF | TIM_SR_CC3IF | TIM_SR_CC4IF));   /* clear handled flags */

    if (flags & TIM_SR_UIF)   GPIOC->BSRR = GPIO_PIN_8 | GPIO_PIN_9;                 /* both high */
    if (flags & TIM_SR_CC3IF) GPIOC->BSRR = (uint32_t)GPIO_PIN_8 << 16;              /* PC8 low */
    if (flags & TIM_SR_CC4IF) GPIOC->BSRR = (uint32_t)GPIO_PIN_9 << 16;              /* PC9 low */
}
