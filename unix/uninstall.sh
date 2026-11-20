#!/usr/bin/env bash
# Removes mygns3theme on Linux and macOS: switches GNS3 back to the Classic
# style, restores the original GNS3 files (sudo only when required) and deletes
# the theme files.
#
# Usage: ./uninstall.sh [--gns3-dir PATH] [--yes]
set -euo pipefail

GNS3_DIR=""
ASSUME_YES=0
while [ $# -gt 0 ]; do
    case "$1" in
        --gns3-dir) GNS3_DIR="${2:?--gns3-dir needs a value}"; shift 2 ;;
        -y|--yes) ASSUME_YES=1; shift ;;
        -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

HERE="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$HERE/mygns3theme.py" ]; then ROOT="$HERE"; else ROOT="$(dirname "$HERE")"; fi
TOOL="$ROOT/mygns3theme.py"

step() { printf '\033[1;35m==>\033[0m %s\n' "$1"; }
die() { printf '\033[31mERROR:\033[0m %s\n' "$1" >&2; exit 1; }

# restoring files works with any Python 3.10+
PY="$(command -v python3 || true)"
[ -n "$PY" ] || die "python3 is required"

GNS3_ARGS=()
[ -n "$GNS3_DIR" ] && GNS3_ARGS=(--gns3-dir "$GNS3_DIR")

if pgrep -x gns3 >/dev/null 2>&1; then
    if [ "$ASSUME_YES" != 1 ]; then
        read -r -p "GNS3 is running. Close it now? [Y/n] " answer </dev/tty || answer=""
        case "$answer" in ""|[yYoO]*) ;; *) die "close GNS3 and run this script again" ;; esac
    fi
    if [ "$(uname)" = "Darwin" ]; then osascript -e 'quit app "GNS3"' >/dev/null 2>&1 || true; else pkill -x gns3 || true; fi
    for _ in $(seq 1 20); do pgrep -x gns3 >/dev/null 2>&1 || break; sleep 1; done
    pgrep -x gns3 >/dev/null 2>&1 && die "GNS3 is still running; close it and run this script again"
fi

step "Switching GNS3 back to the Classic style"
"$PY" "$TOOL" ${GNS3_ARGS[@]+"${GNS3_ARGS[@]}"} reset-style

step "Restoring the original GNS3 files"
DETECTED="$("$PY" "$TOOL" ${GNS3_ARGS[@]+"${GNS3_ARGS[@]}"} detect --json)" || die "GNS3 was not found; pass --gns3-dir"
field() { "$PY" -c 'import json,sys; v=json.load(sys.stdin).get(sys.argv[1]); print("" if v is None else v)' "$1" <<<"$DETECTED"; }
TARGET="$(field path)"
if [ "$(field writable)" = "True" ]; then
    "$PY" "$TOOL" --gns3-dir "$TARGET" unpatch
else
    sudo "$PY" "$TOOL" --gns3-dir "$TARGET" unpatch
fi

step "Removing the theme files"
"$PY" "$TOOL" remove-themes
printf '    \033[32mmygns3theme removed.\033[0m\n'
