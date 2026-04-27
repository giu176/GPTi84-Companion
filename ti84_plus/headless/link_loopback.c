/*
 * link_loopback: silent-mode DBUS roundtrip test on an emulated 84+.
 *
 * No TI-BASIC program. Both legs use the silent variable transfer
 * protocol the calc OS handles directly:
 *
 *   1. Cold-boot the calc.
 *   2. Build a known list L1 = {65, 66, 67}.
 *   3. Silent-send it (PC -> CALC: VAR / ACK / CTS / ACK / DATA / ACK / EOT).
 *   4. Silent-request it back (PC -> CALC: REQ / ACK / VAR / ACK / CTS /
 *      ACK / DATA / ACK / EOT).
 *   5. Decode the BCD floats and compare to the original payload.
 *   6. Dump the LCD.
 *
 * This exercises the exact protocol path the Pico bridge will speak in
 * production: the calc is never doing anything other than sitting at the
 * homescreen with its OS link service handling everything silently.
 *
 * Usage: link_loopback <rom> [sav]
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include <ticables.h>
#include <ticalcs.h>
#include <tifiles.h>

#include <tilem.h>

/* ------------------------------------------------------------------ */
/* helpers (mirror headless.c)                                          */
/* ------------------------------------------------------------------ */

static int run_for_us(TilemCalc *calc, int microseconds)
{
    int rem = 0;
    tilem_z80_run_time(calc, microseconds, &rem);
    return microseconds - rem;
}

static int run_until_link_ready(TilemCalc *calc, int timeout_us)
{
    calc->linkport.linkemu = TILEM_LINK_EMULATOR_GRAY;
    while (timeout_us > 0) {
        if (tilem_linkport_graylink_ready(calc))
            return 0;
        timeout_us -= run_for_us(calc, 1000);
    }
    return -1;
}

static int send_byte(TilemCalc *calc, uint8_t value, int timeout_us)
{
    if (run_until_link_ready(calc, timeout_us))
        return -1;
    if (tilem_linkport_graylink_send_byte(calc, value))
        return -1;
    if (run_until_link_ready(calc, timeout_us))
        return -1;
    return 0;
}

static int recv_byte(TilemCalc *calc, int timeout_us)
{
    int v;
    calc->linkport.linkemu = TILEM_LINK_EMULATOR_GRAY;
    while (timeout_us > 0) {
        v = tilem_linkport_graylink_get_byte(calc);
        if (v >= 0)
            return v;
        timeout_us -= run_for_us(calc, 1000);
    }
    return -1;
}

/* ------------------------------------------------------------------ */
/* internal cable adapter (libticables -> libtilemcore)                  */
/* ------------------------------------------------------------------ */

#define CBL_TIMEOUT_US(cbl) ((cbl)->timeout * 100000)

static int ilp_open(CableHandle *cbl)
{
    tilem_linkport_graylink_reset((TilemCalc *)cbl->priv);
    return 0;
}

static int ilp_close(CableHandle *cbl)
{
    TilemCalc *calc = cbl->priv;
    calc->linkport.linkemu = TILEM_LINK_EMULATOR_NONE;
    tilem_linkport_graylink_reset(calc);
    return 0;
}

static int ilp_reset(CableHandle *cbl)
{
    tilem_linkport_graylink_reset((TilemCalc *)cbl->priv);
    return 0;
}

static int ilp_send(CableHandle *cbl, uint8_t *data, uint32_t count)
{
    TilemCalc *calc = cbl->priv;
    int timeout = CBL_TIMEOUT_US(cbl);
    for (uint32_t i = 0; i < count; i++) {
        if (send_byte(calc, data[i], timeout))
            return ERROR_WRITE_TIMEOUT;
    }
    return 0;
}

static int ilp_recv(CableHandle *cbl, uint8_t *data, uint32_t count)
{
    TilemCalc *calc = cbl->priv;
    int timeout = CBL_TIMEOUT_US(cbl);
    for (uint32_t i = 0; i < count; i++) {
        int v = recv_byte(calc, timeout);
        if (v < 0)
            return ERROR_READ_TIMEOUT;
        data[i] = (uint8_t)v;
    }
    run_for_us(calc, 10000);
    return 0;
}

static int ilp_check(CableHandle *cbl, int *status)
{
    TilemCalc *calc = cbl->priv;
    *status = STATUS_NONE;
    if (calc->linkport.lines)
        *status |= STATUS_RX;
    if (calc->linkport.extlines)
        *status |= STATUS_TX;
    return 0;
}

static CableHandle *make_internal_cable(TilemCalc *calc)
{
    CableHandle *cbl = ticables_handle_new(CABLE_ILP, PORT_0);
    if (!cbl)
        return NULL;
    cbl->priv = calc;
    cbl->cable->open = ilp_open;
    cbl->cable->close = ilp_close;
    cbl->cable->reset = ilp_reset;
    cbl->cable->send = ilp_send;
    cbl->cable->recv = ilp_recv;
    cbl->cable->check = ilp_check;
    return cbl;
}

