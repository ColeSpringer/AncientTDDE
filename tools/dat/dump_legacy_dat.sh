#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 [input.dat [output-directory]]"
    echo "Defaults: legacy/original/resources/_common/dat/empires2_x2_p1.dat -> legacy/reference/dat-verified"
    echo "Set GENIEUTILS to override ~/dev/tools/genieutils."
}

if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
    usage
    exit 0
fi
if (( $# > 2 )); then
    usage >&2
    exit 2
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd -P)"
GENIEUTILS="${GENIEUTILS:-$HOME/dev/tools/genieutils}"
DAT="${1:-$ROOT/legacy/original/resources/_common/dat/empires2_x2_p1.dat}"
OUT="${2:-$ROOT/legacy/reference/dat-verified}"
BUILD="$ROOT/.build/dat-dump"

for tool in g++ gdb realpath mktemp; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "$tool is required (on Debian/Ubuntu: sudo apt install g++ gdb coreutils)" >&2
        exit 1
    fi
done

if [[ ! -f "$DAT" ]]; then
    echo "DAT not found: $DAT" >&2
    exit 1
fi

if [[ ! -f "$GENIEUTILS/build/libgenieutils.so" ]]; then
    echo "genieutils library not found: $GENIEUTILS/build/libgenieutils.so" >&2
    exit 1
fi

DAT="$(realpath -e -- "$DAT")"
# Strip trailing separators without collapsing '..' ahead of symlink resolution.
OUT="$(dirname -- "$OUT")/$(basename -- "$OUT")"
if [[ -L "$OUT" || ( -e "$OUT" && ! -d "$OUT" ) ]]; then
    echo "Output must be a directory, not a file or symlink: $OUT" >&2
    exit 1
fi
OUT="$(realpath -m -- "$OUT")"
if [[ "$OUT" == / || "$ROOT" == "$OUT" || "$ROOT" == "$OUT/"* ||
      "$DAT" == "$OUT/"* || "$SCRIPT_DIR" == "$OUT" || "$SCRIPT_DIR" == "$OUT/"* ||
      "$BUILD" == "$OUT" || "$BUILD" == "$OUT/"* ]]; then
    echo "Output must not contain the input DAT, repository, or dump tools: $OUT" >&2
    exit 1
fi

mkdir -p "$BUILD"

echo "Building DAT loader..."
g++ \
  -std=c++20 \
  -g3 \
  -ggdb \
  -O0 \
  -fno-eliminate-unused-debug-types \
  -femit-class-debug-always \
  "$SCRIPT_DIR/full_dump_loader.cpp" \
  -I"$GENIEUTILS/include" \
  -L"$GENIEUTILS/build" \
  -Wl,-rpath,"$GENIEUTILS/build" \
  -lgenieutils \
  -o "$BUILD/full-dump-loader"

# Build the entire export alongside the destination. A failed GDB run leaves
# the previous output intact; only a completed manifest permits replacement.
mkdir -p -- "$(dirname -- "$OUT")"
STAGING="$(mktemp -d "$(dirname -- "$OUT")/.dat-dump.XXXXXX")"
BACKUP=""

cleanup() {
    local status=$?
    trap - EXIT
    if [[ -n "$BACKUP" && -d "$BACKUP" && ! -e "$OUT" ]]; then
        if ! mv -T -- "$BACKUP" "$OUT"; then
            echo "Previous output is preserved at: $BACKUP" >&2
        fi
    fi
    if [[ -n "$STAGING" && -d "$STAGING" ]]; then
        rm -rf -- "$STAGING"
    fi
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

export DAT_INPUT="$DAT"
export DAT_DUMP_OUT="$STAGING"
export DAT_DUMP_SCRIPT="$SCRIPT_DIR/gdb_dump.py"

gdb \
  -nx \
  -q \
  -batch \
  "$BUILD/full-dump-loader" \
  -ex 'set pagination off' \
  -ex 'set print elements 0' \
  -ex 'set max-value-size unlimited' \
  -ex 'set python print-stack full' \
  -ex 'break dat_dump_breakpoint' \
  -ex 'run' \
  -ex "python import os, runpy; runpy.run_path(os.environ['DAT_DUMP_SCRIPT'], run_name='__main__')"

if [[ ! -s "$STAGING/manifest.json" ]]; then
    echo "DAT export did not produce a completed manifest." >&2
    exit 1
fi

if [[ -d "$OUT" ]]; then
    BACKUP="$STAGING.previous"
    mv -T -- "$OUT" "$BACKUP"
fi
mv -T -- "$STAGING" "$OUT"
STAGING=""
if [[ -n "$BACKUP" ]]; then
    rm -rf -- "$BACKUP"
    BACKUP=""
fi

echo
echo "DAT reference generated:"
echo "  $OUT/manifest.json"
