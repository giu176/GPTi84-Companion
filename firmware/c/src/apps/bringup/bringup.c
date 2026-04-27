// Pico W bring-up validation.
//
// Wiring: jumper between GP2 (pin 4) and GP3 (pin 5). GP2 driven, GP3 read.
//
// Build: see firmware/c/README.md. Flash bringup.uf2 via BOOTSEL or
//   `picotool load -f firmware/c/build/bringup.uf2 && picotool reboot`.
// Observe: `tio /dev/ttyACM0` (or any USB-CDC monitor) at any baud.

#include <stdio.h>
#include <stdlib.h>

#include "pico/stdlib.h"
#include "pico/cyw43_arch.h"
#include "hardware/pio.h"
#include "hardware/clocks.h"

#include "bringup.pio.h"

#define PIN_OUT 2
#define PIN_IN  3

static void fail(const char *msg) {
    printf("FAIL: %s\n", msg);
    while (true) {
        sleep_ms(1000);
    }
}

static void wait_for_serial(void) {
    // Give a USB-CDC host time to attach so we don't drop the first prints.
    // 3 s is enough for `tio` reconnect; bump if you miss output.
    sleep_ms(3000);
}

// 1. CPU GPIO loopback.
static void test_gpio_loopback(void) {
    gpio_init(PIN_OUT);
    gpio_set_dir(PIN_OUT, GPIO_OUT);
    gpio_init(PIN_IN);
    gpio_set_dir(PIN_IN, GPIO_IN);

    gpio_put(PIN_OUT, 0);
    sleep_ms(2);
    if (gpio_get(PIN_IN) != 0) {
        fail("GP2 driven LOW but GP3 reads HIGH (jumper or pin map wrong)");
    }
    gpio_put(PIN_OUT, 1);
    sleep_ms(2);
    if (gpio_get(PIN_IN) != 1) {
        fail("GP2 driven HIGH but GP3 reads LOW (jumper or pin map wrong)");
    }
    printf("PASS: CPU GPIO drives GP2 and GP3 follows it.\n");
}

// 2. PIO claims a pin and holds it. Confirms PIO programs assemble, load,
//    and execute.
static void test_pio_hold(void) {
    PIO pio = pio0;
    uint sm = 0;
    uint offset = pio_add_program(pio, &hold_high_program);
    pio_sm_config c = hold_high_program_get_default_config(offset);
    sm_config_set_set_pins(&c, PIN_OUT, 1);
    pio_gpio_init(pio, PIN_OUT);
    pio_sm_set_consecutive_pindirs(pio, sm, PIN_OUT, 1, true);
    pio_sm_init(pio, sm, offset, &c);
    pio_sm_set_enabled(pio, sm, true);

    sleep_ms(5);
    int held = gpio_get(PIN_IN);

    pio_sm_set_enabled(pio, sm, false);
    pio_remove_program(pio, &hold_high_program, offset);
    // Hand the pin back to the SIO so later tests own it cleanly.
    gpio_init(PIN_OUT);
    gpio_set_dir(PIN_OUT, GPIO_OUT);

    if (held != 1) {
        fail("PIO program ran but did not drive GP2 HIGH");
    }
    printf("PASS: PIO program drives a pin independently of CPU.\n");
}

