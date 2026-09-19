from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path

SCHEMA = "axm.weather-atmosphere-study/v0.1"
EVIDENCE_SCHEMA = "axm.weather-atmosphere-evidence/v0.1"


def _canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def load_study(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError("unsupported schema")
    validate(data)
    return data


def _unit(vector):
    x, y = map(float, vector)
    length = math.hypot(x, y)
    if length <= 0.0:
        raise ValueError("wind_xy must be nonzero")
    return (x / length, y / length)


def validate(data):
    width, height = map(float, data["scene_size_m"])
    if width <= 0 or height <= 0:
        raise ValueError("scene_size_m must be positive")
    _unit(data["wind_xy"])
    if data.get("wind_semantics") != "VISUAL_DIRECTION_ONLY_NOT_PHYSICAL_WIND_SPEED":
        raise ValueError("wind semantics must stay visual-only")
    if float(data["visual_speed_m_per_s"]) <= 0:
        raise ValueError("visual_speed_m_per_s must be positive")
    if int(data["particle_count"]) <= 0 or int(data["particle_count"]) > 256:
        raise ValueError("particle_count out of bounded range")
    times = [float(t) for t in data["times_s"]]
    if len(times) < 2 or times != sorted(times) or times[0] != 0.0:
        raise ValueError("times_s must be sorted and begin at 0")
    lo, hi = map(float, data["streak_length_m"])
    if not (0 < lo <= hi):
        raise ValueError("invalid streak length range")
    margin = float(data["safe_margin_m"])
    max_disp = float(data["visual_speed_m_per_s"]) * times[-1]
    if margin <= max_disp:
        raise ValueError("safe_margin_m must exceed maximum displacement so this proof has no wraparound")
    if 2 * margin >= min(width, height):
        raise ValueError("safe_margin_m leaves no interior particle field")


def make_particles(data):
    rng = random.Random(int(data["seed"]))
    width, height = map(float, data["scene_size_m"])
    margin = float(data["safe_margin_m"])
    lo, hi = map(float, data["streak_length_m"])
    particles = []
    for index in range(int(data["particle_count"])):
        particles.append({
            "id": f"wind-streak-{index:03d}",
            "x0": rng.uniform(-width / 2 + margin, width / 2 - margin),
            "y0": rng.uniform(-height / 2 + margin, height / 2 - margin),
            "length_m": rng.uniform(lo, hi),
            "opacity": rng.uniform(0.28, 0.78),
            "width_px": rng.uniform(1.0, 2.4),
        })
    return particles


def sample_particle(particle, data, time_s):
    dx, dy = _unit(data["wind_xy"])
    speed = float(data["visual_speed_m_per_s"])
    x = particle["x0"] + dx * speed * float(time_s)
    y = particle["y0"] + dy * speed * float(time_s)
    tail_x = x - dx * float(particle["length_m"])
    tail_y = y - dy * float(particle["length_m"])
    return {"x": x, "y": y, "tail_x": tail_x, "tail_y": tail_y}


def evaluate(data):
    particles = make_particles(data)
    t0 = float(data["times_s"][0])
    t1 = float(data["times_s"][-1])
    ux, uy = _unit(data["wind_xy"])
    projected = []
    cross = []
    for particle in particles:
        a = sample_particle(particle, data, t0)
        b = sample_particle(particle, data, t1)
        ddx, ddy = b["x"] - a["x"], b["y"] - a["y"]
        projected.append(ddx * ux + ddy * uy)
        cross.append(abs(ddx * (-uy) + ddy * ux))
    expected = float(data["visual_speed_m_per_s"]) * (t1 - t0)
    checks = {
        "source_context_is_context_only": data.get("source_context", {}).get("relationship") == "CONSUMES_CONTEXT_ONLY_WEATHER_HANDOFF",
        "wind_is_visual_only": data.get("wind_semantics") == "VISUAL_DIRECTION_ONLY_NOT_PHYSICAL_WIND_SPEED",
        "all_particles_move_downwind": all(value > 0 for value in projected),
        "mean_projected_displacement_matches_authored_visual_speed": abs(sum(projected) / len(projected) - expected) <= 1e-9,
        "crosswind_drift_is_zero_in_v0": max(cross, default=0.0) <= 1e-9,
    }
    return {
        "schema": EVIDENCE_SCHEMA,
        "study_id": data["study_id"],
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "source_digest": digest(data),
        "particle_count": len(particles),
        "sample_times_s": data["times_s"],
        "normalized_visual_wind_xy": [ux, uy],
        "mean_projected_displacement_m": sum(projected) / len(projected),
        "maximum_crosswind_drift_m": max(cross, default=0.0),
        "truth_boundary": data["truth_boundary"],
    }


def _map_xy(x, y, data, width_px=960, height_px=720):
    width_m, height_m = map(float, data["scene_size_m"])
    px = (float(x) + width_m / 2) / width_m * width_px
    py = height_px - (float(y) + height_m / 2) / height_m * height_px
    return px, py


def build_svg(data, time_s, particles=None):
    particles = particles or make_particles(data)
    width_px, height_px = 960, 720
    ux, uy = _unit(data["wind_xy"])
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px}" height="{height_px}" viewBox="0 0 {width_px} {height_px}">',
        '<rect width="960" height="720" fill="#10151f"/>',
        '<rect x="420" y="100" width="120" height="540" fill="#162235" stroke="#335074" stroke-dasharray="8 6"/>',
        f'<text x="24" y="36" fill="#d7e7ff" font-family="monospace" font-size="20">AXM wind atmosphere t={float(time_s):.2f}s</text>',
        f'<text x="24" y="62" fill="#8fb6e8" font-family="monospace" font-size="14">visual direction=({ux:.4f},{uy:.4f}) / context-only</text>',
        '<g stroke-linecap="round">',
    ]
    for particle in particles:
        sample = sample_particle(particle, data, time_s)
        x1, y1 = _map_xy(sample["tail_x"], sample["tail_y"], data)
        x2, y2 = _map_xy(sample["x"], sample["y"], data)
        lines.append(
            f'<line id="{particle["id"]}" x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" '
            f'stroke="#b9ddff" stroke-width="{particle["width_px"]:.3f}" opacity="{particle["opacity"]:.3f}"/>'
        )
    lines.extend(['</g>', '</svg>'])
    return "\n".join(lines) + "\n"


