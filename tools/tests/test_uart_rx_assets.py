from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


class UartRxAssetsTest(unittest.TestCase):
    def test_uart_rx_assets_hook_membership_and_board_pins_exist(self) -> None:
        main_text = (ROOT / "src" / "periph" / "main.spade").read_text(encoding="utf-8")
        module_text = (ROOT / "src" / "periph" / "uart_rx.spade").read_text(encoding="utf-8")
        test_top_text = (ROOT / "src" / "periph" / "uart_rx_test_top.spade").read_text(encoding="utf-8")
        synth_top_text = (ROOT / "src" / "periph" / "uart_rx_synth_top.spade").read_text(encoding="utf-8")
        test_text = (ROOT / "test" / "unit" / "test_uart_rx.py").read_text(encoding="utf-8")
        hook_text = (TOOLS / "run_precommit_checks.sh").read_text(encoding="utf-8")
        script_text = (TOOLS / "run_uart_rx_synth_smoke.sh").read_text(encoding="utf-8")
        pcf_text = (ROOT / "icebreaker.pcf").read_text(encoding="utf-8")

        self.assertIn("pub mod uart_rx;", main_text)
        self.assertIn("pub mod uart_rx_synth_top;", main_text)
        self.assertIn("pub mod uart_rx_test_top;", main_text)
        self.assertIn("pub struct UartRxOut", module_text)
        self.assertIn("2-flop synchronizer", module_text)
        self.assertIn("sampled_byte", module_text)
        self.assertIn("entity uart_rx_test_top(", test_top_text)
        self.assertIn("#[no_mangle(all)]", synth_top_text)
        self.assertIn("uart_rx(clk, rst_i, rx_i, 104u16, 52u16)", synth_top_text)
        self.assertIn("# top = periph::uart_rx_test_top::uart_rx_test_top", test_text)
        self.assertIn('"test/unit/test_uart_rx.py"', hook_text)
        self.assertIn("periph::uart_rx_synth_top::uart_rx_synth_top", script_text)
        self.assertIn("SB_LUT4", script_text)
        self.assertIn("SB_DFF", script_text)
        self.assertIn("set_io -nowarn RX          6", pcf_text)
        self.assertIn("set_io -nowarn TX          9", pcf_text)

        for board_top in (
            ROOT / "src" / "board" / "icebreaker_top.spade",
            ROOT / "src" / "board" / "icebreaker_lcd_test_top.spade",
            ROOT / "src" / "board" / "icebreaker_alu_loop_top.spade",
        ):
            board_text = board_top.read_text(encoding="utf-8")
            self.assertIn("RX: bool", board_text)
            self.assertIn("TX: inv bool", board_text)
            self.assertIn("set TX = true;", board_text)
