// Raw GPIO sampler v2: high-speed circular capture.
//
// Continuously samples both pins at full speed into a ring buffer (no logging
// inside the sample loop). Triggers a "dump" when activity is detected
// (anything other than both-high), captures for a fixed window, then prints
// every transition with microsecond resolution. After dumping, resumes
// sampling for the next event.
//
// This catches sub-millisecond transitions that ESP_LOGI per-edge cannot.

#include "logic_probe.h"
#include "driver/gpio.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "esp_task_wdt.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <string.h>

#define PIN_RED   1
#define PIN_WHITE 2

#define BUF_LEN   16384  // ~16K samples
#define POST_TRIGGER_SAMPLES 8000

typedef struct {
    int64_t t_us;
    uint8_t state;  // bit0=red bit1=white
} sample_t;

static sample_t buf[BUF_LEN];
static const char *TAG = "probe";

static inline uint8_t read_state(void) {
    int r = gpio_get_level(PIN_RED);
    int w = gpio_get_level(PIN_WHITE);
    return (uint8_t)((r & 1) | ((w & 1) << 1));
}

static void dump_capture(int start_idx, int count) {
    ESP_LOGI(TAG, "=== capture begin (%d samples) ===", count);
    uint8_t prev = 0xFF;
    int printed = 0;
    int64_t base_t = buf[start_idx % BUF_LEN].t_us;

    for (int i = 0; i < count; i++) {
        int idx = (start_idx + i) % BUF_LEN;
        if (buf[idx].state != prev) {
            int r = buf[idx].state & 1;
            int w = (buf[idx].state >> 1) & 1;
            int64_t dt = buf[idx].t_us - base_t;
            ESP_LOGI(TAG, "  +%lld us  red=%d white=%d", (long long)dt, r, w);
            prev = buf[idx].state;
            printed++;
            if (printed > 200) {
                ESP_LOGW(TAG, "  ... (truncated, more transitions follow)");
                break;
            }
        }
    }
    ESP_LOGI(TAG, "=== capture end (%d transitions) ===", printed);
}

static void probe_task(void *arg) {
    gpio_config_t cfg = {
        .pin_bit_mask = (1ULL << PIN_RED) | (1ULL << PIN_WHITE),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&cfg);

    // Subscribe this task to the WDT so we can feed it.
    esp_task_wdt_add(NULL);

    ESP_LOGI(TAG, "v2 sampler online. trigger=any change from idle. run Send( on calc.");
    ESP_LOGI(TAG, "initial: red=%d white=%d", gpio_get_level(PIN_RED), gpio_get_level(PIN_WHITE));

    int write_idx = 0;
    uint8_t idle_state = read_state();  // typically 0b11 (both high)
    int64_t last_wdt = esp_timer_get_time();

    while (1) {
        // Fast pre-trigger fill
        while (1) {
            int64_t now = esp_timer_get_time();
            uint8_t s = read_state();
            buf[write_idx].t_us = now;
            buf[write_idx].state = s;
            write_idx = (write_idx + 1) % BUF_LEN;

            if (s != idle_state) {
                ESP_LOGW(TAG, "TRIGGER at t=%lld state=0x%x", (long long)now, s);
                break;
            }

            // Feed WDT every ~500ms
            if (now - last_wdt > 500000) {
                esp_task_wdt_reset();
                taskYIELD();
                last_wdt = now;
            }
        }

        // Post-trigger: capture more samples
        int trigger_idx = write_idx == 0 ? BUF_LEN - 1 : write_idx - 1;
        int post_count = 0;
        int64_t post_start = esp_timer_get_time();
        int64_t last_activity = post_start;

        while (post_count < POST_TRIGGER_SAMPLES) {
            int64_t now = esp_timer_get_time();
            uint8_t s = read_state();
            buf[write_idx].t_us = now;
            buf[write_idx].state = s;
            write_idx = (write_idx + 1) % BUF_LEN;
            post_count++;

            if (s != idle_state) last_activity = now;

            // If quiet for 200ms, end capture early
            if (now - last_activity > 200000) break;

            if (now - last_wdt > 500000) {
                esp_task_wdt_reset();
                last_wdt = now;
            }
        }

        // Compute window: ~200 pre-trigger samples + post-trigger
        int dump_start = (trigger_idx - 200 + BUF_LEN) % BUF_LEN;
        int dump_count = 200 + post_count;
        dump_capture(dump_start, dump_count);

        ESP_LOGI(TAG, "rearmed. listening for next event.");
        // small pause so log finishes flushing
        vTaskDelay(pdMS_TO_TICKS(100));
        esp_task_wdt_reset();
    }
}

esp_err_t logic_probe_start(void) {
    BaseType_t ok = xTaskCreate(probe_task, "logic_probe", 8192, NULL, 10, NULL);
    return ok == pdPASS ? ESP_OK : ESP_FAIL;
}
