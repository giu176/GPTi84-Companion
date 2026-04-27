set shell := ["bash", "-euo", "pipefail", "-c"]

repo_root := justfile_directory()

firmware_src := repo_root / "firmware/c"
firmware_build := firmware_src / "build"
firmware_cmakelists := firmware_src / "CMakeLists.txt"

decoder_src := repo_root / "ti84_plus"
decoder_build := decoder_src / "build"
decoder_binary := decoder_build / "decoder"
decoder_default_input := decoder_src / "ti84_plus_255/TI84Plus_OS255.8Xu"

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
