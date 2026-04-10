from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "gate_ppu_composition.sh"


class GatePpuCompositionTest(unittest.TestCase):
    def test_dry_run_covers_all_composition_gate_criteria(self) -> None:
        completed = subprocess.run(
            [str(SCRIPT), "--dry-run"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        stdout = completed.stdout
        self.assertIn("=== PPU COMPOSITION GATE: Milestone D Ready ===", stdout)
        self.assertIn("Criterion 1: Wave C owned ROM differential bundle", stdout)
        self.assertIn("Criterion 2: Object selection and draw-priority unit tests", stdout)
        self.assertIn("Criterion 3: dmg-acid2 reference image comparison", stdout)
        self.assertIn("Criterion 4: Object-selection invariants", stdout)
        self.assertIn("Criterion 5: Draw-priority invariants", stdout)
        self.assertIn("Criterion 6: Full-frame PyBoy composition scenes", stdout)
        self.assertIn("tools/run_ppu_wave_c_verilator.sh", stdout)
        self.assertIn("ICEBOY_PPU_WAVE_C_INCLUDE_RED=1", stdout)
        self.assertIn("tools/run_dma_mode2_hide_verilator.sh", stdout)
        self.assertIn("tools/run_obj_dma_metadata_corrupt_verilator.sh", stdout)
        self.assertIn("test/ppu/unit/test_obj_priority.py", stdout)
        self.assertIn("tools/run_dmg_acid2_verilator.sh", stdout)
        self.assertIn("tools.tests.test_ppu_wave_c_reference", stdout)
        self.assertIn("test/ppu/unit/test_obj_fetch.py", stdout)
        self.assertIn("test/ppu/unit/test_obj_transfer_live.py", stdout)
        self.assertIn("tools.tests.test_ppu_spatial_oracle_wave_c", stdout)
        self.assertIn("=== PPU COMPOSITION: 6 passed, 0 failed ===", stdout)


if __name__ == "__main__":
    unittest.main()
