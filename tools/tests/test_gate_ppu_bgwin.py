from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "gate_ppu_bgwin.sh"


class GatePpuBgwinTest(unittest.TestCase):
    def test_dry_run_covers_all_bg_window_gate_criteria(self) -> None:
        completed = subprocess.run(
            [str(SCRIPT), "--dry-run"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        stdout = completed.stdout
        self.assertIn("=== PPU BG/WINDOW GATE: Milestone C Ready ===", stdout)
        self.assertIn("Criterion 1: Wave B owned ROM differential suites", stdout)
        self.assertIn("Criterion 2: BG fetch and SCX discard unit suites", stdout)
        self.assertIn("Criterion 3: Tile decode and window trigger unit suites", stdout)
        self.assertIn("Criterion 4: Integrated scanline semantic suites", stdout)
        self.assertIn("Criterion 5: PyBoy tilemap/window semantic references", stdout)
        self.assertIn("Criterion 6: Wave B.5 mealybug canary subset", stdout)
        self.assertIn("test/rom/test_ppu_wave_b.py", stdout)
        self.assertIn("test/ppu/unit/test_bg_fetcher.py", stdout)
        self.assertIn("test/ppu/unit/test_bg_fifo.py", stdout)
        self.assertIn("test/ppu/unit/test_tile.py", stdout)
        self.assertIn("test/ppu/unit/test_window.py", stdout)
        self.assertIn("test/ppu/unit/test_ppu_invariants.py", stdout)
        self.assertIn("test/harness/test_soc_lockstep_top.py", stdout)
        self.assertIn("tools.tests.test_ppu_wave_b_reference", stdout)
        self.assertIn("tools/run_ppu_wave_b_mealybug_verilator.sh", stdout)
        self.assertIn("=== PPU BG/WINDOW: 6 passed, 0 failed ===", stdout)


if __name__ == "__main__":
    unittest.main()
