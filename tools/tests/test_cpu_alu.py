from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CPU_MAIN_PATH = ROOT / "src" / "cpu" / "main.spade"
CPU_ALU_PATH = ROOT / "src" / "cpu" / "alu.spade"
CPU_TYPES_PATH = ROOT / "src" / "cpu" / "types.spade"


class CpuAluContractTest(unittest.TestCase):
    def test_cpu_module_exports_alu_submodule(self) -> None:
        text = CPU_MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn("pub mod alu;", text)

    def test_alu_contract_and_stub_exist_in_alu_module(self) -> None:
        text = CPU_ALU_PATH.read_text(encoding="utf-8")
        for symbol in [
            "enum AluKind",
            "enum RotShiftKind",
            "enum BitResSetKind",
            "struct AluResult",
            "val8: uint<8>",
            "val16: uint<16>",
            "flags: Flags",
            "enum AluReq",
            "Idle",
            "Add8 { a: uint<8>, b: uint<8>, carry_in: bool }",
            "Sub8 { a: uint<8>, b: uint<8>, carry_in: bool }",
            "And8 { a: uint<8>, b: uint<8> }",
            "Or8 { a: uint<8>, b: uint<8> }",
            "Xor8 { a: uint<8>, b: uint<8> }",
            "Cp8 { a: uint<8>, b: uint<8> }",
            "Inc8 { x: uint<8>, f_prev: Flags }",
            "Dec8 { x: uint<8>, f_prev: Flags }",
            "Add16 { a: uint<16>, b: uint<16>, z_preserve: bool }",
            "AddSpE8 { sp: uint<16>, off: uint<8> }",
            "Daa { a: uint<8>, f_prev: Flags }",
            "Cpl { a: uint<8>, f_prev: Flags }",
            "Scf { f_prev: Flags }",
            "Ccf { f_prev: Flags }",
            "RotShift { kind: RotShiftKind, x: uint<8>, f_prev: Flags, zero_on_result: bool }",
            "BitResSet { kind: BitResSetKind, bit_index: uint<3>, x: uint<8>, f_prev: Flags }",
            "pub fn idle_alu_result() -> AluResult",
            "pub fn alu(req: AluReq) -> AluResult",
            "_ => idle_alu_result()",
        ]:
            self.assertIn(symbol, text)

    def test_cpu_types_import_alu_kind_from_alu_module(self) -> None:
        text = CPU_TYPES_PATH.read_text(encoding="utf-8")
        self.assertIn("use lib::cpu::alu::AluKind;", text)
        self.assertNotIn("pub enum AluKind", text)


if __name__ == "__main__":
    unittest.main()
