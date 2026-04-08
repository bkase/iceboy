from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "gate_ppu_timing.sh"


class GatePpuTimingTest(unittest.TestCase):
    def test_dry_run_covers_all_timing_gate_criteria(self) -> None:
        completed = subprocess.run(
            [str(SCRIPT), "--dry-run"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        stdout = completed.stdout
        self.assertIn("=== PPU TIMING/CONTROL GATE: Milestone B Ready ===", stdout)
        self.assertIn("Criterion 1: Wave A owned ROM differential suites", stdout)
        self.assertIn("Criterion 2: Wave A mooneye timing/control subset", stdout)
        self.assertIn("Criterion 3: PPU mode FSM unit tests", stdout)
        self.assertIn("Criterion 4: STAT/LYC/IRQ unit tests", stdout)
        self.assertIn("Criterion 5: PPU invariant timing subset", stdout)
        self.assertIn("Criterion 6: Video access policy unit tests", stdout)
        self.assertIn("Criterion 7: No unexplained PPU lockstep divergence smoke", stdout)
        self.assertIn("test/rom/test_ppu_wave_a.py", stdout)
        self.assertIn("tools/run_ppu_wave_a_mooneye_verilator.sh", stdout)
        self.assertIn("--skip-build", stdout)
        self.assertIn("test/ppu/unit/test_ppu_modes.py", stdout)
        self.assertIn("test/ppu/unit/test_stat_irq.py", stdout)
        self.assertIn("test/ppu/unit/test_ppu_invariants.py", stdout)
        self.assertIn("test/ppu/unit/test_access_policy.py", stdout)
        self.assertIn("test/harness/test_soc_lockstep_top.py", stdout)
        self.assertIn("=== PPU TIMING/CONTROL: 7 passed, 0 failed ===", stdout)


if __name__ == "__main__":
    unittest.main()
