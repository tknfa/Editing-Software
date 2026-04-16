# Phase 2 Status

## Current focus

Phase 2 is now underway on top of the working OpenShot baseline.

The first implemented slice improves the retime workflow instead of changing the engine:

- traced the current OpenShot retime flow through `openshot-qt` and `libopenshot`
- confirmed timing mode already retimes clips by edge-dragging in the qwidget timeline
- added a `Custom Retime...` action to the clip `Time` menu
- added reusable helper math for custom retime duration calculations

## Current retime map

### UI entry points

- `upstream/openshot-qt/src/windows/views/timeline.py`
  - fixed speed presets
  - reverse
  - freeze / freeze + zoom
  - repeat
  - new custom retime dialog
- `upstream/openshot-qt/src/windows/main_window.py`
  - timing tool toggle
- `upstream/openshot-qt/src/windows/views/timeline_backend/qwidget/clip.py`
  - timing-mode edge drag retime commits
- `upstream/openshot-qt/src/windows/models/properties_model.py`
  - generic `time` keyframe editing

### Retime logic

- `upstream/openshot-qt/src/windows/views/retime.py`
  - keyframe scaling and reverse helpers
  - clip retime application logic
  - custom retime dialog and duration helpers

### Engine path

- `upstream/libopenshot/src/Clip.h`
  - `Clip.time` keyframe curve
- `upstream/libopenshot/src/Clip.cpp`
  - time-mapped frame and audio handling in `apply_timemapping()`
- `upstream/libopenshot/src/FrameMapper.*`
  - mapped-reader direction and frame/audio resampling support

## What changed

- Added a `Custom Retime...` dialog that supports:
  - forward or reverse direction
  - retime by relative speed multiplier
  - retime by exact target duration
- Added a compact retime panel inside the `Properties` dock with:
  - live duration / direction / average speed / curve status
  - quick `0.5x`, `1x`, `2x`, and `4x` presets
  - one-click reverse, freeze, and freeze + zoom actions
  - direct ramp controls for edit, add point, remove point, and segment easing presets
- Added a `Ramp` submenu to the clip `Time` menu with:
  - `Edit Time Curve`
  - `Add Ramp Point`
  - `Remove Ramp Point`
  - easing presets for `Linear`, `Hold`, `Ease In`, `Ease Out`, and `Ease In/Out`
- Added qwidget-only visual ramp authoring support on selected clips when filtering to `time`:
  - visible time-ramp curve drawn directly on the clip body
  - curve-aligned draggable time markers instead of bottom-lane-only markers
  - property-filter-aware marker filtering so `time` editing feels focused
- Added retime-state overlays for selected clips with special time segments:
  - freeze spans tint the clip and label the frozen region
  - hold spans are surfaced separately from normal forward ramps
  - reverse spans get a stronger striped overlay so backward playback reads immediately
- Added retime audio controls in the dock and clip `Time` menu:
  - `Source Default`, `Pitch Shifts With Speed`, and `Mute Retimed Audio` options
  - live `Audio` and `Pitch` status labels in the dock
  - waveform refreshes only when the resulting clip should still display audio
- Added cleaner direct ramp editing for the qwidget timeline:
  - retime points now have larger hit targets and clearer hover/active emphasis
  - time-curve points can be dragged directly on the curve, including vertical retime-value changes
  - first and last ramp points stay horizontally constrained so the edit remains predictable
- Added a compact `At Playhead` readout in the retime dock:
  - current source frame/time under the playhead
  - current segment mode and effective speed
  - current segment easing label
- Added a simple transition preset shelf in the `Properties` dock:
  - one-click `Jugg Shake`, `Whip Push`, `Slam Zoom`, `Glitch Ripple`, and `Clean Fade` actions
  - works from either one selected transition or two overlapping clips on the same track
  - creates or restyles the overlap target without sending you through the full transition browser
- Added the first cached datamosh-derived asset flow:
  - one selected video clip can generate `Cut Mosh`, `Classic Melt`, `Repeat Melt`, or `Jiggle Pulse`
  - results are cached under the OpenShot user cache and reused on repeat requests
  - generated clips are imported automatically and placed above the source clip on a safe upper track
  - this first version bakes the source trim only, not the current clip effect/retime stack
