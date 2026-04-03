# top = cpu::semantics_load_test_top::semantics_load_test_top
import cocotb
from cocotb.triggers import Timer


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
        "next_imm_lo": (output_value >> 112) & 0xFF,
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
        "phase_kind": 0,
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
async def test_ld_r_r_completes_in_fetch(dut):
    snapshot = await sample(dut, initial_state(opcode=0x41, b=0x11, c=0x77), bus_resp=0x41)
    assert snapshot["commit_present"] is True
    assert snapshot["next_b"] == 0x77
    assert snapshot["next_pc"] == 0x0101
    assert snapshot["next_phase_kind"] == 0
    assert snapshot["bus_req_kind"] == 1
    assert snapshot["bus_req_addr"] == 0x0100


@cocotb.test()
async def test_ld_r_n_fetches_then_writes_immediate(dut):
    fetch = await sample(dut, initial_state(opcode=0x06), bus_resp=0x06)
    assert fetch["next_phase_kind"] == 3
    assert fetch["next_phase_cont"] == 0
    assert fetch["next_phase_cont_data"] == 0

    writeback = await sample(dut, follow_state(fetch), bus_resp=0x9A)
    assert writeback["next_b"] == 0x9A
    assert writeback["next_pc"] == 0x0102
    assert writeback["next_phase_kind"] == 0
    assert writeback["bus_req_kind"] == 1
    assert writeback["bus_req_addr"] == 0x0101


@cocotb.test()
async def test_ld_r_from_hl_reads_memory_then_updates_register(dut):
    fetch = await sample(dut, initial_state(opcode=0x46, h=0xC1, l=0x23), bus_resp=0x46)
    assert fetch["next_phase_kind"] == 6
    assert fetch["next_phase_addr"] == 0xC123
    assert fetch["next_phase_cont"] == 0
    assert fetch["next_phase_cont_data"] == 0

    readback = await sample(dut, follow_state(fetch), bus_resp=0x5C)
    assert readback["next_b"] == 0x5C
    assert readback["next_phase_kind"] == 0
    assert readback["bus_req_kind"] == 1
    assert readback["bus_req_addr"] == 0xC123


@cocotb.test()
async def test_ld_hl_n_fetches_immediate_then_writes_memory(dut):
    fetch = await sample(dut, initial_state(opcode=0x36, h=0xD0, l=0x44), bus_resp=0x36)
    assert fetch["next_phase_kind"] == 3
    assert fetch["next_phase_cont"] == 1

    imm = await sample(dut, follow_state(fetch), bus_resp=0xAB)
    assert imm["next_phase_kind"] == 7
    assert imm["next_phase_addr"] == 0xD044
    assert imm["next_phase_data"] == 0xAB

    write = await sample(dut, follow_state(imm), bus_resp=0x00)
    assert write["bus_req_kind"] == 2
    assert write["bus_req_addr"] == 0xD044
    assert write["bus_req_data"] == 0xAB
    assert write["next_phase_kind"] == 0


@cocotb.test()
async def test_ld_a_from_bc_uses_readmem_continuation(dut):
    fetch = await sample(dut, initial_state(opcode=0x0A, b=0x80, c=0x12), bus_resp=0x0A)
    assert fetch["next_phase_kind"] == 6
    assert fetch["next_phase_cont"] == 1
    assert fetch["next_phase_addr"] == 0x8012

    readback = await sample(dut, follow_state(fetch), bus_resp=0x3E)
    assert readback["next_a"] == 0x3E
    assert readback["next_phase_kind"] == 0


@cocotb.test()
async def test_ld_a_from_nn_walks_imm16_then_memory(dut):
    fetch = await sample(dut, initial_state(opcode=0xFA), bus_resp=0xFA)
    assert fetch["next_phase_kind"] == 4
    assert fetch["next_phase_cont"] == 1

    lo = await sample(dut, follow_state(fetch), bus_resp=0x34)
    assert lo["next_phase_kind"] == 5
    assert lo["next_phase_cont"] == 1
    assert lo["next_phase_aux"] == 0x0034

    hi = await sample(dut, follow_state(lo), bus_resp=0x12)
    assert hi["next_phase_kind"] == 6
    assert hi["next_phase_addr"] == 0x1234
    assert hi["next_pc"] == 0x0103

    readback = await sample(dut, follow_state(hi), bus_resp=0xC7)
    assert readback["next_a"] == 0xC7
    assert readback["next_phase_kind"] == 0


@cocotb.test()
async def test_ld_sp_hl_executes_on_internal_cycle(dut):
    fetch = await sample(dut, initial_state(opcode=0xF9, h=0xAB, l=0xCD, sp=0xFFFE), bus_resp=0xF9)
    assert fetch["next_phase_kind"] == 2
    assert fetch["next_pc"] == 0x0101

    execute = await sample(dut, follow_state(fetch), bus_resp=0x00)
    assert execute["next_sp"] == 0xABCD
    assert execute["next_phase_kind"] == 0
    assert execute["bus_req_kind"] == 0


@cocotb.test()
async def test_ld_hl_sp_plus_e8_uses_execute_and_flag_policy(dut):
    fetch = await sample(dut, initial_state(opcode=0xF8, sp=0xFFF8), bus_resp=0xF8)
    assert fetch["next_phase_kind"] == 3
    assert fetch["next_phase_cont"] == 4

    imm = await sample(dut, follow_state(fetch), bus_resp=0x08)
    assert imm["next_phase_kind"] == 2
    assert imm["next_imm_lo"] == 0x08

    execute = await sample(dut, follow_state(imm), bus_resp=0x00)
    assert execute["next_h"] == 0x00
    assert execute["next_l"] == 0x00
    assert execute["next_f"] == 0x30
    assert execute["next_phase_kind"] == 0


