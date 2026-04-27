#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Ti84 Plus needs two pages dumped:
 *   - The first dump is the boot page on all calculators
 *   - The second dump (only on 84+ series) is the USB code page
 *
 * Default file names follow: D8[34][PC][BS]E[12].8xv
 *
 * .8Xu (TIFL) header layout — first bytes of the file:
 *   0x00: "**TIFL**"        (8-byte magic)
 *   0x08: major version     (BCD-packed byte: 0x02 = "2")
 *   0x09: minor version     (BCD-packed byte: 0x55 = "55")
 *   0x0A: flags / reserved
 *   0x0B: object type
 *   0x0C..0x10: date        (BCD: DD MM YYYY)
 *   0x11: name length
 *   0x12..0x19: name        (8 bytes, "basecode" for OS files)
 *   0x1A..0x2F: filler
 *   0x30..0x31: type magic  (0x73 0x23 = TI-83+ family OS file)
 *   0x32..0x49: filler
 *   0x4A..0x4D: payload byte length (little-endian uint32)
 *   0x4E: start of payload (Intel HEX records)
 *
 * Inside the payload, the first record's 10th data byte's low nibble is a
 * "cert ID" distinguishing 83+ (0x04) from 84+ (0x0A). Determined empirically
 * and corroborated by tari/rom8x.
 */

#define TIFL_MAGIC "**TIFL**"
#define TIFL_MAGIC_LEN 8
#define OFF_VERSION 0x08
#define OFF_TYPE_MAGIC 0x30
#define TYPE_MAGIC_OS_83PLUS 0x2373 /* little-endian 0x73 0x23 */
#define OFF_DATA_LEN 0x4A
#define HEADER_LEN 0x4E

#define PAGE_SIZE 0x4000  /* 16 KiB flash page */
#define MAX_PAGES 0x80    /* 84+SE has 0x40, 84+CSE up to 0x80 */

struct tifl_header {
    unsigned major;
    unsigned minor;
    uint16_t type_magic;
    uint32_t data_len;
};

enum tifl_err {
    TIFL_OK = 0,
    TIFL_ERR_TRUNCATED = -1,
    TIFL_ERR_BAD_MAGIC = -2,
    TIFL_ERR_UNSUPPORTED_TYPE = -3,
};

enum hex_err {
    HEX_OK = 0,
    HEX_ERR_NO_COLON = -1,
    HEX_ERR_BAD_HEX = -2,
    HEX_ERR_TRUNCATED = -3,
    HEX_ERR_CHECKSUM = -4,
};

struct hex_record {
    uint8_t type;
    uint16_t addr;
    uint8_t data[255];
    uint8_t len;
};

/* BCD: each nibble is one decimal digit. 0x55 → 55, 0x02 → 2. */
static unsigned bcd_to_uint(uint8_t b) { return (b >> 4) * 10 + (b & 0x0F); }

/* Reads the TIFL header from f (which must be positioned at offset 0).
 * On success, fills *out and leaves the file positioned at HEADER_LEN. */
static int read_tifl_header(FILE *f, struct tifl_header *out) {
    uint8_t buf[HEADER_LEN];
    if (fread(buf, 1, HEADER_LEN, f) != HEADER_LEN) {
        return TIFL_ERR_TRUNCATED;
    }
    if (memcmp(buf, TIFL_MAGIC, TIFL_MAGIC_LEN) != 0) {
        return TIFL_ERR_BAD_MAGIC;
    }

    out->major = bcd_to_uint(buf[OFF_VERSION]);
    out->minor = bcd_to_uint(buf[OFF_VERSION + 1]);

    /* Little-endian: low byte first. Casts force unsigned shifts. */
    out->type_magic = (uint16_t)buf[OFF_TYPE_MAGIC] | (uint16_t)buf[OFF_TYPE_MAGIC + 1] << 8;
    out->data_len = (uint32_t)buf[OFF_DATA_LEN] | (uint32_t)buf[OFF_DATA_LEN + 1] << 8 |
                    (uint32_t)buf[OFF_DATA_LEN + 2] << 16 |
                    (uint32_t)buf[OFF_DATA_LEN + 3] << 24;

    if (out->type_magic != TYPE_MAGIC_OS_83PLUS) {
        return TIFL_ERR_UNSUPPORTED_TYPE;
    }
    return TIFL_OK;
}

/* Returns 0..15 for a valid hex digit, -1 otherwise. */
static int hex_nibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

/* Two ASCII hex chars → one byte. Returns -1 if either nibble is invalid. */
static int hex_byte(const char *p) {
    int hi = hex_nibble(p[0]);
    int lo = hex_nibble(p[1]);
    if (hi < 0 || lo < 0) return -1;
    return (hi << 4) | lo;
}

