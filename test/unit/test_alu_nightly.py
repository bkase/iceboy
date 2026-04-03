# top = cpu::alu_test_top::arithmetic_alu_test_top
from __future__ import annotations

import os
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

from spec.flag_policies import Flags, adc8, add8, daa, sbc8, sub8


OP_ADD = 0
OP_ADC = 1
OP_SUB = 2
OP_SBC = 3
OP_DAA = 12
NIGHTLY_ENABLED = os.environ.get("ICEBOY_NIGHTLY") == "1"
LIMIT_ENV = os.environ.get("ICEBOY_NIGHTLY_LIMIT")
LIMIT = int(LIMIT_ENV) if LIMIT_ENV else None


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


def iter_u8_pairs(limit: int | None = None):
    count = 0
    for lhs in range(0x100):
        for rhs in range(0x100):
            yield lhs, rhs
            count += 1
            if limit is not None and count >= limit:
                return


def iter_daa_inputs(limit: int | None = None):
    count = 0
    for a in range(0x100):
        for n in (False, True):
            for h in (False, True):
                for c in (False, True):
                    yield a, Flags(z=False, n=n, h=h, c=c)
                    count += 1
                    if limit is not None and count >= limit:
                        return


@cocotb.test()
async def test_exhaustive_add_adc_sub_sbc_vectors(dut):
    if not NIGHTLY_ENABLED:
        return
    for lhs, rhs in iter_u8_pairs(limit=LIMIT):
        assert_matches(await sample(dut, op=OP_ADD, a=lhs, b=rhs), add8(lhs, rhs))
        assert_matches(await sample(dut, op=OP_SUB, a=lhs, b=rhs), sub8(lhs, rhs))
        for carry_in in (False, True):
            assert_matches(await sample(dut, op=OP_ADC, a=lhs, b=rhs, c_in=carry_in), adc8(lhs, rhs, carry_in))
            assert_matches(await sample(dut, op=OP_SBC, a=lhs, b=rhs, c_in=carry_in), sbc8(lhs, rhs, carry_in))


@cocotb.test()
async def test_exhaustive_daa_vectors(dut):
    if not NIGHTLY_ENABLED:
        return
    for a, flags in iter_daa_inputs(limit=LIMIT):
        assert_matches(
            await sample(dut, op=OP_DAA, a=a, b=0, z_in=flags.z, n_in=flags.n, h_in=flags.h, c_in=flags.c),
            daa(a, flags),
        )
