#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv-openshot"

brew_install_if_missing() {
  local formula="$1"

  if brew list --versions "$formula" >/dev/null 2>&1; then
    echo "==> $formula already installed"
  else
    echo "==> Installing $formula"
    brew install "$formula"
  fi
}

brew_install_if_missing qt@5
brew_install_if_missing pyqt@5
brew_install_if_missing ffmpeg
brew_install_if_missing zeromq
brew_install_if_missing cppzmq
brew_install_if_missing libomp

if [[ ! -d "$VENV_DIR" ]]; then
  echo "==> Creating local venv at $VENV_DIR"
  python3 -m venv --system-site-packages "$VENV_DIR"
fi

echo "==> Installing workspace Python packages"
"$VENV_DIR/bin/pip" install \
  requests \
  pyzmq \
  defusedxml \
  sentry-sdk \
  distro \
  pyxdg \
  PyOpenGL

echo
echo "Phase 1 dependencies are ready."

