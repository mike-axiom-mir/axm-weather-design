import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("weather_variation_family", ROOT / "tools" / "weather_variation_family.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WeatherVariationFamilyTests(unittest.TestCase):
    def setUp(self):
        self.base = MODULE.WIND.load_study(ROOT / "examples" / "wind_atmosphere_baseline_001.json")
        self.family = MODULE.load_family(ROOT / "examples" / "wind_atmosphere_variation_family_001.json")

    def test_three_retained_seeds_are_materially_distinct_and_keep_weather_gate(self):
        receipts = []
        for seed in self.family["retained_seeds"]:
            _, _, receipt = MODULE.evaluate_variant(self.base, self.family, seed)
            self.assertEqual(receipt["status"], "PASS")
            self.assertTrue(receipt["checks"]["existing_weather_gate_passes"])
            self.assertTrue(receipt["checks"]["only_seed_and_study_id_are_mutated"])
            receipts.append(receipt)
        self.assertEqual(len({r["particle_layout_digest"] for r in receipts}), 3)
        self.assertEqual(len({r["candidate_source_digest"] for r in receipts}), 3)

    def test_same_seed_is_exactly_deterministic(self):
        a = MODULE.evaluate_variant(self.base, self.family, 44021)
        b = MODULE.evaluate_variant(self.base, self.family, 44021)
        self.assertEqual(a, b)

    def test_baseline_seed_holds_instead_of_claiming_variation(self):
        _, _, receipt = MODULE.evaluate_variant(self.base, self.family, self.base["seed"])
        self.assertEqual(receipt["status"], "HOLD_VARIANT_GATE")
        self.assertFalse(receipt["checks"]["materially_different_from_baseline"])

    def test_source_digest_drift_fails_closed(self):
        changed = copy.deepcopy(self.base)
        changed["visual_speed_m_per_s"] = 1.7
        with self.assertRaises(ValueError):
            MODULE.evaluate_variant(changed, self.family, 1207)

    def test_family_cannot_silently_claim_wind_or_density_mutation(self):
        changed = copy.deepcopy(self.family)
        changed["immutable_fields"] = [field for field in changed["immutable_fields"] if field != "wind_xy"]
        with self.assertRaises(ValueError):
            MODULE.validate_family(changed)
        changed = copy.deepcopy(self.family)
        changed["immutable_fields"] = [field for field in changed["immutable_fields"] if field != "particle_count"]
        with self.assertRaises(ValueError):
            MODULE.validate_family(changed)

    def test_evidence_builder_passes_family_and_negative_control(self):
        with tempfile.TemporaryDirectory() as output:
            summary = MODULE.build_family_evidence(
                ROOT / "examples" / "wind_atmosphere_baseline_001.json",
                ROOT / "examples" / "wind_atmosphere_variation_family_001.json",
                output,
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue(all(summary["checks"].values()))
            self.assertTrue((Path(output) / "seed_comparison_0500ms.svg").exists())


if __name__ == "__main__":
    unittest.main()
