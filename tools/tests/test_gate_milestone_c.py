from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "gate_milestone_c.sh"


class GateMilestoneCTest(unittest.TestCase):
    def test_dry_run_covers_all_milestone_c_criteria(self) -> None:
        completed = subprocess.run(
            [str(SCRIPT), "--dry-run"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        stdout = completed.stdout
        self.assertIn("=== MILESTONE C GATE: CPU Wave A Ready ===", stdout)
        self.assertIn("Criterion 1: Wave A ROM differential suites", stdout)
        self.assertIn("Criterion 2: Formal invariants", stdout)
        self.assertIn("Criterion 3: Simulation invariants and write-enable discipline", stdout)
        self.assertIn("Criterion 4: Divergence artifact audit", stdout)
        self.assertIn("test/rom/test_loads_basic.py", stdout)
        self.assertIn("test/rom/test_alu_flags.py", stdout)
        self.assertIn("test/rom/test_alu16_sp.py", stdout)
        self.assertIn("test/rom/test_flow_stack.py", stdout)
        self.assertIn("test/rom/test_cb_bitops.py", stdout)
        self.assertIn("test/rom/test_mem_rwb.py", stdout)
        self.assertIn("test/rom/test_alu_loop.py", stdout)
        self.assertIn("tools/run_formal_cpu_invariants.sh", stdout)
        self.assertIn("tools/run_formal_cpu_hold.sh", stdout)
        self.assertIn("test/unit/test_cpu_invariants_loads.py", stdout)
        self.assertIn("test/unit/test_cpu_invariants_flow.py", stdout)
        self.assertIn("test/unit/test_write_enable.py", stdout)
        self.assertIn("test/harness/test_write_enable_hold.py", stdout)
        self.assertIn("bench/artifacts", stdout)
        self.assertIn("=== MILESTONE C: 4 passed, 0 failed ===", stdout)


if __name__ == "__main__":
    unittest.main()