/* ------------------------------------------------------------------ */
/* TI real-list payload encode/decode (small non-negative integers)      */
/* ------------------------------------------------------------------ */

/* TI 9-byte real float layout for k in [0, 99]:
 *   [0]    sign     0x00 positive
 *   [1]    exponent 0x80 + floor(log10(k)); 0x80 single-digit, 0x81 two-digit
 *   [2-8]  7 BCD digit pairs, big-endian, leading digit of mantissa first
 * Zero is encoded as all-zero bytes. */
static void encode_real_small(uint8_t *out, uint8_t k)
{
    memset(out, 0, 9);
    if (k == 0)
        return;
    if (k < 10) {
        out[1] = 0x80;
        out[2] = (uint8_t)(k << 4);
    } else {
        out[1] = 0x81;
        out[2] = (uint8_t)(((k / 10) << 4) | (k % 10));
    }
}

static int decode_real_small(const uint8_t *f, uint8_t *out)
{
    if (f[0] != 0x00)
        return -1;
    uint8_t exp = f[1];
    uint8_t d   = f[2];
    if (exp == 0x00 && d == 0x00) {
        *out = 0;
        return 0;
    }
    if (exp == 0x80) {
        *out = (uint8_t)(d >> 4);
        return 0;
    }
    if (exp == 0x81) {
        *out = (uint8_t)(((d >> 4) & 0xF) * 10 + (d & 0xF));
        return 0;
    }
    return -1;
}

static FileContent *build_list_l1(const uint8_t *data, int n)
{
    FileContent *fc = tifiles_content_create_regular(CALC_TI84P);
    if (!fc)
        return NULL;

    int body_len = 2 + n * 9;
    VarEntry *ve = tifiles_ve_create_alloc_data(body_len);
    if (!ve) {
        tifiles_content_delete_regular(fc);
        return NULL;
    }

    ve->data[0] = (uint8_t)(n & 0xFF);
    ve->data[1] = (uint8_t)((n >> 8) & 0xFF);
    for (int i = 0; i < n; i++)
        encode_real_small(ve->data + 2 + i * 9, data[i]);

    /* On-calc list-name encoding: 0x5D = list token, 0x00 = L1 (..0x05 = L6).
     * NOT the ASCII string "L1": the calc OS will create a separate custom
     * list and Get(L1) / silent-request("L1") will say MISSING_VAR. */
    ve->name[0] = 0x5D;
    ve->name[1] = 0x00;
    ve->name[2] = '\0';
    ve->folder[0] = '\0';
    ve->type    = TI83p_LIST;
    ve->attr    = ATTRB_NONE;
    ve->version = 0;
    ve->size    = body_len;

    if (tifiles_content_add_entry(fc, ve) < 0) {
        tifiles_content_delete_regular(fc);
        return NULL;
    }
    return fc;
}

/* Find the first VarEntry in fc and decode its body as a list of small
 * non-negative integers. Returns element count, or -1 on shape error. */
static int extract_list_l1(FileContent *fc, uint8_t *out, int max)
{
    if (!fc || fc->num_entries == 0 || !fc->entries || !fc->entries[0])
        return -1;
    VarEntry *ve = fc->entries[0];
    if (ve->size < 2)
        return -1;
    int n = ve->data[0] | (ve->data[1] << 8);
    if (n > max)
        return -1;
    if ((int)ve->size < 2 + n * 9)
        return -1;
    for (int i = 0; i < n; i++) {
        if (decode_real_small(ve->data + 2 + i * 9, &out[i]))
            return -1;
    }
    return n;
}

/* ------------------------------------------------------------------ */
/* LCD dump                                                             */
/* ------------------------------------------------------------------ */

static void dump_lcd_ascii(TilemCalc *calc, FILE *out)
{
    TilemLCDBuffer *buf = tilem_lcd_buffer_new();
    tilem_lcd_get_frame1(calc, buf);
    fprintf(out, "+");
    for (int x = 0; x < buf->width; x++)
        fputc('-', out);
    fprintf(out, "+\n");
    for (int y = 0; y < buf->height; y++) {
        fputc('|', out);
        for (int x = 0; x < buf->width; x++) {
            uint8_t v = buf->data[y * buf->rowstride + x];
            fputc(v ? '#' : ' ', out);
        }
        fputc('|', out);
        fputc('\n', out);
    }
    fprintf(out, "+");
    for (int x = 0; x < buf->width; x++)
        fputc('-', out);
    fprintf(out, "+\n");
    tilem_lcd_buffer_free(buf);
}

/* ------------------------------------------------------------------ */
/* main                                                                 */
/* ------------------------------------------------------------------ */

static const uint8_t kPayload[] = {65, 66, 67};
#define PAYLOAD_N ((int)(sizeof kPayload))

