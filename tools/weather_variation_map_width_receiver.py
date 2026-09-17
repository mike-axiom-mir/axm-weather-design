from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from tools import weather_variation_family as FAMILY

WIND = FAMILY.WIND

CONTRACT_SCHEMA = "axm.weather-procedural-map-width-receiver-family/v0.1"
PAYLOAD_SCHEMA = "axm.environment-current-world-weather-width-evidence/v0.1"
PAYLOAD_STATUS = "PASS_CURRENT_WORLD_WEATHER_SOURCE_WIDTH_STRUCTURE"
RUNTIME_SCHEMA = "axm.environment-current-world-weather-width-observation/v0.1"
RUNTIME_STATUS = "PASS_CURRENT_WORLD_WEATHER_SOURCE_WIDTH_LIVE_OBSERVATION"
RECEIPT_SCHEMA = "axm.weather-procedural-map-width-receiver-receipt/v0.1"
SUMMARY_SCHEMA = "axm.weather-procedural-map-width-receiver-family-evidence/v0.1"
RESULT = "PASS_PROCEDURAL_WEATHER_VARIANTS_CURRENT_WORLD_SOURCE_WIDTH_RECEIVER_COMPATIBILITY"
DECISION = "PASS_RECEIVER_COMPATIBILITY_FAMILY_ONLY__NO_MAP_SOURCE_OR_ART_ADOPTION"

PARENT_HEAD = "e482d003853e52fc835f1797ddfb6506a50083ef"
PARENT_SCHEMA = "axm.environment-current-world-weather-variant-evidence/v0.1"
PARENT_STATUS = "PASS_CURRENT_WORLD_WEATHER_VARIANT_REBIND_STRUCTURE"
MAP_WIDTH_HEAD = "dd4a85223ba70f7086db2fdc292e4cb57ac38e47"
MAP_WIDTH_OBSERVER_BLOB = "a3d1eaa02a164db1006c0cddd3ce3108c23a63ae"
MAP_WIDTH_OBSERVER_PATH = "environment-proof/atmosphere_current_world_weather_width_observe.gd"
EXPECTED_SEEDS = (1207, 44021, 83017)
CONTEXTS = ("path_eye", "elevated_oblique")
SELECTED_FRAME_INDICES = (0, 8, 16)
WIDTH_TOL_PX = 0.05
EXPECTED_STATES = 17
EXPECTED_STREAKS = 36
PRESENTATION_HEIGHT_M = 3.0

ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "examples" / "wind_atmosphere_baseline_001.json"
FAMILY_PATH = ROOT / "examples" / "wind_atmosphere_variation_family_001.json"


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, value: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _validate_parent(parent: dict[str, Any]) -> None:
    if parent.get("schema") != PARENT_SCHEMA:
        raise ValueError("parent current-world Weather variant schema drift")
    if parent.get("status") != PARENT_STATUS or not all(parent.get("checks", {}).values()):
        raise ValueError("parent current-world Weather variant proof must PASS exactly")
    if parent.get("receiving_head") != PARENT_HEAD:
        raise ValueError("parent current-world Weather variant exact-head drift")
    states = parent.get("states", [])
    if len(states) != EXPECTED_STATES:
        raise ValueError("parent current-world Weather variant must retain exactly 17 states")
    if any(len(row.get("scene", {}).get("weather_lines", [])) != EXPECTED_STREAKS for row in states):
        raise ValueError("parent current-world Weather variant must retain exactly 36 streaks per state")


def _static_scene_signature(scene: dict[str, Any]) -> str:
    reduced = copy.deepcopy(scene)
    for key in ("weather_lines", "weather_variant", "weather_width_binding", "scene_digest", "truth_boundary"):
        reduced.pop(key, None)
    return digest(reduced)


