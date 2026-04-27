#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    const char *path = argc > 1 ? argv[1] : "ti84_plus/ti84_plus_255/TI84Plus_OS255.8Xu";

    FILE *f = fopen(path, "rb");
    if (!f) {
        perror(path);
        return 1;
    }

    fseek(f, 0, SEEK_END);
    long len = ftell(f);
    rewind(f);

    unsigned char *buf = malloc(len);
    if (!buf) {
        fclose(f);
        fputs("out of memory\n", stderr);
        return 1;
    }

    if (fread(buf, 1, len, f) != (size_t)len) {
        perror("fread");
        free(buf);
        fclose(f);
        return 1;
    }
    fclose(f);

    printf("read %ld bytes from %s\n", len, path);
    printf("first 16 bytes:");
    for (int i = 0; i < 16 && i < len; i++) {
        printf(" %02x", buf[i]);
    }
    putchar('\n');

    free(buf);
    return 0;
}
