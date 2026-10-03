#include "pi_link.h"
#include <string.h>

enum { PS_SYNC = 0, PS_TYPE, PS_LEN, PS_PAYLOAD, PS_CHECKSUM };

void pi_link_init(pi_link_t *pl) {
    memset(pl, 0, sizeof(*pl));
    pl->parse_state = PS_SYNC;
}

static void handle_frame(pi_link_t *pl, uint32_t now_ms) {
    if (pl->rx_type == PI_LINK_FRAME_HEARTBEAT) {
        pl->last_heartbeat_ms = now_ms;
    } else if (pl->rx_type == PI_LINK_FRAME_ACTUATOR_CMD && pl->rx_len == 4) {
        int16_t a0, a1;
        memcpy(&a0, &pl->rx_payload[0], sizeof(a0));
        memcpy(&a1, &pl->rx_payload[2], sizeof(a1));
        pl->actuator_cmd[0] = a0 / 1000.0f;
        pl->actuator_cmd[1] = a1 / 1000.0f;
        pl->have_actuator_cmd = true;
        pl->last_heartbeat_ms = now_ms; /* any valid frame counts as liveness */
    }
}

void pi_link_poll(pi_link_t *pl, const cansat_hal_t *hal, uint32_t now_ms) {
    if (!hal->pi_uart_read) return;

    uint8_t buf[64];
    int n = hal->pi_uart_read(hal->ctx, buf, (int)sizeof(buf));
    for (int i = 0; i < n; i++) {
        uint8_t b = buf[i];
        switch (pl->parse_state) {
        case PS_SYNC:
            if (b == PI_LINK_SYNC) pl->parse_state = PS_TYPE;
            break;
        case PS_TYPE:
            pl->rx_type = b;
            pl->parse_state = PS_LEN;
            break;
        case PS_LEN:
            pl->rx_len = b;
            pl->rx_idx = 0;
            if (pl->rx_len == 0) pl->parse_state = PS_CHECKSUM;
            else if (pl->rx_len > sizeof(pl->rx_payload)) pl->parse_state = PS_SYNC; /* malformed */
            else pl->parse_state = PS_PAYLOAD;
            break;
        case PS_PAYLOAD:
            pl->rx_payload[pl->rx_idx++] = b;
            if (pl->rx_idx >= pl->rx_len) pl->parse_state = PS_CHECKSUM;
            break;
        case PS_CHECKSUM: {
            uint8_t chk = (uint8_t)(pl->rx_type ^ pl->rx_len);
            for (int k = 0; k < pl->rx_len; k++) chk ^= pl->rx_payload[k];
            if (chk == b) handle_frame(pl, now_ms);
            pl->parse_state = PS_SYNC;
            break;
        }
        default:
            pl->parse_state = PS_SYNC;
            break;
        }
    }
}

bool pi_link_is_alive(const pi_link_t *pl, uint32_t now_ms, uint32_t timeout_ms) {
    if (pl->last_heartbeat_ms == 0) return false;
    return (now_ms - pl->last_heartbeat_ms) <= timeout_ms;
}