int main(int argc, char **argv)
{
    if (argc < 2 || argc > 3) {
        fprintf(stderr, "usage: %s <rom> [sav]\n", argv[0]);
        return 2;
    }
    const char *rom_path = argv[1];
    const char *sav_path = (argc == 3) ? argv[2] : NULL;

    ticables_library_init();
    ticalcs_library_init();
    tifiles_library_init();

    TilemCalc *calc = tilem_calc_new(TILEM_CALC_TI84P);
    if (!calc) {
        fprintf(stderr, "tilem_calc_new failed\n");
        return 1;
    }

    FILE *romf = fopen(rom_path, "rb");
    if (!romf) { perror(rom_path); return 1; }
    FILE *savf = NULL;
    if (sav_path) {
        savf = fopen(sav_path, "rb");
        if (!savf) { perror(sav_path); return 1; }
    }
    if (tilem_calc_load_state(calc, romf, savf)) {
        fprintf(stderr, "tilem_calc_load_state failed\n");
        return 1;
    }
    fclose(romf);
    if (savf) fclose(savf);

    fprintf(stderr, "[loopback] booting...\n");
    run_for_us(calc, 3 * 1000 * 1000);

    /* --- send leg ------------------------------------------------- */

    fprintf(stderr, "[loopback] sending L1 = {65, 66, 67} (silent)...\n");
    FileContent *fc_send = build_list_l1(kPayload, PAYLOAD_N);
    if (!fc_send) {
        fprintf(stderr, "build_list_l1 failed\n");
        return 1;
    }

    CableHandle *cbl = make_internal_cable(calc);
    CalcHandle  *ch  = ticalcs_handle_new(CALC_TI84P);
    if (!cbl || !ch) {
        fprintf(stderr, "cable/handle alloc failed\n");
        return 1;
    }
    ticables_options_set_timeout(cbl, 30 * 10);
    ticalcs_cable_attach(ch, cbl);

    int e = ticalcs_calc_send_var(ch, MODE_SEND_LAST_VAR, fc_send);
    if (e) {
        fprintf(stderr, "ticalcs_calc_send_var: %d\n", e);
        return 1;
    }

    ticalcs_cable_detach(ch);
    ticalcs_handle_del(ch);
    ticables_handle_del(cbl);

    /* Let the OS settle and clear the "Done" prompt. */
    run_for_us(calc, 1 * 1000 * 1000);

    /* --- recv leg ------------------------------------------------- */

    fprintf(stderr, "[loopback] requesting L1 back (silent)...\n");
    FileContent *fc_recv = tifiles_content_create_regular(CALC_TI84P);
    if (!fc_recv) {
        fprintf(stderr, "tifiles_content_create_regular failed\n");
        return 1;
    }

    VarRequest req;
    memset(&req, 0, sizeof req);
    req.name[0] = 0x5D;
    req.name[1] = 0x00;
    req.type    = TI83p_LIST;
    req.attr    = ATTRB_NONE;
    req.version = 0;

    cbl = make_internal_cable(calc);
    ch  = ticalcs_handle_new(CALC_TI84P);
    if (!cbl || !ch) {
        fprintf(stderr, "cable/handle alloc failed (recv)\n");
        return 1;
    }
    ticables_options_set_timeout(cbl, 30 * 10);
    ticalcs_cable_attach(ch, cbl);

    e = ticalcs_calc_recv_var(ch, MODE_NORMAL, fc_recv, &req);
    if (e) {
        fprintf(stderr, "ticalcs_calc_recv_var: %d\n", e);
        return 1;
    }

    ticalcs_cable_detach(ch);
    ticalcs_handle_del(ch);
    ticables_handle_del(cbl);

    /* --- verify --------------------------------------------------- */

    uint8_t got[16];
    int n = extract_list_l1(fc_recv, got, (int)(sizeof got));
    if (n != PAYLOAD_N) {
        fprintf(stderr, "[loopback] FAIL: expected %d elements, got %d\n",
                PAYLOAD_N, n);
        return 1;
    }
    for (int i = 0; i < n; i++) {
        if (got[i] != kPayload[i]) {
            fprintf(stderr, "[loopback] FAIL: element %d: sent %u, got %u\n",
                    i, kPayload[i], got[i]);
            return 1;
        }
    }

    fprintf(stderr, "[loopback] OK: roundtripped {");
    for (int i = 0; i < n; i++)
        fprintf(stderr, "%s%u", i ? ", " : "", got[i]);
    fprintf(stderr, "}\n");

    /* --- LCD ------------------------------------------------------ */

    run_for_us(calc, 500 * 1000);
    fprintf(stderr, "[loopback] LCD:\n");
    dump_lcd_ascii(calc, stdout);

    tifiles_content_delete_regular(fc_send);
    tifiles_content_delete_regular(fc_recv);
    tilem_calc_free(calc);
    tifiles_library_exit();
    ticalcs_library_exit();
    ticables_library_exit();
    return 0;
}
