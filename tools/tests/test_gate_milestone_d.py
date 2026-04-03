from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "gate_milestone_d.sh"


class GateMilestoneDTest(unittest.TestCase):
    def test_dry_run_covers_all_milestone_d_criteria(self) -> None:
        completed = subprocess.run(
            [str(SCRIPT), "--dry-run"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        stdout = completed.stdout
        self.assertIn("=== MILESTONE D GATE: Interrupt/Timer Ready ===", stdout)
        self.assertIn("Criterion 1: Wave B ROM differential suites", stdout)
        self.assertIn("Criterion 2: Strict lockstep timer/interrupt subsets", stdout)
        self.assertIn("Criterion 3: Seeded interrupt injection scenarios", stdout)
        self.assertIn("Criterion 4: EI+HALT edge cases and HALT wake behavior", stdout)
        self.assertIn("Criterion 5: Timer and interrupt unit suites", stdout)
        self.assertIn("Criterion 6: Deterministic joypad differential", stdout)
        self.assertIn("Criterion 7: Interrupt source coverage matrix", stdout)
        self.assertIn("test/rom/test_ei_delay.py", stdout)
        self.assertIn("test/rom/test_timer_div_basic.py", stdout)
        self.assertIn("test/rom/test_timer_irq_halt.py", stdout)
        self.assertIn("test/lockstep/test_cpu_lockstep.py", stdout)
        self.assertIn("test/lockstep/test_interrupt_injection.py", stdout)
        self.assertIn("test/lockstep/test_ei_halt_corners.py", stdout)
        self.assertIn("test/unit/test_timer.py", stdout)
        self.assertIn("test/unit/test_interrupts_basic.py", stdout)
        self.assertIn("test/unit/test_interrupt_service.py", stdout)
        self.assertIn("test/rom/test_joy_diverge_persist.py", stdout)
        self.assertIn("=== Interrupt Source Coverage ===", stdout)
        self.assertIn("Required interrupt sources: covered", stdout)
        self.assertIn("=== MILESTONE D: 7 passed, 0 failed ===", stdout)


if __name__ == "__main__":
    unittest.main()
