# Weather Variation Family 001

Status: EXPERIMENTAL / WEATHER-LOCAL PROCEDURAL EVIDENCE

This lane proceduralizes one repeated operation already present in the exact Weather baseline: choosing a deterministic stochastic layout for the 36 visual atmosphere streaks. It does not add a new weather simulation and it does not alter the authored visual wind semantics.

## Exact prerequisite

- repository: `mike-axiom-mir/axm-weather-design`
- prerequisite PR: `#2 — Add first bounded wind atmosphere visual baseline`
- exact prerequisite head: `ca2eaba519e8449835b0ea6ef944b7080c3caa6a`
- exact baseline source digest: `b33feba47b0a0f9a99ec439e32a87ff6d4cb2dacffe33ba78f8b646c3a1be8d6`

The family fails closed if that source digest changes.

## Bounded family

Schema: `axm.weather-atmosphere-variation-family/v0.1`

Family: `wind-atmosphere-seeded-field-001`

The only mutable source fields are:

- `study_id` — derived evidence identity;
- `seed` — integer in `[0, 2147483647]`.

The family preserves exactly:

- map-context provenance;
- scene extent;
- visual wind direction;
- `VISUAL_DIRECTION_ONLY_NOT_PHYSICAL_WIND_SPEED` semantics;
- visual displacement speed;
- particle count;
- sample times;
- streak-length bounds;
- safe margin / no-wrap proof window;
- baseline truth boundary.

Changing wind direction, speed, density/count, timings or physical meaning remains VFX / Weather source-authoring work and is outside this procedural contract.

## Acceptance and HOLD boundary

Every candidate re-runs the existing Weather `evaluate()` gate. In addition, a retained variant must:

- move at least 30 of 36 indexed streak starting positions by at least `0.25 m` relative to the baseline seed;
- occupy all four XY quadrants;
- span at least 70% of the available interior width and 70% of the available interior height.

A seed that does not satisfy those gates returns `HOLD_VARIANT_GATE`. The generator does not silently change wind semantics, increase density, widen the scene, pick a different seed, or weaken the gate to manufacture a PASS.

The baseline seed `9142` is retained as a deliberate negative control: because it reproduces the original particle field rather than a material variation, it must HOLD.

## Multi-seed evidence

Retained family seeds:

- `1207`
- `44021`
- `83017`

CI requires all three to:

- pass the existing Weather directional evidence;
- preserve every immutable field;
- pass the material-difference and field-spread gates;
- produce distinct candidate source digests;
- produce distinct particle-layout digests.

The retained artifact contains per-seed source JSON, exact particle JSON, receipt JSON and the `t=0.50 s` SVG, plus a side-by-side seed comparison and family summary.

## Truth boundary

A PASS establishes only that this exact Weather source can deterministically produce multiple materially different bounded visual-streak layouts while preserving its authored visual direction/motion semantics and source context. It does not establish better visual composition, physical weather, turbulence, precipitation, volumetrics, target-engine particle behavior, Environment acceptance, runtime performance, CANON, production readiness, a Universal Creation weather primitive, or Procedural Design mastery.

This stays Weather-local. Horizontal extraction should wait until repeated procedural families demonstrate genuinely duplicated domain-neutral machinery rather than merely sharing the concepts of seeds and validation.
