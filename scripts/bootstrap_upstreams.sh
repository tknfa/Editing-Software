#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM_DIR="$ROOT_DIR/upstream"
CLONE_DEPTH="${CLONE_DEPTH:-1}"

mkdir -p "$UPSTREAM_DIR"

clone_repo() {
  local name="$1"
  local url="$2"
  local role="$3"
  local target="$UPSTREAM_DIR/$name"

  if [[ -d "$target/.git" ]]; then
    echo "==> $name already exists; fetching latest refs"
    git -C "$target" fetch --all --tags --prune
    return
  fi

  echo "==> Cloning $name"
  echo "    role: $role"

  if [[ "$CLONE_DEPTH" == "0" ]]; then
    git clone "$url" "$target"
  else
    git clone --depth "$CLONE_DEPTH" "$url" "$target"
  fi
}

clone_repo "openshot-qt" "https://github.com/OpenShot/openshot-qt.git" "Primary desktop editor shell and UI reference"
clone_repo "libopenshot" "https://github.com/OpenShot/libopenshot.git" "Primary timeline, effect, and render engine reference"
clone_repo "libopenshot-audio" "https://github.com/OpenShot/libopenshot-audio.git" "Audio engine dependency for OpenShot builds"
clone_repo "datamosher-pro" "https://github.com/Akascape/Datamosher-Pro.git" "Datamosh workflow reference and processing inspiration"
clone_repo "gl-transitions" "https://github.com/gl-transitions/gl-transitions.git" "Shader transition source library"
clone_repo "mlt" "https://github.com/mltframework/mlt.git" "Backup/reference editing engine and plugin system"

echo
echo "Bootstrap complete."
echo "Upstream repositories are available in: $UPSTREAM_DIR"
