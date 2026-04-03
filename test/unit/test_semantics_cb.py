# top = cpu::semantics_cb_test_top::semantics_cb_test_top
from __future__ import annotations

import cocotb
from cocotb.triggers import Timer


PHASE_FETCH = 0
PHASE_FETCH_PREFIX = 1
PHASE_READ_MEM = 6
PHASE_WRITE_MEM = 7

PREFIX_CB = 1
READ_CONT_BITOP_FROM_MEM = 5
BIT_KIND_BIT = 12
BIT_KIND_RES = 13
ROT_KIND_RLC = 0


def decode_output(output_value: int) -> dict[str, int | bool]:
    return {
        "next_pc": (output_value >> 208) & 0xFFFF,
        "next_sp": (output_value >> 192) & 0xFFFF,
        "next_a": (output_value >> 184) & 0xFF,
        "next_f": (output_value >> 176) & 0xFF,
        "next_b": (output_value >> 168) & 0xFF,
        "next_c": (output_value >> 160) & 0xFF,
        "next_d": (output_value >> 152) & 0xFF,
        "next_e": (output_value >> 144) & 0xFF,
        "next_h": (output_value >> 136) & 0xFF,
        "next_l": (output_value >> 128) & 0xFF,
        "next_opcode": (output_value >> 120) & 0xFF,
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
        "h": 0xC1,
        "l": 0x23,
        "opcode": 0x00,
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
async def test_fetch_cb_enters_prefix_phase(dut):
    snapshot = await sample(dut, initial_state(), bus_resp=0xCB)
    assert snapshot["next_pc"] == 0x0101
    assert snapshot["next_opcode"] == 0xCB
    assert snapshot["next_phase_kind"] == PHASE_FETCH_PREFIX
    assert snapshot["next_phase_cont"] == PREFIX_CB
    assert snapshot["commit_present"] is True


@cocotb.test()
async def test_cb_rlc_b_executes_during_prefix_fetch(dut):
    fetch_cb = await sample(dut, initial_state(b=0x81), bus_resp=0xCB)
    cb_step = await sample(dut, follow_state(fetch_cb), bus_resp=0x00)
    assert cb_step["bus_req_kind"] == 1
    assert cb_step["bus_req_addr"] == 0x0101
    assert cb_step["next_pc"] == 0x0102
    assert cb_step["next_opcode"] == 0x00
    assert cb_step["next_b"] == 0x03
    assert cb_step["next_f"] == 0x10
    assert cb_step["next_phase_kind"] == PHASE_FETCH


@cocotb.test()
async def test_cb_bit_7_hl_reads_memory_without_writeback(dut):
    fetch_cb = await sample(dut, initial_state(f=0x10), bus_resp=0xCB)
    cb_step = await sample(dut, follow_state(fetch_cb), bus_resp=0x7E)
    assert cb_step["next_pc"] == 0x0102
    assert cb_step["next_opcode"] == 0x7E
    assert cb_step["next_phase_kind"] == PHASE_READ_MEM
    assert cb_step["next_phase_addr"] == 0xC123
    assert cb_step["next_phase_cont"] == READ_CONT_BITOP_FROM_MEM
    assert cb_step["next_phase_cont_data"] == BIT_KIND_BIT
    assert cb_step["next_phase_data"] == 7

    read_step = await sample(dut, follow_state(cb_step), bus_resp=0x80)
    assert read_step["bus_req_kind"] == 1
    assert read_step["bus_req_addr"] == 0xC123
    assert read_step["next_f"] == 0x30
    assert read_step["next_phase_kind"] == PHASE_FETCH


@cocotb.test()
async def test_cb_res_0_hl_reads_then_writes_back(dut):
    fetch_cb = await sample(dut, initial_state(f=0xA0), bus_resp=0xCB)
    cb_step = await sample(dut, follow_state(fetch_cb), bus_resp=0x86)
    assert cb_step["next_phase_kind"] == PHASE_READ_MEM
    assert cb_step["next_phase_cont"] == READ_CONT_BITOP_FROM_MEM
    assert cb_step["next_phase_cont_data"] == BIT_KIND_RES
    assert cb_step["next_phase_data"] == 0

    read_step = await sample(dut, follow_state(cb_step), bus_resp=0x9B)
    assert read_step["bus_req_kind"] == 1
    assert read_step["bus_req_addr"] == 0xC123
    assert read_step["next_f"] == 0xA0
    assert read_step["next_phase_kind"] == PHASE_WRITE_MEM
    assert read_step["next_phase_addr"] == 0xC123
    assert read_step["next_phase_data"] == 0x9A

    write_step = await sample(dut, follow_state(read_step), bus_resp=0x00)
    assert write_step["bus_req_kind"] == 2
    assert write_step["bus_req_addr"] == 0xC123
    assert write_step["bus_req_data"] == 0x9A
    assert write_step["next_phase_kind"] == PHASE_FETCH


@cocotb.test()
async def test_cb_rlc_hl_reads_then_writes_back_with_flags(dut):
    fetch_cb = await sample(dut, initial_state(), bus_resp=0xCB)
    cb_step = await sample(dut, follow_state(fetch_cb), bus_resp=0x06)
    assert cb_step["next_phase_kind"] == PHASE_READ_MEM
    assert cb_step["next_phase_cont"] == READ_CONT_BITOP_FROM_MEM
    assert cb_step["next_phase_cont_data"] == ROT_KIND_RLC
    assert cb_step["next_phase_data"] == 0xFF

    read_step = await sample(dut, follow_state(cb_step), bus_resp=0x80)
    assert read_step["next_f"] == 0x10
    assert read_step["next_phase_kind"] == PHASE_WRITE_MEM
    assert read_step["next_phase_addr"] == 0xC123
    assert read_step["next_phase_data"] == 0x01

    write_step = await sample(dut, follow_state(read_step), bus_resp=0x00)
    assert write_step["bus_req_kind"] == 2
    assert write_step["bus_req_addr"] == 0xC123
    assert write_step["bus_req_data"] == 0x01
    assert write_step["next_phase_kind"] == PHASE_FETCH