@cocotb.test()
async def test_ldh_and_hl_autoincrement_paths_adjust_addresses(dut):
    ldh_fetch = await sample(dut, initial_state(opcode=0xF0), bus_resp=0xF0)
    imm = await sample(dut, follow_state(ldh_fetch), bus_resp=0x80)
    assert imm["next_phase_kind"] == 6
    assert imm["next_phase_addr"] == 0xFF80
    ldh_done = await sample(dut, follow_state(imm), bus_resp=0x66)
    assert ldh_done["next_a"] == 0x66

    hli_fetch = await sample(dut, initial_state(opcode=0x2A, h=0xC0, l=0x10), bus_resp=0x2A)
    hli_done = await sample(dut, follow_state(hli_fetch), bus_resp=0x55)
    assert hli_done["next_a"] == 0x55
    assert hli_done["next_h"] == 0xC0
    assert hli_done["next_l"] == 0x11

    hld_fetch = await sample(dut, initial_state(opcode=0x32, a=0x99, h=0xC0, l=0x20), bus_resp=0x32)
    hld_done = await sample(dut, follow_state(hld_fetch), bus_resp=0x00)
    assert hld_done["bus_req_kind"] == 2
    assert hld_done["bus_req_addr"] == 0xC020
    assert hld_done["bus_req_data"] == 0x99
    assert hld_done["next_h"] == 0xC0
    assert hld_done["next_l"] == 0x1F


@cocotb.test()
async def test_ld_nn_sp_emits_two_writes(dut):
    fetch = await sample(dut, initial_state(opcode=0x08, sp=0xABCD), bus_resp=0x08)
    lo = await sample(dut, follow_state(fetch), bus_resp=0x34)
    hi = await sample(dut, follow_state(lo), bus_resp=0x12)
    assert hi["next_phase_kind"] == 7
    assert hi["next_phase_addr"] == 0x1234
    assert hi["next_phase_data"] == 0xCD
    assert hi["next_phase_cont"] == 1
    assert hi["next_phase_cont_data"] == 0xAB
    assert hi["next_phase_aux"] == 0x1235

    low_write = await sample(dut, follow_state(hi), bus_resp=0x00)
    assert low_write["bus_req_kind"] == 2
    assert low_write["bus_req_addr"] == 0x1234
    assert low_write["bus_req_data"] == 0xCD
    assert low_write["next_phase_addr"] == 0x1235
    assert low_write["next_phase_data"] == 0xAB

    high_write = await sample(dut, follow_state(low_write), bus_resp=0x00)
    assert high_write["bus_req_kind"] == 2
    assert high_write["bus_req_addr"] == 0x1235
    assert high_write["bus_req_data"] == 0xAB
    assert high_write["next_phase_kind"] == 0


@cocotb.test()
async def test_push_and_pop_pair_follow_two_cycle_stack_sequence(dut):
    push_fetch = await sample(dut, initial_state(opcode=0xC5, sp=0xFFF0, b=0x12, c=0x34), bus_resp=0xC5)
    assert push_fetch["next_phase_kind"] == 2
    assert push_fetch["next_pc"] == 0x0101

    push_execute = await sample(dut, follow_state(push_fetch), bus_resp=0x00)
    assert push_execute["next_phase_kind"] == 7
    assert push_execute["next_phase_addr"] == 0xFFEF
    assert push_execute["next_phase_data"] == 0x12
    assert push_execute["next_phase_cont"] == 2
    assert push_execute["next_phase_cont_data"] == 0x34
    assert push_execute["next_phase_aux"] == 0xFFEE

    push_hi = await sample(dut, follow_state(push_execute), bus_resp=0x00)
    assert push_hi["bus_req_kind"] == 2
    assert push_hi["bus_req_addr"] == 0xFFEF
    assert push_hi["bus_req_data"] == 0x12
    assert push_hi["next_sp"] == 0xFFEF
    assert push_hi["next_phase_addr"] == 0xFFEE
    assert push_hi["next_phase_data"] == 0x34

    push_lo = await sample(dut, follow_state(push_hi), bus_resp=0x00)
    assert push_lo["bus_req_kind"] == 2
    assert push_lo["bus_req_addr"] == 0xFFEE
    assert push_lo["bus_req_data"] == 0x34
    assert push_lo["next_sp"] == 0xFFEE
    assert push_lo["next_phase_kind"] == 0

    pop_fetch = await sample(dut, initial_state(opcode=0xC1, sp=0xFFEE), bus_resp=0xC1)
    assert pop_fetch["next_phase_kind"] == 6
    assert pop_fetch["next_phase_addr"] == 0xFFEE
    assert pop_fetch["next_phase_cont"] == 2
    assert pop_fetch["next_phase_cont_data"] == 0

    pop_lo = await sample(dut, follow_state(pop_fetch), bus_resp=0x34)
    assert pop_lo["next_sp"] == 0xFFEF
    assert pop_lo["next_phase_kind"] == 6
    assert pop_lo["next_phase_addr"] == 0xFFEF
    assert pop_lo["next_phase_cont"] == 3
    assert pop_lo["next_phase_data"] == 0x34
    assert pop_lo["next_phase_cont_data"] == 0

    pop_hi = await sample(dut, follow_state(pop_lo), bus_resp=0x12)
    assert pop_hi["next_b"] == 0x12
    assert pop_hi["next_c"] == 0x34
    assert pop_hi["next_sp"] == 0xFFF0
    assert pop_hi["next_phase_kind"] == 0
