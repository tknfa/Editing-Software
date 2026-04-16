# Build Plan

## Phase 0: Workspace bootstrap

Deliverables:

- main workspace repo
- upstream source manifest
- repeatable bootstrap script
- architecture and implementation notes

Exit criteria:

- all target upstream repos cloned under `upstream/`

## Phase 1: OpenShot baseline on macOS

Deliverables:

- `openshot-qt` source available locally
- `libopenshot` source available locally
- `libopenshot-audio` source available locally
- documented build steps for the current machine
- first successful launch of the upstream editor

Exit criteria:

- import, timeline playback, and export work on this Mac

## Phase 2: Time remap MVP

Deliverables:

- speed presets
- speed keyframes
- bezier ramps
- reverse clip support
- freeze frame insertion

Exit criteria:

- a short test edit can mix normal playback, ramps, and reverse without crashes

## Phase 3: Background jobs and cache

Deliverables:

- queued long-running jobs
- cached generated media
- progress and failure reporting

Exit criteria:

- expensive operations do not block the main UI thread

## Phase 4: Datamosh integration

Deliverables:

- clip-to-derived-asset datamosh action
- cached generated datamosh media
- first curated preset pack

Exit criteria:

- user can create and reuse datamoshed clips inside a project

## Phase 5: Transition engine

Deliverables:

- preset schema for stylized transitions
- initial shader-backed transition support
- transform-driven shake and zoom transitions

Exit criteria:

- first five "jugg-like" presets are usable end-to-end

## Phase 6: Performance and reliability

Deliverables:

- proxies
- preview quality controls
- render caching
- autosave and crash recovery checks

Exit criteria:

- timeline remains responsive on real edits