- Added a compact `Clip Looks` preset strip in the `Properties` dock:
  - one-click `Punch Zoom`, `Jugg Shake`, `RGB Split`, and `Glitch Ripple` cards for selected visual clips
  - cards apply a managed stack so the fast path stays simple and the look can be cleared in one click
  - managed effects swap cleanly without removing unrelated user-added clip effects
- Added beat-aware timing helpers to the transition preset panel:
  - `Overlap`, `1/4 Beat`, `1/2 Beat`, `1 Beat`, and `2 Beats` timing buttons now live beside the transition presets
  - timing uses markers around the cut when possible, then falls back to a compact BPM field
  - selected transitions can be resized in place without losing their existing static-mask curves
  - preset clicks now honor the currently selected timing mode, so style and timing stay in one simple flow
- Added a small datamosh history/reapply strip to the datamosh panel:
  - recent cached variants now appear as quick `Show ...` buttons under the main datamosh presets
  - each recent button selects the existing generated clip when it is still on the timeline, or restores it from cache above the source if it was removed
  - recent history and source/generated clip links are now persisted in clip UI metadata, so the strip follows generated variants back to their source clip across app restarts
- Upgraded datamosh baking from source-trim extraction to edited-result rendering:
  - datamosh now renders a temporary isolated timeline for the selected clip before preprocessing, so clip retimes, managed look cards, transforms, and clip-level effect stacks flow into the moshed result
  - cache keys now track the clip's edited render signature instead of only trim bounds, so visual changes invalidate stale cached variants more reliably
  - the edited-result render path is kept internal and automatic, so the user flow stays the same: select clip, click preset, get a cached variant above the source
- Added a top-level `Quick Actions` panel to keep the fast path simple:
  - the Properties dock now surfaces a compact favorites strip first, with the strongest one-click actions for the current context
  - clip selections get favorites like `2x Speed`, `Reverse`, `Freeze`, `Jugg Shake`, and `Cut Mosh`
  - transition selections get favorites like `Jugg Shake`, `Whip Push`, `Find Hit`, and `Beat Pair`
  - inherited detailed property editing is now tucked behind a lightweight `Show/Hide Detailed Properties` toggle, so the dock defaults to the simpler workflow instead of dropping straight into the full property table
- Added a lightweight preview-performance pass for heavier edits:
  - the `Quick Actions` panel now surfaces `Draft Preview` and `Optimize Preview` only when the current clip or transition selection is likely to preview heavily
  - `Draft Preview` now persists between launches and simply scales the timeline preview render size, keeping the UI clean while making retime/style-heavy sequences feel lighter
  - `Optimize Preview` reuses the existing proxy generation path behind a one-click shortcut, so heavier clips can get lighter source media without leaving the fast path
  - quick-edit UI state now saves more reliably because both the detailed-properties toggle and preview mode have matching hidden default settings entries
- Added a compact proxy/cache status strip to keep heavier playback fixes inside the quick workflow:
  - the `Quick Actions` panel now shows a small `Preview Status` strip for heavy clip selections, with the current preview mode plus whether optimized media is ready, missing, building, or still using the source
  - the strip keeps controls state-aware and minimal: `Build/Rebuild Preview`, `Remove Preview`, `Cancel Build`, and `Clear Cache` only appear when they make sense
  - rebuilds now follow a safer path that clears managed proxy outputs and unlinks the current proxy metadata before regenerating, without deleting externally linked preview files
  - preview cache clears now live in the same fast path, so recovering from stutter or stale frames no longer requires dropping into inherited menus
- Added a cleanup pass that trims inherited OpenShot workspace clutter:
  - the old `Views` menu now behaves like a `Workspace` switch, with `Quick Edit Workspace` and `Full Workspace` labels that fit the product direction more clearly
  - the quick workspace is now persisted and restored on startup, so the app opens back into the cleaner layout instead of drifting into the inherited multi-dock setup
  - quick workspace now keeps `Files`, `Preview`, `Properties`, and `Timeline` visible by default while tucking `Transitions`, `Effects`, `Emojis`, `Captions`, and `Tutorial` out of the way
  - fuller access is still one click away, and the legacy freeze/show-all workspace actions are hidden so the View menu stops reading like a generic desktop app shell
- Added a tiny favorites-tuning pass for the quick-actions row:
  - the main quick-actions row now shows only the strongest enabled actions by default, instead of every available shortcut at once
  - clip favorites now lead with the product-specific looks first, so `Jugg Shake`, `Cut Mosh`, and `2x Speed` stay front and center when they are available
  - extra quick actions now sit behind a small persisted `Show More` / `Show Fewer` toggle, which keeps the default interface cleaner without taking away access
  - disabled actions no longer consume space in the compact row, so unavailable options stop pushing more useful actions out of sight
