from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

import sys

sys.path.insert(0, str(ROOT / "tools"))

import pipeline_insertion_evaluation as pipe_eval


SAMPLE_LOG = """
Info: Max frequency for clock 'CLK': 16.13 MHz (PASS at 12.00 MHz)
Info: Critical path report for clock 'CLK' (posedge -> posedge):
Info:       type curr  total name
Info:   source hardware_core_0.membus_0.joypad_0.visible_p1
Info:   route  hardware_core_0.membus_0.oam_ebr_0.dp_bram_0.mem
Info:   sink   hardware_core_0.bus_read_data_reg
Info: 19.12 ns logic, 38.10 ns routing
Info: Critical path report for cross-domain path '<async>' -> 'posedge CLK':
""".strip()


class PipelineInsertionEvaluationTest(unittest.TestCase):
    def test_extract_primary_clock_critical_path_returns_only_first_clock_section(self) -> None:
        lines = pipe_eval.extract_primary_clock_critical_path(SAMPLE_LOG)

        self.assertTrue(lines[0].startswith("Info: Critical path report for clock"))
        self.assertFalse(any("cross-domain" in line for line in lines))

    def test_evaluate_defers_when_bus_path_meets_timing(self) -> None:
        baseline = {
            "clock_constraint": {"achieved_mhz": 15.17, "target_mhz": 12.0},
            "artifacts": {"nextpnr_log": "/tmp/nextpnr.log"},
        }

        report = pipe_eval.evaluate(baseline, pipe_eval.extract_primary_clock_critical_path(SAMPLE_LOG))

        self.assertEqual(report["summary"]["critical_path_cluster"], "bus_peripheral_readback")
        self.assertEqual(
            report["summary"]["overall_recommendation"],
            "keep current latency; no pipeline insertion recommended",
        )
        self.assertTrue(all(candidate["recommendation"] == "defer" for candidate in report["candidates"]))

    def test_render_markdown_includes_cluster_and_excerpt(self) -> None:
        report = {
            "summary": {
                "overall_recommendation": "keep current latency; no pipeline insertion recommended",
                "achieved_mhz": 15.17,
                "target_mhz": 12.0,
                "timing_margin_mhz": 3.17,
                "critical_path_cluster": "bus_peripheral_readback",
            },
            "critical_path_lines": pipe_eval.extract_primary_clock_critical_path(SAMPLE_LOG),
            "candidates": [
                {
                    "candidate": "decode -> operand select -> ALU -> flag pack",
                    "recommendation": "defer",
                    "reasoning": ["reason"],
                }
            ],
        }

        markdown = pipe_eval.render_markdown(
            report,
            hardware_baseline_path=Path("docs/hardware/icebreaker_up5k_baseline.json"),
            nextpnr_log=Path("build/hw_baseline/nextpnr.log"),
        )

        self.assertIn("# Pipeline Insertion Evaluation", markdown)
        self.assertIn("`bus_peripheral_readback`", markdown)
        self.assertIn("## Critical Path Excerpt", markdown)

    def test_nextpnr_log_path_uses_baseline_artifact(self) -> None:
        payload = {"artifacts": {"nextpnr_log": "/tmp/example.log"}}
        self.assertEqual(pipe_eval.nextpnr_log_path(payload), Path("/tmp/example.log"))


if __name__ == "__main__":
    unittest.main()
