# Editing Software

Experimental macOS-first editing software for fast, stylized video work with a focus on time remapping, datamoshing, and high-energy transition design.

This workspace is not a greenfield editor. It is a product-oriented development workspace built on top of proven open-source video tooling, with OpenShot serving as the current application baseline and additional upstream repositories informing specialized workflows.

## Overview

The goal of this project is to produce a locally runnable editing application that feels unusually strong in three areas:

- expressive speed ramps and retime workflows
- cached datamosh generation that can be reused inside an edit
- one-click, "jugg"-leaning transition and clip-style presets

The software is being shaped around ease of use. Rather than exposing every inherited OpenShot panel and property table as the primary workflow, the current direction favors:

- compact dock panels
- quick actions and guided next steps
- preset-first editing for the most common stylized moves
- progressive disclosure for detailed controls

## Current Status

This project is currently in a usable local alpha state for development and testing on macOS.

What that means today:

- the OpenShot baseline builds and launches locally from source
- the app includes custom retime, transition, datamosh, quick-action, export, and startup guidance flows
- the interface has been simplified for the early edit workflow
- the project is suitable for active local experimentation, not production distribution

This repository is intended for personal/local use at the moment. It is not yet packaged as a polished standalone macOS application bundle for general users.

## Core Capabilities Implemented

### Time Remapping

- custom retime dialog for speed or exact-duration edits
- reverse, freeze, and freeze-plus-zoom shortcuts
- ramp authoring helpers and easing presets
- visual timeline feedback for freeze, hold, and reverse spans
- playhead-aware retime readout in the Properties dock
- compact audio retime behavior controls

### Datamoshing

- one-click datamosh presets for selected clips
- cached derived-asset workflow instead of destructive media replacement
- recent variant history with source/generated clip linkage
- baking from the current edited clip result rather than only the raw source trim

### Transitions And Clip Styling

- one-click transition presets such as `Jugg Shake`, `Whip Push`, and `Slam Zoom`
- beat-aware timing helpers
- transient-assisted `Find Hit` marker placement
- one-click clip looks such as `Punch Zoom`, `Jugg Shake`, `RGB Split`, and `Glitch Ripple`
- compact preset amount controls for softer or harder application

### Workflow Simplification

- `Start Here` project guidance for empty and newly imported projects
- `Quick Actions` and `Next Move` panels for first-cut editing
- quick export preset cards
- draft preview and optimize-preview shortcuts
- simplified quick-edit workspace with more inherited OpenShot complexity tucked away by default

## Architecture

The current implementation strategy is to reuse strong upstream systems where they already solve hard video-editing problems well, then layer product-specific workflows on top.

- `OpenShot/openshot-qt`
  Desktop editor shell, timeline UI, dock/panel structure, and the main application baseline.
- `OpenShot/libopenshot`
  Timeline, clips, keyframes, render pipeline, and retime-related engine behavior.
- `OpenShot/libopenshot-audio`
  Audio runtime dependency used by the OpenShot stack.
- `Akascape/Datamosher-Pro`
  Reference for datamosh processing approaches and effect behavior.
- `gl-transitions/gl-transitions`
  Transition reference material and shader-oriented transition ideas.
- `mltframework/mlt`
  Secondary reference engine kept available in case OpenShot becomes a hard blocker.

More detailed notes live in [ARCHITECTURE.md](</Users/devinkane/Editing Software/docs/ARCHITECTURE.md>).

## Workspace Layout

- `upstream/`
  Cloned third-party repositories used as the application baseline or as technical references.
- `docs/`
  Architecture notes, phase plans, and implementation status.
- `scripts/`
  Bootstrap, dependency, build, and run helpers.
- `config/`
  Source manifests and local workspace configuration.
- `cache/`
  Generated cache data and intermediate outputs.
- `artifacts/`
  Test renders, exports, and packaging outputs.

## Getting Started

### 1. Install dependencies

```bash
bash ./scripts/install_phase1_deps.sh
```

### 2. Build the baseline stack

```bash
bash ./scripts/build_openshot_baseline.sh
```

### 3. Launch the editor

```bash
bash ./scripts/run_openshot_baseline.sh
```

The helper scripts live in:

- [install_phase1_deps.sh](</Users/devinkane/Editing Software/scripts/install_phase1_deps.sh>)
- [build_openshot_baseline.sh](</Users/devinkane/Editing Software/scripts/build_openshot_baseline.sh>)
- [run_openshot_baseline.sh](</Users/devinkane/Editing Software/scripts/run_openshot_baseline.sh>)

## Development Notes

- The current reliable local backend is the `qwidget` timeline path.
- The project has been validated primarily as a source-based macOS development environment.
- The codebase contains inherited OpenShot behavior alongside custom workflow layers built in this workspace.
- Current work has emphasized local usability and editing flow before packaging and general-user hardening.

For detailed progress history, see:

- [PHASE1_STATUS.md](</Users/devinkane/Editing Software/docs/PHASE1_STATUS.md>)
- [PHASE2_STATUS.md](</Users/devinkane/Editing Software/docs/PHASE2_STATUS.md>)
- [BUILD_PLAN.md](</Users/devinkane/Editing Software/docs/BUILD_PLAN.md>)

## Limitations

- This is still an alpha workspace, not a finished commercial-grade editor.
- Some upstream OpenShot warnings and rough edges are still present.
- The project is optimized for local development and testing, not yet for turnkey installation.
- The interface has been simplified substantially, but inherited editor complexity still exists underneath the new quick workflow.
- Packaging, deeper reliability work, and long-session testing still remain.

## Licensing And Distribution Implications

This project is built around upstream repositories with their own licenses and distribution requirements. That matters even for a technically successful build.

- `openshot-qt` is GPL-licensed.
- `libopenshot` and related OpenShot components carry their own licensing terms and commercial options in some cases.
- `Datamosher-Pro`, `gl-transitions`, and other references each have separate licenses and dependency implications.

Practical implication:

- for personal/local use, the current setup is straightforward
- for redistribution, shipping, or commercialization, licensing needs to be reviewed carefully before treating this as a distributable product

This README is not legal advice. If the project moves beyond local use, a proper license review should happen before packaging or release.

## Project Direction

The near-term direction is to keep strengthening the fast editing path:

- tighter transition and audio feedback around beat and hit detection
- more refined visual hierarchy in the simplified dock panels
- additional reduction of inherited UI friction where the default OpenShot experience is heavier than this product needs

## Repository Purpose

This repository serves as the control center for the application effort:

- it documents the architecture and build strategy
- it houses helper scripts for bootstrapping and running the editor
- it tracks the customization work being layered onto the upstream baseline

It should be read as an active product workspace, not a clean-room standalone editor implementation.
4