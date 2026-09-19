# Wind Atmosphere Baseline 001

This is the first source-owned VFX / atmosphere candidate in `axm-weather-design`.

It deliberately consumes only the **context-only** handoff from `axm-map-design` PR #2: scene size `24 m × 18 m` and visual wind direction `[1.0, 0.35]`. It does not import map authority, gameplay state, physics, or final environment art.

The source contract `axm.weather-atmosphere-study/v0.1` creates 36 deterministic atmospheric streaks and samples them at `0.00 s`, `0.25 s`, and `0.50 s`. The evidence window is intentionally short enough that no streak wraps across the scene boundary, so measured displacement can be compared directly with the declared visual direction.

Run:

```bash
python tools/wind_atmosphere.py
python -m unittest discover -s tests -v
```

Generated evidence under `evidence/wind_atmosphere_baseline_001/`:

- `frame_0000ms.svg`
- `frame_0250ms.svg`
- `frame_0500ms.svg`
- `comparison.svg` — the three exact frames side-by-side
- `evidence.json` — exact direction/displacement checks and source digest

## What PASS means

PASS proves only that this exact deterministic visual particle field moves in the declared 2D visual wind direction over the bounded evidence window, with zero crosswind drift in this simple v0 model, and that the map handoff remains labelled context-only.

It does **not** prove physical wind speed, forces, turbulence, precipitation, volumetric weather, vegetation/cloth response, collision, gameplay, damage, target-engine particles, runtime performance, material/lighting quality, final art direction, or visual appeal.

## Environment handoff

The generated SVGs use the same `24 m × 18 m` coordinate extent as the current environment baseline so Environment / World Art can overlay or compare them without transferring source ownership. A future integration pass should consume the exact weather candidate by provenance and replace the map's context-only arrow with a real visual overlay; it must rerun environment readability checks rather than inheriting this PASS.
