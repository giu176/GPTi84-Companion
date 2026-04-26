#pragma once

#include <stdint.h>
#include <stddef.h>
#include "esp_err.h"

#define LINK_GPIO_RED   1
#define LINK_GPIO_WHITE 2

esp_err_t link_dbus_init(void);

// Send one DBUS byte. Blocks until done or timeout. Returns ESP_OK or ESP_ERR_TIMEOUT.
esp_err_t link_dbus_send_byte(uint8_t b, uint32_t timeout_us);

// Receive one DBUS byte. Blocks. timeout_us == 0 means wait forever.
esp_err_t link_dbus_recv_byte(uint8_t *out, uint32_t timeout_us);

// Send a buffer of raw bytes. No framing — pure DBUS-byte transport.
esp_err_t link_dbus_send(const uint8_t *buf, size_t len, uint32_t per_byte_timeout_us);

// Receive into buffer. Returns number of bytes actually read in *out_len.
esp_err_t link_dbus_recv(uint8_t *buf, size_t maxlen, size_t *out_len, uint32_t per_byte_timeout_us);

// Diagnostic counters for the recv path. Updated in place by recv_bit.
typedef struct {
    uint32_t bits_started;          // edge detected, debounce passed
    uint32_t bits_completed;        // full handshake including peer release
    uint32_t timeout_waiting_start; // (A) never saw a start edge
    uint32_t timeout_waiting_release; // (B) saw start, acked, peer never released
    int64_t  last_phase_b_us;       // duration of the most recent phase-B wait
    uint32_t last_bit_value;        // 0 or 1 (only valid if bits_started > 0)
    uint32_t last_linevals;         // raw linevals at last decode
} link_dbus_recv_stats_t;

void link_dbus_get_recv_stats(link_dbus_recv_stats_t *out);
void link_dbus_reset_recv_stats(void);

// Packet-level header. Matches TI DBUS framing:
//   byte 0: machine ID (endpoint)
//   byte 1: command ID
//   bytes 2-3: little-endian payload length
typedef struct {
    uint8_t  machine_id;
    uint8_t  command;
    uint16_t length;
} link_dbus_header_t;

// Receive a 4-byte header. Blocks per byte up to per_byte_timeout_us.
esp_err_t link_dbus_recv_header(link_dbus_header_t *hdr, uint32_t per_byte_timeout_us);

// Receive a payload of `length` bytes followed by a 2-byte little-endian checksum.
// Validates checksum (sum of payload bytes mod 65536). Returns ESP_ERR_INVALID_CRC on mismatch.
esp_err_t link_dbus_recv_payload(uint8_t *buf, uint16_t length, uint32_t per_byte_timeout_us);

// Send a header + optional payload + checksum. Computes checksum if payload is present.
esp_err_t link_dbus_send_packet(uint8_t machine_id, uint8_t command,
                                const uint8_t *payload, uint16_t length,
                                uint32_t per_byte_timeout_us);
