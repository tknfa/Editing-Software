# Editing Software

Experimental macOS-first editing software for fast, stylized video work with a focus on advanced time remapping, datamoshing, and high-energy transition design.

[![Watch the live demo on YouTube](https://img.youtube.com/vi/Ktxvz2U8dnA/hqdefault.jpg)](https://youtu.be/Ktxvz2U8dnA)

[Watch the live demo on YouTube](https://youtu.be/Ktxvz2U8dnA)

## About

This project is a product-oriented editing workspace built on top of proven open-source video tooling. Instead of creating a video editor from scratch, it extends the OpenShot stack with a simpler workflow and custom features for glitch-heavy, speed-ramp-driven editing.

Basic information:

- Platform: macOS-first development workflow
- Status: local alpha, runnable from source
- Application baseline: `OpenShot/openshot-qt` + `libopenshot`
- Core focus: time remapping, datamoshing, stylized transitions, and fast editing flow
- Current goal: make advanced visual edits easier to create without digging through a complicated interface

## What This Project Focuses On

- Advanced retime tools with speed graphs, ramp editing, freeze/reverse controls, and smoother interpolation modes
- Cached datamosh generation that can be dropped back into the timeline as a reusable asset
- Jugg-style transitions and one-click clip looks for energetic short-form edits
- A cleaner editing workflow built around quick actions, guided next steps, and progressive disclosure

## Here's How This App Can Help You!

- Turn raw clips into stylized edits faster by keeping speed ramps, freezes, and impact timing close at hand
- Experiment with glitch and datamosh treatments without destructively changing your original media
- Build aggressive fight edits, highlight edits, or short-form content with less setup friction
- Stay focused on editing instead of digging through a dense inherited editor interface
- Preview and shape timing visually with custom retime tools designed around ease of use

## Current Feature Highlights

### Time Remapping

- Custom retime dialog for speed-based and duration-based edits
- Segment-based speed graph workflow
- Reverse, freeze, and freeze-plus-zoom shortcuts
- Ramp editing with easing presets
- Clip-level interpolation modes including `Source Frames`, `Frame Blend`, and `Optical Flow`

### Datamosh Workflow

- One-click datamosh presets
- Cached derived-asset generation
- Reusable recent variants
- Baking from the edited clip result rather than only the raw source trim

### Transitions And Style

- One-click transition presets such as `Jugg Shake`, `Whip Push`, and `Slam Zoom`
- Beat-aware timing helpers and transient-assisted hit finding
- One-click clip looks such as `Punch Zoom`, `Jugg Shake`, `RGB Split`, and `Glitch Ripple`
- Compact amount controls for softer or harder stylization

### Workflow Simplification

- `Start Here` guidance for empty and newly imported projects
- `Quick Actions` and `Next Move` panels
- Quick export preset cards
- Preview-performance shortcuts
- Simplified quick-edit workspace with less inherited OpenShot clutter exposed by default

## Architecture

The current implementation strategy is to reuse strong upstream systems where they already solve hard video-editing problems well, then layer product-specific workflows on top.

- `OpenShot/openshot-qt`
  Main desktop editor shell, dock layout, and timeline UI baseline
- `OpenShot/libopenshot`
  Editing engine, timeline, keyframes, rendering, and retime behavior
- `OpenShot/libopenshot-audio`
  Audio dependency required by the OpenShot stack
- `Akascape/Datamosher-Pro`
  Reference for datamosh processing ideas and effect behavior
- `gl-transitions/gl-transitions`
  Reference material for transition styles and shader ideas
- `mltframework/mlt`
  Secondary reference engine kept around in case the OpenShot path becomes limiting

More detailed notes live in [ARCHITECTURE.md](</Users/devinkane/Editing Software/docs/ARCHITECTURE.md>).

## How To Run The Program

This project currently runs from source on macOS.

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

Helpful script references:

- [install_phase1_deps.sh](</Users/devinkane/Editing Software/scripts/install_phase1_deps.sh>)
- [build_openshot_baseline.sh](</Users/devinkane/Editing Software/scripts/build_openshot_baseline.sh>)
- [run_openshot_baseline.sh](</Users/devinkane/Editing Software/scripts/run_openshot_baseline.sh>)

Current notes:

- The most reliable local backend is the `qwidget` timeline path
- The app is validated primarily as a source-based macOS development environment
- This is a local alpha, not yet a packaged standalone `.app`

## Workspace Layout

- `upstream/`
  Third-party repositories used as the application baseline or as technical references
- `docs/`
  Architecture notes, plans, status logs, and supporting screenshots
- `scripts/`
  Bootstrap, dependency, build, and run helpers
- `config/`
  Source manifests and local workspace configuration
- `cache/`
  Generated cache data and intermediate outputs
- `artifacts/`
  Test renders, exports, and packaging outputs

## Current Status

This project is in a usable local alpha state for development and testing.

What that means right now:

- The OpenShot baseline builds and launches locally
- Major custom workflows for retime, datamosh, transitions, and simplified editing are already in place
- The interface is being actively shaped around speed and ease of use
- The app is suitable for local experimentation, prototyping, and personal editing workflows

## Limitations

- This is still an alpha workspace, not a finished commercial-grade editor
- Some inherited OpenShot rough edges and warnings still exist
- The project is optimized for local development and testing, not turnkey installation
- Packaging, deeper reliability work, and long-session hardening still remain

## Licensing And Distribution Implications

This project depends on upstream repositories with their own licenses and distribution requirements.

- `openshot-qt` is GPL-licensed
- `libopenshot` and related OpenShot components have their own licensing terms
- `Datamosher-Pro`, `gl-transitions`, and other references bring separate license considerations

Practical implication:

- Personal and local use is straightforward
- Redistribution or commercialization should include a proper license review first

This README is not legal advice.

## Useful Project Docs

- [ARCHITECTURE.md](</Users/devinkane/Editing Software/docs/ARCHITECTURE.md>)
- [BUILD_PLAN.md](</Users/devinkane/Editing Software/docs/BUILD_PLAN.md>)
- [PHASE1_STATUS.md](</Users/devinkane/Editing Software/docs/PHASE1_STATUS.md>)
- [PHASE2_STATUS.md](</Users/devinkane/Editing Software/docs/PHASE2_STATUS.md>)

## Repository Purpose

This repository is the control center for the application effort. It documents the architecture, stores build and run helpers, and tracks the customization work being layered onto the upstream OpenShot baseline.