// 3. PIO shifts FIFO data onto a pin at a configured bit rate.
//    Pattern is alternating 0xAA bytes -> exactly 8 edges per byte.
//    With N bytes at BIT_HZ, expect 8*N - 1 edges over (8*N / BIT_HZ) seconds.
//    Sampled from the CPU; allow slop.
static void test_pio_shift(void) {
    const uint32_t BIT_HZ = 2000;
    const uint32_t N_BYTES = 4;
    const uint32_t EXPECTED_EDGES = 8 * N_BYTES - 1;

    PIO pio = pio0;
    uint sm = 0;
    uint offset = pio_add_program(pio, &shift_out_program);
    pio_sm_config c = shift_out_program_get_default_config(offset);
    sm_config_set_out_pins(&c, PIN_OUT, 1);
    sm_config_set_out_shift(&c, true /*shift_right*/, true /*autopull*/, 8);
    pio_gpio_init(pio, PIN_OUT);
    pio_sm_set_consecutive_pindirs(pio, sm, PIN_OUT, 1, true);

    // Each `out` instruction has [1] delay -> 2 cycles per bit.
    float div = (float)clock_get_hz(clk_sys) / (float)(BIT_HZ * 2);
    sm_config_set_clkdiv(&c, div);

    pio_sm_init(pio, sm, offset, &c);

    for (uint32_t i = 0; i < N_BYTES; i++) {
        pio_sm_put_blocking(pio, sm, 0xAA);
    }

    int last = gpio_get(PIN_IN);
    int edges = 0;
    pio_sm_set_enabled(pio, sm, true);

    absolute_time_t deadline = make_timeout_time_ms(
        (1000 * 8 * N_BYTES) / BIT_HZ + 50);
    while (absolute_time_diff_us(get_absolute_time(), deadline) > 0) {
        int v = gpio_get(PIN_IN);
        if (v != last) {
            edges++;
            last = v;
        }
    }
    pio_sm_set_enabled(pio, sm, false);
    pio_remove_program(pio, &shift_out_program, offset);
    gpio_init(PIN_OUT);
    gpio_set_dir(PIN_OUT, GPIO_OUT);

    if ((uint32_t)edges < EXPECTED_EDGES / 2) {
        char buf[96];
        snprintf(buf, sizeof(buf),
                 "PIO FIFO shift produced %d edges, expected ~%u",
                 edges, EXPECTED_EDGES);
        fail(buf);
    }
    printf("PASS: PIO shifts FIFO bytes onto pin (counted %d edges, expected ~%u).\n",
           edges, EXPECTED_EDGES);
}

// 4. WiFi radio is functional. Init CYW43, scan, deinit.
static int scan_result(void *env, const cyw43_ev_scan_result_t *r) {
    (void)env;
    (void)r;
    int *count = (int *)env;
    (*count)++;
    return 0;
}

static void test_wifi_scan(void) {
    if (cyw43_arch_init()) {
        fail("cyw43_arch_init() failed -- CYW43 driver not ready");
    }
    cyw43_arch_enable_sta_mode();

    int aps = 0;
    cyw43_wifi_scan_options_t opts = {0};
    if (cyw43_wifi_scan(&cyw43_state, &opts, &aps, scan_result) != 0) {
        cyw43_arch_deinit();
        fail("cyw43_wifi_scan() failed to start");
    }

    // Block until the scan finishes (or 10 s, whichever first).
    absolute_time_t deadline = make_timeout_time_ms(10000);
    while (cyw43_wifi_scan_active(&cyw43_state)) {
        if (absolute_time_diff_us(get_absolute_time(), deadline) <= 0) break;
        sleep_ms(100);
    }

    uint8_t mac[6] = {0};
    cyw43_wifi_get_mac(&cyw43_state, CYW43_ITF_STA, mac);

    cyw43_arch_deinit();

    bool mac_zero = (mac[0] | mac[1] | mac[2] | mac[3] | mac[4] | mac[5]) == 0;
    if (mac_zero) {
        fail("WiFi MAC reads as zero -- CYW43 driver not initialized");
    }
    printf("PASS: WiFi radio active, MAC %02x:%02x:%02x:%02x:%02x:%02x, %d APs visible.\n",
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5], aps);
}

int main(void) {
    stdio_init_all();
    wait_for_serial();

    printf("\nti84-superdeluxe Pico W bring-up (C)\n");
    printf("====================================\n");

    test_gpio_loopback();
    test_pio_hold();
    test_pio_shift();
    test_wifi_scan();

    printf("\nAll checks passed. Pico W is ready for DBUS bring-up.\n");

    while (true) {
        sleep_ms(1000);
    }
}
