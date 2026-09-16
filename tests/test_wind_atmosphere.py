import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("wind_atmosphere", ROOT / "tools/wind_atmosphere.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WindAtmosphereTests(unittest.TestCase):
    def setUp(self):
        self.source = ROOT / "examples" / "wind_atmosphere_baseline_001.json"
        self.data = MODULE.load_study(self.source)

    def test_baseline_passes_bounded_direction_checks(self):
        report = MODULE.evaluate(self.data)
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(report["particle_count"], 36)
        self.assertAlmostEqual(report["mean_projected_displacement_m"], 0.9, places=9)
        self.assertLessEqual(report["maximum_crosswind_drift_m"], 1e-9)

    def test_generation_is_deterministic(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            report_a = MODULE.build(self.source, first)
            report_b = MODULE.build(self.source, second)
            self.assertEqual(report_a, report_b)
            for name in ["frame_0000ms.svg", "frame_0250ms.svg", "frame_0500ms.svg", "comparison.svg", "evidence.json"]:
                self.assertEqual((Path(first) / name).read_bytes(), (Path(second) / name).read_bytes())

    def test_visual_direction_change_changes_particle_motion(self):
        changed = copy.deepcopy(self.data)
        changed["wind_xy"] = [-0.25, 1.0]
        particle = MODULE.make_particles(changed)[0]
        a = MODULE.sample_particle(particle, changed, 0.0)
        b = MODULE.sample_particle(particle, changed, 0.5)
        self.assertLess(b["x"], a["x"])
        self.assertGreater(b["y"], a["y"])
        self.assertEqual(MODULE.evaluate(changed)["status"], "PASS")

    def test_zero_wind_fails_closed(self):
        changed = copy.deepcopy(self.data)
        changed["wind_xy"] = [0.0, 0.0]
        with self.assertRaises(ValueError):
            MODULE.validate(changed)

    def test_physical_wind_claim_is_rejected(self):
        changed = copy.deepcopy(self.data)
        changed["wind_semantics"] = "PHYSICAL_WIND_MPS"
        with self.assertRaises(ValueError):
            MODULE.validate(changed)

    def test_margin_prevents_wraparound_in_evidence_window(self):
        changed = copy.deepcopy(self.data)
        changed["safe_margin_m"] = 0.5
        with self.assertRaises(ValueError):
            MODULE.validate(changed)

    def test_frame_contains_real_time_sampled_streak_geometry(self):
        particles = MODULE.make_particles(self.data)
        svg0 = MODULE.build_svg(self.data, 0.0, particles)
        svg1 = MODULE.build_svg(self.data, 0.5, particles)
        self.assertEqual(svg0.count('<line id="wind-streak-'), 36)
        self.assertEqual(svg1.count('<line id="wind-streak-'), 36)
        self.assertNotEqual(svg0, svg1)
        self.assertIn("context-only", svg1)


if __name__ == "__main__":
    unittest.main()
