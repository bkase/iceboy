from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


class IcebreakerUartRomTopAssetsTest(unittest.TestCase):
    def test_uart_rom_top_sources_and_runner_assets_exist(self) -> None:
        board_main = (ROOT / "src" / "board" / "main.spade").read_text(encoding="utf-8")
        top_text = (ROOT / "src" / "board" / "icebreaker_uart_rom_top.spade").read_text(encoding="utf-8")
        wrapper_text = (ROOT / "test" / "harness" / "verilog" / "icebreaker_uart_rom_top_verilator_wrapper.sv").read_text(encoding="utf-8")
        main_text = (TOOLS / "verilator" / "icebreaker_uart_rom_top_main.cpp").read_text(encoding="utf-8")
        runner_text = (TOOLS / "run_icebreaker_uart_rom_verilator.sh").read_text(encoding="utf-8")
        protocol_test = (ROOT / "test" / "unit" / "test_uart_rom_top_protocol.py").read_text(encoding="utf-8")

        self.assertIn("pub mod icebreaker_uart_rom_top;", board_main)
        self.assertIn("entity icebreaker_uart_rom_top(", top_text)
        self.assertIn("entity icebreaker_uart_rom_protocol_test_top(", top_text)
        self.assertIn("inst rom_uploader(", top_text)
        self.assertIn("inst hardware_soc_core_visible(", top_text)
        self.assertIn("inst rom_spram_rw(", top_text)
        self.assertIn("cpu_addr: core.rom_ports.cpu_addr", top_text)
        self.assertIn("loader_write_en: uploader.loader_write_en", top_text)
        self.assertIn("let core_rst = board_rst || uploader.hold_reset;", top_text)
        self.assertIn("reg(CLK) upload_t_index_reg: uint<2>", top_text)
        self.assertIn("uart_bit_ticks()", top_text)
        self.assertIn("uart_half_bit_ticks()", top_text)

        self.assertIn("module icebreaker_uart_rom_top_verilator_wrapper", wrapper_text)
        self.assertIn("icebreaker_uart_rom_top impl", wrapper_text)
        self.assertIn("input wire rx_i", wrapper_text)
        self.assertIn("output wire tx_o", wrapper_text)

        self.assertIn("--rom-path=", main_text)
        self.assertIn("send_upload_frame", main_text)
        self.assertIn("receive_uart_ack", main_text)
        self.assertIn("icebreaker_uart_rom_top mismatch first-diff=", main_text)
        self.assertIn("matched ", main_text)

        self.assertIn("bench/roms/out/bg_static.gb", runner_text)
        self.assertIn("bench/ref/BG_STATIC.py", runner_text)
        self.assertIn("icebreaker_uart_rom_top_verilator_wrapper", runner_text)
        self.assertIn("tools/verilator/icebreaker_uart_rom_top_main.cpp", runner_text)
        self.assertIn("--rom-prefix-len=", runner_text)
        self.assertIn("--captured-png=", runner_text)
        self.assertIn("--reference-png=", runner_text)
        self.assertIn("--diff-png=", runner_text)

        self.assertIn("# top = board::icebreaker_uart_rom_top::icebreaker_uart_rom_protocol_test_top", protocol_test)
        self.assertIn("test_happy_path_uploads_256_byte_payload_and_deasserts_reset", protocol_test)


if __name__ == "__main__":
    unittest.main()
