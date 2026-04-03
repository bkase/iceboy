# top = cpu::semantics_alu_test_top::semantics_alu_test_top
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
    raise RuntimeError("Unable to locate iceboy repo root for semantic ALU tests")


ROOT = find_repo_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spec.flag_policies import Flags, add8, adc8, ccf, cpl, daa, dec8, inc8, or8, rl8, rlc8, rr8, rrc8, scf


PHASE_FETCH = 0
PHASE_EXECUTE = 2
PHASE_READ_IMM8 = 3
PHASE_READ_MEM = 6
PHASE_WRITE_MEM = 7

READ_CONT_ALU_FROM_MEM = 4
IMM8_CONT_ALU_IMM8 = 5


def flags_to_f(flags: Flags) -> int:
    return (
        (0x80 if flags.z else 0x00)
        | (0x40 if flags.n else 0x00)
        | (0x20 if flags.h else 0x00)
        | (0x10 if flags.c else 0x00)
    )


def decode_output(output_value: int) -> dict[str, int | bool]:
    return {
        "next_pc": (output_value >> 224) & 0xFFFF,
        "next_sp": (output_value >> 208) & 0xFFFF,
        "next_a": (output_value >> 200) & 0xFF,
        "next_f": (output_value >> 192) & 0xFF,
        "next_b": (output_value >> 184) & 0xFF,
        "next_c": (output_value >> 176) & 0xFF,
        "next_d": (output_value >> 168) & 0xFF,
        "next_e": (output_value >> 160) & 0xFF,
        "next_h": (output_value >> 152) & 0xFF,
        "next_l": (output_value >> 144) & 0xFF,
        "next_opcode": (output_value >> 136) & 0xFF,
        "next_imm_lo": (output_value >> 128) & 0xFF,
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
async def test_add_a_r_executes_after_fetch(dut):
    fetch = await sample(dut, initial_state(opcode=0x80, a=0x12, b=0x34), bus_resp=0x80)
    assert fetch["next_phase_kind"] == PHASE_EXECUTE
    assert fetch["next_pc"] == 0x0101
    assert fetch["bus_req_kind"] == 1
    assert fetch["bus_req_addr"] == 0x0100

    execute = await sample(dut, follow_state(fetch), bus_resp=0x00)
    expected = add8(0x12, 0x34)
    assert execute["next_a"] == expected.value
    assert execute["next_f"] == flags_to_f(expected.flags)
    assert execute["next_phase_kind"] == PHASE_FETCH
    assert execute["bus_req_kind"] == 0


@cocotb.test()
async def test_adc_a_n_fetches_immediate_then_executes(dut):
    fetch = await sample(dut, initial_state(opcode=0xCE, a=0x0F, f=0x10), bus_resp=0xCE)
    assert fetch["next_phase_kind"] == PHASE_READ_IMM8
    assert fetch["next_phase_cont"] == IMM8_CONT_ALU_IMM8
    assert fetch["next_phase_cont_data"] == 1

    imm = await sample(dut, follow_state(fetch), bus_resp=0x01)
    assert imm["next_pc"] == 0x0102
    assert imm["next_imm_lo"] == 0x01
    assert imm["next_phase_kind"] == PHASE_EXECUTE

    execute = await sample(dut, follow_state(imm), bus_resp=0x00)
    expected = adc8(0x0F, 0x01, True)
    assert execute["next_a"] == expected.value
    assert execute["next_f"] == flags_to_f(expected.flags)
    assert execute["next_phase_kind"] == PHASE_FETCH


@cocotb.test()
async def test_or_a_hl_reads_memory_then_executes(dut):
    fetch = await sample(dut, initial_state(opcode=0xB6, a=0x80, h=0xC1, l=0x23), bus_resp=0xB6)
    assert fetch["next_phase_kind"] == PHASE_READ_MEM
    assert fetch["next_phase_cont"] == READ_CONT_ALU_FROM_MEM
    assert fetch["next_phase_cont_data"] == 5
    assert fetch["next_phase_addr"] == 0xC123

    readback = await sample(dut, follow_state(fetch), bus_resp=0x01)
    assert readback["next_temp"] == 0x0001
    assert readback["next_phase_kind"] == PHASE_EXECUTE
    assert readback["bus_req_kind"] == 1
    assert readback["bus_req_addr"] == 0xC123

    execute = await sample(dut, follow_state(readback), bus_resp=0x00)
    expected = or8(0x80, 0x01)
    assert execute["next_a"] == expected.value
    assert execute["next_f"] == flags_to_f(expected.flags)
    assert execute["next_phase_kind"] == PHASE_FETCH


@cocotb.test()
async def test_dec_r_updates_target_and_flags(dut):
    fetch = await sample(dut, initial_state(opcode=0x05, b=0x10, f=0x10), bus_resp=0x05)
    assert fetch["next_phase_kind"] == PHASE_EXECUTE

    execute = await sample(dut, follow_state(fetch), bus_resp=0x00)
    expected = dec8(0x10, carry_in=True)
    assert execute["next_b"] == expected.value
    assert execute["next_f"] == flags_to_f(expected.flags)
    assert execute["next_phase_kind"] == PHASE_FETCH


@cocotb.test()
async def test_inc_hl_reads_executes_and_writes_back(dut):
    fetch = await sample(dut, initial_state(opcode=0x34, h=0xC0, l=0x44, f=0x10), bus_resp=0x34)
    assert fetch["next_phase_kind"] == PHASE_READ_MEM
    assert fetch["next_phase_cont"] == READ_CONT_ALU_FROM_MEM
    assert fetch["next_phase_cont_data"] == 8
    assert fetch["next_phase_addr"] == 0xC044

    readback = await sample(dut, follow_state(fetch), bus_resp=0x0F)
    assert readback["next_temp"] == 0x000F
    assert readback["next_phase_kind"] == PHASE_EXECUTE

    execute = await sample(dut, follow_state(readback), bus_resp=0x00)
    expected = inc8(0x0F, carry_in=True)
    assert execute["next_f"] == flags_to_f(expected.flags)
    assert execute["next_temp"] == expected.value
    assert execute["next_phase_kind"] == PHASE_WRITE_MEM
    assert execute["next_phase_addr"] == 0xC044
    assert execute["next_phase_data"] == expected.value

    writeback = await sample(dut, follow_state(execute), bus_resp=0x00)
    assert writeback["bus_req_kind"] == 2
    assert writeback["bus_req_addr"] == 0xC044
    assert writeback["bus_req_data"] == expected.value
    assert writeback["next_phase_kind"] == PHASE_FETCH


@cocotb.test()
async def test_misc_flag_family_executes_curated_cases(dut):
    daa_fetch = await sample(dut, initial_state(opcode=0x27, a=0x9A, f=0x00), bus_resp=0x27)
    daa_execute = await sample(dut, follow_state(daa_fetch), bus_resp=0x00)
    daa_expected = daa(0x9A, Flags(False, False, False, False))
    assert daa_execute["next_a"] == daa_expected.value
    assert daa_execute["next_f"] == flags_to_f(daa_expected.flags)

    cpl_fetch = await sample(dut, initial_state(opcode=0x2F, a=0x3C, f=0x80), bus_resp=0x2F)
    cpl_execute = await sample(dut, follow_state(cpl_fetch), bus_resp=0x00)
    cpl_expected = cpl(0x3C, True, False)
    assert cpl_execute["next_a"] == cpl_expected.value
    assert cpl_execute["next_f"] == flags_to_f(cpl_expected.flags)

    scf_fetch = await sample(dut, initial_state(opcode=0x37, f=0x80), bus_resp=0x37)
    scf_execute = await sample(dut, follow_state(scf_fetch), bus_resp=0x00)
    assert scf_execute["next_f"] == flags_to_f(scf(True))

    ccf_fetch = await sample(dut, initial_state(opcode=0x3F, f=0x90), bus_resp=0x3F)
    ccf_execute = await sample(dut, follow_state(ccf_fetch), bus_resp=0x00)
    assert ccf_execute["next_f"] == flags_to_f(ccf(True, True))


@cocotb.test()
async def test_accumulator_rotates_keep_z_clear_unlike_cb_equivalents(dut):
    cases = [
        (0x07, rlc8, rlc8, 0x00, {}),
        (0x0F, rrc8, rrc8, 0x00, {}),
        (0x17, rl8, rl8, 0x00, {"c_in": False}),
        (0x1F, rr8, rr8, 0x00, {"c_in": False}),
    ]

    for opcode, op_fn, cb_fn, value, kwargs in cases:
        f = 0x10 if kwargs.get("c_in", False) else 0x00
        fetch = await sample(dut, initial_state(opcode=opcode, a=value, f=f), bus_resp=opcode)
        execute = await sample(dut, follow_state(fetch), bus_resp=0x00)
        if opcode in (0x07, 0x0F):
            expected = op_fn(value, zero_affects=False)
            cb_expected = cb_fn(value, zero_affects=True)
        else:
            carry_in = kwargs["c_in"]
            expected = op_fn(value, carry_in, zero_affects=False)
            cb_expected = cb_fn(value, carry_in, zero_affects=True)
        assert execute["next_a"] == expected.value
        assert execute["next_f"] == flags_to_f(expected.flags)
        assert expected.flags.z is False
        assert cb_expected.flags.z is True
