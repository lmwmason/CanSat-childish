#ifndef PI_LINK_H
#define PI_LINK_H

#include <stdint.h>
#include <stdbool.h>
#include "cansat_hal.h"

/*
 * Minimal UART frame protocol between STM32 and the companion Pi:
 *   [0xAA sync][type][len][payload...][checksum]
 * checksum = type ^ len ^ payload[0] ^ payload[1] ^ ...
 *
 * This is the ONLY thing the failsafe logic depends on: as long as
 * HEARTBEAT frames keep arriving within pi_link_timeout_ms, the link
 * is considered alive. No Pi code (or a Pi that never boots) simply
 * never satisfies this, which is what drives the mothership into
 * CTRL_FAILSAFE_AUTONOMOUS.
 */
#define PI_LINK_SYNC 0xAA
#define PI_LINK_FRAME_HEARTBEAT     0x01
#define PI_LINK_FRAME_ACTUATOR_CMD  0x02 /* payload: int16 cmd[2], scaled x1000 */

typedef struct {
    uint32_t last_heartbeat_ms;
    bool have_actuator_cmd;
    float actuator_cmd[2];

    /* byte parser state */
    int parse_state;
    uint8_t rx_type;
    uint8_t rx_len;
    uint8_t rx_payload[16];
    uint8_t rx_idx;
} pi_link_t;

void pi_link_init(pi_link_t *pl);
void pi_link_poll(pi_link_t *pl, const cansat_hal_t *hal, uint32_t now_ms);
bool pi_link_is_alive(const pi_link_t *pl, uint32_t now_ms, uint32_t timeout_ms);

#endif /* PI_LINK_H */
