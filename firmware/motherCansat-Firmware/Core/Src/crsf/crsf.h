#ifndef CRSF_H
#define CRSF_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include "stm32f4xx_hal.h"

/* CRSF receiver (Crossfire Nano RX) on a UART at 420000 baud 8N1.
 * Bytes are received in the UART RX interrupt and parsed into 16 channels. */

#define CRSF_NUM_CHANNELS    16
#define CRSF_AUX1_CHANNEL    5          /* channel number 1..16: AUX1 = CH5 */
#define CRSF_SWITCH_ON_RAW   1400       /* raw 172..1811; >1400 (~1755 us) counts as "on" */
#define CRSF_LINK_TIMEOUT_MS 500u

uint8_t  crsf_crc8(const uint8_t *p, uint8_t n);

/* Starts reception on the given UART (enables the RXNE interrupt and USART IRQ). */
void     crsf_init(UART_HandleTypeDef *huart);

/* Sends one complete CRSF frame (addr, len, type, payload, crc) to the receiver. Blocking, <1 ms. */
void     crsf_send_frame(uint8_t type, const uint8_t *payload, uint8_t payloadLen);

/* Raw channel value 172..1811 (992 = center), channel is 1..16. */
uint16_t crsf_get_channel(uint8_t channel);
/* Same value converted to microseconds (988..2012). */
uint16_t crsf_get_channel_us(uint8_t channel);

/* 1 if a valid RC frame arrived recently. */
uint8_t  crsf_link_ok(uint32_t nowMs);
/* 1 if the channel is above the switch threshold and the link is OK. */
uint8_t  crsf_switch_on(uint8_t channel, uint32_t nowMs);
uint8_t  crsf_aux1_on(uint32_t nowMs);

#ifdef __cplusplus
}
#endif

#endif /* CRSF_H */
