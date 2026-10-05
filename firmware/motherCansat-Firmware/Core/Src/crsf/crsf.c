#include "crsf.h"

#define CRSF_ADDR_FC        0xC8
#define CRSF_ADDR_RADIO     0xEA
#define CRSF_ADDR_TX        0xEE
#define CRSF_TYPE_RC        0x16
#define CRSF_RC_PAYLOAD_LEN 22
#define CRSF_MAX_FRAME_LEN  62          /* type + payload + crc */

static UART_HandleTypeDef *g_huart;
static volatile uint16_t g_channels[CRSF_NUM_CHANNELS];
static volatile uint32_t g_lastFrameMs;
static volatile uint8_t  g_hasFrame;

/* parser state */
static uint8_t g_buf[CRSF_MAX_FRAME_LEN];
static uint8_t g_len;       /* expected length of type+payload+crc */
static uint8_t g_pos;
static uint8_t g_state;     /* 0 = wait addr, 1 = wait len, 2 = body */

static uint8_t crc8(const uint8_t *p, uint8_t n)
{
    uint8_t crc = 0;
    while (n--) {
        crc ^= *p++;
        for (uint8_t i = 0; i < 8; i++)
            crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0xD5) : (uint8_t)(crc << 1);
    }
    return crc;
}

static void decode_channels(const uint8_t *p)
{
    uint32_t bits = 0;
    uint8_t nbits = 0, ch = 0;
    for (uint8_t i = 0; i < CRSF_RC_PAYLOAD_LEN && ch < CRSF_NUM_CHANNELS; i++) {
        bits |= (uint32_t)p[i] << nbits;
        nbits += 8;
        while (nbits >= 11 && ch < CRSF_NUM_CHANNELS) {
            g_channels[ch++] = (uint16_t)(bits & 0x7FF);
            bits >>= 11;
            nbits -= 11;
        }
    }
}

static void feed(uint8_t b)
{
    switch (g_state) {
    case 0:
        if (b == CRSF_ADDR_FC || b == CRSF_ADDR_RADIO || b == CRSF_ADDR_TX) g_state = 1;
        break;
    case 1:
        if (b >= 2 && b <= CRSF_MAX_FRAME_LEN) { g_len = b; g_pos = 0; g_state = 2; }
        else g_state = 0;
        break;
    default:
        g_buf[g_pos++] = b;
        if (g_pos >= g_len) {
            /* g_buf = type, payload..., crc */
            if (crc8(g_buf, (uint8_t)(g_len - 1)) == g_buf[g_len - 1] &&
                g_buf[0] == CRSF_TYPE_RC && g_len == CRSF_RC_PAYLOAD_LEN + 2) {
                decode_channels(&g_buf[1]);
                g_lastFrameMs = HAL_GetTick();
                g_hasFrame = 1;
            }
            g_state = 0;
        }
        break;
    }
}

void crsf_init(UART_HandleTypeDef *huart)
{
    g_huart = huart;
    g_state = 0;
    g_hasFrame = 0;
    for (uint8_t i = 0; i < CRSF_NUM_CHANNELS; i++) g_channels[i] = 992;

    __HAL_UART_ENABLE_IT(huart, UART_IT_RXNE);
    HAL_NVIC_SetPriority(USART6_IRQn, 1, 0);
    HAL_NVIC_EnableIRQ(USART6_IRQn);
}

/* Defined here because CubeMX does not generate it unless the USART6 global
 * interrupt is enabled in the .ioc. If you enable it there, delete this. */
void USART6_IRQHandler(void)
{
    if (!g_huart) return;
    uint32_t sr = g_huart->Instance->SR;
    if (sr & (UART_FLAG_RXNE | UART_FLAG_ORE)) {
        uint8_t b = (uint8_t)g_huart->Instance->DR;   /* reading SR then DR clears flags */
        if (!(sr & (UART_FLAG_ORE | UART_FLAG_FE | UART_FLAG_NE | UART_FLAG_PE)))
            feed(b);
    }
}

uint16_t crsf_get_channel(uint8_t channel)
{
    if (channel < 1 || channel > CRSF_NUM_CHANNELS) return 992;
    return g_channels[channel - 1];
}

uint16_t crsf_get_channel_us(uint8_t channel)
{
    int32_t raw = crsf_get_channel(channel);
    return (uint16_t)(((raw - 992) * 5) / 8 + 1500);
}

uint8_t crsf_link_ok(uint32_t nowMs)
{
    return g_hasFrame && (nowMs - g_lastFrameMs) < CRSF_LINK_TIMEOUT_MS;
}

uint8_t crsf_switch_on(uint8_t channel, uint32_t nowMs)
{
    return crsf_link_ok(nowMs) && crsf_get_channel(channel) > CRSF_SWITCH_ON_RAW;
}

uint8_t crsf_aux1_on(uint32_t nowMs)
{
    return crsf_switch_on(CRSF_AUX1_CHANNEL, nowMs);
}
