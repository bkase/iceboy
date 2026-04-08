from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

import sys

sys.path.insert(0, str(ROOT / "tools"))

import encoding_optimization_evaluation as enc_eval


class EncodingOptimizationEvaluationTest(unittest.TestCase):
    def test_evaluate_prefers_deferral_when_area_is_tight_and_timing_is_clean(self) -> None:
        activity = {
            "windows": {
                "demo": {
                    "top_signals": [
                        {"path": "cpu.output__", "toggles": 50},
                        {"path": "cpu.step.commit", "toggles": 30},
                        {"path": "cpu.bus_req", "toggles": 10},
                    ]
                }
            }
        }
        hardware = enc_eval.HardwareSummary(
            lut4_used=3800,
            lut4_available=5280,
            achieved_mhz=15.1,
            target_mhz=12.0,
        )

        report = enc_eval.evaluate(activity, hardware)

        self.assertEqual(report["summary"]["overall_recommendation"], "keep current encodings for now")
        self.assertEqual(report["summary"]["timing_pressure"], "low")
        self.assertEqual(report["summary"]["area_pressure"], "high")
        self.assertTrue(all(entry["recommendation"] == "defer" for entry in report["candidates"]))

    def test_render_markdown_includes_candidate_sections(self) -> None:
        report = {
            "summary": {
                "overall_recommendation": "keep current encodings for now",
                "evidence_quality": "aggregate",
            },
            "hardware": {
                "lut4_used": 10,
                "lut4_available": 20,
                "lut4_utilization": 0.5,
                "achieved_mhz": 15.0,
                "target_mhz": 12.0,
                "timing_margin_mhz": 3.0,
            },
            "candidates": [
                {"candidate": "Phase enum", "recommendation": "defer", "reasoning": ["reason a", "reason b"]},
            ],
        }

        markdown = enc_eval.render_markdown(
            report,
            activity_path=Path("bench/manifests/activity_windows_baseline.json"),
            hardware_path=Path("docs/hardware/icebreaker_up5k_baseline.json"),
        )

        self.assertIn("# Encoding Optimization Evaluation", markdown)
        self.assertIn("### Phase enum", markdown)
        self.assertIn("- Recommendation: defer", markdown)

    def test_main_writes_default_report_shape(self) -> None:
        activity = {
            "windows": {
                "demo": {
                    "top_signals": [
                        {"path": "cpu.output__", "toggles": 12},
                        {"path": "cpu.step", "toggles": 8},
                    ]
                }
            }
        }
        hardware = {
            "utilization": {"lut4_used": 100, "lut4_available": 200},
            "clock_constraint": {"achieved_mhz": 15.0, "target_mhz": 12.0},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            activity_path = root / "activity.json"
            hardware_path = root / "hardware.json"
            out_path = root / "report.md"
            activity_path.write_text(json.dumps(activity), encoding="utf-8")
            hardware_path.write_text(json.dumps(hardware), encoding="utf-8")

            report = enc_eval.evaluate(
                enc_eval.load_json(activity_path),
                enc_eval.load_hardware_summary(hardware_path),
            )
            out_path.write_text(
                enc_eval.render_markdown(report, activity_path=activity_path, hardware_path=hardware_path),
                encoding="utf-8",
            )

            text = out_path.read_text(encoding="utf-8")
            self.assertIn("Overall recommendation: keep current encodings for now", text)


if __name__ == "__main__":
    unittest.main()
