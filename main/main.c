// Receive a full TI variable transfer.
// Expected sequence on the wire (calc → ESP, ESP → calc):
//   calc: RTS  hdr+payload+cks  (0xC9, "ready to send variable X")
//   ESP : ACK  hdr-only         (0x56)
//   ESP : CTS  hdr-only         (0x09, "go ahead")
//   calc: DATA hdr+payload+cks  (0x15, the actual variable data)
//   ESP : ACK  hdr-only         (0x56)
//   calc: EOT  hdr-only         (0x92, "we're done")
//   ESP : ACK  hdr-only         (0x56)
//
// Header-only packets have length=0 and no payload/checksum on the wire.

#include "esp_log.h"
#include "esp_timer.h"
#include "esp_rom_sys.h"
#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "link_dbus.h"

static const char *TAG = "ti84sd";

// TI command IDs (mirroring vendor/ArTICL/TICL.h)
#define CMD_VAR  0x06
#define CMD_CTS  0x09
#define CMD_DATA 0x15
#define CMD_ACK  0x56
#define CMD_EOT  0x92
#define CMD_RTS  0xC9

// 5-second per-byte timeout. Plenty even on a sluggish link.
#define BYTE_TIMEOUT_US (5LL * 1000LL * 1000LL)

// Our endpoint when replying. We identify as a computer (COMP83P = 0x23).
// The calc sends RTS with its own endpoint (0x82 in our captures); we reply
// with ours, not theirs — same as ArTICL's CBL2 receive flow.
static uint8_t g_our_endpoint = 0x23;

static const char *cmd_name(uint8_t c) {
    switch (c) {
        case CMD_VAR:  return "VAR";
        case CMD_CTS:  return "CTS";
        case CMD_DATA: return "DATA";
        case CMD_ACK:  return "ACK";
        case CMD_EOT:  return "EOT";
        case CMD_RTS:  return "RTS";
        default:       return "?";
    }
}

static void hexdump(const uint8_t *buf, size_t len) {
    char line[3 * 16 + 1];
    for (size_t off = 0; off < len; off += 16) {
        size_t row = (len - off) < 16 ? (len - off) : 16;
        char *p = line;
        for (size_t i = 0; i < row; i++) {
            p += snprintf(p, 4, "%02x ", buf[off + i]);
        }
        *p = 0;
        ESP_LOGI(TAG, "  %04zx: %s", off, line);
    }
}

// Header-only commands carry no payload on the wire even when their length
// field is non-zero (some calc firmwares stuff the prior var size into EOT's
// length field as a "transfer of N bytes done" closing marker).
static int is_header_only_cmd(uint8_t cmd) {
    return cmd == CMD_ACK || cmd == CMD_CTS || cmd == CMD_EOT;
}

// Receive one packet. Header always; payload+checksum only when the command
// actually carries a payload (RTS, DATA, etc.).
static esp_err_t recv_packet(link_dbus_header_t *hdr, uint8_t *payload_buf, size_t payload_cap) {
    esp_err_t err = link_dbus_recv_header(hdr, BYTE_TIMEOUT_US);
    if (err != ESP_OK) return err;

    ESP_LOGI(TAG, "<- %-4s  ep=0x%02x  len=%u",
             cmd_name(hdr->command), hdr->machine_id, hdr->length);

    if (is_header_only_cmd(hdr->command)) return ESP_OK;
    if (hdr->length == 0) return ESP_OK;
    if (hdr->length > payload_cap) {
        ESP_LOGE(TAG, "payload too large: %u > %u", hdr->length, (unsigned)payload_cap);
        return ESP_ERR_NO_MEM;
    }
    err = link_dbus_recv_payload(payload_buf, hdr->length, BYTE_TIMEOUT_US);
    if (err == ESP_OK || err == ESP_ERR_INVALID_CRC) hexdump(payload_buf, hdr->length);
    return err;
}

static esp_err_t send_header_only(uint8_t cmd) {
    ESP_LOGI(TAG, "-> %-4s  ep=0x%02x", cmd_name(cmd), g_our_endpoint);
    return link_dbus_send_packet(g_our_endpoint, cmd, NULL, 0, BYTE_TIMEOUT_US);
}

void app_main(void) {
    ESP_LOGI(TAG, "ti84-superdeluxe — full receive state machine");
    ESP_ERROR_CHECK(link_dbus_init());

    static uint8_t payload[1024];

    while (1) {
        ESP_LOGI(TAG, "=== waiting for transfer (press Send on calc) ===");

        link_dbus_header_t hdr;
        // Step 1: wait for RTS
        esp_err_t err = recv_packet(&hdr, payload, sizeof(payload));
        if (err != ESP_OK) {
            // Quiet timeouts (no peer talking) just loop. Other errors get logged.
            if (err != ESP_ERR_TIMEOUT) ESP_LOGW(TAG, "recv RTS: err %d", err);
            vTaskDelay(pdMS_TO_TICKS(50));
            continue;
        }
        if (hdr.command != CMD_RTS) {
            ESP_LOGW(TAG, "expected RTS, got 0x%02x — restarting", hdr.command);
            continue;
        }
        // Keep g_our_endpoint = 0x23 (COMP83P) — we reply as a computer.

        // Step 2: ACK the RTS
        err = send_header_only(CMD_ACK);
        if (err != ESP_OK) { ESP_LOGW(TAG, "send ACK: err %d", err); continue; }

        // Step 3: send CTS
        err = send_header_only(CMD_CTS);
        if (err != ESP_OK) { ESP_LOGW(TAG, "send CTS: err %d", err); continue; }

        // Step 4: receive ACK from calc (acknowledging our CTS)
        err = recv_packet(&hdr, payload, sizeof(payload));
        if (err != ESP_OK) { ESP_LOGW(TAG, "recv post-CTS ACK: err %d", err); continue; }
        if (hdr.command != CMD_ACK) {
            ESP_LOGW(TAG, "expected ACK, got 0x%02x", hdr.command);
            continue;
        }

        // Step 5: receive DATA
        err = recv_packet(&hdr, payload, sizeof(payload));
        if (err != ESP_OK) { ESP_LOGW(TAG, "recv DATA: err %d", err); continue; }
        if (hdr.command != CMD_DATA) {
            ESP_LOGW(TAG, "expected DATA, got 0x%02x", hdr.command);
            continue;
        }

        // Step 6: ACK the DATA
        err = send_header_only(CMD_ACK);
        if (err != ESP_OK) { ESP_LOGW(TAG, "send post-DATA ACK: err %d", err); continue; }

        // Settle gap: let the wire fully release before we start listening for
        // EOT. Without this we sometimes catch a phantom start edge from the
        // tail of our own ACK send and decode the EOT header misaligned.
        esp_rom_delay_us(200);

        // Step 7: receive EOT
        err = recv_packet(&hdr, payload, sizeof(payload));
        if (err != ESP_OK) { ESP_LOGW(TAG, "recv EOT: err %d", err); continue; }
        if (hdr.command != CMD_EOT) {
            ESP_LOGW(TAG, "expected EOT, got 0x%02x", hdr.command);
            continue;
        }

        // Step 7: final ACK
        err = send_header_only(CMD_ACK);
        if (err != ESP_OK) { ESP_LOGW(TAG, "send final ACK: err %d", err); continue; }

        ESP_LOGI(TAG, "=== TRANSFER COMPLETE ===");
    }
}
