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

from spec.flag_policies import Flags, add16_hl, adc8, add8, add_sp_e8, and8, ccf, cp8, cpl, daa, dec8, inc8, ld_hl_sp_plus_e8, or8, rl8, rlc8, rr8, rrc8, sbc8, scf, sla8, sra8, srl8, sub8, swap8, xor8


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
OP_DAA = 12
OP_CPL = 13
OP_SCF = 14
OP_CCF = 15
OP_RLCA = 16
OP_RRCA = 17
OP_RLA = 18
OP_RRA = 19
OP_RLC = 20
OP_RRC = 21
OP_RL = 22
OP_RR = 23
OP_SLA = 24
OP_SRA = 25
OP_SRL = 26
OP_SWAP = 27
OP_BIT = 28
OP_RES = 29
OP_SET = 30
VALUES = (0x00, 0x01, 0x0F, 0x10, 0x7F, 0x80, 0xFE, 0xFF)
VALUES16 = (0x0000, 0x0001, 0x0FFF, 0x1000, 0x7FFF, 0x8000, 0xFFFE, 0xFFFF)
OFFSETS8 = (0x00, 0x01, 0x08, 0x0F, 0x10, 0x7F, 0x80, 0xF8, 0xFF)
BIT_INDICES = tuple(range(8))
FLAG_COMBOS = tuple(Flags(z=z, n=n, h=h, c=c) for z in (False, True) for n in (False, True) for h in (False, True) for c in (False, True))


def decode_output(output_value: int) -> dict[str, int | bool]:
    return {
        "val16": (output_value >> 12) & 0xFFFF,
        "val8": (output_value >> 4) & 0xFF,
        "z": bool((output_value >> 3) & 0x1),
        "n": bool((output_value >> 2) & 0x1),
        "h": bool((output_value >> 1) & 0x1),
        "c": bool(output_value & 0x1),
    }


async def sample(
    dut,
    *,
    op: int,
    a: int,
    b: int,
    z_in: bool = False,
    n_in: bool = False,
    h_in: bool = False,
    c_in: bool = False,
) -> dict[str, int | bool]:
    dut.op_i.value = op & 0x1F
    dut.a_i.value = a & 0xFFFF
    dut.b_i.value = b & 0xFFFF
    dut.z_in_i.value = int(z_in)
    dut.n_in_i.value = int(n_in)
    dut.h_in_i.value = int(h_in)
    dut.c_in_i.value = int(c_in)
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


def assert_flag_only(snapshot: dict[str, int | bool], *, value: int, flags: Flags) -> None:
    assert snapshot == {
        "val16": value & 0xFFFF,
        "val8": value & 0xFF,
        "z": flags.z,
        "n": flags.n,
        "h": flags.h,
        "c": flags.c,
    }, (snapshot, value, flags)


def assert_val_flags(snapshot: dict[str, int | bool], *, value: int, flags: Flags) -> None:
    assert snapshot == {
        "val16": value & 0xFFFF,
        "val8": value & 0xFF,
        "z": flags.z,
        "n": flags.n,
        "h": flags.h,
        "c": flags.c,
    }, (snapshot, value, flags)


def assert_idle(snapshot: dict[str, int | bool]) -> None:
    assert snapshot == {
        "val16": 0,
        "val8": 0,
        "z": False,
        "n": False,
        "h": False,
        "c": False,
    }, snapshot


def bit_result(value: int, bit_index: int, carry_in: bool) -> tuple[int, Flags]:
    bit_set = ((value >> bit_index) & 0x1) == 1
    return value & 0xFF, Flags(z=not bit_set, n=False, h=True, c=carry_in)


def res_result(value: int, bit_index: int, flags: Flags) -> tuple[int, Flags]:
    return ((value & ~(1 << bit_index)) & 0xFF, flags)


def set_result(value: int, bit_index: int, flags: Flags) -> tuple[int, Flags]:
    return ((value | (1 << bit_index)) & 0xFF, flags)


