# top = cpu::semantics_wordalu_test_top::semantics_wordalu_test_top
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
    raise RuntimeError("Unable to locate iceboy repo root for semantic word ALU tests")


ROOT = find_repo_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spec.flag_policies import add16_hl, add_sp_e8, ld_hl_sp_plus_e8


PHASE_FETCH = 0
PHASE_EXECUTE = 2
PHASE_READ_IMM8 = 3

IMM8_CONT_LOAD_HL_SP_DISP = 4
IMM8_CONT_ADD_SP_DISP = 5


def flags_to_f(flags) -> int:
    return (
        (0x80 if flags.z else 0x00)
        | (0x40 if flags.n else 0x00)
        | (0x20 if flags.h else 0x00)
        | (0x10 if flags.c else 0x00)
    )


def decode_output(output_value: int) -> dict[str, int | bool]:
    return {
        "next_pc": (output_value >> 232) & 0xFFFF,
        "next_sp": (output_value >> 216) & 0xFFFF,
        "next_a": (output_value >> 208) & 0xFF,
        "next_f": (output_value >> 200) & 0xFF,
        "next_b": (output_value >> 192) & 0xFF,
        "next_c": (output_value >> 184) & 0xFF,
        "next_d": (output_value >> 176) & 0xFF,
        "next_e": (output_value >> 168) & 0xFF,
        "next_h": (output_value >> 160) & 0xFF,
        "next_l": (output_value >> 152) & 0xFF,
        "next_opcode": (output_value >> 144) & 0xFF,
        "next_imm_lo": (output_value >> 136) & 0xFF,
        "next_imm_hi": (output_value >> 128) & 0xFF,
        "next_temp": (output_value >> 112) & 0xFFFF,
        "bus_req_kind": (output_value >> 110) & 0x3,
        "bus_req_addr": (output_value >> 94) & 0xFFFF,
        "bus_req_data": (output_value >> 86) & 0xFF,
        "next_phase_kind": (output_value >> 82) & 0xF,
        "next_phase_cont": (output_value >> 78) & 0xF,
        "next_phase_addr": (output_value >> 62) & 0xFFFF,
        "next_phase_data": (output_value >> 54) & 0xFF,
        "next_phase_cont_data": (output_value >> 46) & 0xFF,
        "next_phase_aux": (output_value >> 30) & 0xFFFF,
        "commit_present": bool((output_value >> 29) & 0x1),
    }


def initial_state(**overrides: int) -> dict[str, int]:
    state = {
        "pc": 0x0100,
        "sp": 0xFFFE,
        "a": 0x12,
        "f": 0x00,
        "b": 0x34,
        "c": 0x56,
        "d": 0x78,
        "e": 0x9A,
        "h": 0xC0,
        "l": 0x10,
        "opcode": 0x00,
        "imm_lo": 0x00,
        "imm_hi": 0x00,
        "temp": 0x0000,
        "phase_kind": PHASE_FETCH,
        "phase_cont": 0,
        "phase_addr": 0,
        "phase_data": 0,
        "phase_cont_data": 0,
        "phase_aux": 0,
    }
    state.update(overrides)
    return state


def follow_state(snapshot: dict[str, int | bool]) -> dict[str, int]:
    return {
        "pc": int(snapshot["next_pc"]),
        "sp": int(snapshot["next_sp"]),
        "a": int(snapshot["next_a"]),
        "f": int(snapshot["next_f"]),
        "b": int(snapshot["next_b"]),
        "c": int(snapshot["next_c"]),
        "d": int(snapshot["next_d"]),
        "e": int(snapshot["next_e"]),
        "h": int(snapshot["next_h"]),
        "l": int(snapshot["next_l"]),
        "opcode": int(snapshot["next_opcode"]),
        "imm_lo": int(snapshot["next_imm_lo"]),
        "imm_hi": int(snapshot["next_imm_hi"]),
        "temp": int(snapshot["next_temp"]),
        "phase_kind": int(snapshot["next_phase_kind"]),
        "phase_cont": int(snapshot["next_phase_cont"]),
        "phase_addr": int(snapshot["next_phase_addr"]),
        "phase_data": int(snapshot["next_phase_data"]),
        "phase_cont_data": int(snapshot["next_phase_cont_data"]),
        "phase_aux": int(snapshot["next_phase_aux"]),
    }


async def sample(dut, state: dict[str, int], *, bus_resp: int, irq_pending: int = 0) -> dict[str, int | bool]:
    dut.state_pc_i.value = state["pc"] & 0xFFFF
    dut.state_sp_i.value = state["sp"] & 0xFFFF
    dut.state_a_i.value = state["a"] & 0xFF
    dut.state_f_i.value = state["f"] & 0xFF
    dut.state_b_i.value = state["b"] & 0xFF
    dut.state_c_i.value = state["c"] & 0xFF
    dut.state_d_i.value = state["d"] & 0xFF
    dut.state_e_i.value = state["e"] & 0xFF
    dut.state_h_i.value = state["h"] & 0xFF
    dut.state_l_i.value = state["l"] & 0xFF
    dut.state_opcode_i.value = state["opcode"] & 0xFF
    dut.state_imm_lo_i.value = state["imm_lo"] & 0xFF
    dut.state_imm_hi_i.value = state["imm_hi"] & 0xFF
    dut.state_temp_i.value = state["temp"] & 0xFFFF
    dut.state_phase_kind_i.value = state["phase_kind"] & 0xF
    dut.state_phase_cont_i.value = state["phase_cont"] & 0xF
    dut.state_phase_addr_i.value = state["phase_addr"] & 0xFFFF
    dut.state_phase_data_i.value = state["phase_data"] & 0xFF
    dut.state_phase_cont_data_i.value = state["phase_cont_data"] & 0xFF
    dut.state_phase_aux_i.value = state["phase_aux"] & 0xFFFF
    dut.bus_resp_i.value = bus_resp & 0xFF
    dut.irq_pending_i.value = irq_pending & 0x1F
    await Timer(1, units="ns")
    return decode_output(int(dut.output__.value))


