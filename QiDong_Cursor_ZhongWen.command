#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/CursorHanHua_GongJu.py"
CURSOR_USER_DIR="${CURSOR_USER_DATA_DIR:-$HOME/Library/Application Support/Cursor}"

find_cursor_app() {
  if [ -n "${CURSOR_INSTALL_DIR:-}" ] && [ -d "$CURSOR_INSTALL_DIR" ]; then
    case "$CURSOR_INSTALL_DIR" in
      *.app) printf '%s\n' "$CURSOR_INSTALL_DIR"; return 0 ;;
      *) if [ -d "$CURSOR_INSTALL_DIR/Contents/Resources/app" ]; then printf '%s\n' "$CURSOR_INSTALL_DIR"; return 0; fi ;;
    esac
  fi

  for candidate in \
    "/Applications/Cursor.app" \
    "$HOME/Applications/Cursor.app" \
    "$HOME/Applications/Cursor" \
    "/Applications/Cursor"
  do
    if [ -d "$candidate/Contents/Resources/app" ] || [ -d "$candidate/resources/app" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

CURSOR_APP="$(find_cursor_app || true)"
if [ -z "$CURSOR_APP" ]; then
  echo "[ERROR] Cursor app not found. Set CURSOR_INSTALL_DIR to Cursor.app or install Cursor in /Applications."
  exit 1
fi

if [ -d "$CURSOR_APP/Contents/Resources/app" ]; then
  export CURSOR_INSTALL_DIR="$CURSOR_APP"
  CURSOR_EXE="$CURSOR_APP/Contents/MacOS/Cursor"
else
  export CURSOR_INSTALL_DIR="$CURSOR_APP"
  CURSOR_EXE="$CURSOR_APP/Cursor"
fi

if [ ! -f "$PYTHON_SCRIPT" ]; then
  echo "[ERROR] Translation script not found: $PYTHON_SCRIPT"
  exit 1
fi

if [ ! -x "$CURSOR_EXE" ]; then
  echo "[ERROR] Cursor executable not found: $CURSOR_EXE"
  exit 1
fi

if [ ! -e "$CURSOR_USER_DIR" ]; then
  mkdir -p "$CURSOR_USER_DIR"
fi

python3 "$PYTHON_SCRIPT"

open -a "$CURSOR_APP" --args --user-data-dir="$CURSOR_USER_DIR"
