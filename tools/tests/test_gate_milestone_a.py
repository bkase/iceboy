from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "gate_milestone_a.sh"


class GateMilestoneATest(unittest.TestCase):
    def test_dry_run_covers_all_milestone_a_criteria(self) -> None:
        completed = subprocess.run(
            [str(SCRIPT), "--dry-run"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        stdout = completed.stdout
        self.assertIn("=== MILESTONE A GATE: Harness Ready ===", stdout)
        self.assertIn("Criterion 1: Generator reproducibility", stdout)
        self.assertIn("Criterion 2: Smoke scripts", stdout)
        self.assertIn("Criterion 3: Harness tests", stdout)
        self.assertIn("Criterion 4: Semantic failure", stdout)
        self.assertIn("tools/oracle.sh", stdout)
        self.assertIn("tools/smoke.sh", stdout)
        self.assertIn("swim synth", stdout)
        self.assertIn("tools/formal.sh", stdout)
        self.assertIn("tools.tests.test_decode_completeness", stdout)
        self.assertIn("test_reset_profile", stdout)
        self.assertIn("test_event_script_determinism", stdout)
        self.assertIn("test_cpu_lockstep", stdout)
        self.assertIn("=== MILESTONE A: 4 passed, 0 failed ===", stdout)


if __name__ == "__main__":
    unittest.main()