/* Parses one Intel HEX line (':' + ASCII hex, no trailing newline assumed).
 * The line length `n` is the number of chars after the ':' is verified.
 *
 * Layout after the colon:
 *   2 chars  byte count (LL)
 *   4 chars  address    (AAAA, big-endian)
 *   2 chars  type       (TT)
 *   2*LL     data
 *   2 chars  checksum   (CC)
 *
 * Checksum: sum of all decoded bytes (LL, addr hi/lo, TT, data, CC) is 0 mod 256. */
static int parse_hex_record(const char *line, size_t n, struct hex_record *out) {
    if (n < 1 || line[0] != ':') return HEX_ERR_NO_COLON;

    /* Need at least LL+AAAA+TT+CC = 10 hex chars after the colon. */
    if (n < 1 + 10) return HEX_ERR_TRUNCATED;

    int bc = hex_byte(line + 1);
    if (bc < 0) return HEX_ERR_BAD_HEX;

    /* Total chars required after ':' = 2 (LL) + 4 (addr) + 2 (type) + 2*LL + 2 (csum). */
    size_t need = 1 + 2 + 4 + 2 + (size_t)bc * 2 + 2;
    if (n < need) return HEX_ERR_TRUNCATED;

    int ah = hex_byte(line + 3);
    int al = hex_byte(line + 5);
    int tt = hex_byte(line + 7);
    if (ah < 0 || al < 0 || tt < 0) return HEX_ERR_BAD_HEX;

    /* Running sum used for checksum verification. */
    uint8_t sum = (uint8_t)bc + (uint8_t)ah + (uint8_t)al + (uint8_t)tt;

    for (int i = 0; i < bc; i++) {
        int b = hex_byte(line + 9 + i * 2);
        if (b < 0) return HEX_ERR_BAD_HEX;
        out->data[i] = (uint8_t)b;
        sum = (uint8_t)(sum + (uint8_t)b);
    }

    int cs = hex_byte(line + 9 + bc * 2);
    if (cs < 0) return HEX_ERR_BAD_HEX;
    sum = (uint8_t)(sum + (uint8_t)cs);
    if (sum != 0) return HEX_ERR_CHECKSUM;

    out->len = (uint8_t)bc;
    out->addr = (uint16_t)((ah << 8) | al);
    out->type = (uint8_t)tt;
    return HEX_OK;
}

/* Reads from `pos` up to (but not including) the next '\n', returning the line
 * length and writing the index of the first char past the line into *next.
 * Trailing '\r' is stripped. End-of-buffer counts as end-of-line. */
static size_t scan_line(const uint8_t *buf, size_t len, size_t pos, size_t *next) {
    size_t start = pos;
    while (pos < len && buf[pos] != '\n') pos++;
    size_t end = pos;
    *next = (pos < len) ? pos + 1 : pos;
    if (end > start && buf[end - 1] == '\r') end--;
    return end - start;
}

struct walk_stats {
    uint32_t data_records;
    uint32_t ext_records;
    uint32_t eof_records;
    uint32_t other_records;
    uint64_t data_bytes;
    uint8_t  page_touched[MAX_PAGES];   /* 1 if page has any data */
    uint16_t page_min[MAX_PAGES];       /* lowest addr written, per page */
    uint16_t page_max_end[MAX_PAGES];   /* one past highest addr written */
    unsigned pages_touched;             /* count of distinct pages */
};

/* TI's .8Xu departs from the Intel HEX spec for type-02 records. Standard HEX
 * uses type-02 to set a 20-bit segmented base (paragraph << 4). TI overloads
 * the record to carry the destination *flash page number*: the two data bytes
 * form a 16-bit page index that selects which 16 KiB page the following
 * type-00 records belong to.
 *
 * Within-record addresses are Z80 *absolute* addresses, not within-page
 * offsets. The 84+ memory map places the boot page (page 0) at 0x0000-0x3FFF
 * and any banked page at 0x4000-0x7FFF, so the actual within-page offset is
 * (record.addr & 0x3FFF) regardless of which page is selected. Type-04
 * (32-bit linear extended) is not used in this format. */
struct walker {
    uint16_t cur_page;
    int      have_page;
};

/* Walks the Intel HEX payload, verifying every record and tracking which
 * flash pages are touched. `cb` is invoked once per type-00 data record with
 * the current page, the within-page offset, the data, and `user`. cb may be
 * NULL for a stats-only pass. */
typedef int (*data_cb)(uint16_t page, uint16_t off, const uint8_t *data, uint8_t len, void *user);

