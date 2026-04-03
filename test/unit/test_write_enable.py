# top = cpu::write_enable_test_top::write_enable_test_top
from __future__ import annotations

import cocotb
from cocotb.triggers import Timer


PHASE_FETCH = 0
PHASE_EXECUTE = 2
PHASE_READ_IMM8 = 3
PHASE_READ_MEM = 6

BUS_REQ_IDLE = 0
BUS_REQ_READ = 1


def decode_output(output_value: int) -> dict[str, int | bool]:
    return {
        "next_pc": (output_value >> 201) & 0xFFFF,
        "next_sp": (output_value >> 185) & 0xFFFF,
        "next_a": (output_value >> 177) & 0xFF,
        "next_f": (output_value >> 169) & 0xFF,
        "next_b": (output_value >> 161) & 0xFF,
        "next_c": (output_value >> 153) & 0xFF,
        "next_d": (output_value >> 145) & 0xFF,
        "next_e": (output_value >> 137) & 0xFF,
        "next_h": (output_value >> 129) & 0xFF,
        "next_l": (output_value >> 121) & 0xFF,
        "next_ime": (output_value >> 119) & 0x3,
        "next_opcode": (output_value >> 111) & 0xFF,
        "next_phase_kind": (output_value >> 107) & 0xF,
        "next_phase_addr": (output_value >> 91) & 0xFFFF,
        "next_phase_data": (output_value >> 83) & 0xFF,
        "next_phase_cont_data": (output_value >> 75) & 0xFF,
        "bus_req_kind": (output_value >> 73) & 0x3,
        "bus_req_addr": (output_value >> 57) & 0xFFFF,
        "bus_req_data": (output_value >> 49) & 0xFF,
        "commit_present": bool((output_value >> 48) & 0x1),
        "pc_write_valid": bool((output_value >> 47) & 0x1),
        "sp_write_valid": bool((output_value >> 46) & 0x1),
        "phase_write_valid": bool((output_value >> 45) & 0x1),
        "a_we": bool((output_value >> 44) & 0x1),
        "f_we": bool((output_value >> 43) & 0x1),
        "b_we": bool((output_value >> 42) & 0x1),
        "c_we": bool((output_value >> 41) & 0x1),
        "d_we": bool((output_value >> 40) & 0x1),
        "e_we": bool((output_value >> 39) & 0x1),
        "h_we": bool((output_value >> 38) & 0x1),
        "l_we": bool((output_value >> 37) & 0x1),
    }


