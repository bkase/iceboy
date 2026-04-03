# top = cpu::semantics_interrupt_test_top::semantics_interrupt_test_top
from __future__ import annotations

import cocotb
from cocotb.triggers import Timer


PHASE_FETCH = 0
PHASE_HALTED = 1
PHASE_SERVICE = 2

IRQ_VBLANK = 0
IRQ_LCD_STAT = 1
IRQ_TIMER = 2
IRQ_SERIAL = 3
IRQ_JOYPAD = 4

SUBPHASE_DELAY1 = 0
SUBPHASE_DELAY2 = 1
SUBPHASE_PUSH_PC_HI = 2
SUBPHASE_PUSH_PC_LO = 3
SUBPHASE_JUMP = 4

IME_DISABLED = 0
IME_PENDING_ENABLE = 1
IME_ENABLED = 2

HALT_RUNNING = 0
HALT_HALTED = 1

BUS_REQ_IDLE = 0
BUS_REQ_READ = 1
BUS_REQ_WRITE = 2


def decode_output(output_value: int) -> dict[str, int | bool]:
    return {
        "next_pc": (output_value >> 112) & 0xFFFF,
        "next_sp": (output_value >> 96) & 0xFFFF,
        "next_ime": (output_value >> 94) & 0x3,
        "next_halt": (output_value >> 92) & 0x3,
        "next_phase_kind": (output_value >> 88) & 0x3,
        "next_irq_sel": (output_value >> 85) & 0x7,
        "next_irq_phase": (output_value >> 82) & 0x7,
        "bus_req_kind": (output_value >> 80) & 0x3,
        "bus_req_addr": (output_value >> 64) & 0xFFFF,
        "bus_req_data": (output_value >> 56) & 0xFF,
        "pc_write_valid": bool((output_value >> 55) & 0x1),
        "pc_write": (output_value >> 39) & 0xFFFF,
        "sp_write_valid": bool((output_value >> 38) & 0x1),
        "sp_write": (output_value >> 22) & 0xFFFF,
        "irq_ack_valid": bool((output_value >> 21) & 0x1),
        "irq_ack_bit": (output_value >> 18) & 0x7,
        "commit_present": bool((output_value >> 17) & 0x1),
    }


async def sample(
    dut,
    *,
    state_pc: int = 0x0100,
    state_sp: int = 0xFFFE,
    state_ime: int = IME_DISABLED,
    state_halt: int = HALT_RUNNING,
    state_phase_kind: int = PHASE_FETCH,
    state_irq_sel: int = IRQ_VBLANK,
    state_irq_phase: int = SUBPHASE_DELAY1,
    bus_resp: int = 0x00,
    irq_pending: int = 0,
) -> dict[str, int | bool]:
    dut.state_pc_i.value = state_pc & 0xFFFF
    dut.state_sp_i.value = state_sp & 0xFFFF
    dut.state_ime_i.value = state_ime & 0x3
    dut.state_halt_i.value = state_halt & 0x3
    dut.state_phase_kind_i.value = state_phase_kind & 0x3
    dut.state_irq_sel_i.value = state_irq_sel & 0x7
    dut.state_irq_phase_i.value = state_irq_phase & 0x7
    dut.bus_resp_i.value = bus_resp & 0xFF
    dut.irq_pending_i.value = irq_pending & 0x1F
    await Timer(1, units="ns")
    return decode_output(int(dut.output__.value))


def assert_fields(actual: dict[str, int | bool], **expected: int | bool) -> None:
    for key, value in expected.items():
        assert actual[key] == value, f"{key}: expected {value!r}, got {actual[key]!r}"


@cocotb.test()
async def test_fetch_preempts_to_highest_priority_interrupt_and_acks(dut):
    snapshot = await sample(
        dut,
        state_pc=0x4567,
        state_sp=0xD000,
        state_ime=IME_ENABLED,
        state_phase_kind=PHASE_FETCH,
        irq_pending=0x14,
    )
    assert_fields(
        snapshot,
        next_pc=0x4567,
        next_sp=0xD000,
        next_ime=IME_DISABLED,
        next_halt=HALT_RUNNING,
        next_phase_kind=PHASE_SERVICE,
        next_irq_sel=IRQ_TIMER,
        next_irq_phase=SUBPHASE_DELAY1,
        bus_req_kind=BUS_REQ_IDLE,
        irq_ack_valid=True,
        irq_ack_bit=IRQ_TIMER,
        commit_present=True,
        pc_write_valid=False,
        sp_write_valid=False,
    )


