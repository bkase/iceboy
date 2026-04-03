# top = cpu::semantics_flow_test_top::semantics_flow_test_top
from __future__ import annotations

import cocotb
from cocotb.triggers import Timer


PHASE_FETCH = 0
PHASE_EXECUTE = 2
PHASE_READ_IMM8 = 3
PHASE_READ_IMM16_LO = 4
PHASE_READ_IMM16_HI = 5
PHASE_READ_MEM = 6
PHASE_WRITE_MEM = 7

IMM8_CONT_RELATIVE_JUMP = 6
IMM16_CONT_JUMP_ABS = 4
IMM16_CONT_CALL_TARGET = 5
WRITE_CONT_PUSH_HI = 2
WRITE_CONT_PUSH_LO = 3
READ_CONT_POP_LO = 2
READ_CONT_POP_HI = 3

IME_DISABLED = 0
IME_PENDING = 1
IME_ENABLED = 2


def decode_output(output_value: int) -> dict[str, int | bool]:
    return {
        "next_pc": (output_value >> 234) & 0xFFFF,
        "next_sp": (output_value >> 218) & 0xFFFF,
        "next_a": (output_value >> 210) & 0xFF,
        "next_f": (output_value >> 202) & 0xFF,
        "next_b": (output_value >> 194) & 0xFF,
        "next_c": (output_value >> 186) & 0xFF,
        "next_d": (output_value >> 178) & 0xFF,
        "next_e": (output_value >> 170) & 0xFF,
        "next_h": (output_value >> 162) & 0xFF,
        "next_l": (output_value >> 154) & 0xFF,
        "next_ime": (output_value >> 152) & 0x3,
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
        "ime": IME_DISABLED,
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
        "ime": int(snapshot["next_ime"]),
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
    dut.state_ime_i.value = state["ime"] & 0x3
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
async def test_push_bc_uses_internal_then_two_writes(dut):
    fetch = await sample(dut, initial_state(opcode=0xC5, sp=0xFFFE, b=0x12, c=0x34), bus_resp=0xC5)
    assert fetch["next_phase_kind"] == PHASE_EXECUTE
    assert fetch["next_pc"] == 0x0101

    execute = await sample(dut, follow_state(fetch), bus_resp=0x00)
    assert execute["next_phase_kind"] == PHASE_WRITE_MEM
    assert execute["next_phase_addr"] == 0xFFFD
    assert execute["next_phase_data"] == 0x12
    assert execute["next_phase_cont"] == WRITE_CONT_PUSH_LO
    assert execute["next_phase_cont_data"] == 0x34
    assert execute["next_phase_aux"] == 0xFFFC

    write_hi = await sample(dut, follow_state(execute), bus_resp=0x00)
    assert write_hi["bus_req_kind"] == 2
    assert write_hi["bus_req_addr"] == 0xFFFD
    assert write_hi["bus_req_data"] == 0x12
    assert write_hi["next_sp"] == 0xFFFD
    assert write_hi["next_phase_kind"] == PHASE_WRITE_MEM
    assert write_hi["next_phase_addr"] == 0xFFFC
    assert write_hi["next_phase_data"] == 0x34

    write_lo = await sample(dut, follow_state(write_hi), bus_resp=0x00)
    assert write_lo["bus_req_kind"] == 2
    assert write_lo["bus_req_addr"] == 0xFFFC
    assert write_lo["bus_req_data"] == 0x34
    assert write_lo["next_sp"] == 0xFFFC
    assert write_lo["next_phase_kind"] == PHASE_FETCH


@cocotb.test()
async def test_pop_af_masks_low_nibble_of_f(dut):
    fetch = await sample(dut, initial_state(opcode=0xF1, sp=0xC100), bus_resp=0xF1)
    assert fetch["next_phase_kind"] == PHASE_READ_MEM
    assert fetch["next_phase_cont"] == READ_CONT_POP_LO
    assert fetch["next_phase_cont_data"] == 4
    assert fetch["next_phase_addr"] == 0xC100

    read_lo = await sample(dut, follow_state(fetch), bus_resp=0x3F)
    assert read_lo["next_sp"] == 0xC101
    assert read_lo["next_phase_kind"] == PHASE_READ_MEM
    assert read_lo["next_phase_cont"] == READ_CONT_POP_HI
    assert read_lo["next_phase_data"] == 0x3F
    assert read_lo["next_phase_cont_data"] == 4

    read_hi = await sample(dut, follow_state(read_lo), bus_resp=0xAB)
    assert read_hi["next_a"] == 0xAB
    assert read_hi["next_f"] == 0x30
    assert read_hi["next_sp"] == 0xC102
    assert read_hi["next_phase_kind"] == PHASE_FETCH


@cocotb.test()
async def test_jp_nn_taken_uses_internal_cycle(dut):
    fetch = await sample(dut, initial_state(opcode=0xC3), bus_resp=0xC3)
    assert fetch["next_phase_kind"] == PHASE_READ_IMM16_LO
    assert fetch["next_phase_cont"] == IMM16_CONT_JUMP_ABS

    lo = await sample(dut, follow_state(fetch), bus_resp=0x34)
    assert lo["next_phase_kind"] == PHASE_READ_IMM16_HI
    assert lo["next_phase_cont"] == IMM16_CONT_JUMP_ABS
    assert lo["next_phase_aux"] == 0x0034

    hi = await sample(dut, follow_state(lo), bus_resp=0x12)
    assert hi["next_pc"] == 0x0103
    assert hi["next_temp"] == 0x1234
    assert hi["next_phase_kind"] == PHASE_EXECUTE

    execute = await sample(dut, follow_state(hi), bus_resp=0x00)
    assert execute["next_pc"] == 0x1234
    assert execute["next_phase_kind"] == PHASE_FETCH


@cocotb.test()
async def test_jp_nz_nn_not_taken_uses_short_tuple(dut):
    fetch = await sample(dut, initial_state(opcode=0xC2, f=0x80), bus_resp=0xC2)
    lo = await sample(dut, follow_state(fetch), bus_resp=0x78)
    hi = await sample(dut, follow_state(lo), bus_resp=0x56)
    assert hi["next_pc"] == 0x0103
    assert hi["next_phase_kind"] == PHASE_FETCH
    assert hi["bus_req_kind"] == 1
    assert hi["commit_present"] is True


@cocotb.test()
async def test_jp_hl_updates_pc_on_fetch_only(dut):
    fetch = await sample(dut, initial_state(opcode=0xE9, h=0xC1, l=0x23), bus_resp=0xE9)
    assert fetch["next_pc"] == 0xC123
    assert fetch["next_phase_kind"] == PHASE_FETCH
    assert fetch["commit_present"] is True


@cocotb.test()
async def test_jr_relative_taken_and_not_taken_short_tuple(dut):
    fetch = await sample(dut, initial_state(opcode=0x18), bus_resp=0x18)
    assert fetch["next_phase_kind"] == PHASE_READ_IMM8
    assert fetch["next_phase_cont"] == IMM8_CONT_RELATIVE_JUMP

    imm = await sample(dut, follow_state(fetch), bus_resp=0xFE)
    assert imm["next_pc"] == 0x0102
    assert imm["next_phase_kind"] == PHASE_EXECUTE

    execute = await sample(dut, follow_state(imm), bus_resp=0x00)
    assert execute["next_pc"] == 0x0100
    assert execute["next_phase_kind"] == PHASE_FETCH

    cc_fetch = await sample(dut, initial_state(opcode=0x20, f=0x80), bus_resp=0x20)
    cc_imm = await sample(dut, follow_state(cc_fetch), bus_resp=0x10)
    assert cc_imm["next_pc"] == 0x0102
    assert cc_imm["next_phase_kind"] == PHASE_FETCH


@cocotb.test()
async def test_call_nn_taken_pushes_return_pc_and_sets_target(dut):
    fetch = await sample(dut, initial_state(opcode=0xCD, sp=0xFFFE), bus_resp=0xCD)
    assert fetch["next_phase_kind"] == PHASE_READ_IMM16_LO
    assert fetch["next_phase_cont"] == IMM16_CONT_CALL_TARGET

    lo = await sample(dut, follow_state(fetch), bus_resp=0x78)
    hi = await sample(dut, follow_state(lo), bus_resp=0x56)
    assert hi["next_pc"] == 0x0103
    assert hi["next_temp"] == 0x5678
    assert hi["next_phase_kind"] == PHASE_EXECUTE

    execute = await sample(dut, follow_state(hi), bus_resp=0x00)
    assert execute["next_phase_kind"] == PHASE_WRITE_MEM
    assert execute["next_phase_addr"] == 0xFFFD
    assert execute["next_phase_data"] == 0x01
    assert execute["next_phase_cont"] == WRITE_CONT_PUSH_HI
    assert execute["next_phase_aux"] == 0x0103

    write_hi = await sample(dut, follow_state(execute), bus_resp=0x00)
    assert write_hi["bus_req_kind"] == 2
    assert write_hi["bus_req_addr"] == 0xFFFD
    assert write_hi["bus_req_data"] == 0x01
    assert write_hi["next_sp"] == 0xFFFD
    assert write_hi["next_phase_kind"] == PHASE_WRITE_MEM
    assert write_hi["next_phase_addr"] == 0xFFFC
    assert write_hi["next_phase_data"] == 0x03

    write_lo = await sample(dut, follow_state(write_hi), bus_resp=0x00)
    assert write_lo["bus_req_kind"] == 2
    assert write_lo["bus_req_addr"] == 0xFFFC
    assert write_lo["bus_req_data"] == 0x03
    assert write_lo["next_sp"] == 0xFFFC
    assert write_lo["next_pc"] == 0x5678
    assert write_lo["next_phase_kind"] == PHASE_FETCH


@cocotb.test()
async def test_call_nz_nn_not_taken_uses_short_tuple(dut):
    fetch = await sample(dut, initial_state(opcode=0xC4, f=0x80), bus_resp=0xC4)
    lo = await sample(dut, follow_state(fetch), bus_resp=0x34)
    hi = await sample(dut, follow_state(lo), bus_resp=0x12)
    assert hi["next_pc"] == 0x0103
    assert hi["next_phase_kind"] == PHASE_FETCH
    assert hi["next_sp"] == 0xFFFE


@cocotb.test()
async def test_ret_and_reti_sequences(dut):
    fetch = await sample(dut, initial_state(opcode=0xC9, sp=0xC100), bus_resp=0xC9)
    assert fetch["next_phase_kind"] == PHASE_READ_MEM
    assert fetch["next_phase_cont"] == READ_CONT_POP_LO
    assert fetch["next_phase_cont_data"] == 3

    read_lo = await sample(dut, follow_state(fetch), bus_resp=0x34)
    read_hi = await sample(dut, follow_state(read_lo), bus_resp=0x12)
    assert read_hi["next_sp"] == 0xC102
    assert read_hi["next_phase_kind"] == PHASE_EXECUTE
    assert read_hi["next_imm_hi"] == 0x02
    assert read_hi["next_temp"] == 0x1234

    execute = await sample(dut, follow_state(read_hi), bus_resp=0x00)
    assert execute["next_pc"] == 0x1234
    assert execute["next_phase_kind"] == PHASE_FETCH
    assert execute["next_ime"] == IME_DISABLED

    reti_fetch = await sample(dut, initial_state(opcode=0xD9, sp=0xC100, ime=IME_DISABLED), bus_resp=0xD9)
    reti_lo = await sample(dut, follow_state(reti_fetch), bus_resp=0x78)
    reti_hi = await sample(dut, follow_state(reti_lo), bus_resp=0x56)
    reti_execute = await sample(dut, follow_state(reti_hi), bus_resp=0x00)
    assert reti_execute["next_pc"] == 0x5678
    assert reti_execute["next_ime"] == IME_ENABLED
    assert reti_execute["next_phase_kind"] == PHASE_FETCH


@cocotb.test()
async def test_ret_nz_not_taken_uses_two_cycle_tuple(dut):
    fetch = await sample(dut, initial_state(opcode=0xC0, f=0x80), bus_resp=0xC0)
    assert fetch["next_phase_kind"] == PHASE_EXECUTE
    assert fetch["next_imm_hi"] == 0x01

    execute = await sample(dut, follow_state(fetch), bus_resp=0x00)
    assert execute["next_phase_kind"] == PHASE_FETCH
    assert execute["next_sp"] == 0xFFFE
    assert execute["next_pc"] == 0x0101


@cocotb.test()
async def test_pending_ei_enables_only_after_multicycle_call_completes(dut):
    fetch = await sample(dut, initial_state(opcode=0xCD, ime=IME_PENDING), bus_resp=0xCD)
    assert fetch["next_ime"] == IME_PENDING
    assert fetch["next_phase_kind"] == PHASE_READ_IMM16_LO

    lo = await sample(dut, follow_state(fetch), bus_resp=0x78)
    assert lo["next_ime"] == IME_PENDING
    assert lo["next_phase_kind"] == PHASE_READ_IMM16_HI

    hi = await sample(dut, follow_state(lo), bus_resp=0x56)
    assert hi["next_ime"] == IME_PENDING
    assert hi["next_phase_kind"] == PHASE_EXECUTE

    execute = await sample(dut, follow_state(hi), bus_resp=0x00)
    assert execute["next_ime"] == IME_PENDING
    assert execute["next_phase_kind"] == PHASE_WRITE_MEM

    write_hi = await sample(dut, follow_state(execute), bus_resp=0x00)
    assert write_hi["next_ime"] == IME_PENDING
    assert write_hi["next_phase_kind"] == PHASE_WRITE_MEM

    write_lo = await sample(dut, follow_state(write_hi), bus_resp=0x00)
    assert write_lo["next_ime"] == IME_ENABLED
    assert write_lo["next_phase_kind"] == PHASE_FETCH
