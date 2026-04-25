// Transparent TCP <-> DBUS bridge.
//
// Server accepts one client at a time on the configured port. Bytes received
// on the socket are sent out the calc link port. Bytes received from the link
// port are forwarded back to the socket. No framing — raw bytes both ways.
//
// Two FreeRTOS tasks once a client connects: socket→link and link→socket.

#include "tcp_bridge.h"
#include "link_dbus.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"
#include <string.h>
#include <errno.h>

static const char *TAG = "bridge";

#define DBUS_BIT_TIMEOUT_US 500000  // 500ms per bit handshake max

typedef struct {
    int sock;
} bridge_ctx_t;

static void link_to_sock_task(void *arg) {
    bridge_ctx_t *ctx = arg;
    uint8_t b;
    while (1) {
        // Short timeout so we yield often and notice if the calc went away.
        esp_err_t err = link_dbus_recv_byte(&b, 100000);
        if (err == ESP_OK) {
            int sent = send(ctx->sock, &b, 1, 0);
            if (sent <= 0) {
                ESP_LOGW(TAG, "send() failed: errno=%d", errno);
                break;
            }
            ESP_LOGI(TAG, "calc->host: 0x%02x", b);
        } else if (err == ESP_ERR_TIMEOUT) {
            // No byte from calc this window. Loop and try again.
            taskYIELD();
        } else {
            ESP_LOGW(TAG, "link_dbus_recv_byte err=%d", err);
            break;
        }
    }
    vTaskDelete(NULL);
}

static void handle_client(int sock) {
    bridge_ctx_t ctx = { .sock = sock };
    TaskHandle_t link_task = NULL;
    xTaskCreate(link_to_sock_task, "link2sock", 4096, &ctx, 5, &link_task);

    uint8_t buf[64];
    while (1) {
        int n = recv(sock, buf, sizeof(buf), 0);
        if (n <= 0) {
            if (n < 0) ESP_LOGW(TAG, "recv() errno=%d", errno);
            break;
        }
        for (int i = 0; i < n; i++) {
            esp_err_t err = link_dbus_send_byte(buf[i], DBUS_BIT_TIMEOUT_US);
            if (err != ESP_OK) {
                ESP_LOGW(TAG, "link_dbus_send_byte err=%d at byte %d", err, i);
                goto done;
            }
            ESP_LOGI(TAG, "host->calc: 0x%02x", buf[i]);
        }
    }
done:
    if (link_task) vTaskDelete(link_task);
    close(sock);
    ESP_LOGI(TAG, "client closed");
}

static void server_task(void *arg) {
    int port = (int)(intptr_t)arg;

    int listen_sock = socket(AF_INET, SOCK_STREAM, 0);
    if (listen_sock < 0) {
        ESP_LOGE(TAG, "socket() failed: errno=%d", errno);
        vTaskDelete(NULL);
        return;
    }

    int yes = 1;
    setsockopt(listen_sock, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));

    struct sockaddr_in addr = {
        .sin_family = AF_INET,
        .sin_addr.s_addr = htonl(INADDR_ANY),
        .sin_port = htons(port),
    };
    if (bind(listen_sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        ESP_LOGE(TAG, "bind() failed: errno=%d", errno);
        close(listen_sock);
        vTaskDelete(NULL);
        return;
    }
    if (listen(listen_sock, 1) < 0) {
        ESP_LOGE(TAG, "listen() failed: errno=%d", errno);
        close(listen_sock);
        vTaskDelete(NULL);
        return;
    }

    ESP_LOGI(TAG, "listening on :%d", port);

    while (1) {
        struct sockaddr_in client;
        socklen_t client_len = sizeof(client);
        int sock = accept(listen_sock, (struct sockaddr *)&client, &client_len);
        if (sock < 0) {
            ESP_LOGW(TAG, "accept() failed: errno=%d", errno);
            continue;
        }
        char ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &client.sin_addr, ip, sizeof(ip));
        ESP_LOGI(TAG, "client connected from %s", ip);
        handle_client(sock);
    }
}

esp_err_t tcp_bridge_start(int port) {
    BaseType_t ok = xTaskCreate(server_task, "tcp_bridge", 4096,
                                (void *)(intptr_t)port, 5, NULL);
    return ok == pdPASS ? ESP_OK : ESP_FAIL;
}
