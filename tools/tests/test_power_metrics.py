from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

import sys

sys.path.insert(0, str(ROOT / "test" / "harness"))

import power_metrics
from power_metrics import PowerMetrics, PpuPowerMetrics


class PowerMetricsTest(unittest.TestCase):
    def test_summary_and_anomaly_lines_cover_expected_ratios(self) -> None:
        metrics = PowerMetrics(
            total_cycles=10,
            bus_active_cycles=4,
            alu_active_cycles=1,
            halted_cycles=3,
            halt_quiescent_cycles=2,
            reg_a_we_cycles=1,
            reg_f_we_cycles=1,
            reg_b_we_cycles=1,
            reg_c_we_cycles=0,
            reg_d_we_cycles=0,
            reg_e_we_cycles=0,
            reg_h_we_cycles=0,
            reg_l_we_cycles=0,
            reg_sp_we_cycles=0,
            reg_pc_we_cycles=6,
        )

        summary = metrics.summary_lines()
        self.assertIn("total_cycles=10", summary[0])
        self.assertIn("bus_active=4/10 (0.400)", summary[1])
        self.assertIn("halt_quiescent=2/3 (0.667)", summary[3])
        anomalies = metrics.anomaly_lines()
        self.assertIn("pc_write_enable duty cycle exceeds 50%", anomalies)
        self.assertIn("halted window includes non-quiescent cycles", anomalies)

    def test_append_metrics_artifact_persists_multiple_cases(self) -> None:
        metrics = PowerMetrics(
            total_cycles=4,
            bus_active_cycles=1,
            alu_active_cycles=0,
            halted_cycles=0,
            halt_quiescent_cycles=0,
            reg_a_we_cycles=0,
            reg_f_we_cycles=0,
            reg_b_we_cycles=0,
            reg_c_we_cycles=0,
            reg_d_we_cycles=0,
            reg_e_we_cycles=0,
            reg_h_we_cycles=0,
            reg_l_we_cycles=0,
            reg_sp_we_cycles=0,
            reg_pc_we_cycles=1,
        )
        original_root = power_metrics.ARTIFACT_ROOT
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                power_metrics.ARTIFACT_ROOT = Path(tmpdir)
                target = power_metrics.append_metrics_artifact("suite.py", "case_one", metrics)
                power_metrics.append_metrics_artifact("suite.py", "case_two", metrics)
                payload = json.loads(target.read_text(encoding="utf-8"))
                self.assertEqual(payload["suite"], "suite.py")
                self.assertEqual([entry["case"] for entry in payload["cases"]], ["case_one", "case_two"])
        finally:
            power_metrics.ARTIFACT_ROOT = original_root

    def test_ppu_summary_lines_cover_expected_ratios(self) -> None:
        metrics = PpuPowerMetrics(
            total_dots=8,
            mem_req_cycles=2,
            pixel_emit_cycles=1,
            ly_mode_mutation_cycles=1,
            window_mutation_cycles=0,
            oam_scan_mutation_cycles=2,
            line_objs_mutation_cycles=0,
            fetcher_mutation_cycles=0,
            bg_fifo_mutation_cycles=0,
            obj_fifo_mutation_cycles=0,
            bg_fifo_nonempty_cycles=0,
            obj_fifo_nonempty_cycles=0,
        )

        summary = metrics.summary_lines()
        self.assertIn("total_dots=8", summary[0])
        self.assertIn("mem_req=2/8 (0.250)", summary[1])
        self.assertIn("pixel_emit=1/8 (0.125)", summary[2])
        self.assertEqual(metrics.anomaly_lines(), [])


if __name__ == "__main__":
    unittest.main()
