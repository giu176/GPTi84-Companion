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
