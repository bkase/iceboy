from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CPU_MAIN_PATH = ROOT / "src" / "cpu" / "main.spade"
CPU_DECODE_TYPES_PATH = ROOT / "src" / "cpu" / "decode_types.spade"
CPU_TYPES_PATH = ROOT / "src" / "cpu" / "types.spade"


class CpuDecodeTypesContractTest(unittest.TestCase):
    def test_cpu_module_exports_decode_types_submodule(self) -> None:
        text = CPU_MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn("pub mod decode_types;", text)

    def test_decode_contract_covers_instruction_families_and_operands(self) -> None:
        text = CPU_DECODE_TYPES_PATH.read_text(encoding="utf-8")
        for symbol in [
            "enum PrefixKind",
            "enum ConditionCode",
            "Nz",
            "Z",
            "Nc",
            "C",
            "enum Operand8",
            "Register { r8: R8 }",
            "Imm8",
            "AddrHl",
            "AddrBc",
            "AddrDe",
            "AddrHli",
            "AddrHld",
            "AddrImm16",
            "IoImm8",
            "IoC",
            "enum Operand16",
            "RegisterPair { pair: RegPair }",
            "Imm16",
            "SpPlusE8",
            "enum AddressingMode",
            "Relative8",
            "MemoryViaRegPair { pair: RegPair }",
            "MemoryViaHl",
            "MemoryViaHlIncrement",
            "MemoryViaHlDecrement",
            "Stack",
            "Prefixed { prefix: PrefixKind }",
            "SpPlusE8",
            "enum DecodedOpClass",
            "WordAlu",
            "enum ControlTarget",
            "Return { enable_interrupts: bool }",
            "enum MiscKind",
            "enum BitOpKind",
            "RotateShift { kind: RotShiftKind }",
            "enum WordAluKind",
            "enum StackOpKind",
            "enum DecodedOp",
            "Load {",
            "Alu {",
            "WordAlu {",
            "ControlFlow {",
            "BitOp {",
            "zero_on_result: bool",
            "Stack {",
            "Misc {",
            "InterruptControl {",
            "pub fn decoded_op_class(op: DecodedOp) -> DecodedOpClass",
            "pub fn invalid_decoded_op() -> DecodedOp",
        ]:
            self.assertIn(symbol, text)

    def test_cpu_types_import_decoded_op_from_decode_types_module(self) -> None:
        text = CPU_TYPES_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "use lib::cpu::decode_types::{DecodedOp, PrefixKind, invalid_decoded_op};",
            text,
        )
        self.assertNotIn("pub enum DecodedOp", text)
        self.assertNotIn("pub enum PrefixKind", text)


if __name__ == "__main__":
    unittest.main()
