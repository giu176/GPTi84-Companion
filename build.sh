#!/usr/bin/env bash
# Usage:
#   ./build.sh             Build every registered Pico app.
#   ./build.sh <app>       Build only <app> (must be add_pico_app'd in CMakeLists.txt).
#   ./build.sh -l          List registered apps.
#   ./build.sh -c          Wipe the build directory and exit.
#   ./build.sh -h          Show this help.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src_dir="$repo_root/firmware/c"
build_dir="$src_dir/build"
cmakelists="$src_dir/CMakeLists.txt"

list_apps() {
    grep -oP '(?<=add_pico_app\()[^)]+' "$cmakelists"
}

usage() { sed -n '2,7p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    -l|--list) list_apps; exit 0 ;;
    -c|--clean) rm -rf "$build_dir"; echo "Removed $build_dir"; exit 0 ;;
esac

target="${1:-}"
if [[ -n "$target" ]] && ! list_apps | grep -qx "$target"; then
    echo "error: '$target' is not registered in $cmakelists" >&2
    echo "registered apps:" >&2
    list_apps | sed 's/^/  /' >&2
    exit 1
fi

if [[ ! -f "$build_dir/CMakeCache.txt" ]]; then
    cmake -S "$src_dir" -B "$build_dir"
fi

if [[ -n "$target" ]]; then
    cmake --build "$build_dir" --target "$target" -j
else
    cmake --build "$build_dir" -j
fi
