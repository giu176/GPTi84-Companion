#include <stdint.h>
#include <stdio.h>
#include <string.h>

/* Ti84 Plus needs two pages dumped:
 *   - The first dump is the boot page on all calculators
 *   - The second dump (only on 84+ series) is the USB code page
 *
 * Default file names follow: D8[34][PC][BS]E[12].8xv
 *
 * .8Xu (TIFL) header layout — first bytes of the file:
 *   0x00: "**TIFL**"      (8-byte magic)
 *   0x08: major version   (BCD-packed byte: 0x02 = "2")
 *   0x09: minor version   (BCD-packed byte: 0x55 = "55")
 *   0x0A: flags / reserved
 *   0x0B: object type
 *   0x0C..0x11: date (BCD: DD MM YYYY, year as two bytes)
 *   0x12: name length
 *   0x13..0x1A: name (8 bytes, zero-padded)
 *   0x1B..0x2F: filler / padding
 *   0x30..0x33: payload record count (little-endian uint32)
 *   0x34: start of payload (Intel HEX records)
 */

#define TIFL_MAGIC      "**TIFL**"
#define TIFL_MAGIC_LEN  8
#define OFF_VERSION     0x08
#define OFF_DATA_LEN    0x30
#define HEADER_LEN      0x34

/* BCD: each nibble is one decimal digit. 0x55 → 55, 0x02 → 2. */
static unsigned bcd_to_uint(uint8_t b) {
    return (b >> 4) * 10 + (b & 0x0F);
}

int main(int argc, char **argv) {
    const char *path = argc > 1 ? argv[1] : "ti84_plus/ti84_plus_255/TI84Plus_OS255.8Xu";

    FILE *f = fopen(path, "rb");
    if (!f) {
        perror(path);
        return 1;
    }

    uint8_t header[HEADER_LEN];
    if (fread(header, 1, HEADER_LEN, f) != HEADER_LEN) {
        fprintf(stderr, "%s: file shorter than TIFL header (%d bytes)\n", path, HEADER_LEN);
        fclose(f);
        return 1;
    }

    if (memcmp(header, TIFL_MAGIC, TIFL_MAGIC_LEN) != 0) {
        fprintf(stderr, "%s: not a TIFL file (bad magic)\n", path);
        fclose(f);
        return 1;
    }

    unsigned major = bcd_to_uint(header[OFF_VERSION]);
    unsigned minor = bcd_to_uint(header[OFF_VERSION + 1]);

    /* Little-endian: low byte first. */
    uint32_t records =
        (uint32_t)header[OFF_DATA_LEN]            |
        (uint32_t)header[OFF_DATA_LEN + 1] <<  8  |
        (uint32_t)header[OFF_DATA_LEN + 2] << 16  |
        (uint32_t)header[OFF_DATA_LEN + 3] << 24;

    printf("file:    %s\n", path);
    printf("version: %u.%02u\n", major, minor);
    printf("records: %u\n", records);

    fclose(f);
    return 0;
}
