from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "gate_milestone_b.sh"


class GateMilestoneBTest(unittest.TestCase):
    def test_dry_run_covers_all_milestone_b_criteria(self) -> None:
        completed = subprocess.run(
            [str(SCRIPT), "--dry-run"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        stdout = completed.stdout
        self.assertIn("=== MILESTONE B GATE: ALU + Decode Ready ===", stdout)
        self.assertIn("Criterion 1: ALU unit tests", stdout)
        self.assertIn("Criterion 2: Decode snapshot tests", stdout)
        self.assertIn("Criterion 3: Single-op differential tests", stdout)
        self.assertIn("Criterion 4: Opcode family coverage report", stdout)
        self.assertIn("swim test test/unit/test_alu.py", stdout)
        self.assertIn("swim test test/unit/test_decode.py", stdout)
        self.assertIn("swim test test/unit/test_decode_cb.py", stdout)
        self.assertIn("swim test test/unit/test_cpu_single_op.py", stdout)
        self.assertIn("=== Opcode Family Coverage ===", stdout)
        self.assertIn("control_misc: 2 suite(s)", stdout)
        self.assertIn("Zero coverage families: none", stdout)
        self.assertIn("=== MILESTONE B: 4 passed, 0 failed ===", stdout)


if __name__ == "__main__":
    unittest.main()