@cocotb.test()
async def test_halted_entry_clears_halt_and_acks(dut):
    snapshot = await sample(
        dut,
        state_pc=0x2222,
        state_sp=0xC100,
        state_ime=IME_ENABLED,
        state_halt=HALT_HALTED,
        state_phase_kind=PHASE_HALTED,
        irq_pending=0x02,
    )
    assert_fields(
        snapshot,
        next_pc=0x2222,
        next_sp=0xC100,
        next_ime=IME_DISABLED,
        next_halt=HALT_RUNNING,
        next_phase_kind=PHASE_SERVICE,
        next_irq_sel=IRQ_LCD_STAT,
        next_irq_phase=SUBPHASE_DELAY1,
        bus_req_kind=BUS_REQ_IDLE,
        irq_ack_valid=True,
        irq_ack_bit=IRQ_LCD_STAT,
        commit_present=True,
    )


@cocotb.test()
async def test_service_delays_and_stack_push_sequence(dut):
    delay1 = await sample(
        dut,
        state_pc=0x3456,
        state_sp=0xFFFE,
        state_ime=IME_DISABLED,
        state_phase_kind=PHASE_SERVICE,
        state_irq_sel=IRQ_SERIAL,
        state_irq_phase=SUBPHASE_DELAY1,
    )
    assert_fields(
        delay1,
        next_phase_kind=PHASE_SERVICE,
        next_irq_sel=IRQ_SERIAL,
        next_irq_phase=SUBPHASE_DELAY2,
        bus_req_kind=BUS_REQ_IDLE,
        irq_ack_valid=False,
        sp_write_valid=False,
    )

    delay2 = await sample(
        dut,
        state_pc=0x3456,
        state_sp=0xFFFE,
        state_ime=IME_DISABLED,
        state_phase_kind=PHASE_SERVICE,
        state_irq_sel=IRQ_SERIAL,
        state_irq_phase=SUBPHASE_DELAY2,
    )
    assert_fields(
        delay2,
        next_phase_kind=PHASE_SERVICE,
        next_irq_sel=IRQ_SERIAL,
        next_irq_phase=SUBPHASE_PUSH_PC_HI,
        bus_req_kind=BUS_REQ_IDLE,
        irq_ack_valid=False,
        sp_write_valid=False,
    )

    push_hi = await sample(
        dut,
        state_pc=0x3456,
        state_sp=0xFFFE,
        state_ime=IME_DISABLED,
        state_phase_kind=PHASE_SERVICE,
        state_irq_sel=IRQ_SERIAL,
        state_irq_phase=SUBPHASE_PUSH_PC_HI,
    )
    assert_fields(
        push_hi,
        next_pc=0x3456,
        next_sp=0xFFFD,
        next_phase_kind=PHASE_SERVICE,
        next_irq_sel=IRQ_SERIAL,
        next_irq_phase=SUBPHASE_PUSH_PC_LO,
        bus_req_kind=BUS_REQ_WRITE,
        bus_req_addr=0xFFFD,
        bus_req_data=0x34,
        sp_write_valid=True,
        sp_write=0xFFFD,
        irq_ack_valid=False,
    )

    push_lo = await sample(
        dut,
        state_pc=0x3456,
        state_sp=0xFFFD,
        state_ime=IME_DISABLED,
        state_phase_kind=PHASE_SERVICE,
        state_irq_sel=IRQ_SERIAL,
        state_irq_phase=SUBPHASE_PUSH_PC_LO,
    )
    assert_fields(
        push_lo,
        next_pc=0x3456,
        next_sp=0xFFFC,
        next_phase_kind=PHASE_SERVICE,
        next_irq_sel=IRQ_SERIAL,
        next_irq_phase=SUBPHASE_JUMP,
        bus_req_kind=BUS_REQ_WRITE,
        bus_req_addr=0xFFFC,
        bus_req_data=0x56,
        sp_write_valid=True,
        sp_write=0xFFFC,
        irq_ack_valid=False,
    )


@cocotb.test()
async def test_jump_subphase_targets_each_vector(dut):
    for irq_sel, vector in (
        (IRQ_VBLANK, 0x0040),
        (IRQ_LCD_STAT, 0x0048),
        (IRQ_TIMER, 0x0050),
        (IRQ_SERIAL, 0x0058),
        (IRQ_JOYPAD, 0x0060),
    ):
        snapshot = await sample(
            dut,
            state_pc=0x3A00,
            state_sp=0xBFFE,
            state_ime=IME_DISABLED,
            state_phase_kind=PHASE_SERVICE,
            state_irq_sel=irq_sel,
            state_irq_phase=SUBPHASE_JUMP,
        )
        assert_fields(
            snapshot,
            next_pc=vector,
            next_sp=0xBFFE,
            next_phase_kind=PHASE_FETCH,
            bus_req_kind=BUS_REQ_IDLE,
            pc_write_valid=True,
            pc_write=vector,
            sp_write_valid=False,
            irq_ack_valid=False,
            commit_present=True,
        )
