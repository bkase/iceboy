# top = cpu::semantics_load_test_top::semantics_load_test_top
from __future__ import annotations

import sys
from pathlib import Path

import cocotb
from cocotb.triggers import Timer

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spec.sm83_opcodes import UNPREFIXED_BY_OPCODE


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
        "f": 0xB0,
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


def assert_untouched_registers(
    before: dict[str, int],
    after: dict[str, int | bool],
    *,
    changed: frozenset[str],
    scope: str,
) -> None:
    for name in ("a", "f", "b", "c", "d", "e", "h", "l", "sp"):
        if name in changed:
            continue
        assert int(after[f"next_{name}"]) == before[name], (
            f"{scope}: expected {name} unchanged at 0x{before[name]:X}, got 0x{int(after[f'next_{name}']):X}"
        )


def assert_f_low_nibble_zero(snapshot: dict[str, int | bool], scope: str) -> None:
    assert (int(snapshot["next_f"]) & 0x0F) == 0, f"{scope}: F low nibble must remain zero"


@cocotb.test()
async def test_ld_b_n8_only_touches_target_register_and_pc(dut):
    metadata = UNPREFIXED_BY_OPCODE[0x06]
    assert metadata.family == "load"
    assert metadata.cycles_tstates == (8,)

    start = initial_state()
    fetch = await sample(dut, start, bus_resp=0x06)
    assert_f_low_nibble_zero(fetch, "LD B,n8 fetch")
    writeback = await sample(dut, follow_state(fetch), bus_resp=0x42)

    assert int(writeback["next_b"]) == 0x42
    assert int(writeback["next_pc"]) == start["pc"] + metadata.length_bytes
    assert_untouched_registers(start, writeback, changed=frozenset({"b"}), scope="LD B,n8")
    assert_f_low_nibble_zero(writeback, "LD B,n8 writeback")


@cocotb.test()
async def test_ld_a_from_hl_preserves_untouched_registers(dut):
    metadata = UNPREFIXED_BY_OPCODE[0x7E]
    assert metadata.family == "memory_load"
    assert metadata.cycles_tstates == (8,)

    start = initial_state(a=0x11, h=0xC1, l=0x23)
    fetch = await sample(dut, start, bus_resp=0x7E)
    assert_f_low_nibble_zero(fetch, "LD A,(HL) fetch")
    readback = await sample(dut, follow_state(fetch), bus_resp=0x5C)

    assert int(readback["next_a"]) == 0x5C
    assert int(readback["next_pc"]) == start["pc"] + metadata.length_bytes
    assert_untouched_registers(start, readback, changed=frozenset({"a"}), scope="LD A,(HL)")
    assert_f_low_nibble_zero(readback, "LD A,(HL) readback")


@cocotb.test()
async def test_ld_hl_n_writes_memory_only_on_documented_final_mcycle(dut):
    metadata = UNPREFIXED_BY_OPCODE[0x36]
    assert metadata.family == "memory_load"
    assert metadata.cycles_tstates == (12,)
    expected_mcycles = metadata.cycles_tstates[0] // 4
    assert expected_mcycles == 3

    start = initial_state(h=0xD0, l=0x44)
    fetch = await sample(dut, start, bus_resp=0x36)
    imm = await sample(dut, follow_state(fetch), bus_resp=0xAB)
    write = await sample(dut, follow_state(imm), bus_resp=0x00)

    assert int(fetch["bus_req_kind"]) == 1
    assert int(imm["bus_req_kind"]) == 1
    assert int(write["bus_req_kind"]) == 2
    assert int(write["bus_req_addr"]) == 0xD044
    assert int(write["bus_req_data"]) == 0xAB
    assert int(write["next_pc"]) == start["pc"] + metadata.length_bytes
    assert_untouched_registers(start, write, changed=frozenset(), scope="LD (HL),n8")
    assert_f_low_nibble_zero(fetch, "LD (HL),n8 fetch")
    assert_f_low_nibble_zero(imm, "LD (HL),n8 imm")
    assert_f_low_nibble_zero(write, "LD (HL),n8 write")
