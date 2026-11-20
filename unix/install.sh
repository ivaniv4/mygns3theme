#!/usr/bin/env bash
# mygns3theme installer for Linux and macOS.
#
# Finds GNS3, finds (or offers to install) the Python version needed to patch
# it, closes GNS3 if needed, patches it (sudo only when required), installs
# every theme and selects the one you pick.
#
# Usage: ./install.sh [--theme ID|NAME] [--gns3-dir PATH] [--yes]
set -euo pipefail

THEME=""
GNS3_DIR=""
ASSUME_YES=0
while [ $# -gt 0 ]; do
    case "$1" in
        --theme) THEME="${2:?--theme needs a value}"; shift 2 ;;
        --gns3-dir) GNS3_DIR="${2:?--gns3-dir needs a value}"; shift 2 ;;
        -y|--yes) ASSUME_YES=1; shift ;;
        -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# the scripts sit next to mygns3theme.py in a release, in unix/ in the repository
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$HERE/mygns3theme.py" ]; then ROOT="$HERE"; else ROOT="$(dirname "$HERE")"; fi
TOOL="$ROOT/mygns3theme.py"

step() { printf '\033[1;35m==>\033[0m %s\n' "$1"; }
done_() { printf '    \033[32m%s\033[0m\n' "$1"; }
die() { printf '\033[31mERROR:\033[0m %s\n' "$1" >&2; exit 1; }
confirm() {
    [ "$ASSUME_YES" = 1 ] && return 0
    local answer
    read -r -p "$1 [Y/n] " answer </dev/tty || answer=""
    case "$answer" in ""|[yYoO]*) return 0 ;; *) return 1 ;; esac
}
json_field() { "$BASE_PY" -c 'import json,sys; d=json.load(sys.stdin) or {}; v=d.get(sys.argv[1]); print("" if v is None else v)' "$1" <<<"$DETECTED"; }

find_python() {
    local version="$1" candidate
    for candidate in "python$version" "/opt/homebrew/bin/python$version" "/usr/local/bin/python$version" \
                     "/Library/Frameworks/Python.framework/Versions/$version/bin/python$version"; do
        if command -v "$candidate" >/dev/null 2>&1; then command -v "$candidate"; return 0; fi
    done
    return 1
}

printf '\n  \033[1;35mmygns3theme\033[0m - Material 3 themes for GNS3\n\n'

BASE_PY="$(command -v python3 || true)"
[ -n "$BASE_PY" ] || die "python3 is required (macOS: xcode-select --install or brew install python)"

GNS3_ARGS=()
[ -n "$GNS3_DIR" ] && GNS3_ARGS=(--gns3-dir "$GNS3_DIR")

# 1. GNS3 and the matching Python
step "Looking for GNS3"
DETECTED="$("$BASE_PY" "$TOOL" ${GNS3_ARGS[@]+"${GNS3_ARGS[@]}"} detect --json)" || die "GNS3 was not found; pass --gns3-dir"
KIND="$(json_field kind)"
TARGET="$(json_field path)"
NEEDED="$(json_field python)"
done_ "$TARGET ($KIND install, GNS3 $(json_field version))"

PY="$BASE_PY"
if [ -n "$NEEDED" ]; then
    step "Looking for Python $NEEDED (the version GNS3 was built with)"
    if ! PY="$(find_python "$NEEDED")"; then
        if [ "$(uname)" = "Darwin" ] && command -v brew >/dev/null 2>&1 && confirm "Install python@$NEEDED with Homebrew?"; then
            brew install "python@$NEEDED"
            PY="$(find_python "$NEEDED")" || die "python$NEEDED still not found after brew install"
        else
            die "Python $NEEDED is required: install it (python.org, Homebrew, or your package manager) and run this script again"
        fi
    fi
    done_ "$PY"
fi

# 2. GNS3 must be closed
if pgrep -x gns3 >/dev/null 2>&1; then
    step "GNS3 is running"
    confirm "Close GNS3 now? (projects are saved on the server)" || die "close GNS3 and run this script again"
    if [ "$(uname)" = "Darwin" ]; then osascript -e 'quit app "GNS3"' >/dev/null 2>&1 || true; else pkill -x gns3 || true; fi
    for _ in $(seq 1 20); do pgrep -x gns3 >/dev/null 2>&1 || break; sleep 1; done
    pgrep -x gns3 >/dev/null 2>&1 && die "GNS3 is still running; close it and run this script again"
    done_ "GNS3 closed"
fi

# 3. Theme choice
if [ -z "$THEME" ]; then
    step "Choose a theme"
    THEME_IDS=()
    i=0
    while IFS=$'\t' read -r id name mode; do
        i=$((i + 1))
        THEME_IDS+=("$id")
        printf '    %2d. %-22s %s\n' "$i" "$name" "$mode"
    done < <("$PY" -c 'import json,sys; [print(t["id"], t["name"], t["mode"], sep="\t") for t in json.load(sys.stdin)]' \
              <<<"$("$PY" "$TOOL" list --json)")
    read -r -p "    Theme number [1] " choice </dev/tty || choice=""
    choice="${choice:-1}"
    case "$choice" in ''|*[!0-9]*) die "invalid choice: $choice" ;; esac
    [ "$choice" -ge 1 ] && [ "$choice" -le "$i" ] || die "invalid choice: $choice"
    THEME="${THEME_IDS[$((choice - 1))]}"
fi

# 4. Patch GNS3 (sudo only when the install is not writable)
step "Adding theme support to GNS3"
if [ "$(json_field writable)" = "True" ]; then
    "$PY" "$TOOL" --gns3-dir "$TARGET" patch
else
    done_ "Administrator rights are needed (sudo)"
    sudo "$PY" "$TOOL" --gns3-dir "$TARGET" patch
fi

# 5. Themes (as the current user, they live in ~/.config/GNS3)
step "Installing the themes"
"$PY" "$TOOL" --gns3-dir "$TARGET" apply --theme "$THEME"

step "Done"
"$PY" "$TOOL" --gns3-dir "$TARGET" status
printf '\n    \033[32mSwitch theme any time: Edit > Preferences > General > Interface style\033[0m\n\n'

LAUNCHER="$(json_field launcher)"
if [ -n "$LAUNCHER" ] && confirm "Start GNS3 now?"; then
    if [ "$(uname)" = "Darwin" ] && [ "${LAUNCHER%.app}" != "$LAUNCHER" ]; then
        open "$LAUNCHER"
    else
        nohup "$LAUNCHER" >/dev/null 2>&1 &
    fi
fi
