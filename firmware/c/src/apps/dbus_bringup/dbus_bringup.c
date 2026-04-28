// DBUS bring-up diagnostics, no handshake assumed.
//
// We've confirmed the per-bit handshake hangs at "calc never acks". This
// firmware does not attempt the protocol; it just probes the wire so we
// can locate the failure. Three sub-tests in a loop:
//
//  T1) Idle WITHOUT Pico pull-ups: if the lines still read HIGH, the calc's
//      internal pull-ups are reaching us through real conductors. If they
//      go LOW, the only thing holding them HIGH in the previous firmware
//      was the Pico's internal pull-up: the data wire is broken between
//      Pico and calc.
//
//  T2) Drive each line low alone for 50 ms, then release. The calc, if
//      its link RX interrupt is alive, may pull the OTHER line low to
//      acknowledge a perceived bit-start. We sample the other line
//      throughout to see if the calc reacts.
//
//  T3) Passive listen with no Pico drive for 1 s. If the calc is mid-send
//      from a prior aborted CBL2 handshake or stuck Send(), it'll periodically
//      pull a line low. If we see any transitions, the calc is *trying* to
//      talk and we're the deaf one.
//
// Wiring: D0=GPIO6 (TIP/red), D1=GPIO7 (RING/white), GND through sleeve.

#include <stdio.h>

#include "pico/stdlib.h"

#define D0_PIN 6
#define D1_PIN 7

static void line_release(uint pin) { gpio_set_dir(pin, GPIO_IN); }
static void line_assert(uint pin) { gpio_set_dir(pin, GPIO_OUT); }
static bool line_low(uint pin) { return !gpio_get(pin); }

static void pin_setup(uint pin, bool with_pullup) {
    gpio_init(pin);
    gpio_put(pin, 0);
    if (with_pullup) {
        gpio_pull_up(pin);
    } else {
        gpio_disable_pulls(pin);
    }
    gpio_set_dir(pin, GPIO_IN);
}

static void test_idle_no_pullups(void) {
    pin_setup(D0_PIN, false);
    pin_setup(D1_PIN, false);
    sleep_ms(5);
    bool d0 = !line_low(D0_PIN);
    bool d1 = !line_low(D1_PIN);
    printf("T1 idle (Pico pull-ups OFF): D0=%s D1=%s\n",
           d0 ? "HIGH" : "LOW ", d1 ? "HIGH" : "LOW ");
    if (d0 && d1) {
        printf("    -> calc pull-ups reach Pico through real conductors. good.\n");
    } else {
        printf("    -> a line is floating LOW with no Pico pull-up: that conductor is broken/unplugged.\n");
    }
}

static void test_drive_one_line(uint drive_pin, uint watch_pin, const char *drive_name,
                                const char *watch_name) {
    pin_setup(D0_PIN, true);
    pin_setup(D1_PIN, true);
    sleep_ms(5);

    // Sample watch_pin every ~200 us during a 50 ms drive. If the calc
    // reacts at all, watch_pin will go low at some point.
    line_assert(drive_pin);
    bool watch_went_low = false;
    absolute_time_t deadline = make_timeout_time_ms(50);
    while (absolute_time_diff_us(get_absolute_time(), deadline) > 0) {
        if (line_low(watch_pin)) {
            watch_went_low = true;
            break;
        }
        busy_wait_us(200);
    }
    line_release(drive_pin);

    if (watch_went_low) {
        printf("T2 drive %s low: %s WENT LOW within 50 ms -> calc is acknowledging!\n",
               drive_name, watch_name);
    } else {
        printf("T2 drive %s low: %s stayed HIGH for 50 ms -> calc did not react.\n",
               drive_name, watch_name);
    }
    sleep_ms(20);  // let calc see the release before the next test
}

static void test_passive_listen(void) {
    pin_setup(D0_PIN, true);
    pin_setup(D1_PIN, true);
    sleep_ms(5);

    bool d0_prev = !line_low(D0_PIN);
    bool d1_prev = !line_low(D1_PIN);
    int d0_edges = 0;
    int d1_edges = 0;
    absolute_time_t deadline = make_timeout_time_ms(1000);
    while (absolute_time_diff_us(get_absolute_time(), deadline) > 0) {
        bool d0 = !line_low(D0_PIN);
        bool d1 = !line_low(D1_PIN);
        if (d0 != d0_prev) {
            d0_edges++;
            d0_prev = d0;
        }
        if (d1 != d1_prev) {
            d1_edges++;
            d1_prev = d1;
        }
    }
    printf("T3 passive 1 s: D0 edges=%d, D1 edges=%d\n", d0_edges, d1_edges);
    if (d0_edges == 0 && d1_edges == 0) {
        printf("    -> calc is silent. nothing trying to talk on this end.\n");
    } else {
        printf("    -> calc is driving the line. it's mid-something; reset calc state.\n");
    }
}

int main(void) {
    stdio_init_all();

    pin_setup(D0_PIN, true);
    pin_setup(D1_PIN, true);

    for (int i = 5; i > 0; i--) {
        printf("waiting for monitor... %d\n", i);
        sleep_ms(1000);
    }
    printf("\nDBUS wire diagnostics  D0=GP%d  D1=GP%d\n", D0_PIN, D1_PIN);
    printf("==========================================\n\n");

    while (true) {
        test_idle_no_pullups();
        test_drive_one_line(D0_PIN, D1_PIN, "D0", "D1");
        test_drive_one_line(D1_PIN, D0_PIN, "D1", "D0");
        test_passive_listen();
        printf("---\n");
        sleep_ms(2000);
    }
}
