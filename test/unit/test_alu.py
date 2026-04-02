# top = cpu::alu_test_top::arithmetic_alu_test_top
from __future__ import annotations

import sys
from pathlib import Path

import cocotb
from cocotb.triggers import Timer


def find_repo_root() -> Path:
    candidates = [Path(__file__).resolve(), Path.cwd().resolve()]
    for candidate in candidates:
        for path in (candidate, *candidate.parents):
            if (path / "swim.toml").exists() and (path / "spec" / "flag_policies.py").exists():
                return path
    raise RuntimeError("Unable to locate iceboy repo root for spec imports")


ROOT = find_repo_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spec.flag_policies import add16_hl, adc8, add8, add_sp_e8, and8, cp8, dec8, inc8, ld_hl_sp_plus_e8, or8, sbc8, sub8, xor8


OP_ADD = 0
OP_ADC = 1
OP_SUB = 2
OP_SBC = 3
OP_CP = 4
OP_AND = 5
OP_OR = 6
OP_XOR = 7
OP_INC = 8
OP_DEC = 9
OP_ADD16 = 10
OP_ADD_SP_E8 = 11
VALUES = (0x00, 0x01, 0x0F, 0x10, 0x7F, 0x80, 0xFE, 0xFF)
VALUES16 = (0x0000, 0x0001, 0x0FFF, 0x1000, 0x7FFF, 0x8000, 0xFFFE, 0xFFFF)
OFFSETS8 = (0x00, 0x01, 0x08, 0x0F, 0x10, 0x7F, 0x80, 0xF8, 0xFF)


def decode_output(output_value: int) -> dict[str, int | bool]:
    return {
        "val16": (output_value >> 12) & 0xFFFF,
        "val8": (output_value >> 4) & 0xFF,
        "z": bool((output_value >> 3) & 0x1),
        "n": bool((output_value >> 2) & 0x1),
        "h": bool((output_value >> 1) & 0x1),
        "c": bool(output_value & 0x1),
    }


async def sample(dut, *, op: int, a: int, b: int, carry_in: bool, z_in: bool = False) -> dict[str, int | bool]:
    dut.op_i.value = op & 0x1F
    dut.a_i.value = a & 0xFFFF
    dut.b_i.value = b & 0xFFFF
    dut.carry_in_i.value = int(carry_in)
    dut.z_in_i.value = int(z_in)
    await Timer(1, units="ns")
    return decode_output(int(dut.output__.value))


def assert_matches(snapshot: dict[str, int | bool], expected) -> None:
    assert snapshot == {
        "val16": expected.value & 0xFFFF,
        "val8": expected.value & 0xFF,
        "z": expected.flags.z,
        "n": expected.flags.n,
        "h": expected.flags.h,
        "c": expected.flags.c,
    }, (snapshot, expected)


@cocotb.test()
async def test_curated_arithmetic_flag_edges(dut):
    cases = [
        (OP_ADD, 0x0F, 0x01, False, add8(0x0F, 0x01)),
        (OP_ADD, 0xFF, 0x01, False, add8(0xFF, 0x01)),
        (OP_ADC, 0x0F, 0x00, True, adc8(0x0F, 0x00, True)),
        (OP_ADC, 0xFF, 0x00, True, adc8(0xFF, 0x00, True)),
        (OP_SUB, 0x10, 0x01, False, sub8(0x10, 0x01)),
        (OP_SUB, 0x00, 0x01, False, sub8(0x00, 0x01)),
        (OP_SBC, 0x10, 0x00, True, sbc8(0x10, 0x00, True)),
        (OP_SBC, 0x00, 0x00, True, sbc8(0x00, 0x00, True)),
        (OP_CP, 0x00, 0x01, False, cp8(0x00, 0x01)),
        (OP_CP, 0x40, 0x40, False, cp8(0x40, 0x40)),
        (OP_AND, 0xF0, 0x0F, False, and8(0xF0, 0x0F)),
        (OP_AND, 0xFF, 0x00, False, and8(0xFF, 0x00)),
        (OP_OR, 0x80, 0x01, False, or8(0x80, 0x01)),
        (OP_OR, 0x00, 0x00, False, or8(0x00, 0x00)),
        (OP_XOR, 0xFF, 0x0F, False, xor8(0xFF, 0x0F)),
        (OP_XOR, 0xAA, 0xAA, False, xor8(0xAA, 0xAA)),
        (OP_INC, 0x0F, 0x00, False, inc8(0x0F, carry_in=False)),
        (OP_INC, 0xFF, 0x00, True, inc8(0xFF, carry_in=True)),
        (OP_DEC, 0x10, 0x00, False, dec8(0x10, carry_in=False)),
        (OP_DEC, 0x00, 0x00, True, dec8(0x00, carry_in=True)),
        (OP_ADD16, 0x0FFF, 0x0001, True, add16_hl(0x0FFF, 0x0001, z_in=True)),
        (OP_ADD16, 0xFFFF, 0x0001, False, add16_hl(0xFFFF, 0x0001, z_in=False)),
        (OP_ADD_SP_E8, 0x0008, 0x00F8, False, add_sp_e8(0x0008, 0xF8)),
        (OP_ADD_SP_E8, 0x00FF, 0x0001, False, add_sp_e8(0x00FF, 0x01)),
    ]

    for op, a, b, carry_in, expected in cases:
        snapshot = await sample(
            dut,
            op=op,
            a=a,
            b=b,
            carry_in=carry_in,
            z_in=expected.flags.z if op == OP_ADD16 else False,
        )
        assert_matches(snapshot, expected)


@cocotb.test()
async def test_generated_arithmetic_vectors_match_spec_flag_policies(dut):
    for a in VALUES:
        for b in VALUES:
            assert_matches(await sample(dut, op=OP_ADD, a=a, b=b, carry_in=False), add8(a, b))
            assert_matches(await sample(dut, op=OP_SUB, a=a, b=b, carry_in=False), sub8(a, b))
            assert_matches(await sample(dut, op=OP_CP, a=a, b=b, carry_in=False), cp8(a, b))
            assert_matches(await sample(dut, op=OP_AND, a=a, b=b, carry_in=False), and8(a, b))
            assert_matches(await sample(dut, op=OP_OR, a=a, b=b, carry_in=False), or8(a, b))
            assert_matches(await sample(dut, op=OP_XOR, a=a, b=b, carry_in=False), xor8(a, b))
            for carry_in in (False, True):
                assert_matches(await sample(dut, op=OP_ADC, a=a, b=b, carry_in=carry_in), adc8(a, b, carry_in))
                assert_matches(await sample(dut, op=OP_SBC, a=a, b=b, carry_in=carry_in), sbc8(a, b, carry_in))
                assert_matches(await sample(dut, op=OP_INC, a=a, b=0x00, carry_in=carry_in), inc8(a, carry_in))
                assert_matches(await sample(dut, op=OP_DEC, a=a, b=0x00, carry_in=carry_in), dec8(a, carry_in))
    for a in VALUES16:
        for b in VALUES16:
            for z_in in (False, True):
                assert_matches(await sample(dut, op=OP_ADD16, a=a, b=b, carry_in=False, z_in=z_in), add16_hl(a, b, z_in))
        for off in OFFSETS8:
            expected = add_sp_e8(a, off)
            assert_matches(await sample(dut, op=OP_ADD_SP_E8, a=a, b=off, carry_in=False), expected)
            assert expected == ld_hl_sp_plus_e8(a, off)
