from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "gate_milestone_e.sh"


class GateMilestoneETest(unittest.TestCase):
    def test_dry_run_covers_all_power_gate_criteria(self) -> None:
        completed = subprocess.run(
            [str(SCRIPT), "--dry-run"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        stdout = completed.stdout
        self.assertIn("=== MILESTONE E GATE: Power Baseline Ready ===", stdout)
        self.assertIn("Criterion 1: HALT quiescence holds the core still", stdout)
        self.assertIn("Criterion 2: ALU idle isolation is measurable", stdout)
        self.assertIn("Criterion 3: Representative activity windows produce SAIF captures", stdout)
        self.assertIn("Criterion 4: Recorded UP5K synthesis baseline is healthy", stdout)
        self.assertIn("Criterion 5: Hardware build remains debug-free and within budget", stdout)
        self.assertIn("Criterion 6: Duty-cycle power artifacts are present", stdout)
        self.assertIn("test/power/test_halt_quiescence.py", stdout)
        self.assertIn("test/power/test_duty_cycle_metrics.py", stdout)
        self.assertIn("tools/run_activity_capture_windows.sh", stdout)
        self.assertIn("docs/hardware/icebreaker_up5k_baseline.json", stdout)
        self.assertIn("tools/verify_hw_build.sh", stdout)
        self.assertIn("bench/artifacts/power_metrics/test_duty_cycle_metrics.py.json", stdout)
        self.assertIn("=== MILESTONE E: 6 passed, 0 failed ===", stdout)


if __name__ == "__main__":
    unittest.main()
