from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from spade_cocotb_smoke import run_smoke


class SpadeCocotbIntegrationTest(unittest.TestCase):
    def test_smoke_pipeline_produces_waveform(self) -> None:
        waveform = run_smoke()
        self.assertTrue(waveform.is_file())
        self.assertGreater(waveform.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
