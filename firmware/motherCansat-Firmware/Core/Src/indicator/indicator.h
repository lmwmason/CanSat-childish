#ifndef INDICATOR_H
#define INDICATOR_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include "stm32f4xx_hal.h"

/* Buzzer + LEDs. The pins are NOT labeled in the .ioc, so check them here.
 * The buzzer is driven as an ACTIVE buzzer (GPIO high = sound). */
#define BUZZER_PORT   GPIOA
#define BUZZER_PIN    GPIO_PIN_4

#define LED_STATUS_PORT GPIOA          /* LD2: lit while the drop is detected */
#define LED_STATUS_PIN  GPIO_PIN_5

/* Every LED that should blink after landing (the status LED is included too). */
typedef struct { GPIO_TypeDef *port; uint16_t pin; } IndicatorPin;
#define INDICATOR_LED_LIST \
    { LED_STATUS_PORT, LED_STATUS_PIN }, \
    { GPIOB, GPIO_PIN_12 }, \
    { GPIOB, GPIO_PIN_13 }, \
    { GPIOB, GPIO_PIN_14 }, \
    { GPIOB, GPIO_PIN_15 }

#define LANDED_BLINK_MS 250u    /* LEDs toggle and the buzzer beeps on every "on" phase */

/* Call every loop. Normal: only the status LED shows the drop state.
 * Landed: all LEDs blink together and the buzzer beeps. */
void indicator_update(uint8_t dropping, uint8_t landed, uint32_t nowMs);

#ifdef __cplusplus
}
#endif

#endif /* INDICATOR_H */
