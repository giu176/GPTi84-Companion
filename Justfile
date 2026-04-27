set shell := ["bash", "-euo", "pipefail", "-c"]

repo_root := justfile_directory()

firmware_src := repo_root / "firmware/c"
firmware_build := firmware_src / "build"
firmware_cmakelists := firmware_src / "CMakeLists.txt"

decoder_src := repo_root / "ti84_plus"
decoder_build := decoder_src / "build"
decoder_binary := decoder_build / "decoder"
encoder_binary := decoder_build / "encoder"
decoder_default_input := decoder_src / "ti84_plus_255/TI84Plus_OS255.8Xu"

emu_rom := decoder_src / "ti84_plus_255/xander_ti84_romdump_2026-04-27.rom"
emu_state := decoder_src / "ti84_plus_255/clean.sav"
tilem_src := repo_root / "vendor/tilem"
tilem_build := tilem_src / "build"
tilem_binary := tilem_build / "gui/tilem2"
headless_binary := decoder_build / "tilem_headless"
mk_hello_binary := decoder_build / "mk_hello_8xp"
hello_8xp := decoder_src / "programs/HELLO.8Xp"
loopback_binary := decoder_build / "link_loopback"

# List available recipes.
default:
    @just --list

# Build the firmware (or a single app: `just build bringup`).
build target="":
    #!/usr/bin/env bash
    set -euo pipefail
    target="{{target}}"
    if [[ -n "$target" ]] && ! grep -oP '(?<=add_pico_app\()[^)]+' "{{firmware_cmakelists}}" | grep -qx "$target"; then
        echo "error: '$target' is not registered in {{firmware_cmakelists}}" >&2
        echo "registered apps:" >&2
        grep -oP '(?<=add_pico_app\()[^)]+' "{{firmware_cmakelists}}" | sed 's/^/  /' >&2
        exit 1
    fi
    if [[ ! -f "{{firmware_build}}/CMakeCache.txt" ]]; then
        cmake -S "{{firmware_src}}" --preset pico-w
    fi
    if [[ -n "$target" ]]; then
        cmake --build "{{firmware_build}}" --target "$target" -j
    else
        cmake --build "{{firmware_build}}" -j
    fi

# List firmware apps registered in CMakeLists.txt.
build-list:
    @grep -oP '(?<=add_pico_app\()[^)]+' "{{firmware_cmakelists}}"

# Wipe the firmware build directory.
build-clean:
    rm -rf "{{firmware_build}}"
    @echo "Removed {{firmware_build}}"

# Build (if needed) and run the host-side .8Xu decoder.
# Args: [input.8Xu] [output.bin]. With 0 args, uses the bundled OS 2.55 input
# and skips writing. With 1 arg, writes <input_basename>.bin into the build dir.
decode *args:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ ! -f "{{decoder_build}}/CMakeCache.txt" ]]; then
        cmake -S "{{decoder_src}}" -B "{{decoder_build}}"
    fi
    cmake --build "{{decoder_build}}" --target decoder -j
    args=({{args}})
    case ${#args[@]} in
        0) exec "{{decoder_binary}}" "{{decoder_default_input}}" ;;
        1) exec "{{decoder_binary}}" "${args[0]}" "{{decoder_build}}/$(basename "${args[0]}" .8Xu).bin" ;;
        *) exec "{{decoder_binary}}" "${args[@]}" ;;
    esac

# Wipe the decoder build directory.
decode-clean:
    rm -rf "{{decoder_build}}"
    @echo "Removed {{decoder_build}}"

# Encode os.bin + os.bin.meta back into a .8Xu.
# Args: <os.bin> <out.8Xu>. The meta file is read from <os.bin>.meta.
encode bin out:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ ! -f "{{decoder_build}}/CMakeCache.txt" ]]; then
        cmake -S "{{decoder_src}}" -B "{{decoder_build}}"
    fi
    cmake --build "{{decoder_build}}" --target encoder -j
    exec "{{encoder_binary}}" "{{bin}}" "{{bin}}.meta" "{{out}}"

# Decode then re-encode and verify byte-identical round-trip.
# With 0 args, runs against the bundled OS 2.55. With 1 arg, against that file.
roundtrip *args:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ ! -f "{{decoder_build}}/CMakeCache.txt" ]]; then
        cmake -S "{{decoder_src}}" -B "{{decoder_build}}"
    fi
    cmake --build "{{decoder_build}}" --target decoder encoder -j
    args=({{args}})
    input="${args[0]:-{{decoder_default_input}}}"
    base="$(basename "$input" .8Xu)"
    bin="{{decoder_build}}/${base}.bin"
    out="{{decoder_build}}/${base}.roundtrip.8Xu"
    "{{decoder_binary}}" "$input" "$bin" >/dev/null
    "{{encoder_binary}}" "$bin" "$bin.meta" "$out" >/dev/null
    if cmp -s "$input" "$out"; then
        echo "OK: $out is byte-identical to $input"
    else
        echo "MISMATCH between $input and $out" >&2
        cmp "$input" "$out" || true
        exit 1
    fi

# Build the patched local TilEm (autotools, out-of-tree).
emu-build:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ ! -f "{{tilem_build}}/Makefile" ]]; then
        mkdir -p "{{tilem_build}}"
        cd "{{tilem_build}}"
        ../configure --prefix="{{tilem_build}}/install"
    fi
    make -C "{{tilem_build}}" -j

# Wipe the local TilEm build directory.
emu-clean:
    rm -rf "{{tilem_build}}"
    @echo "Removed {{tilem_build}}"