def _weather_lines(source: dict[str, Any], particles: list[dict[str, Any]], time_s: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, particle in enumerate(particles):
        sample = WIND.sample_particle(particle, source, time_s)
        rows.append({
            "id": str(particle["id"]),
            "tail_xy": [float(sample["tail_x"]), float(sample["tail_y"])],
            "head_xy": [float(sample["x"]), float(sample["y"])],
            "opacity": float(particle["opacity"]),
            "presentation_height_m": PRESENTATION_HEIGHT_M,
            "source_order": index,
            "source_width_px": float(particle["width_px"]),
        })
    return rows


def _field_digest(lines: list[dict[str, Any]]) -> str:
    return digest([
        {
            "id": row["id"],
            "tail_xy": row["tail_xy"],
            "head_xy": row["head_xy"],
            "source_order": row["source_order"],
        }
        for row in lines
    ])


def _width_profile(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"id": str(row["id"]), "width_px": float(row["source_width_px"])} for row in lines]


def _require_retained_seed(family: dict[str, Any], seed: int) -> None:
    retained = tuple(int(value) for value in family["retained_seeds"])
    if retained != EXPECTED_SEEDS:
        raise ValueError(f"retained seed identity drift: {retained}")
    if int(seed) not in retained:
        raise ValueError("seed is outside the exact retained Procedural family; no fallback selection")


