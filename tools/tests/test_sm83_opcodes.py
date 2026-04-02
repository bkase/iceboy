from __future__ import annotations

import unittest

from spec.sm83_opcodes import (
    ALL_OPCODES,
    CB_PREFIXED_BY_OPCODE,
    CB_PREFIXED_OPCODES,
    CompareScope,
    FlagEffect,
    PrefixClass,
    UNPREFIXED_BY_OPCODE,
    UNPREFIXED_OPCODES,
    AddressingForm,
)


class Sm83OpcodeMetadataTest(unittest.TestCase):
    def test_opcode_tables_are_complete(self) -> None:
        self.assertEqual(len(UNPREFIXED_OPCODES), 0x100)
        self.assertEqual(len(CB_PREFIXED_OPCODES), 0x100)
        self.assertEqual(len(ALL_OPCODES), 0x200)
        self.assertEqual(set(UNPREFIXED_BY_OPCODE), set(range(0x100)))
        self.assertEqual(set(CB_PREFIXED_BY_OPCODE), set(range(0x100)))

    def test_conditional_cycles_are_not_taken_then_taken(self) -> None:
        self.assertEqual(UNPREFIXED_BY_OPCODE[0x20].mnemonic, "JR NZ, e8")
        self.assertEqual(UNPREFIXED_BY_OPCODE[0x20].cycles_tstates, (8, 12))
        self.assertEqual(UNPREFIXED_BY_OPCODE[0xC2].mnemonic, "JP NZ, a16")
        self.assertEqual(UNPREFIXED_BY_OPCODE[0xC2].cycles_tstates, (12, 16))
        self.assertEqual(UNPREFIXED_BY_OPCODE[0xC4].mnemonic, "CALL NZ, a16")
        self.assertEqual(UNPREFIXED_BY_OPCODE[0xC4].cycles_tstates, (12, 24))

    def test_edge_case_mnemonics_are_normalized(self) -> None:
        self.assertEqual(UNPREFIXED_BY_OPCODE[0x22].mnemonic, "LD [HL+], A")
        self.assertEqual(UNPREFIXED_BY_OPCODE[0x2A].mnemonic, "LD A, [HL+]")
        self.assertEqual(UNPREFIXED_BY_OPCODE[0xF8].mnemonic, "LD HL, SP + e8")
        self.assertEqual(CB_PREFIXED_BY_OPCODE[0x46].mnemonic, "BIT 0, [HL]")

    def test_illegal_opcode_slots_are_preserved(self) -> None:
        illegal = UNPREFIXED_BY_OPCODE[0xD3]
        self.assertTrue(illegal.is_illegal)
        self.assertEqual(illegal.mnemonic, "ILLEGAL_D3")
        self.assertEqual(illegal.default_compare_scope, CompareScope.INVALID_OPCODE)
        self.assertEqual(illegal.prefix, PrefixClass.NONE)

    def test_addressing_forms_and_flag_policies_are_explicit(self) -> None:
        ldh_store = UNPREFIXED_BY_OPCODE[0xE0]
        self.assertEqual(ldh_store.operands[0].addressing_form, AddressingForm.ABSOLUTE_INDIRECT)
        self.assertEqual(ldh_store.operands[0].role, "destination")

        ld_hl_sp_plus_e8 = UNPREFIXED_BY_OPCODE[0xF8]
        self.assertEqual(ld_hl_sp_plus_e8.operands[1].addressing_form, AddressingForm.SP_PLUS_RELATIVE8)
        self.assertEqual(ld_hl_sp_plus_e8.flag_policy["Z"], FlagEffect.RESET)
        self.assertEqual(ld_hl_sp_plus_e8.flag_policy["H"], FlagEffect.AFFECTED)

        cb_bit = CB_PREFIXED_BY_OPCODE[0x46]
        self.assertEqual(cb_bit.operands[0].addressing_form, AddressingForm.BIT_INDEX)
        self.assertEqual(cb_bit.operands[1].addressing_form, AddressingForm.REGISTER_INDIRECT)
        self.assertEqual(cb_bit.default_compare_scope, CompareScope.BITOPS)


if __name__ == "__main__":
    unittest.main()
