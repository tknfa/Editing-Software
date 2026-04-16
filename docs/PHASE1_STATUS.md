# Phase 1 Status

## Current outcome

Phase 1 is functionally complete.

We now have:

- `libopenshot-audio` configured and built locally
- `libopenshot` configured and built locally
- Python bindings for `libopenshot` built successfully
- `openshot-qt` launched successfully against the locally built engine stack

## Verified baseline

Verified on this machine on April 12, 2026:

- macOS `26.3.1`
- Homebrew `5.1.5`
- Python `3.14.3`
- CMake `4.2.3`

## Installed machine dependencies

Installed through Homebrew:

- `qt@5`
- `pyqt@5`
- `ffmpeg`
- `zeromq`
- `cppzmq`
- `libomp`

Installed in the workspace venv:

- `requests`
- `pyzmq`
- `defusedxml`
- `sentry-sdk`
- `distro`
- `pyxdg`
- `PyOpenGL`

## Build decisions used for the baseline

To minimize setup friction, the current baseline build disables a few optional pieces:

- `ENABLE_OPENCV=OFF`
- `ENABLE_MAGICK=OFF`
- `ENABLE_LIB_DOCS=OFF`
- `BUILD_TESTING=OFF`
- `ENABLE_RUBY=0`

This keeps the baseline focused on getting the editor stack working before we add extra optional features.

## Launch notes

The current reliable launch path uses the `qwidget` timeline backend:

- Homebrew `qt@5` no longer bundles `QtWebEngine`
- `qwidget` avoids that dependency for the baseline run

Use:

```bash
./scripts/run_openshot_baseline.sh
```

For sandboxed/headless validation only:

```bash
QT_QPA_PLATFORM=offscreen ./scripts/run_openshot_baseline.sh
```

## Known caveats

- In the Codex sandbox, OpenShot fails when it tries to bind local TCP ports for the thumbnail server and debug logger. This is a sandbox limitation, not an app bug.
- The verified full startup required an unsandboxed run.
- Link warnings mention Homebrew dylibs built for macOS `26.0` while CMake linked with target `13.3`. The app still built and launched, but we should clean this up later if it causes runtime instability.
- Startup logs show JUCE/CoreMIDI assertions on this Mac. The app still launched, but audio/MIDI device handling will need a closer look before we rely on it heavily.

## Next phase

Phase 2 should focus on time remapping inside the OpenShot baseline:

1. trace the current retime UI and data flow in `openshot-qt`
2. identify the exact `libopenshot` classes handling time mapping
3. design the first custom retime UX changes for this project