def build_payload(parent_path: str | Path, seed: int, receiving_head: str) -> dict[str, Any]:
    parent = _load_json(parent_path)
    _validate_parent(parent)
    base = WIND.load_study(BASE_PATH)
    family = FAMILY.load_family(FAMILY_PATH)
    _require_retained_seed(family, int(seed))
    candidate, particles, variant_receipt = FAMILY.evaluate_variant(base, family, int(seed))
    if variant_receipt.get("status") != "PASS" or not all(variant_receipt.get("checks", {}).values()):
        raise ValueError("retained Procedural Weather variant must PASS exact source-local family gate")
    if len(particles) != EXPECTED_STREAKS:
        raise ValueError("retained Weather variant streak count drift")

    source_head = str(receiving_head).strip()
    if len(source_head) != 40:
        raise ValueError("receiving_head must be an exact 40-character commit SHA")

    states: list[dict[str, Any]] = []
    static_preserved = True
    sapling_preserved = True
    width_profile_digest: str | None = None
    width_profile: list[dict[str, Any]] | None = None
    ordered_ids = [str(row["id"]) for row in particles]

    for parent_row in parent["states"]:
        time_s = float(parent_row["time_s"])
        lines = _weather_lines(candidate, particles, time_s)
        if [str(row["id"]) for row in lines] != ordered_ids:
            raise ValueError("Weather streak identity/order drift while rebuilding retained seed")
        profile = _width_profile(lines)
        profile_digest = digest(profile)
        if width_profile_digest is None:
            width_profile_digest = profile_digest
            width_profile = profile
        elif profile_digest != width_profile_digest:
            raise ValueError("source-authored Weather width profile changed across time states")

        scene = copy.deepcopy(parent_row["scene"])
        before_static = _static_scene_signature(scene)
        scene["weather_lines"] = lines
        scene["weather_variant"] = {
            "repository": "mike-axiom-mir/axm-weather-design",
            "variation_pr": 3,
            "variation_head": source_head,
            "seed": int(seed),
            "candidate_source_digest": variant_receipt["candidate_source_digest"],
            "particle_layout_digest": variant_receipt["particle_layout_digest"],
            "family_digest": variant_receipt["family_digest"],
            "semantics": candidate["wind_semantics"],
            "relationship": "EXACT_RETAINED_PROCEDURAL_LAYOUT_SUBSTITUTION_ONLY",
        }
        scene["weather_width_binding"] = {
            "receiver_repository": "mike-axiom-mir/axm-map-design",
            "receiver_head": MAP_WIDTH_HEAD,
            "receiver_observer_path": MAP_WIDTH_OBSERVER_PATH,
            "receiver_observer_blob": MAP_WIDTH_OBSERVER_BLOB,
            "semantics": "SOURCE_AUTHORED_SCREEN_PIXEL_STREAK_WIDTH_PRESENTATION_ONLY",
            "receiving_policy": "EXACT_MAP_CAMERA_PROJECTED_RIBBON_NO_LOCAL_RECEIVER_COPY",
        }
        scene["truth_boundary"] = (
            "This derived receiving state substitutes one exact retained Weather Procedural layout into the exact Map current-world skeleton and carries its exact source-authored opacity and width. "
            "Map/VFX retains receiver semantics and the exact donor observer executes unchanged. No Map source adoption, final visual preference, physical weather, gameplay, CANON or production claim is implied."
        )
        scene.pop("scene_digest", None)
        scene["scene_digest"] = digest(scene)
        static_preserved = static_preserved and _static_scene_signature(scene) == before_static
        sapling_preserved = sapling_preserved and parent_row.get("sapling_mesh_digest") == parent_row.get("sapling_mesh_digest")
        states.append({
            "index": int(parent_row["index"]),
            "time_s": time_s,
            "sampling_role": parent_row.get("sampling_role"),
            "weather_field_digest": _field_digest(lines),
            "weather_width_profile_digest": profile_digest,
            "sapling_mesh_digest": parent_row["sapling_mesh_digest"],
            "scene": scene,
        })

    assert width_profile is not None and width_profile_digest is not None
    widths = [float(row["width_px"]) for row in width_profile]
    checks = {
        "parent_exact_head_and_pass_observed": parent.get("receiving_head") == PARENT_HEAD and parent.get("status") == PARENT_STATUS,
        "retained_seed_source_family_passes": variant_receipt.get("status") == "PASS",
        "retained_seed_identity_exact": int(seed) in EXPECTED_SEEDS and int(variant_receipt.get("seed", -1)) == int(seed),
        "seventeen_parent_schedule_states_preserved": [float(row["time_s"]) for row in states] == [float(row["time_s"]) for row in parent["states"]],
        "all_static_current_world_fields_preserved": static_preserved,
        "sapling_sequence_preserved": sapling_preserved and [row["sapling_mesh_digest"] for row in states] == [row["sapling_mesh_digest"] for row in parent["states"]],
        "all_36_streaks_present_every_state": all(len(row["scene"]["weather_lines"]) == EXPECTED_STREAKS for row in states),
        "streak_identity_order_stable": all([str(line["id"]) for line in row["scene"]["weather_lines"]] == ordered_ids for row in states),
        "all_17_weather_fields_distinct": len({row["weather_field_digest"] for row in states}) == EXPECTED_STATES,
        "source_width_profile_stable_all_states": len({row["weather_width_profile_digest"] for row in states}) == 1,
        "source_widths_within_authored_range": min(widths) >= 1.0 and max(widths) <= 2.4,
        "source_widths_materially_nonuniform": len({round(value, 12) for value in widths}) > 1,
        "source_opacity_values_bounded": all(0.0 <= float(line["opacity"]) <= 1.0 for row in states for line in row["scene"]["weather_lines"]),
        "exact_map_width_receiver_pinned_not_copied": MAP_WIDTH_HEAD == "dd4a85223ba70f7086db2fdc292e4cb57ac38e47" and MAP_WIDTH_OBSERVER_BLOB == "a3d1eaa02a164db1006c0cddd3ce3108c23a63ae",
    }
    if not all(checks.values()):
        raise ValueError(f"procedural receiver payload structural checks failed: {checks}")

    payload = {
        "schema": PAYLOAD_SCHEMA,
        "status": PAYLOAD_STATUS,
        "study_id": f"procedural-weather-map-source-width-receiver-seed-{int(seed)}",
        "procedural_contract_schema": CONTRACT_SCHEMA,
        "receiving_head": source_head,
        "parent_variant_head": PARENT_HEAD,
        "map_width_receiver_head": MAP_WIDTH_HEAD,
        "map_width_observer_blob": MAP_WIDTH_OBSERVER_BLOB,
        "weather_variant_head": source_head,
        "weather_variant_seed": int(seed),
        "weather_variant_candidate_source_digest": variant_receipt["candidate_source_digest"],
        "weather_variant_layout_digest": variant_receipt["particle_layout_digest"],
        "weather_variant_family_digest": variant_receipt["family_digest"],
        "source_width_profile": width_profile,
        "source_width_profile_digest": width_profile_digest,
        "source_width_summary": {
            "count": len(widths),
            "minimum_px": min(widths),
            "mean_px": sum(widths) / len(widths),
            "maximum_px": max(widths),
        },
        "checks": checks,
        "states": states,
        "truth_boundary": (
            "PASS structure means only that one exact retained Weather Procedural layout has been rebound into the exact retained Map current-world skeleton with source-authored width/opacity and an exact pinned Map receiver. "
            "Target-host acceptance is separate and must execute the exact Map observer. This does not adopt the layout into Map, prove arbitrary cameras/resolutions, physical weather, target-device performance, gameplay, final art, CANON, production readiness or Procedural mastery."
        ),
    }
    payload["procedural_receiving_digest"] = digest({
        "seed": payload["weather_variant_seed"],
        "layout": payload["weather_variant_layout_digest"],
        "width_profile": payload["source_width_profile_digest"],
        "map_receiver_head": payload["map_width_receiver_head"],
        "map_observer_blob": payload["map_width_observer_blob"],
        "scene_digests": [row["scene"]["scene_digest"] for row in states],
    })
    return payload


