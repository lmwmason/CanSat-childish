#include "indicator.h"

static const IndicatorPin g_leds[] = { INDICATOR_LED_LIST };
#define LED_COUNT (sizeof(g_leds) / sizeof(g_leds[0]))

static void set_all_leds(GPIO_PinState s)
{
    for (unsigned i = 0; i < LED_COUNT; i++)
        HAL_GPIO_WritePin(g_leds[i].port, g_leds[i].pin, s);
}

void indicator_update(uint8_t dropping, uint8_t landed, uint32_t nowMs)
{
    if (landed) {
        GPIO_PinState on = ((nowMs / LANDED_BLINK_MS) & 1u) ? GPIO_PIN_RESET : GPIO_PIN_SET;
        set_all_leds(on);
        HAL_GPIO_WritePin(BUZZER_PORT, BUZZER_PIN, on);
        return;
    }

    HAL_GPIO_WritePin(BUZZER_PORT, BUZZER_PIN, GPIO_PIN_RESET);
    set_all_leds(GPIO_PIN_RESET);
    HAL_GPIO_WritePin(LED_STATUS_PORT, LED_STATUS_PIN, dropping ? GPIO_PIN_SET : GPIO_PIN_RESET);
}
