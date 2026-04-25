#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "link_dbus.h"
#include "wifi.h"
#include "tcp_bridge.h"
#include "secrets.h"

static const char *TAG = "ti84sd";

void app_main(void) {
    ESP_LOGI(TAG, "ti84-superdeluxe boot");

    ESP_ERROR_CHECK(link_dbus_init());

    if (wifi_start_and_wait() != ESP_OK) {
        ESP_LOGE(TAG, "wifi failed, halting");
        while (1) vTaskDelay(pdMS_TO_TICKS(1000));
    }

    ESP_ERROR_CHECK(tcp_bridge_start(TCP_BRIDGE_PORT));

    ESP_LOGI(TAG, "bridge ready, port %d", TCP_BRIDGE_PORT);
}