# Boot the TilEm emulator from saved state (falls back to cold ROM boot if no state file).
emu: emu-build
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -f "{{emu_state}}" ]]; then
        exec "{{tilem_binary}}" -s "{{emu_state}}"
    else
        echo "no state file at {{emu_state}} — cold-booting; quit-and-save to create one" >&2
        exec "{{tilem_binary}}" -r "{{emu_rom}}"
    fi

# Boot from a saved clean state, optionally sending a file (.8Xu/.8Xp) on entry.
# Falls back to a cold ROM boot if the state file doesn't exist yet.
emu-send *args: emu-build
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -f "{{emu_state}}" ]]; then
        exec "{{tilem_binary}}" -s "{{emu_state}}" {{args}}
    else
        echo "no state file at {{emu_state}} — cold-booting; quit-and-save to create one" >&2
        exec "{{tilem_binary}}" -r "{{emu_rom}}" {{args}}
    fi

# Decode + re-encode the default OS, then send the round-tripped .8Xu to the emulator.
emu-roundtrip: roundtrip
    #!/usr/bin/env bash
    set -euo pipefail
    base="$(basename "{{decoder_default_input}}" .8Xu)"
    just emu-send "{{decoder_build}}/${base}.roundtrip.8Xu"

# Boot from clean state with a file in flight, capturing tilem_warning/tilem_message
# output (stderr) to a log file. Use this to diagnose flash/link-layer issues.
emu-trace *args: emu-build
    #!/usr/bin/env bash
    set -euo pipefail
    log="{{decoder_build}}/tilem-trace.log"
    mkdir -p "$(dirname "$log")"
    echo "trace → $log (tail -f to follow)" >&2
    if [[ -f "{{emu_state}}" ]]; then
        "{{tilem_binary}}" -s "{{emu_state}}" {{args}} 2>"$log"
    else
        echo "no state file at {{emu_state}} — cold-booting; quit-and-save to create one" >&2
        "{{tilem_binary}}" -r "{{emu_rom}}" {{args}} 2>"$log"
    fi
    echo "trace saved ($(wc <"$log") lines): $log" >&2

# Collapse the latest emu-trace log into a count-prefixed unique-line summary,
# preserving order of first occurrence so the boot/install timeline is readable.
emu-trace-summary:
    #!/usr/bin/env bash
    set -euo pipefail
    log="{{decoder_build}}/tilem-trace.log"
    if [[ ! -f "$log" ]]; then
        echo "no trace log at $log — run \`just emu-trace ...\` first" >&2
        exit 1
    fi
    awk '
        { count[$0]++; if (!($0 in seen)) { order[++n] = $0; seen[$0] = 1 } }
        END { for (i = 1; i <= n; i++) printf "%6d  %s\n", count[order[i]], order[i] }
    ' "$log"

# Build (if needed) and run the headless TilEm harness.
# Cold-boots from <emu_rom>+<emu_state>, sends a .8Xp through the graylink,
# runs prgmHELLO from the homescreen, dumps the LCD as ASCII to stdout.
# With no args, regenerates HELLO.8Xp first and uses it.
emu-headless *args: emu-build
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ ! -f "{{decoder_build}}/CMakeCache.txt" ]]; then
        cmake -S "{{decoder_src}}" -B "{{decoder_build}}"
    fi
    cmake --build "{{decoder_build}}" --target tilem_headless mk_hello_8xp -j
    args=({{args}})
    if [[ ${#args[@]} -eq 0 ]]; then
        mkdir -p "$(dirname "{{hello_8xp}}")"
        "{{mk_hello_binary}}" "{{hello_8xp}}"
        prog="{{hello_8xp}}"
    else
        prog="${args[0]}"
    fi
    exec "{{headless_binary}}" "{{emu_rom}}" "$prog" "{{emu_state}}"

# Build and run the silent-mode DBUS roundtrip test.
# Cold-boots an emulated 84+, silent-sends L1 = {65, 66, 67}, silent-
# requests it back, decodes the BCD floats, verifies the bytes match.
# No TI-BASIC program: this exercises the protocol the Pico bridge
# will speak in production.
emu-link-loopback: emu-build
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ ! -f "{{decoder_build}}/CMakeCache.txt" ]]; then
        cmake -S "{{decoder_src}}" -B "{{decoder_build}}"
    fi
    cmake --build "{{decoder_build}}" --target link_loopback -j
    exec "{{loopback_binary}}" "{{emu_rom}}" "{{emu_state}}"

# Format all C/C++ sources outside vendor/ and build/.
fmt:
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{repo_root}}"
    mapfile -d '' files < <(
        find . \
            \( -path ./vendor -o -path ./build -o -path '*/build' -o -path ./.git \) -prune -o \
            -type f \( -name '*.c' -o -name '*.h' -o -name '*.cpp' -o -name '*.hpp' \) -print0
    )
    if [[ ${#files[@]} -eq 0 ]]; then
        echo "no source files found"
        exit 0
    fi
    clang-format -i "${files[@]}"
    echo "formatted ${#files[@]} files"

# Check formatting without writing changes (CI-friendly, non-zero exit if dirty).
fmt-check:
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{repo_root}}"
    mapfile -d '' files < <(
        find . \
            \( -path ./vendor -o -path ./build -o -path '*/build' -o -path ./.git \) -prune -o \
            -type f \( -name '*.c' -o -name '*.h' -o -name '*.cpp' -o -name '*.hpp' \) -print0
    )
    if [[ ${#files[@]} -eq 0 ]]; then
        echo "no source files found"
        exit 0
    fi
    clang-format --dry-run --Werror "${files[@]}"
    echo "all ${#files[@]} files formatted correctly"
