// TI DBUS (link port) bit-banged driver.
//
// Protocol summary: two open-collector lines (red, white), idle high.
// Sender pulls one line low to assert a bit (red=0, white=1), waits for
// the receiver to pull the OTHER line low as ack, sender releases its line,
// receiver releases ack. One bit transferred per handshake. LSB first.
//
// Lines must be configured as open-drain: drive low, or release (input + pullup).

#include "link_dbus.h"
#include "driver/gpio.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "dbus";

static inline void line_release(int gpio) {
    gpio_set_level(gpio, 1); // open-drain "high" = released (pullup wins)
}

static inline void line_pull_low(int gpio) {
    gpio_set_level(gpio, 0);
}

static inline int line_read(int gpio) {
    return gpio_get_level(gpio);
}

static inline int64_t now_us(void) {
    return esp_timer_get_time();
}

static esp_err_t wait_for(int gpio, int level, uint32_t timeout_us) {
    int64_t deadline = now_us() + timeout_us;
    while (line_read(gpio) != level) {
        if (now_us() > deadline) return ESP_ERR_TIMEOUT;
    }
    return ESP_OK;
}

esp_err_t link_dbus_init(void) {
    gpio_config_t cfg = {
        .pin_bit_mask = (1ULL << LINK_GPIO_RED) | (1ULL << LINK_GPIO_WHITE),
        .mode = GPIO_MODE_INPUT_OUTPUT_OD,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    esp_err_t err = gpio_config(&cfg);
    if (err != ESP_OK) return err;

    line_release(LINK_GPIO_RED);
    line_release(LINK_GPIO_WHITE);

    ESP_LOGI(TAG, "init: red=GPIO%d white=GPIO%d (open-drain, pullup)", LINK_GPIO_RED, LINK_GPIO_WHITE);
    return ESP_OK;
}

// Send one bit. bit=0 → pull red low. bit=1 → pull white low.
// Wait for the OTHER line to go low (ack), then release our line, wait for ack release.
static esp_err_t send_bit(int bit, uint32_t timeout_us) {
    int my_line  = bit ? LINK_GPIO_WHITE : LINK_GPIO_RED;
    int ack_line = bit ? LINK_GPIO_RED   : LINK_GPIO_WHITE;

    // Wait until both lines are idle high (peer not currently sending).
    int64_t deadline = now_us() + timeout_us;
    while (line_read(LINK_GPIO_RED) == 0 || line_read(LINK_GPIO_WHITE) == 0) {
        if (now_us() > deadline) return ESP_ERR_TIMEOUT;
    }

    line_pull_low(my_line);

    if (wait_for(ack_line, 0, timeout_us) != ESP_OK) {
        line_release(my_line);
        return ESP_ERR_TIMEOUT;
    }

    line_release(my_line);

    if (wait_for(ack_line, 1, timeout_us) != ESP_OK) {
        return ESP_ERR_TIMEOUT;
    }

    return ESP_OK;
}

// Receive one bit. Wait for one line to go low, that's the data bit.
// Pull the other line low as ack, wait for sender to release, then release ack.
static esp_err_t recv_bit(int *bit, uint32_t timeout_us) {
    int64_t deadline = now_us() + timeout_us;

    int red, white;
    while (1) {
        red   = line_read(LINK_GPIO_RED);
        white = line_read(LINK_GPIO_WHITE);
        if (red == 0 && white == 1) { *bit = 0; break; }
        if (red == 1 && white == 0) { *bit = 1; break; }
        if (now_us() > deadline) return ESP_ERR_TIMEOUT;
    }

    int ack_line  = (*bit) ? LINK_GPIO_RED   : LINK_GPIO_WHITE;
    int data_line = (*bit) ? LINK_GPIO_WHITE : LINK_GPIO_RED;

    line_pull_low(ack_line);

    if (wait_for(data_line, 1, timeout_us) != ESP_OK) {
        line_release(ack_line);
        return ESP_ERR_TIMEOUT;
    }

    line_release(ack_line);
    return ESP_OK;
}

esp_err_t link_dbus_send_byte(uint8_t b, uint32_t timeout_us) {
    for (int i = 0; i < 8; i++) {
        int bit = (b >> i) & 1; // LSB first
        esp_err_t err = send_bit(bit, timeout_us);
        if (err != ESP_OK) return err;
    }
    return ESP_OK;
}

esp_err_t link_dbus_recv_byte(uint8_t *out, uint32_t timeout_us) {
    uint8_t b = 0;
    for (int i = 0; i < 8; i++) {
        int bit;
        esp_err_t err = recv_bit(&bit, timeout_us == 0 ? UINT32_MAX : timeout_us);
        if (err != ESP_OK) return err;
        b |= (bit & 1) << i;
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
