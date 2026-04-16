#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="$ROOT_DIR/.sandbox-home"
PYTHON_BIN="$ROOT_DIR/.venv-openshot/bin/python"
OPENSHOT_QT_DIR="$ROOT_DIR/upstream/openshot-qt"
LIBOPENSHOT_PYTHON="$ROOT_DIR/upstream/libopenshot/build/bindings/python"
LIBOPENSHOT_LIB="$ROOT_DIR/upstream/libopenshot/build/src"
LIBOPENSHOT_AUDIO_LIB="$ROOT_DIR/upstream/libopenshot-audio/build"
DEFAULT_BACKEND="${OPENSHOT_BACKEND:-qwidget}"

mkdir -p "$HOME_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing Python environment: $PYTHON_BIN"
  echo "Run ./scripts/install_phase1_deps.sh first."
  exit 1
fi

if [[ ! -f "$LIBOPENSHOT_PYTHON/_openshot.so" ]]; then
  echo "Missing libopenshot Python bindings."
  echo "Run ./scripts/build_openshot_baseline.sh first."
  exit 1
fi

exec env \
  HOME="$HOME_DIR" \
  PYTHONPATH="$LIBOPENSHOT_PYTHON" \
  DYLD_LIBRARY_PATH="$LIBOPENSHOT_LIB:$LIBOPENSHOT_AUDIO_LIB:/opt/homebrew/lib:/opt/homebrew/opt/zeromq/lib:/opt/homebrew/opt/libomp/lib" \
  "$PYTHON_BIN" \
  "$OPENSHOT_QT_DIR/src/launch.py" \
  -b "$DEFAULT_BACKEND" \
  "$@"

