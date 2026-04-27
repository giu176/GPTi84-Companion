#!/usr/bin/env bash
# Usage:
#   ./format.sh           Format every C/C++ source under the repo (excluding vendor/, build/).
#   ./format.sh --check   Exit non-zero if anything would change. No files written.
#   ./format.sh -h        Show this help.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$repo_root"

usage() { sed -n '2,5p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

mode=write
case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    --check)   mode=check ;;
    "")        ;;
    *)         echo "unknown arg: $1" >&2; usage >&2; exit 2 ;;
esac

mapfile -d '' files < <(
    find . \
        \( -path ./vendor -o -path ./build -o -path '*/build' -o -path ./.git \) -prune -o \
        -type f \( -name '*.c' -o -name '*.h' -o -name '*.cpp' -o -name '*.hpp' \) -print0
)

if [[ ${#files[@]} -eq 0 ]]; then
    echo "no source files found"
    exit 0
fi

if [[ "$mode" == check ]]; then
    clang-format --dry-run --Werror "${files[@]}"
    echo "all ${#files[@]} files formatted correctly"
else
    clang-format -i "${files[@]}"
    echo "formatted ${#files[@]} files"
fi