def initial_state(**overrides: int) -> dict[str, int]:
    state = {
        "pc": 0x0100,
        "sp": 0xFFFE,
        "a": 0x12,
        "f": 0xB0,
        "b": 0x34,
        "c": 0x56,
        "d": 0x78,
        "e": 0x9A,
        "h": 0xC1,
        "l": 0x23,
        "ime": 0,
        "opcode": 0x00,
        "phase_kind": PHASE_FETCH,
        "phase_addr": 0,
        "phase_data": 0,
        "phase_cont_data": 0,
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
        "phase_kind": int(snapshot["next_phase_kind"]),
        "phase_addr": int(snapshot["next_phase_addr"]),
        "phase_data": int(snapshot["next_phase_data"]),
        "phase_cont_data": int(snapshot["next_phase_cont_data"]),
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
    dut.state_phase_kind_i.value = state["phase_kind"] & 0xF
    dut.state_phase_addr_i.value = state["phase_addr"] & 0xFFFF
    dut.state_phase_data_i.value = state["phase_data"] & 0xFF
    dut.state_phase_cont_data_i.value = state["phase_cont_data"] & 0xFF
    dut.bus_resp_i.value = bus_resp & 0xFF
    dut.irq_pending_i.value = irq_pending & 0x1F
    await Timer(1, units="ns")
    return decode_output(int(dut.output__.value))


def assert_only_writes(snapshot: dict[str, int | bool], *allowed: str) -> None:
    expected = {f"{name}_we" for name in allowed if name in {"a", "f", "b", "c", "d", "e", "h", "l"}}
    for field in ("a_we", "f_we", "b_we", "c_we", "d_we", "e_we", "h_we", "l_we"):
        if field in expected:
            assert snapshot[field] is True, f"expected {field} asserted"
        else:
            assert snapshot[field] is False, f"unexpected {field} asserted"


def assert_registers_hold(before: dict[str, int], after: dict[str, int | bool], *names: str) -> None:
    for name in names:
        assert int(after[f"next_{name}"]) == before[name], f"{name} changed unexpectedly"


@cocotb.test()
async def test_nop_only_advances_pc_without_arch_register_writes(dut):
    start = initial_state(a=0x42, f=0xB0, b=0x11, c=0x22, d=0x33, e=0x44, h=0x55, l=0x66, sp=0xFFF0)
    snapshot = await sample(dut, start, bus_resp=0x00)

    assert snapshot["commit_present"] is True
    assert snapshot["next_pc"] == start["pc"] + 1
    assert snapshot["pc_write_valid"] is True
    assert snapshot["sp_write_valid"] is False
    assert snapshot["phase_write_valid"] is False
    assert snapshot["bus_req_kind"] == BUS_REQ_READ
    assert snapshot["bus_req_addr"] == start["pc"]
    assert_registers_hold(start, snapshot, "a", "f", "b", "c", "d", "e", "h", "l", "sp")
    assert_only_writes(snapshot)


@cocotb.test()
async def test_targeted_write_discipline_for_load_and_alu_representatives(dut):
    ld_fetch = await sample(dut, initial_state(opcode=0x06), bus_resp=0x06)
    assert ld_fetch["next_phase_kind"] == PHASE_READ_IMM8
    assert ld_fetch["pc_write_valid"] is True
    assert ld_fetch["phase_write_valid"] is True
    assert_only_writes(ld_fetch)

    ld_done = await sample(dut, follow_state(ld_fetch), bus_resp=0x42)
    assert ld_done["next_b"] == 0x42
    assert ld_done["pc_write_valid"] is True
    assert ld_done["sp_write_valid"] is False
    assert ld_done["phase_write_valid"] is True
    assert_only_writes(ld_done, "b")
    assert_registers_hold(initial_state(opcode=0x06), ld_done, "a", "f", "c", "d", "e", "h", "l", "sp")

    add_fetch = await sample(dut, initial_state(opcode=0x80, a=0x12, b=0x34), bus_resp=0x80)
    assert add_fetch["next_phase_kind"] == PHASE_EXECUTE
    assert add_fetch["pc_write_valid"] is True
    assert add_fetch["phase_write_valid"] is True
    assert_only_writes(add_fetch)

    add_exec = await sample(dut, follow_state(add_fetch), bus_resp=0x00)
    assert add_exec["next_a"] == 0x46
    assert add_exec["next_f"] == 0x00
    assert add_exec["pc_write_valid"] is False
    assert add_exec["sp_write_valid"] is False
    assert add_exec["phase_write_valid"] is True
    assert_only_writes(add_exec, "a", "f")
    assert_registers_hold(initial_state(opcode=0x80, a=0x12, b=0x34), add_exec, "b", "c", "d", "e", "h", "l", "sp")


@cocotb.test()
async def test_multi_cycle_load_holds_arch_registers_until_read_completes(dut):
    start = initial_state(opcode=0x7E, a=0x11, h=0xC1, l=0x23)
    fetch = await sample(dut, start, bus_resp=0x7E)

    assert fetch["next_phase_kind"] == PHASE_READ_MEM
    assert fetch["next_phase_addr"] == 0xC123
    assert fetch["pc_write_valid"] is True
    assert fetch["phase_write_valid"] is True
    assert_only_writes(fetch)
    assert_registers_hold(start, fetch, "a", "f", "b", "c", "d", "e", "h", "l", "sp")

    read = await sample(dut, follow_state(fetch), bus_resp=0x5C)
    assert read["next_a"] == 0x5C
    assert read["pc_write_valid"] is False
    assert read["sp_write_valid"] is False
    assert read["phase_write_valid"] is True
    assert read["bus_req_kind"] == BUS_REQ_READ
    assert read["bus_req_addr"] == 0xC123
    assert_only_writes(read, "a")
    assert_registers_hold(start, read, "f", "b", "c", "d", "e", "h", "l", "sp")


@cocotb.test()
async def test_write_enable_duty_cycle_report_has_expected_baseline(dut):
    samples = [
        await sample(dut, initial_state(opcode=0x00), bus_resp=0x00),
    ]

    ld_fetch = await sample(dut, initial_state(opcode=0x06), bus_resp=0x06)
    samples.append(ld_fetch)
    samples.append(await sample(dut, follow_state(ld_fetch), bus_resp=0x42))

    add_fetch = await sample(dut, initial_state(opcode=0x80, a=0x12, b=0x34), bus_resp=0x80)
    samples.append(add_fetch)
    samples.append(await sample(dut, follow_state(add_fetch), bus_resp=0x00))

    mem_fetch = await sample(dut, initial_state(opcode=0x7E, h=0xC1, l=0x23), bus_resp=0x7E)
    samples.append(mem_fetch)
    samples.append(await sample(dut, follow_state(mem_fetch), bus_resp=0x5C))

    fields = ("a_we", "f_we", "b_we", "c_we", "d_we", "e_we", "h_we", "l_we", "pc_write_valid", "sp_write_valid")
    counts = {field: sum(1 for sample in samples if sample[field]) for field in fields}
    total = len(samples)

    cocotb.log.info("write_enable duty baseline over %d cycles", total)
    for field in fields:
        cocotb.log.info("  %s: %d/%d", field, counts[field], total)

    assert counts["a_we"] == 2
    assert counts["f_we"] == 1
    assert counts["b_we"] == 1
    assert counts["c_we"] == 0
    assert counts["d_we"] == 0
    assert counts["e_we"] == 0
    assert counts["h_we"] == 0
    assert counts["l_we"] == 0
    assert counts["pc_write_valid"] == 5
    assert counts["sp_write_valid"] == 0