@cocotb.test()
async def test_add_hl_rr_executes_after_fetch_and_preserves_z(dut):
    fetch = await sample(dut, initial_state(opcode=0x09, h=0x0F, l=0xFF, b=0x00, c=0x01, f=0x80), bus_resp=0x09)
    assert fetch["next_phase_kind"] == PHASE_EXECUTE
    assert fetch["next_pc"] == 0x0101

    execute = await sample(dut, follow_state(fetch), bus_resp=0x00)
    expected = add16_hl(0x0FFF, 0x0001, z_in=True)
    assert execute["next_h"] == (expected.value >> 8) & 0xFF
    assert execute["next_l"] == expected.value & 0xFF
    assert execute["next_f"] == flags_to_f(expected.flags)
    assert execute["next_phase_kind"] == PHASE_FETCH


@cocotb.test()
async def test_inc_rr_updates_pair_without_touching_flags(dut):
    fetch = await sample(dut, initial_state(opcode=0x13, d=0x12, e=0xFF, f=0xA0), bus_resp=0x13)
    assert fetch["next_phase_kind"] == PHASE_EXECUTE

    execute = await sample(dut, follow_state(fetch), bus_resp=0x00)
    assert execute["next_d"] == 0x13
    assert execute["next_e"] == 0x00
    assert execute["next_f"] == 0xA0
    assert execute["next_phase_kind"] == PHASE_FETCH


@cocotb.test()
async def test_dec_sp_updates_sp_without_touching_flags(dut):
    fetch = await sample(dut, initial_state(opcode=0x3B, sp=0x0000, f=0x50), bus_resp=0x3B)
    assert fetch["next_phase_kind"] == PHASE_EXECUTE

    execute = await sample(dut, follow_state(fetch), bus_resp=0x00)
    assert execute["next_sp"] == 0xFFFF
    assert execute["next_f"] == 0x50
    assert execute["next_phase_kind"] == PHASE_FETCH


@cocotb.test()
async def test_add_sp_e8_uses_two_internal_cycles(dut):
    fetch = await sample(dut, initial_state(opcode=0xE8, sp=0x00FF, f=0x80), bus_resp=0xE8)
    assert fetch["next_phase_kind"] == PHASE_READ_IMM8
    assert fetch["next_phase_cont"] == IMM8_CONT_ADD_SP_DISP

    imm = await sample(dut, follow_state(fetch), bus_resp=0x01)
    assert imm["next_pc"] == 0x0102
    assert imm["next_phase_kind"] == PHASE_EXECUTE
    assert imm["next_imm_lo"] == 0x01
    assert imm["next_imm_hi"] == 0x00

    stage1 = await sample(dut, follow_state(imm), bus_resp=0x00)
    expected = add_sp_e8(0x00FF, 0x01)
    assert stage1["next_sp"] == 0x00FF
    assert stage1["next_f"] == flags_to_f(expected.flags)
    assert stage1["next_temp"] == expected.value
    assert stage1["next_imm_hi"] == 0x01
    assert stage1["next_phase_kind"] == PHASE_EXECUTE

    stage2 = await sample(dut, follow_state(stage1), bus_resp=0x00)
    assert stage2["next_sp"] == expected.value
    assert stage2["next_f"] == flags_to_f(expected.flags)
    assert stage2["next_imm_hi"] == 0x00
    assert stage2["next_phase_kind"] == PHASE_FETCH


@cocotb.test()
async def test_ld_hl_sp_plus_e8_finishes_in_single_internal_cycle(dut):
    fetch = await sample(dut, initial_state(opcode=0xF8, sp=0xFFF8), bus_resp=0xF8)
    assert fetch["next_phase_kind"] == PHASE_READ_IMM8
    assert fetch["next_phase_cont"] == IMM8_CONT_LOAD_HL_SP_DISP

    imm = await sample(dut, follow_state(fetch), bus_resp=0x08)
    assert imm["next_pc"] == 0x0102
    assert imm["next_phase_kind"] == PHASE_EXECUTE

    execute = await sample(dut, follow_state(imm), bus_resp=0x00)
    expected = ld_hl_sp_plus_e8(0xFFF8, 0x08)
    assert execute["next_h"] == (expected.value >> 8) & 0xFF
    assert execute["next_l"] == expected.value & 0xFF
    assert execute["next_f"] == flags_to_f(expected.flags)
    assert execute["next_imm_hi"] == 0x00
    assert execute["next_phase_kind"] == PHASE_FETCH

