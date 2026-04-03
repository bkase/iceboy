from __future__ import annotations

import unittest
from pathlib import Path

from tools.sm83_decode_reference import extract_generated_table, render_unprefixed_decode_cases


ROOT = Path(__file__).resolve().parents[2]
CPU_MAIN_PATH = ROOT / "src" / "cpu" / "main.spade"
CPU_DECODE_PATH = ROOT / "src" / "cpu" / "decode.spade"
CPU_DECODE_TEST_TOP_PATH = ROOT / "src" / "cpu" / "decode_test_top.spade"


class CpuDecodeModuleTest(unittest.TestCase):
    def test_cpu_module_exports_decode_surfaces(self) -> None:
        text = CPU_MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn("pub mod decode;", text)
        self.assertIn("pub mod decode_test_top;", text)

    def test_decode_table_matches_metadata_render(self) -> None:
        text = CPU_DECODE_PATH.read_text(encoding="utf-8")
        self.assertEqual(extract_generated_table(text), render_unprefixed_decode_cases().strip())

    def test_decode_test_top_invokes_decoder_projection(self) -> None:
        text = CPU_DECODE_TEST_TOP_PATH.read_text(encoding="utf-8")
        self.assertIn("use lib::cpu::decode::{decode, decode_cb};", text)
        self.assertIn("pub entity decode_test_top(opcode: uint<8>) -> uint<82>", text)
        self.assertIn("pub entity decode_cb_test_top(opcode: uint<8>) -> uint<82>", text)

    def test_decode_module_exposes_cb_decoder(self) -> None:
        text = CPU_DECODE_PATH.read_text(encoding="utf-8")
        self.assertIn("pub fn decode_cb(opcode: uint<8>) -> DecodedOp", text)


if __name__ == "__main__":
    unittest.main()
