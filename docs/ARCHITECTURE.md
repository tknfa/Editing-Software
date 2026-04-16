# Architecture Snapshot

## Product goal

Build a personal-use macOS editing app that feels strongest in three areas:

- expressive speed ramps and time remapping
- practical datamosh workflows
- stylized high-energy transitions with shake, zoom, smear, and glitch flavors

## Recommended implementation shape

Use OpenShot as the primary baseline instead of building a timeline engine from zero.

- `openshot-qt` gives us an existing desktop editor shell
- `libopenshot` gives us clip timing, animation curves, and render primitives
- `libopenshot-audio` completes the OpenShot runtime stack for audio work
- `Datamosher-Pro` informs the background media generation workflow
- `gl-transitions` supplies shader material for more stylized transitions
- `MLT` stays available as a reference if OpenShot becomes a hard blocker

## Module boundaries

### Timeline and retime engine

Primary source: `upstream/libopenshot`

Focus areas:

- clip speed controls
- bezier retime curves
- reverse playback
- freeze frames
- audio resample behavior

### Desktop editor shell

Primary source: `upstream/openshot-qt`

Focus areas:

- timeline interactions
- preview window
- clip property editing
- jobs/progress UI
- preset browsing

### Datamosh pipeline

Primary source: `upstream/datamosher-pro`

Expected workflow:

1. user selects clip range or transition pair
2. editor creates an intermediate source render
3. datamosh worker produces a derived asset in cache
4. derived result is reinserted onto the timeline as media

This should begin as an offline/background operation, not a realtime preview effect.

### Transition system

Primary sources:

- `upstream/gl-transitions`
- custom transform/effect presets on top of the editor engine

Expected transition families:

- shake cuts
- whip and slam zoom transitions
- RGB split impacts
- frame stutter handoffs
- datamosh carryovers

## Workspace strategy

The root workspace manages documentation, scripts, and product-specific planning.
Third-party repositories live under `upstream/` so we can inspect and modify them without mixing their history into the workspace metadata.

## Immediate priorities

1. bootstrap upstream repos
2. get OpenShot baseline building on macOS
3. document the current build chain and blockers
4. implement a narrow time remap MVP before touching datamosh or transitions