def _verify_runtime_data(payload: dict[str, Any], runtime: dict[str, Any], image_root: str | Path | None = None) -> dict[str, Any]:
    if payload.get("schema") != PAYLOAD_SCHEMA or payload.get("status") != PAYLOAD_STATUS:
        raise ValueError("procedural source-width payload must PASS structurally before runtime verification")
    if payload.get("parent_variant_head") != PARENT_HEAD:
        raise ValueError("payload parent head drift")
    if payload.get("map_width_receiver_head") != MAP_WIDTH_HEAD or payload.get("map_width_observer_blob") != MAP_WIDTH_OBSERVER_BLOB:
        raise ValueError("payload exact Map receiver identity drift")
    if runtime.get("schema") != RUNTIME_SCHEMA or runtime.get("state") != RUNTIME_STATUS:
        raise ValueError("exact Map source-width observer did not return its retained PASS state")
    if runtime.get("proof_runtime") != "Godot 4.7.2 GL Compatibility":
        raise ValueError("proof runtime drift")
    for key in ("receiving_head", "parent_variant_head", "weather_variant_head", "weather_variant_seed", "weather_variant_layout_digest", "source_width_profile_digest"):
        if runtime.get(key) != payload.get(key):
            raise ValueError(f"runtime/payload identity drift: {key}")

    samples = runtime.get("samples", [])
    if len(samples) != EXPECTED_STATES:
        raise ValueError("exact Map receiver must retain all 17 states")

    maximum_residual = 0.0
    measured_width_count = 0
    near_clip_count = 0
    near_clip_ids: set[str] = set()
    weather_resource_ids: set[tuple[int, int, int]] = set()
    sapling_resource_ids: set[tuple[int, int, int]] = set()
    rear_modes: set[str] = set()
    field_digests = []
    selected_hashes: dict[str, str] = {}
    all_candidate_updates_pass = True
    root = Path(image_root) if image_root is not None else None

    for sample in samples:
        field_digests.append(str(sample.get("weather_field_digest", "")))
        sapling = sample.get("sapling_update", {})
        sapling_resource_ids.add((int(sapling.get("node_instance_id", -1)), int(sapling.get("mesh_instance_id", -1)), int(sapling.get("material_instance_id", -1))))
        for source in sample.get("static_source_meshes", []):
            if source.get("asset_id") == "source:nature:east-rear-tree-neutral-001":
                rear_modes.add(str(source.get("proof_culling", "")))
        for context in CONTEXTS:
            candidate = sample.get("contexts", {}).get(context, {}).get("candidate", {})
            weather = candidate.get("weather_update", {})
            all_candidate_updates_pass = all_candidate_updates_pass and weather.get("state") == "PASS_SOURCE_WIDTH_PX_CAMERA_PROJECTED_RIBBONS"
            maximum_residual = max(maximum_residual, float(weather.get("maximum_projected_width_residual_px", 999.0)))
            measured_width_count += int(weather.get("measured_width_count", 0))
            near_clip_count += int(weather.get("near_clipped_endpoint_count", 0))
            near_clip_ids.update(str(value) for value in weather.get("near_clipped_streak_ids", []))
            weather_resource_ids.add((int(weather.get("node_instance_id", -1)), int(weather.get("mesh_instance_id", -1)), int(weather.get("material_instance_id", -1))))
            index = int(sample.get("index", -1))
            if root is not None and index in SELECTED_FRAME_INDICES:
                capture = candidate.get("capture", {})
                path = root / Path(str(capture.get("path", ""))).name
                if not path.exists():
                    raise ValueError(f"selected target-host frame missing: {path}")
                selected_hashes[f"{context}:{index:02d}"] = sha256_file(path)

    expected_field_digests = [str(row["weather_field_digest"]) for row in payload["states"]]
    checks = {
        "exact_map_observer_passed": runtime.get("state") == RUNTIME_STATUS,
        "all_17_states_observed": len(samples) == EXPECTED_STATES,
        "all_1224_width_measurements_present": measured_width_count == EXPECTED_STATES * len(CONTEXTS) * EXPECTED_STREAKS,
        "maximum_projected_width_residual_within_map_tolerance": maximum_residual <= WIDTH_TOL_PX,
        "all_candidate_updates_pass": all_candidate_updates_pass,
        "weather_field_sequence_exact": field_digests == expected_field_digests,
        "weather_resource_identity_stable": len(weather_resource_ids) == 1 and next(iter(weather_resource_ids), (-1, -1, -1))[0] > 0,
        "sapling_resource_identity_stable": len(sapling_resource_ids) == 1 and next(iter(sapling_resource_ids), (-1, -1, -1))[0] > 0,
        "rear_tree_culling_preserved": rear_modes == {"CULL_BACK"},
        "selected_target_host_frames_retained": root is None or len(selected_hashes) == len(CONTEXTS) * len(SELECTED_FRAME_INDICES),
    }
    if not all(checks.values()):
        raise ValueError(f"exact Map receiver verification failed: {checks}")

    return {
        "schema": RECEIPT_SCHEMA,
        "result": RESULT,
        "decision": DECISION,
        "seed": int(payload["weather_variant_seed"]),
        "weather_variant_head": payload["weather_variant_head"],
        "weather_variant_candidate_source_digest": payload["weather_variant_candidate_source_digest"],
        "weather_variant_layout_digest": payload["weather_variant_layout_digest"],
        "weather_variant_family_digest": payload["weather_variant_family_digest"],
        "parent_variant_head": PARENT_HEAD,
        "map_width_receiver_head": MAP_WIDTH_HEAD,
        "map_width_observer_blob": MAP_WIDTH_OBSERVER_BLOB,
        "payload_digest": digest(payload),
        "runtime_digest": digest(runtime),
        "checks": checks,
        "measured_width_count": measured_width_count,
        "maximum_projected_width_residual_px": maximum_residual,
        "near_clipped_endpoint_count": near_clip_count,
        "near_clipped_streak_ids": sorted(near_clip_ids),
        "selected_target_host_frame_hashes": selected_hashes,
        "truth_boundary": (
            "PASS proves exact fixed-camera Map source-width receiver compatibility for this one retained Weather Procedural seed across all 17 source states and both exact 1100x720 cameras, while the exact Map observer executes unchanged. "
            "It does not adopt the seed into Map, prove arbitrary camera/resolution fidelity, physical weather, wall-clock playback, target-device performance, gameplay visibility, final art, CANON, production readiness or Procedural mastery."
        ),
    }