static int walk_records(const uint8_t *payload, size_t len, struct walk_stats *st,
                        data_cb cb, void *user) {
    memset(st, 0, sizeof(*st));
    /* TI's streams begin with data for page 0 (the boot page) before the
     * first type-02 selector appears. Seed the walker accordingly. */
    struct walker w = { .cur_page = 0, .have_page = 1 };
    size_t pos = 0;
    size_t lineno = 0;

    while (pos < len) {
        size_t next;
        size_t llen = scan_line(payload, len, pos, &next);
        lineno++;

        /* Skip blank lines and non-record content (the Intel HEX spec allows
         * comments and EOF padding like ^Z; ignore them). */
        if (llen == 0 || payload[pos] != ':') {
            pos = next;
            continue;
        }

        struct hex_record r;
        int rc = parse_hex_record((const char *)(payload + pos), llen, &r);
        if (rc != HEX_OK) {
            fprintf(stderr, "line %zu: parse error %d\n", lineno, rc);
            return rc;
        }

        switch (r.type) {
        case 0x00: {
            if (!w.have_page) {
                fprintf(stderr, "line %zu: data record before any page selector\n", lineno);
                return HEX_ERR_BAD_HEX;
            }
            if (w.cur_page >= MAX_PAGES) {
                fprintf(stderr, "line %zu: page 0x%04X exceeds MAX_PAGES (0x%X)\n",
                        lineno, w.cur_page, MAX_PAGES);
                return HEX_ERR_BAD_HEX;
            }
            uint16_t off = r.addr & 0x3FFF;
            uint32_t end = (uint32_t)off + r.len;
            if (end > PAGE_SIZE) {
                fprintf(stderr, "line %zu: record spans past page boundary "
                                "(page 0x%02X off 0x%04X + %u)\n",
                        lineno, w.cur_page, off, r.len);
                return HEX_ERR_BAD_HEX;
            }

            uint16_t p = w.cur_page;
            if (!st->page_touched[p]) {
                st->page_touched[p] = 1;
                st->page_min[p] = off;
                st->page_max_end[p] = (uint16_t)end;
                st->pages_touched++;
            } else {
                if (off < st->page_min[p]) st->page_min[p] = off;
                if ((uint16_t)end > st->page_max_end[p]) st->page_max_end[p] = (uint16_t)end;
            }
            st->data_records++;
            st->data_bytes += r.len;

            if (cb) {
                int crc = cb(p, off, r.data, r.len, user);
                if (crc != 0) return crc;
            }
            break;
        }
        case 0x01:
            /* End of stream. TI concatenates multiple HEX streams; the next
             * stream re-starts at page 0 unless overridden by a type-02. */
            st->eof_records++;
            w.cur_page = 0;
            w.have_page = 1;
            break;
        case 0x02:
            if (r.len != 2) {
                fprintf(stderr, "line %zu: type-02 with len %u (expected 2)\n", lineno, r.len);
                return HEX_ERR_BAD_HEX;
            }
            /* Page index, big-endian. See the comment above struct walker. */
            w.cur_page = (uint16_t)((r.data[0] << 8) | r.data[1]);
            w.have_page = 1;
            st->ext_records++;
            break;
        case 0x04:
            fprintf(stderr, "line %zu: unexpected type-04 in TI .8Xu stream\n", lineno);
            return HEX_ERR_BAD_HEX;
        default:
            st->other_records++;
            break;
        }

        pos = next;
    }

    return HEX_OK;
}

/* ---- Page extraction ---- */

static int store_page_byte(uint16_t page, uint16_t off, const uint8_t *data, uint8_t len, void *user) {
    uint8_t *buf = user;
    /* walk_records already validated page < MAX_PAGES and off+len <= PAGE_SIZE. */
    memcpy(buf + (size_t)page * PAGE_SIZE + off, data, len);
    return 0;
}

/* Writes touched pages concatenated in ascending page-index order to out_path.
 * Untouched pages are skipped, so file size = pages_touched * PAGE_SIZE.
 * Offsets within the file are *not* flash offsets — gaps are squeezed out. */
static int write_os_image(const uint8_t *buf, const struct walk_stats *st, const char *out_path) {
    FILE *out = fopen(out_path, "wb");
    if (!out) {
        perror(out_path);
        return -1;
    }
    for (unsigned p = 0; p < MAX_PAGES; p++) {
        if (!st->page_touched[p]) continue;
        size_t wrote = fwrite(buf + (size_t)p * PAGE_SIZE, 1, PAGE_SIZE, out);
        if (wrote != PAGE_SIZE) {
            fprintf(stderr, "%s: short write on page 0x%02X\n", out_path, p);
            fclose(out);
            return -1;
        }
    }
    fclose(out);
    return 0;
}

