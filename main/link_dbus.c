// TI DBUS bit-banged driver, modeled directly on ArTICL (KermMartian).
//
// Idle state: both lines INPUT with internal pull-up (high-impedance, weak high).
// To drive a line low: switch to OUTPUT and write 0.
// To release: switch back to INPUT_PULLUP.
//
// Tip = "red wire" = bit value 0
// Ring = "white wire" = bit value 1
// LSB first.

#include "link_dbus.h"
#include "driver/gpio.h"
#include "esp_timer.h"
#include "esp_log.h"
#include <stdint.h>

static const char *TAG = "dbus";

static link_dbus_recv_stats_t g_stats;

void link_dbus_get_recv_stats(link_dbus_recv_stats_t *out) { *out = g_stats; }
void link_dbus_reset_recv_stats(void) {
    g_stats = (link_dbus_recv_stats_t){0};
}

#define TIP   LINK_GPIO_RED    // GPIO1
#define RING  LINK_GPIO_WHITE  // GPIO2

static inline int64_t now_us(void) {
    return esp_timer_get_time();
}

static inline int read_pin(int pin) {
    return gpio_get_level(pin);
}

// Release a single line: input with internal pull-up (idle high)
static inline void release_line(int pin) {
    gpio_set_direction(pin, GPIO_MODE_INPUT);
    gpio_set_pull_mode(pin, GPIO_PULLUP_ONLY);
}

// Pull a single line low: output, write 0
static inline void pull_line_low(int pin) {
    gpio_set_direction(pin, GPIO_MODE_OUTPUT);
    gpio_set_level(pin, 0);
}

static void reset_lines(void) {
    release_line(TIP);
    release_line(RING);
}