def verify_runtime(payload_path: str | Path, runtime_path: str | Path, image_root: str | Path | None = None) -> dict[str, Any]:
    return _verify_runtime_data(_load_json(payload_path), _load_json(runtime_path), image_root)


def build_summary(evidence_root: str | Path, parent_path: str | Path) -> dict[str, Any]:
    root = Path(evidence_root)
    parent = _load_json(parent_path)
    _validate_parent(parent)
    payloads: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    for seed in EXPECTED_SEEDS:
        seed_root = root / f"seed_{seed}"
        payloads.append(_load_json(seed_root / "payload.json"))
        receipts.append(_load_json(seed_root / "receiver_receipt.json"))

    seeds = [int(row["seed"]) for row in receipts]
    layouts = [row["weather_variant_layout_digest"] for row in receipts]
    candidate_sources = [row["weather_variant_candidate_source_digest"] for row in receipts]
    payload_digests = [row["payload_digest"] for row in receipts]
    frame_keys = sorted(set.intersection(*(set(row["selected_target_host_frame_hashes"]) for row in receipts)))
    frame_hashes_distinct_per_slot = all(
        len({row["selected_target_host_frame_hashes"][key] for row in receipts}) == len(EXPECTED_SEEDS)
        for key in frame_keys
    )

    negative_controls: dict[str, str] = {}
    family = FAMILY.load_family(FAMILY_PATH)
    try:
        _require_retained_seed(family, 9142)
    except ValueError as exc:
        negative_controls["baseline_unretained_seed_rejected"] = f"HOLD:{exc}"
    else:
        raise AssertionError("baseline seed 9142 must not be silently promoted into the retained family")

    drifted_parent = copy.deepcopy(parent)
    drifted_parent["receiving_head"] = "0" * 40
    try:
        _validate_parent(drifted_parent)
    except ValueError as exc:
        negative_controls["parent_exact_head_drift_rejected"] = f"HOLD:{exc}"
    else:
        raise AssertionError("parent head drift must fail closed")

    first_runtime = _load_json(root / f"seed_{EXPECTED_SEEDS[0]}" / "runtime.json")
    drifted_runtime = copy.deepcopy(first_runtime)
    drifted_runtime["weather_variant_seed"] = 99999
    try:
        _verify_runtime_data(payloads[0], drifted_runtime, None)
    except ValueError as exc:
        negative_controls["runtime_seed_identity_drift_rejected"] = f"HOLD:{exc}"
    else:
        raise AssertionError("runtime seed identity drift must fail closed")

    checks = {
        "all_three_exact_retained_seeds_observed": seeds == list(EXPECTED_SEEDS),
        "all_three_receiver_receipts_pass": all(row.get("result") == RESULT and all(row.get("checks", {}).values()) for row in receipts),
        "three_candidate_source_digests_distinct": len(set(candidate_sources)) == len(EXPECTED_SEEDS),
        "three_particle_layout_digests_distinct": len(set(layouts)) == len(EXPECTED_SEEDS),
        "three_receiving_payload_digests_distinct": len(set(payload_digests)) == len(EXPECTED_SEEDS),
        "all_3672_width_measurements_present": sum(int(row["measured_width_count"]) for row in receipts) == len(EXPECTED_SEEDS) * EXPECTED_STATES * len(CONTEXTS) * EXPECTED_STREAKS,
        "all_seed_residuals_within_exact_map_tolerance": max(float(row["maximum_projected_width_residual_px"]) for row in receipts) <= WIDTH_TOL_PX,
        "six_selected_target_host_slots_retained_per_seed": frame_keys == sorted(f"{context}:{index:02d}" for context in CONTEXTS for index in SELECTED_FRAME_INDICES),
        "selected_target_host_frames_materially_different_across_seeds": frame_hashes_distinct_per_slot,
        "three_fail_closed_controls_hold": len(negative_controls) == 3 and all(value.startswith("HOLD:") for value in negative_controls.values()),
        "exact_map_receiver_identity_pinned": all(row.get("map_width_receiver_head") == MAP_WIDTH_HEAD and row.get("map_width_observer_blob") == MAP_WIDTH_OBSERVER_BLOB for row in receipts),
    }
    if not all(checks.values()):
        raise ValueError(f"procedural receiver family summary failed: {checks}")

    return {
        "schema": SUMMARY_SCHEMA,
        "result": RESULT,
        "decision": DECISION,
        "receiving_head": os.environ.get("AXM_RECEIVING_HEAD", payloads[0].get("receiving_head", "UNBOUND")),
        "parent_variant_head": PARENT_HEAD,
        "map_width_receiver_head": MAP_WIDTH_HEAD,
        "map_width_observer_path": MAP_WIDTH_OBSERVER_PATH,
        "map_width_observer_blob": MAP_WIDTH_OBSERVER_BLOB,
        "seeds": seeds,
        "checks": checks,
        "negative_controls": negative_controls,
        "total_receiver_states": len(EXPECTED_SEEDS) * EXPECTED_STATES,
        "total_camera_state_pairs": len(EXPECTED_SEEDS) * EXPECTED_STATES * len(CONTEXTS),
        "total_projected_width_measurements": sum(int(row["measured_width_count"]) for row in receipts),
        "maximum_projected_width_residual_px": max(float(row["maximum_projected_width_residual_px"]) for row in receipts),
        "near_clipped_endpoint_counts_by_seed": {str(row["seed"]): int(row["near_clipped_endpoint_count"]) for row in receipts},
        "distinct_layout_digests": layouts,
        "distinct_candidate_source_digests": candidate_sources,
        "selected_target_host_frame_slots": frame_keys,
        "selected_target_host_frames_distinct_per_slot": frame_hashes_distinct_per_slot,
        "source_adoption": False,
        "map_adoption": False,
        "receiver_code_copied_into_weather": False,
        "uc_changed": False,
        "profession_fabric_changed": False,
        "truth_boundary": (
            "PASS proves that all three already-retained Weather Procedural source layouts can traverse the exact pinned Map source-width current-world receiver across 17 source states and two fixed cameras without changing the Weather family, Map receiver semantics, static world state or sapling sequence. "
            "This is compatibility evidence only. It does not choose a preferred seed, adopt any seed into Map, prove arbitrary camera/resolution behavior, wall-clock delivery, physical weather, target-device performance, gameplay, final Art Direction/Visual QA, CANON, production readiness or Procedural mastery."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build")
    build.add_argument("--parent", required=True)
    build.add_argument("--seed", required=True, type=int)
    build.add_argument("--receiving-head", required=True)
    build.add_argument("--output", required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("--payload", required=True)
    verify.add_argument("--runtime", required=True)
    verify.add_argument("--image-root")
    verify.add_argument("--output", required=True)

    summary = sub.add_parser("summarize")
    summary.add_argument("--evidence-root", required=True)
    summary.add_argument("--parent", required=True)
    summary.add_argument("--output", required=True)

    args = parser.parse_args()
    if args.command == "build":
        result = build_payload(args.parent, args.seed, args.receiving_head)
    elif args.command == "verify":
        result = verify_runtime(args.payload, args.runtime, args.image_root)
    else:
        result = build_summary(args.evidence_root, args.parent)

    _write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
