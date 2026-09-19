from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_WIND_SPEC = importlib.util.spec_from_file_location("wind_atmosphere", ROOT / "tools" / "wind_atmosphere.py")
WIND = importlib.util.module_from_spec(_WIND_SPEC)
_WIND_SPEC.loader.exec_module(WIND)

FAMILY_SCHEMA = "axm.weather-atmosphere-variation-family/v0.1"
RECEIPT_SCHEMA = "axm.weather-atmosphere-variation-receipt/v0.1"
SUMMARY_SCHEMA = "axm.weather-atmosphere-variation-family-evidence/v0.1"


def load_family(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_family(data)
    return data


def validate_family(data):
    if data.get("schema") != FAMILY_SCHEMA:
        raise ValueError("unsupported family schema")
    if not str(data.get("family_id", "")).strip():
        raise ValueError("family_id required")
    source_digest = str(data.get("base_source_digest", ""))
    if len(source_digest) != 64 or any(ch not in "0123456789abcdef" for ch in source_digest):
        raise ValueError("base_source_digest must be lowercase sha256")
    seed_min, seed_max = int(data["seed_min"]), int(data["seed_max"])
    if seed_min < 0 or seed_min >= seed_max:
        raise ValueError("invalid seed bounds")
    seeds = [int(seed) for seed in data["retained_seeds"]]
    if len(seeds) < 3 or len(seeds) != len(set(seeds)):
        raise ValueError("retained_seeds must contain at least three distinct values")
    if not all(seed_min <= seed <= seed_max for seed in seeds):
        raise ValueError("retained seed outside family bounds")
    immutable = list(data["immutable_fields"])
    required_immutable = {
        "schema", "source_context", "scene_size_m", "wind_xy", "wind_semantics",
        "visual_speed_m_per_s", "particle_count", "times_s", "streak_length_m",
        "safe_margin_m", "truth_boundary",
    }
    if set(immutable) != required_immutable:
        raise ValueError("immutable_fields must match the bounded v0.1 Weather source contract")
    material_gate = data["material_difference_gate"]
    if int(material_gate["min_moved_start_positions"]) <= 0:
        raise ValueError("min_moved_start_positions must be positive")
    if float(material_gate["min_start_delta_m"]) <= 0:
        raise ValueError("min_start_delta_m must be positive")
    spread_gate = data["field_spread_gate"]
    if int(spread_gate["required_quadrants"]) != 4:
        raise ValueError("v0.1 requires all four XY quadrants")
    for name in ("min_x_span_fraction", "min_y_span_fraction"):
        value = float(spread_gate[name])
        if not (0.0 < value <= 1.0):
            raise ValueError(f"{name} must be in (0, 1]")


def _bind_base(base, family):
    WIND.validate(base)
    actual = WIND.digest(base)
    expected = family["base_source_digest"]
    if actual != expected:
        raise ValueError(f"base source digest mismatch: expected {expected}, got {actual}")


def _candidate(base, family, seed):
    seed = int(seed)
    if not (int(family["seed_min"]) <= seed <= int(family["seed_max"])):
        raise ValueError("seed outside bounded family range")
    result = copy.deepcopy(base)
    result["study_id"] = f'{family["family_id"]}-seed-{seed}'
    result["seed"] = seed
    WIND.validate(result)
    return result


def _layout_metrics(baseline_particles, candidate_particles, candidate, family):
    threshold = float(family["material_difference_gate"]["min_start_delta_m"])
    moved = 0
    for before, after in zip(baseline_particles, candidate_particles):
        if math.hypot(float(after["x0"]) - float(before["x0"]), float(after["y0"]) - float(before["y0"])) >= threshold:
            moved += 1

    quadrants = {
        (1 if float(p["x0"]) >= 0.0 else -1, 1 if float(p["y0"]) >= 0.0 else -1)
        for p in candidate_particles
    }
    xs = [float(p["x0"]) for p in candidate_particles]
    ys = [float(p["y0"]) for p in candidate_particles]
    width, height = map(float, candidate["scene_size_m"])
    margin = float(candidate["safe_margin_m"])
    interior_width = width - 2.0 * margin
    interior_height = height - 2.0 * margin
    x_span = max(xs) - min(xs)
    y_span = max(ys) - min(ys)
    return {
        "moved_start_positions": moved,
        "quadrants_occupied": len(quadrants),
        "x_span_m": x_span,
        "y_span_m": y_span,
        "x_span_fraction_of_interior": x_span / interior_width,
        "y_span_fraction_of_interior": y_span / interior_height,
        "centroid_xy_m": [sum(xs) / len(xs), sum(ys) / len(ys)],
    }


def evaluate_variant(base, family, seed):
    validate_family(family)
    _bind_base(base, family)
    candidate = _candidate(base, family, seed)

    immutable_checks = {
        field: candidate[field] == base[field]
        for field in family["immutable_fields"]
    }
    baseline_particles = WIND.make_particles(base)
    candidate_particles = WIND.make_particles(candidate)
    metrics = _layout_metrics(baseline_particles, candidate_particles, candidate, family)
    weather_report = WIND.evaluate(candidate)
    spread = family["field_spread_gate"]
    material = family["material_difference_gate"]

    checks = {
        "base_source_digest_matches": WIND.digest(base) == family["base_source_digest"],
        "only_seed_and_study_id_are_mutated": all(immutable_checks.values()),
        "existing_weather_gate_passes": weather_report["status"] == "PASS",
        "materially_different_from_baseline": metrics["moved_start_positions"] >= int(material["min_moved_start_positions"]),
        "all_four_quadrants_represented": metrics["quadrants_occupied"] >= int(spread["required_quadrants"]),
        "x_spread_is_bounded_not_clumped": metrics["x_span_fraction_of_interior"] >= float(spread["min_x_span_fraction"]),
        "y_spread_is_bounded_not_clumped": metrics["y_span_fraction_of_interior"] >= float(spread["min_y_span_fraction"]),
    }
    status = "PASS" if all(checks.values()) else "HOLD_VARIANT_GATE"
    return candidate, candidate_particles, {
        "schema": RECEIPT_SCHEMA,
        "family_id": family["family_id"],
        "family_digest": WIND.digest(family),
        "base_source_digest": family["base_source_digest"],
        "candidate_source_digest": WIND.digest(candidate),
        "particle_layout_digest": WIND.digest(candidate_particles),
        "seed": int(seed),
        "status": status,
        "checks": checks,
        "immutable_checks": immutable_checks,
        "layout_metrics": metrics,
        "weather_evidence": weather_report,
        "truth_boundary": family["truth_boundary"],
    }


def build_seed_comparison_svg(base, family, evaluated, time_s=0.5):
    panel_w, panel_h, label_h = 480, 360, 28
    full_w = panel_w * len(evaluated)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{full_w}" height="{panel_h + label_h}" viewBox="0 0 {full_w} {panel_h + label_h}">']
    for index, (candidate, particles, receipt) in enumerate(evaluated):
        body = WIND.build_svg(candidate, time_s, particles).split('>', 1)[1].rsplit('</svg>', 1)[0]
        x = index * panel_w
        out.append(f'<rect x="{x}" y="0" width="{panel_w}" height="{label_h}" fill="#0b111a"/>')
        out.append(f'<text x="{x + 12}" y="19" fill="#d7e7ff" font-family="monospace" font-size="14">seed {receipt["seed"]} / {receipt["status"]}</text>')
        out.append(f'<svg x="{x}" y="{label_h}" width="{panel_w}" height="{panel_h}" viewBox="0 0 960 720">{body}</svg>')
    out.append('</svg>')
    return "\n".join(out) + "\n"


def build_family_evidence(base_path, family_path, output_dir):
    base = WIND.load_study(base_path)
    family = load_family(family_path)
    _bind_base(base, family)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    evaluated = []
    for seed in family["retained_seeds"]:
        candidate, particles, receipt = evaluate_variant(base, family, int(seed))
        evaluated.append((candidate, particles, receipt))
        seed_dir = output / f"seed_{int(seed)}"
        seed_dir.mkdir(parents=True, exist_ok=True)
        (seed_dir / "source.json").write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (seed_dir / "particles.json").write_text(json.dumps(particles, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (seed_dir / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (seed_dir / "frame_0500ms.svg").write_text(WIND.build_svg(candidate, 0.5, particles), encoding="utf-8")

    receipts = [item[2] for item in evaluated]
    layout_digests = [receipt["particle_layout_digest"] for receipt in receipts]
    source_digests = [receipt["candidate_source_digest"] for receipt in receipts]
    all_pass = all(receipt["status"] == "PASS" for receipt in receipts)
    distinct_layouts = len(set(layout_digests)) == len(layout_digests)
    distinct_sources = len(set(source_digests)) == len(source_digests)

    _, _, negative_receipt = evaluate_variant(base, family, int(base["seed"]))
    negative_control_holds = negative_receipt["status"] == "HOLD_VARIANT_GATE"

    summary_checks = {
        "all_retained_seeds_pass": all_pass,
        "all_retained_particle_layouts_are_distinct": distinct_layouts,
        "all_retained_candidate_sources_are_distinct": distinct_sources,
        "baseline_seed_negative_control_holds_for_no_material_difference": negative_control_holds,
    }
    status = "PASS" if all(summary_checks.values()) else "HOLD_FAMILY_EVIDENCE"
    summary = {
        "schema": SUMMARY_SCHEMA,
        "family_id": family["family_id"],
        "family_digest": WIND.digest(family),
        "base_source_digest": family["base_source_digest"],
        "base_head": family["base_head"],
        "receiving_head": os.environ.get("AXM_RECEIVING_HEAD", "LOCAL_UNBOUND"),
        "status": status,
        "checks": summary_checks,
        "retained_seeds": [receipt["seed"] for receipt in receipts],
        "variants": receipts,
        "negative_control": negative_receipt,
        "truth_boundary": family["truth_boundary"],
    }
    (output / "family.json").write_text(json.dumps(family, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "seed_comparison_0500ms.svg").write_text(build_seed_comparison_svg(base, family, evaluated, 0.5), encoding="utf-8")
    return summary


def main():
    base = ROOT / "examples" / "wind_atmosphere_baseline_001.json"
    family = ROOT / "examples" / "wind_atmosphere_variation_family_001.json"
    output = ROOT / "evidence" / "wind_atmosphere_variation_family_001"
    summary = build_family_evidence(base, family, output)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