def build_comparison_svg(data, particles=None):
    particles = particles or make_particles(data)
    frames = [build_svg(data, t, particles) for t in data["times_s"]]
    panel_w, panel_h = 480, 360
    full_w = panel_w * len(frames)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{full_w}" height="{panel_h}" viewBox="0 0 {full_w} {panel_h}">']
    for index, frame in enumerate(frames):
        body = frame.split('>', 1)[1].rsplit('</svg>', 1)[0]
        out.append(f'<svg x="{index * panel_w}" y="0" width="{panel_w}" height="{panel_h}" viewBox="0 0 960 720">{body}</svg>')
    out.append('</svg>')
    return "\n".join(out) + "\n"


def build(source_path, output_dir):
    data = load_study(source_path)
    particles = make_particles(data)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report = evaluate(data)
    for time_s in data["times_s"]:
        stamp = int(round(float(time_s) * 1000))
        (output / f"frame_{stamp:04d}ms.svg").write_text(build_svg(data, time_s, particles), encoding="utf-8")
    (output / "comparison.svg").write_text(build_comparison_svg(data, particles), encoding="utf-8")
    (output / "evidence.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main():
    root = Path(__file__).resolve().parents[1]
    source = root / "examples" / "wind_atmosphere_baseline_001.json"
    output = root / "evidence" / "wind_atmosphere_baseline_001"
    print(json.dumps(build(source, output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