esp_err_t link_dbus_init(void) {
    // Configure both pins as INPUT_PULLUP idle. No interrupt.
    gpio_config_t cfg = {
        .pin_bit_mask = (1ULL << TIP) | (1ULL << RING),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    esp_err_t err = gpio_config(&cfg);
    if (err != ESP_OK) return err;

    reset_lines();
    ESP_LOGI(TAG, "init: tip=GPIO%d ring=GPIO%d (input + pullup idle)", TIP, RING);
    return ESP_OK;
}

// Send one bit using ArTICL-pattern handshake.
static esp_err_t send_bit(int bit, uint32_t timeout_us) {
    int64_t deadline;

    // Wait for both lines high (peer idle) before driving
    deadline = now_us() + timeout_us;
    while (read_pin(TIP) == 0 || read_pin(RING) == 0) {
        if (now_us() > deadline) {
            reset_lines();
            return ESP_ERR_TIMEOUT;
        }
    }

    // Drive our line low: tip for bit=0, ring for bit=1
    int my_line = bit ? RING : TIP;
    int ack_line = bit ? TIP : RING;
    pull_line_low(my_line);

    // Wait for peer to ack by pulling the OTHER line low
    deadline = now_us() + timeout_us;
    while (read_pin(ack_line) == 1) {
        if (now_us() > deadline) {
            reset_lines();
            return ESP_ERR_TIMEOUT;
        }
    }

    // Release our line. Peer will release theirs.
    reset_lines();

    // Wait for peer's ack line to release back to high
    deadline = now_us() + timeout_us;
    while (read_pin(ack_line) == 0) {
        if (now_us() > deadline) {
            reset_lines();
            return ESP_ERR_TIMEOUT;
        }
    }
    reset_lines();
    return ESP_OK;
}

// Receive one bit. Wait for one of the lines to go low, that determines the bit.
// Then ack by pulling the OTHER line low. Wait for peer's line to release.
static esp_err_t recv_bit(int *bit, uint32_t timeout_us) {
    int64_t deadline = now_us() + timeout_us;
    int linevals;

    // Wait until at least one line is low CONSISTENTLY (peer started a bit).
    // Debounce: require the same non-idle reading for ~10us to reject glitches.
    while (1) {
        int t = read_pin(TIP);
        int r = read_pin(RING);
        linevals = (r << 1) | t;
        if (linevals != 0b11) {
            // Confirm by re-sampling for ~10us
            int stable = 1;
            int64_t confirm_until = now_us() + 10;
            while (now_us() < confirm_until) {
                int t2 = read_pin(TIP);
                int r2 = read_pin(RING);
                int v2 = (r2 << 1) | t2;
                if (v2 == 0b11) { stable = 0; break; }
                linevals = v2;
            }
            if (stable) break;
        }
        if (now_us() > deadline) {
            g_stats.timeout_waiting_start++;
            reset_lines();
            return ESP_ERR_TIMEOUT;
        }
    }

    g_stats.bits_started++;
    g_stats.last_linevals = (uint32_t)linevals;

    // linevals = (ring<<1) | tip. tip low ⇒ 0b10 ⇒ bit 0. ring low ⇒ 0b01 ⇒ bit 1.
    *bit = (linevals == 0b10) ? 0 : 1;
    g_stats.last_bit_value = (uint32_t)*bit;

    // Pull the OTHER line low to ack
    int ack_line = (*bit == 0) ? RING : TIP;
    int peer_line = (*bit == 0) ? TIP : RING;
    pull_line_low(ack_line);

    // Wait for peer to release their line (go high)
    int64_t phase_b_start = now_us();
    deadline = phase_b_start + timeout_us;
    while (read_pin(peer_line) == 0) {
        if (now_us() > deadline) {
            g_stats.timeout_waiting_release++;
            g_stats.last_phase_b_us = now_us() - phase_b_start;
            reset_lines();
            return ESP_ERR_TIMEOUT;
        }
    }

    g_stats.last_phase_b_us = now_us() - phase_b_start;
    g_stats.bits_completed++;
    reset_lines();
    return ESP_OK;
}

esp_err_t link_dbus_send_byte(uint8_t b, uint32_t timeout_us) {
    for (int i = 0; i < 8; i++) {
        int bit = b & 1;
        esp_err_t err = send_bit(bit, timeout_us);
        if (err != ESP_OK) return err;
        b >>= 1;
    }
    return ESP_OK;
}

esp_err_t link_dbus_recv_byte(uint8_t *out, uint32_t timeout_us) {
    uint8_t b = 0;
    for (int i = 0; i < 8; i++) {
        int bit;
        esp_err_t err = recv_bit(&bit, timeout_us == 0 ? UINT32_MAX : timeout_us);
        if (err != ESP_OK) return err;
        // LSB first: each new bit goes into MSB, then shift down (matches ArTICL getByte)
        b = (b >> 1) | (bit ? 0x80 : 0x00);
    }
    *out = b;
    return ESP_OK;
}

esp_err_t link_dbus_send(const uint8_t *buf, size_t len, uint32_t per_byte_timeout_us) {
    for (size_t i = 0; i < len; i++) {
        esp_err_t err = link_dbus_send_byte(buf[i], per_byte_timeout_us);
        if (err != ESP_OK) return err;
    }
    return ESP_OK;
}

esp_err_t link_dbus_recv(uint8_t *buf, size_t maxlen, size_t *out_len, uint32_t per_byte_timeout_us) {
    size_t i = 0;
    while (i < maxlen) {
        esp_err_t err = link_dbus_recv_byte(&buf[i], per_byte_timeout_us);
        if (err == ESP_ERR_TIMEOUT) break;
        if (err != ESP_OK) { *out_len = i; return err; }
        i++;
    }
    *out_len = i;
    return ESP_OK;
}

esp_err_t link_dbus_recv_header(link_dbus_header_t *hdr, uint32_t per_byte_timeout_us) {
    uint8_t b[4];
    for (int i = 0; i < 4; i++) {
        esp_err_t err = link_dbus_recv_byte(&b[i], per_byte_timeout_us);
        if (err != ESP_OK) return err;
    }
    hdr->machine_id = b[0];
    hdr->command = b[1];
    hdr->length = (uint16_t)b[2] | ((uint16_t)b[3] << 8);
    return ESP_OK;
}

esp_err_t link_dbus_recv_payload(uint8_t *buf, uint16_t length, uint32_t per_byte_timeout_us) {
    uint16_t sum = 0;
    for (uint16_t i = 0; i < length; i++) {
        esp_err_t err = link_dbus_recv_byte(&buf[i], per_byte_timeout_us);
        if (err != ESP_OK) return err;
        sum += buf[i];
    }
    uint8_t cks[2];
    for (int i = 0; i < 2; i++) {
        esp_err_t err = link_dbus_recv_byte(&cks[i], per_byte_timeout_us);
        if (err != ESP_OK) return err;
    }
    uint16_t recv_sum = (uint16_t)cks[0] | ((uint16_t)cks[1] << 8);
    if (recv_sum != sum) {
        ESP_LOGW(TAG, "checksum mismatch: got 0x%04x, computed 0x%04x", recv_sum, sum);
        return ESP_ERR_INVALID_CRC;
    }
    return ESP_OK;
}

esp_err_t link_dbus_send_packet(uint8_t machine_id, uint8_t command,
                                const uint8_t *payload, uint16_t length,
                                uint32_t per_byte_timeout_us) {
    uint8_t hdr[4] = {
        machine_id,
        command,
        (uint8_t)(length & 0xFF),
        (uint8_t)((length >> 8) & 0xFF),
    };
    esp_err_t err = link_dbus_send(hdr, 4, per_byte_timeout_us);
    if (err != ESP_OK) return err;
    if (length == 0 || payload == NULL) return ESP_OK;

    uint16_t sum = 0;
    for (uint16_t i = 0; i < length; i++) sum += payload[i];
    err = link_dbus_send(payload, length, per_byte_timeout_us);
    if (err != ESP_OK) return err;
    uint8_t cks[2] = { (uint8_t)(sum & 0xFF), (uint8_t)((sum >> 8) & 0xFF) };
    return link_dbus_send(cks, 2, per_byte_timeout_us);
}
