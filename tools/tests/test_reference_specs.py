from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from spec.compare_scopes import (
    COMPARISON_FIELDS_BY_ORACLE_MODE,
    DEFAULT_COMMIT_KIND_BY_ORACLE_MODE,
    CommitKind,
    CompareField,
    OracleMode,
    comparison_fields_for_commit_kind,
)
from spec.flag_policies import (
    Flags,
    add16_hl,
    add8,
    add_sp_e8,
    adc8,
    bit_test,
    ccf,
    daa,
    dec8,
    inc8,
    ld_hl_sp_plus_e8,
    rl8,
    rlc8,
    sbc8,
    scf,
    sub8,
    swap8,
)


ROOT = Path(__file__).resolve().parents[2]
ROM_SCHEMA_PATH = ROOT / "bench" / "manifests" / "rom_schema.yaml"


class FlagPoliciesTest(unittest.TestCase):
    def test_add_and_adc_formulas_match_expected_flags(self) -> None:
        add = add8(0x0F, 0x01)
        self.assertEqual(add.value, 0x10)
        self.assertEqual(add.flags, Flags(z=False, n=False, h=True, c=False))

        adc = adc8(0xFF, 0x00, True)
        self.assertEqual(adc.value, 0x00)
        self.assertEqual(adc.flags, Flags(z=True, n=False, h=True, c=True))

    def test_sub_sbc_inc_dec_preserve_and_borrow_correctly(self) -> None:
        sub = sub8(0x10, 0x01)
        self.assertEqual(sub.value, 0x0F)
        self.assertEqual(sub.flags, Flags(z=False, n=True, h=True, c=False))

        sbc = sbc8(0x00, 0x00, True)
        self.assertEqual(sbc.value, 0xFF)
        self.assertEqual(sbc.flags, Flags(z=False, n=True, h=True, c=True))

        inc = inc8(0xFF, carry_in=True)
        self.assertEqual(inc.value, 0x00)
        self.assertEqual(inc.flags, Flags(z=True, n=False, h=True, c=True))

        dec = dec8(0x00, carry_in=True)
        self.assertEqual(dec.value, 0xFF)
        self.assertEqual(dec.flags, Flags(z=False, n=True, h=True, c=True))

    def test_daa_matches_rgbds_reference_cases(self) -> None:
        add_adjust = daa(0x0A, Flags(z=False, n=False, h=False, c=False))
        self.assertEqual(add_adjust.value, 0x10)
        self.assertEqual(add_adjust.flags, Flags(z=False, n=False, h=False, c=False))

        carry_adjust = daa(0x9A, Flags(z=False, n=False, h=False, c=False))
        self.assertEqual(carry_adjust.value, 0x00)
        self.assertEqual(carry_adjust.flags, Flags(z=True, n=False, h=False, c=True))

        sub_adjust = daa(0x0F, Flags(z=False, n=True, h=True, c=False))
        self.assertEqual(sub_adjust.value, 0x09)
        self.assertEqual(sub_adjust.flags, Flags(z=False, n=True, h=False, c=False))

    def test_16bit_and_signed_offset_rules_match_sm83_behavior(self) -> None:
        add_hl = add16_hl(0x0FFF, 0x0001, z_in=True)
        self.assertEqual(add_hl.value, 0x1000)
        self.assertEqual(add_hl.flags, Flags(z=True, n=False, h=True, c=False))

        add_sp = add_sp_e8(0x0008, 0xF8)
        self.assertEqual(add_sp.value, 0x0000)
        self.assertEqual(add_sp.flags, Flags(z=False, n=False, h=True, c=True))

        self.assertEqual(ld_hl_sp_plus_e8(0x0008, 0xF8), add_sp)

    def test_rotate_bit_swap_and_carry_control_rules(self) -> None:
        cb_rotate = rlc8(0x80)
        self.assertEqual(cb_rotate.value, 0x01)
        self.assertEqual(cb_rotate.flags, Flags(z=False, n=False, h=False, c=True))

        unprefixed_rotate = rl8(0x80, False, zero_affects=False)
        self.assertEqual(unprefixed_rotate.value, 0x00)
        self.assertEqual(unprefixed_rotate.flags, Flags(z=False, n=False, h=False, c=True))

        bit = bit_test(0x00, 3, carry_in=True)
        self.assertEqual(bit.flags, Flags(z=True, n=False, h=True, c=True))

        swapped = swap8(0xF0)
        self.assertEqual(swapped.value, 0x0F)
        self.assertEqual(swapped.flags, Flags(z=False, n=False, h=False, c=False))

        self.assertEqual(scf(z_in=True), Flags(z=True, n=False, h=False, c=True))
        self.assertEqual(ccf(z_in=False, carry_in=True), Flags(z=False, n=False, h=False, c=False))


class CompareScopesTest(unittest.TestCase):
    def test_oracle_mode_values_match_manifest_schema(self) -> None:
        schema = yaml.safe_load(ROM_SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            {mode.value for mode in OracleMode},
            set(schema["allowed_values"]["oracle_mode"]),
        )

    def test_commit_and_mode_field_sets_are_structured(self) -> None:
        instr_fields = COMPARISON_FIELDS_BY_ORACLE_MODE[OracleMode.InstrCommit]
        mcycle_fields = COMPARISON_FIELDS_BY_ORACLE_MODE[OracleMode.MCycleCommit]
        checkpoint_fields = COMPARISON_FIELDS_BY_ORACLE_MODE[OracleMode.Checkpoint]

        self.assertIn(CompareField.Registers, instr_fields)
        self.assertIn(CompareField.Flags, instr_fields)
        self.assertNotIn(CompareField.BusRequest, instr_fields)

        self.assertTrue(instr_fields < mcycle_fields)
        self.assertIn(CompareField.BusRequest, mcycle_fields)
        self.assertIn(CompareField.BusResponse, mcycle_fields)
        self.assertIn(CompareField.CheckpointTag, checkpoint_fields)
        self.assertIn(CompareField.WramSignature, checkpoint_fields)

    def test_default_commit_kind_mapping_is_consistent(self) -> None:
        self.assertIsNone(DEFAULT_COMMIT_KIND_BY_ORACLE_MODE[OracleMode.Unit])
        self.assertEqual(DEFAULT_COMMIT_KIND_BY_ORACLE_MODE[OracleMode.InstrCommit], CommitKind.InstrCommit)
        self.assertEqual(DEFAULT_COMMIT_KIND_BY_ORACLE_MODE[OracleMode.MCycleCommit], CommitKind.MCycle)
        self.assertEqual(
            comparison_fields_for_commit_kind(CommitKind.InterruptAck),
            {
                CompareField.Registers,
                CompareField.Flags,
                CompareField.ProgramCounter,
                CompareField.StackPointer,
                CompareField.ImeState,
                CompareField.HaltState,
                CompareField.IoTouch,
            },
        )


if __name__ == "__main__":
    unittest.main()
