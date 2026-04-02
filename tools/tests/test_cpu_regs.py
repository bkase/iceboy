from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CPU_MAIN_PATH = ROOT / "src" / "cpu" / "main.spade"
CPU_REGS_PATH = ROOT / "src" / "cpu" / "regs.spade"


class CpuRegsContractTest(unittest.TestCase):
    def test_cpu_module_exports_regs_submodule(self) -> None:
        text = CPU_MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn("pub mod regs;", text)

    def test_register_file_contract_and_helpers_live_in_regs_module(self) -> None:
        text = CPU_REGS_PATH.read_text(encoding="utf-8")

        for symbol in [
            "enum R8",
            "A",
            "B",
            "C",
            "D",
            "E",
            "H",
            "L",
            "enum RegPair",
            "BC",
            "DE",
            "HL",
            "SP",
            "AF",
            "struct Registers",
            "struct Flags",
            "pub fn zero_registers() -> Registers",
            "pub fn get_r8(regs: Registers, sel: R8) -> uint<8>",
            "pub fn set_r8(regs: Registers, sel: R8, val: uint<8>) -> Registers",
            "pub fn get_r16(regs: Registers, pair: RegPair) -> uint<16>",
            "pub fn set_r16(regs: Registers, pair: RegPair, val: uint<16>) -> Registers",
            "pub fn flags_from_f(f: uint<8>) -> Flags",
            "pub fn pack_flags(flags: Flags) -> uint<8>",
            "pub fn mask_f(f: uint<8>) -> uint<8>",
            "mask_f(lo_byte(val))",
        ]:
            self.assertIn(symbol, text)


if __name__ == "__main__":
    unittest.main()