- Added a compact export preset card flow to keep finishing a cut simple:
  - the `Properties` dock now includes a small `Export` panel with `Quick MP4`, `High MP4`, `Lossless MP4`, and `Audio MP3` cards plus an `Open Full Export` escape hatch
  - each card opens the existing export dialog already filled in, so the app keeps one stable render path while avoiding a heavy multi-step export setup for common cases
  - `Quick MP4` prefers macOS `videotoolbox` when available, `High MP4` favors the cleaner standard h.264 path, and `Lossless MP4` falls back gracefully if the lossless target is unavailable
  - the panel also keeps the remembered export folder visible, so the finish path reads more like a clear destination than a dense settings form
- Added a lightweight `Start Here` strip for brand-new edits:
  - the `Properties` dock now surfaces a small starter panel while a project is empty or before the first clip hits the timeline, instead of immediately dropping you into generic property tables
  - empty projects now lead with `Import Files` and `Open Project`, while imported-but-not-yet-cut projects switch to direct timeline actions instead of a generic “what next?” state
  - the starter panel reuses the same `Add to Timeline` dialog under the hood, but now it can launch it directly with the selected or first available media so the first edit step is one click closer
  - once timeline clips exist, the starter strip hides itself and gets out of the way
- Strengthened starter guidance once mixed media is imported into the bin:
  - the starter panel now reads media types in the project files list, so the main add action can become `Add First Video`, `Add First Image`, `Add First Audio`, `Add Selected Video`, or `Add Selected Audio` instead of using one generic label
  - when nothing is selected, mixed bins now prefer a strong visual first step by choosing video before stills and audio, which makes first-cut suggestions feel more intentional
  - when audio is selected in a mixed bin, the panel now explains that clearly and nudges you toward selecting a visual clip first if you want to block the cut visually
  - file selection changes in the `Files` dock now refresh the starter guidance immediately, so the suggestion follows what you have highlighted instead of lagging behind
- Added a small launch-state polish pass for startup and brand-new projects:
  - empty or first-clip projects now automatically snap back into the `Quick Edit Workspace` without overwriting the user’s longer-term workspace preference
  - the starter panel now takes over the Properties dock more cleanly by hiding the legacy detailed property table while the launch/start state is active
  - startup, `New Project`, and post-import flows now focus the primary starter action first, so the first useful button is ready instead of dropping focus on a generic toolbar control
  - opening or creating a starter-state project now also raises the `Files`, `Preview`, and `Properties` docks together, so the first-run layout feels intentional and consistent
- Added a first-run aesthetic pass to make the starter state feel more intentional without adding complexity:
  - the `Start Here` panel now has a cleaner hierarchy with a small project line, a stronger headline, a concise bin summary, and a simpler tip line instead of one dense block of copy
  - the primary starter action now gets a full-width first row while supporting actions sit below it, which makes the first move feel obvious without changing the underlying workflow
  - imported-media counts now stay visible in a compact `Bin: ...` summary, and active selections are called out inline as `Selected: ...`, so the first decision is easier to scan at a glance
  - empty projects now use clearer welcome copy that points at import/open first and keeps drag-and-drop as a lightweight tip instead of burying it inside the main message
- Added smarter first-cut presets once the first media lands on the timeline:
  - `Quick Actions` now switches into an early-edit preset set for the first one or two visual clips, surfacing `Punch Zoom`, `Jugg Shake`, and `Freeze Hit` before the more generic clip utilities
  - if there is only one clip on the timeline, the quick-action dock now treats it as the active target even before you click it again, so the first styling move is visible immediately after the add-to-timeline step
  - once the edit grows past that very early stage, the dock automatically falls back to the normal clip quick actions instead of staying stuck in a “starter” mode
  - the new first-cut actions are built on the existing managed effect-card and retime helpers, so they stay simple in the UI without creating a second editing system
