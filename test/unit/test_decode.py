# top = cpu::decode_test_top::decode_test_top
from __future__ import annotations

import sys
from pathlib import Path

import cocotb
from cocotb.triggers import Timer


def find_repo_root() -> Path:
    candidates = [Path(__file__).resolve(), Path.cwd().resolve()]
    for candidate in candidates:
        for path in (candidate, *candidate.parents):
            if (path / "swim.toml").exists() and (path / "tools" / "sm83_decode_reference.py").exists():
                return path
    raise RuntimeError("Unable to locate iceboy repo root for decode reference imports")


ROOT = find_repo_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.sm83_decode_reference import projection_for_unprefixed_opcode


def decode_output(output_value: int) -> dict[str, int]:
    return {
        "invalid": (output_value >> 81) & 0x1,
        "class_id": (output_value >> 77) & 0xF,
        "addressing": (output_value >> 72) & 0x1F,
        "condition": (output_value >> 69) & 0x7,
        "control_target": (output_value >> 66) & 0x7,
        "control_return_enable_interrupts": (output_value >> 65) & 0x1,
        "dst8_kind": (output_value >> 61) & 0xF,
        "dst8_reg": (output_value >> 58) & 0x7,
        "src8_kind": (output_value >> 54) & 0xF,
        "src8_reg": (output_value >> 51) & 0x7,
        "dst16_kind": (output_value >> 48) & 0x7,
        "dst16_reg": (output_value >> 45) & 0x7,
        "src16_kind": (output_value >> 42) & 0x7,
        "src16_reg": (output_value >> 39) & 0x7,
        "alu_kind": (output_value >> 35) & 0xF,
        "word_alu_kind": (output_value >> 32) & 0x7,
        "bit_kind": (output_value >> 29) & 0x7,
        "rot_shift_kind": (output_value >> 25) & 0xF,
        "bit_index": (output_value >> 21) & 0xF,
        "zero_on_result": (output_value >> 20) & 0x1,
        "stack_kind": (output_value >> 18) & 0x3,
        "stack_pair": (output_value >> 15) & 0x7,
        "misc_kind": (output_value >> 11) & 0xF,
        "interrupt_enable": (output_value >> 10) & 0x1,
        "prefix": (output_value >> 8) & 0x3,
        "rst_vector": output_value & 0xFF,
    }


async def sample(dut, *, opcode: int) -> dict[str, int]:
    dut.opcode_i.value = opcode & 0xFF
    await Timer(1, units="ns")
    return decode_output(int(dut.output__.value))


@cocotb.test()
async def test_unprefixed_decoder_matches_metadata_projection_for_all_opcodes(dut):
    for opcode in range(0x100):
        snapshot = await sample(dut, opcode=opcode)
        assert snapshot == projection_for_unprefixed_opcode(opcode), (opcode, snapshot, projection_for_unprefixed_opcode(opcode))