static int slurp_payload(const char *path, const struct tifl_header *h,
                         uint8_t **out_buf, size_t *out_len) {
    FILE *f = fopen(path, "rb");
    if (!f) {
        perror(path);
        return -1;
    }

    if (fseek(f, 0, SEEK_END) != 0) {
        perror("fseek");
        fclose(f);
        return -1;
    }
    long total = ftell(f);
    if (total < 0 || (size_t)total < HEADER_LEN) {
        fprintf(stderr, "%s: file too short\n", path);
        fclose(f);
        return -1;
    }
    size_t tail = (size_t)total - HEADER_LEN;
    if (tail != h->data_len) {
        fprintf(stderr, "%s: header says %u payload bytes, file has %zu\n",
                path, h->data_len, tail);
        fclose(f);
        return -1;
    }

    if (fseek(f, HEADER_LEN, SEEK_SET) != 0) {
        perror("fseek");
        fclose(f);
        return -1;
    }
    uint8_t *buf = malloc(tail);
    if (!buf) {
        fprintf(stderr, "out of memory (%zu bytes)\n", tail);
        fclose(f);
        return -1;
    }
    if (fread(buf, 1, tail, f) != tail) {
        fprintf(stderr, "%s: short read on payload\n", path);
        free(buf);
        fclose(f);
        return -1;
    }
    fclose(f);

    *out_buf = buf;
    *out_len = tail;
    return 0;
}

int main(int argc, char **argv) {
    if (argc > 1 && (strcmp(argv[1], "-h") == 0 || strcmp(argv[1], "--help") == 0)) {
        fprintf(stderr, "usage: %s [path.8Xu] [out.bin]\n", argv[0]);
        return 0;
    }
    const char *path = argc > 1 ? argv[1] : "ti84_plus/ti84_plus_255/TI84Plus_OS255.8Xu";
    const char *out_path = argc > 2 ? argv[2] : NULL;

    FILE *f = fopen(path, "rb");
    if (!f) {
        perror(path);
        return 1;
    }
    struct tifl_header h;
    int rc = read_tifl_header(f, &h);
    fclose(f);
    if (rc != TIFL_OK) {
        switch (rc) {
        case TIFL_ERR_TRUNCATED:
            fprintf(stderr, "%s: file shorter than TIFL header (%d bytes)\n", path, HEADER_LEN);
            break;
        case TIFL_ERR_BAD_MAGIC:
            fprintf(stderr, "%s: not a TIFL file (bad magic)\n", path);
            break;
        case TIFL_ERR_UNSUPPORTED_TYPE:
            fprintf(stderr, "%s: unsupported TIFL object type\n", path);
            break;
        }
        return 1;
    }

    uint8_t *payload;
    size_t payload_len;
    if (slurp_payload(path, &h, &payload, &payload_len) != 0) return 1;

    printf("file:    %s\n", path);
    printf("version: %u.%02u\n", h.major, h.minor);
    printf("type:    0x%04X (%s)\n", h.type_magic,
           h.type_magic == TYPE_MAGIC_OS_83PLUS ? "TI-83+/84+ OS" : "unknown");
    printf("payload: %zu bytes\n", payload_len);

    struct walk_stats st;
    uint8_t *flash = NULL;
    int wrc;

    if (out_path) {
        flash = malloc((size_t)MAX_PAGES * PAGE_SIZE);
        if (!flash) {
            fprintf(stderr, "out of memory (%u bytes)\n", MAX_PAGES * PAGE_SIZE);
            free(payload);
            return 1;
        }
        memset(flash, 0xFF, (size_t)MAX_PAGES * PAGE_SIZE);
        wrc = walk_records(payload, payload_len, &st, store_page_byte, flash);
    } else {
        wrc = walk_records(payload, payload_len, &st, NULL, NULL);
    }
    free(payload);

    if (wrc != HEX_OK) {
        free(flash);
        return 1;
    }

    printf("\nhex walk:\n");
    printf("  data records: %u (%llu bytes)\n", st.data_records,
           (unsigned long long)st.data_bytes);
    printf("  ext  records: %u\n", st.ext_records);
    printf("  eof  records: %u\n", st.eof_records);
    printf("  other:        %u\n", st.other_records);
    printf("  pages:        %u\n", st.pages_touched);
    for (unsigned p = 0; p < MAX_PAGES; p++) {
        if (!st.page_touched[p]) continue;
        unsigned span = st.page_max_end[p] - st.page_min[p];
        printf("    page 0x%02X: 0x%04X..0x%04X (%u bytes)\n",
               p, st.page_min[p], st.page_max_end[p], span);
    }

    if (out_path) {
        if (write_os_image(flash, &st, out_path) != 0) {
            free(flash);
            return 1;
        }
        printf("\nwrote %u pages (%u bytes) to %s\n",
               st.pages_touched, st.pages_touched * PAGE_SIZE, out_path);
    }
    free(flash);
    return 0;
}