@cocotb.test()
async def test_curated_arithmetic_flag_edges(dut):
    cases = [
        (OP_ADD, 0x0F, 0x01, {}, add8(0x0F, 0x01)),
        (OP_ADD, 0xFF, 0x01, {}, add8(0xFF, 0x01)),
        (OP_ADC, 0x0F, 0x00, {"c_in": True}, adc8(0x0F, 0x00, True)),
        (OP_ADC, 0xFF, 0x00, {"c_in": True}, adc8(0xFF, 0x00, True)),
        (OP_SUB, 0x10, 0x01, {}, sub8(0x10, 0x01)),
        (OP_SUB, 0x00, 0x01, {}, sub8(0x00, 0x01)),
        (OP_SBC, 0x10, 0x00, {"c_in": True}, sbc8(0x10, 0x00, True)),
        (OP_SBC, 0x00, 0x00, {"c_in": True}, sbc8(0x00, 0x00, True)),
        (OP_CP, 0x00, 0x01, {}, cp8(0x00, 0x01)),
        (OP_CP, 0x40, 0x40, {}, cp8(0x40, 0x40)),
        (OP_AND, 0xF0, 0x0F, {}, and8(0xF0, 0x0F)),
        (OP_AND, 0xFF, 0x00, {}, and8(0xFF, 0x00)),
        (OP_OR, 0x80, 0x01, {}, or8(0x80, 0x01)),
        (OP_OR, 0x00, 0x00, {}, or8(0x00, 0x00)),
        (OP_XOR, 0xFF, 0x0F, {}, xor8(0xFF, 0x0F)),
        (OP_XOR, 0xAA, 0xAA, {}, xor8(0xAA, 0xAA)),
        (OP_INC, 0x0F, 0x00, {"c_in": False}, inc8(0x0F, carry_in=False)),
        (OP_INC, 0xFF, 0x00, {"c_in": True}, inc8(0xFF, carry_in=True)),
        (OP_DEC, 0x10, 0x00, {"c_in": False}, dec8(0x10, carry_in=False)),
        (OP_DEC, 0x00, 0x00, {"c_in": True}, dec8(0x00, carry_in=True)),
        (OP_ADD16, 0x0FFF, 0x0001, {"z_in": True}, add16_hl(0x0FFF, 0x0001, z_in=True)),
        (OP_ADD16, 0xFFFF, 0x0001, {"z_in": False}, add16_hl(0xFFFF, 0x0001, z_in=False)),
        (OP_ADD_SP_E8, 0x0008, 0x00F8, {}, add_sp_e8(0x0008, 0xF8)),
        (OP_ADD_SP_E8, 0x00FF, 0x0001, {}, add_sp_e8(0x00FF, 0x01)),
        (OP_DAA, 0x9A, 0x0000, {"n_in": False, "h_in": False, "c_in": False}, daa(0x9A, Flags(False, False, False, False))),
        (OP_DAA, 0x13, 0x0000, {"n_in": True, "h_in": True, "c_in": True}, daa(0x13, Flags(False, True, True, True))),
        (OP_CPL, 0x3C, 0x0000, {"z_in": True, "c_in": False}, cpl(0x3C, True, False)),
        (OP_RLCA, 0x80, 0x0000, {}, rlc8(0x80, zero_affects=False)),
        (OP_RRCA, 0x01, 0x0000, {}, rrc8(0x01, zero_affects=False)),
        (OP_RLA, 0x80, 0x0000, {"c_in": True}, rl8(0x80, True, zero_affects=False)),
        (OP_RRA, 0x01, 0x0000, {"c_in": True}, rr8(0x01, True, zero_affects=False)),
        (OP_RLC, 0x80, 0x0000, {}, rlc8(0x80)),
        (OP_RRC, 0x01, 0x0000, {}, rrc8(0x01)),
        (OP_RL, 0x80, 0x0000, {"c_in": True}, rl8(0x80, True)),
        (OP_RR, 0x01, 0x0000, {"c_in": True}, rr8(0x01, True)),
        (OP_SLA, 0x80, 0x0000, {}, sla8(0x80)),
        (OP_SRA, 0x81, 0x0000, {}, sra8(0x81)),
        (OP_SRL, 0x01, 0x0000, {}, srl8(0x01)),
        (OP_SWAP, 0xF0, 0x0000, {}, swap8(0xF0)),
    ]

    for op, a, b, flags_in, expected in cases:
        snapshot = await sample(dut, op=op, a=a, b=b, **flags_in)
        assert_matches(snapshot, expected)

    assert_flag_only(await sample(dut, op=OP_SCF, a=0, b=0, z_in=False, c_in=False), value=0, flags=scf(False))
    assert_flag_only(await sample(dut, op=OP_SCF, a=0, b=0, z_in=True, c_in=False), value=0, flags=scf(True))
    assert_flag_only(await sample(dut, op=OP_CCF, a=0, b=0, z_in=False, c_in=False), value=0, flags=ccf(False, False))
    assert_flag_only(await sample(dut, op=OP_CCF, a=0, b=0, z_in=True, c_in=True), value=0, flags=ccf(True, True))
    value, flags = bit_result(0x80, 7, True)
    assert_val_flags(await sample(dut, op=OP_BIT, a=0x80, b=7, c_in=True), value=value, flags=flags)
    value, flags = res_result(0xFF, 3, Flags(True, True, False, True))
    assert_val_flags(await sample(dut, op=OP_RES, a=0xFF, b=3, z_in=True, n_in=True, h_in=False, c_in=True), value=value, flags=flags)
    value, flags = set_result(0x00, 5, Flags(False, True, True, False))
    assert_val_flags(await sample(dut, op=OP_SET, a=0x00, b=5, z_in=False, n_in=True, h_in=True, c_in=False), value=value, flags=flags)