- Added compact timeline guidance for the first handoff:
  - the `Properties` dock now includes a small `Next Move` panel that appears only during the first one or two visual timeline clips, then hides once the edit grows past that early stage
  - with one clip on the timeline, the guide can now offer a direct `Add Another Clip` step when unused visual media is already in the bin, or fall back to `Import More Clips` if it is not
  - with two clips on the same track, the guide changes from “create the handoff” to “style the handoff” depending on whether the clips overlap yet, and it can select the pair and jump the playhead to the join for you
  - the new guide also participates in the simple-properties visibility rules, so the detailed property table stays tucked away while these early high-level prompts are active
- Polished the wording across `Quick Actions` and `Next Move`:
  - first-cut summaries now read more like simple prompts than feature names, shifting from “presets” language toward shorter “moves” and “next move” phrasing
  - the early-edit hints now use calmer, more directive copy like “set the tone” and “style the first cut,” which keeps the interface feeling lighter during the first edit steps
  - button labels around the first handoff were shortened to clearer phrases like `Select First Cut`, and the default quick-action help text now refers to “clip or handoff” instead of broader editor jargon
  - tooltip copy for the first-cut quick actions was also tightened so the hover text reads more like plain editing guidance than implementation detail
- Added beat-aware defaults to the `Add Another Clip` path from `Next Move`:
  - when the first visual clip is on the timeline, the `Add Another Clip` action now opens the normal add-to-timeline dialog on the same track with a small overlap already filled in, instead of dropping the second shot at a generic position
  - if there is a nearby marker close to the end of the first clip, that marker is used as the overlap start; otherwise the overlap falls back to a small quarter-beat-sized default
  - this keeps the first handoff closer to transition-ready immediately after import, without forcing the user into a separate timing workflow
  - the add-to-timeline dialog itself now accepts an optional preselected track number, so this guidance path can keep both early clips on one track by default
- Added a small spacing polish pass across the quick-edit dock panels:
  - the visible early-workflow panels now share a more consistent 10px outer rhythm, slightly wider button/grid spacing, and cleaner secondary section padding
  - preview, export, and quick-action sub-sections now breathe a bit more, which helps the simple workspace feel more like one intentional surface instead of stacked inherited widgets
  - this was kept deliberately light, so the layout stays familiar while reading cleaner during the first-run and first-cut flow
- Added a compact `Project FPS` tool to the simplified Properties dock:
  - the editor already had profile-level frame-rate handling under the hood, but it was buried behind the generic profile chooser instead of living in the quick workflow
  - the dock now exposes one-click project FPS presets for `23.98`, `24`, `25`, `29.97`, `30`, `50`, `59.94`, and `60`, while preserving the current project width, height, and aspect ratio
  - when no built-in profile matches the current project shape, the app now creates a matching user profile automatically so the FPS choice survives project save/reopen cleanly
  - a `Custom...` button opens the full profile editor from the current project format, which keeps arbitrary numerator/denominator editing available without cluttering the simple path
- Added compact preset amount controls without breaking the one-click flow:
  - `Clip Looks`, transition presets, and datamosh now each expose a simple three-step `Amount` row instead of deeper effect menus
  - changing `Soft` / `Default` / `Hard` on an already-styled clip or transition reapplies the current preset immediately, so fine-tuning stays one click
  - datamosh variants now also track `Light` / `Default` / `Wild` in cache keys, recent-history entries, and generated-clip metadata
- Added lightweight beat-marker helpers to the transition preset panel:
  - quick `Playhead`, `Cut`, `Beat Pair`, and `Clear Nearby` buttons now live beside the existing beat timing controls
  - `Beat Pair` drops a one-beat window around the selected cut using nearby markers when possible, then falls back to the BPM field
  - helper actions reuse normal project markers with duplicate protection, so the fast path stays tidy instead of spraying extra markers
- Added transient-assisted marker placement for faster music syncing:
  - a compact `Find Hit` action now looks for the strongest nearby transient around the selected cut using existing clip waveform data
  - if nearby audio has not been analyzed yet, the helper quietly kicks off waveform generation for those clips instead of failing silently
  - hit detection stays lightweight and local, so the fast path gets better without introducing a separate audio-analysis workflow
- Added focused unit coverage for custom retime and ramp-editing helpers

## Recommended next slice

The next strongest improvement is to keep the editor simple while reducing friction further with:

1. tighter transition/audio feedback around detected hits once the syncing workflow settles
2. a small visual pass on hierarchy and emphasis inside the transition panel, so it matches the simplicity of the first-cut workflow
3. optional “one-click add and overlap” behavior if the normal add dialog still feels like one step too many
