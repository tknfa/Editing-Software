#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUDIO_DIR="$ROOT_DIR/upstream/libopenshot-audio"
VIDEO_DIR="$ROOT_DIR/upstream/libopenshot"

COMMON_PREFIX="/opt/homebrew/opt/qt@5;/opt/homebrew/opt/libomp;/opt/homebrew/opt/zeromq;/opt/homebrew/opt/cppzmq"
COMMON_INCLUDE="/opt/homebrew/include;/opt/homebrew/opt/libomp/include"
COMMON_LIBRARY="/opt/homebrew/lib;/opt/homebrew/opt/libomp/lib"

echo "==> Building libopenshot-audio"
cmake -B "$AUDIO_DIR/build" -S "$AUDIO_DIR" \
  -DCMAKE_BUILD_TYPE=Debug \
  -DAUTO_INSTALL_DOCS=0 \
  -DENABLE_AUDIO_DOCS=0
cmake --build "$AUDIO_DIR/build" -j4

echo "==> Building libopenshot"
cmake -B "$VIDEO_DIR/build" -S "$VIDEO_DIR" \
  -DCMAKE_BUILD_TYPE=Debug \
  -DOpenShotAudio_ROOT="$AUDIO_DIR/build" \
  -DBUILD_TESTING=OFF \
  -DENABLE_LIB_DOCS=OFF \
  -DENABLE_OPENCV=OFF \
  -DENABLE_MAGICK=OFF \
  -DENABLE_RUBY=0 \
  -DCMAKE_PREFIX_PATH="$COMMON_PREFIX" \
  -DCMAKE_INCLUDE_PATH="$COMMON_INCLUDE" \
  -DCMAKE_LIBRARY_PATH="$COMMON_LIBRARY"
cmake --build "$VIDEO_DIR/build" -j4

echo
echo "OpenShot baseline build complete."

