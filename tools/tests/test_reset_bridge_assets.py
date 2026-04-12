from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


class ResetBridgeAssetsTest(unittest.TestCase):
    def test_reset_bridge_assets_and_hook_membership_exist(self) -> None:
        board_main = (ROOT / "src" / "board" / "main.spade").read_text(encoding="utf-8")
        module_text = (ROOT / "src" / "board" / "reset_bridge.spade").read_text(encoding="utf-8")
        test_top_text = (ROOT / "src" / "board" / "reset_bridge_test_top.spade").read_text(encoding="utf-8")
        board_top_text = (ROOT / "src" / "board" / "icebreaker_top.spade").read_text(encoding="utf-8")
        test_text = (ROOT / "test" / "unit" / "test_reset_bridge.py").read_text(encoding="utf-8")
        hook_text = (TOOLS / "run_precommit_checks.sh").read_text(encoding="utf-8")

        self.assertIn("pub mod reset_bridge;", board_main)
        self.assertIn("pub mod reset_bridge_test_top;", board_main)
        self.assertIn("pub struct ResetBridgeOut", module_text)
        self.assertIn("stable_ticks_required", module_text)
        self.assertIn("transition_ready", module_text)
        self.assertIn("initial(false)", module_text)
        self.assertIn("inst reset_bridge(CLK, BTN_N, 48000u16, 16u16).rst", board_top_text)
        self.assertIn("reset_bridge(", test_top_text)
        self.assertIn("# top = board::reset_bridge_test_top::reset_bridge_test_top", test_text)
        self.assertIn("RANDOM_SEQUENCE_COUNT = 1_000", test_text)
        self.assertIn('"test/unit/test_reset_bridge.py"', hook_text)