@cocotb.test()
async def test_generated_alu_vectors_match_spec_flag_policies(dut):
    for a in VALUES:
        for b in VALUES:
            assert_matches(await sample(dut, op=OP_ADD, a=a, b=b), add8(a, b))
            assert_matches(await sample(dut, op=OP_SUB, a=a, b=b), sub8(a, b))
            assert_matches(await sample(dut, op=OP_CP, a=a, b=b), cp8(a, b))
            assert_matches(await sample(dut, op=OP_AND, a=a, b=b), and8(a, b))
            assert_matches(await sample(dut, op=OP_OR, a=a, b=b), or8(a, b))
            assert_matches(await sample(dut, op=OP_XOR, a=a, b=b), xor8(a, b))
            assert_matches(await sample(dut, op=OP_RLCA, a=a, b=0), rlc8(a, zero_affects=False))
            assert_matches(await sample(dut, op=OP_RRCA, a=a, b=0), rrc8(a, zero_affects=False))
            assert_matches(await sample(dut, op=OP_RLC, a=a, b=0), rlc8(a))
            assert_matches(await sample(dut, op=OP_RRC, a=a, b=0), rrc8(a))
            assert_matches(await sample(dut, op=OP_SLA, a=a, b=0), sla8(a))
            assert_matches(await sample(dut, op=OP_SRA, a=a, b=0), sra8(a))
            assert_matches(await sample(dut, op=OP_SRL, a=a, b=0), srl8(a))
            assert_matches(await sample(dut, op=OP_SWAP, a=a, b=0), swap8(a))
            for bit_index in BIT_INDICES:
                value, flags = bit_result(a, bit_index, False)
                assert_val_flags(await sample(dut, op=OP_BIT, a=a, b=bit_index), value=value, flags=flags)
            for c_in in (False, True):
                assert_matches(await sample(dut, op=OP_ADC, a=a, b=b, c_in=c_in), adc8(a, b, c_in))
                assert_matches(await sample(dut, op=OP_SBC, a=a, b=b, c_in=c_in), sbc8(a, b, c_in))
                assert_matches(await sample(dut, op=OP_INC, a=a, b=0x00, c_in=c_in), inc8(a, c_in))
                assert_matches(await sample(dut, op=OP_DEC, a=a, b=0x00, c_in=c_in), dec8(a, c_in))
                assert_matches(await sample(dut, op=OP_RLA, a=a, b=0, c_in=c_in), rl8(a, c_in, zero_affects=False))
                assert_matches(await sample(dut, op=OP_RRA, a=a, b=0, c_in=c_in), rr8(a, c_in, zero_affects=False))
                assert_matches(await sample(dut, op=OP_RL, a=a, b=0, c_in=c_in), rl8(a, c_in))
                assert_matches(await sample(dut, op=OP_RR, a=a, b=0, c_in=c_in), rr8(a, c_in))
                for bit_index in BIT_INDICES:
                    value, flags = bit_result(a, bit_index, c_in)
                    assert_val_flags(await sample(dut, op=OP_BIT, a=a, b=bit_index, c_in=c_in), value=value, flags=flags)
        for flags in FLAG_COMBOS:
            for bit_index in BIT_INDICES:
                value, next_flags = res_result(a, bit_index, flags)
                assert_val_flags(
                    await sample(dut, op=OP_RES, a=a, b=bit_index, z_in=flags.z, n_in=flags.n, h_in=flags.h, c_in=flags.c),
                    value=value,
                    flags=next_flags,
                )
                value, next_flags = set_result(a, bit_index, flags)
                assert_val_flags(
                    await sample(dut, op=OP_SET, a=a, b=bit_index, z_in=flags.z, n_in=flags.n, h_in=flags.h, c_in=flags.c),
                    value=value,
                    flags=next_flags,
                )
    for a in VALUES16:
        for b in VALUES16:
            for z_in in (False, True):
                assert_matches(await sample(dut, op=OP_ADD16, a=a, b=b, z_in=z_in), add16_hl(a, b, z_in))
        for off in OFFSETS8:
            expected = add_sp_e8(a, off)
            assert_matches(await sample(dut, op=OP_ADD_SP_E8, a=a, b=off), expected)
            assert expected == ld_hl_sp_plus_e8(a, off)
    for a in range(256):
        for flags in FLAG_COMBOS:
            assert_matches(
                await sample(dut, op=OP_DAA, a=a, b=0, z_in=flags.z, n_in=flags.n, h_in=flags.h, c_in=flags.c),
                daa(a, flags),
            )
            assert_matches(
                await sample(dut, op=OP_CPL, a=a, b=0, z_in=flags.z, n_in=flags.n, h_in=flags.h, c_in=flags.c),
                cpl(a, flags.z, flags.c),
            )
    for flags in FLAG_COMBOS:
        assert_flag_only(
            await sample(dut, op=OP_SCF, a=0, b=0, z_in=flags.z, n_in=flags.n, h_in=flags.h, c_in=flags.c),
            value=0,
            flags=scf(flags.z),
        )
        assert_flag_only(
            await sample(dut, op=OP_CCF, a=0, b=0, z_in=flags.z, n_in=flags.n, h_in=flags.h, c_in=flags.c),
            value=0,
            flags=ccf(flags.z, flags.c),
        )


@cocotb.test()
async def test_idle_request_isolates_operands_and_holds_zero_output(dut):
    seeds = (
        (0x0000, 0x0000, Flags(False, False, False, False)),
        (0x00FF, 0x0001, Flags(True, False, True, False)),
        (0x1234, 0xABCD, Flags(False, True, False, True)),
        (0xFFFF, 0x00F8, Flags(True, True, True, True)),
    )

    for a, b, flags in seeds:
        snapshot = await sample(
            dut,
            op=31,
            a=a,
            b=b,
            z_in=flags.z,
            n_in=flags.n,
            h_in=flags.h,
            c_in=flags.c,
        )
        assert_idle(snapshot)
