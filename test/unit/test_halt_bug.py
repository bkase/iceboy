# top = cpu::semantics_misc_test_top::semantics_misc_test_top
import cocotb
from cocotb.triggers import Timer


PHASE_FETCH = 0
PHASE_HALTED = 1
PHASE_EXECUTE = 2
PHASE_READ_IMM8 = 3
IME_DISABLED = 0
IME_ENABLED = 2
HALT_RUNNING = 0
HALT_HALTED = 1
HALT_BUG_PENDING = 2
BUS_REQ_IDLE = 0
BUS_REQ_READ = 1


def decode_output(output_value: int) -> dict[str, int | bool]:
    return {
        "next_pc": (output_value >> 112) & 0xFFFF,
        "next_ime": (output_value >> 78) & 0x3,
        "next_halt": (output_value >> 76) & 0x3,
        "next_phase_kind": (output_value >> 72) & 0xF,
        "next_opcode": (output_value >> 64) & 0xFF,
        "bus_req_kind": (output_value >> 62) & 0x3,
        "bus_req_addr": (output_value >> 46) & 0xFFFF,
        "commit_present": bool((output_value >> 45) & 0x1),
        "pc_write_valid": bool((output_value >> 44) & 0x1),
        "pc_write": (output_value >> 28) & 0xFFFF,
    }


async def sample(
    dut,
    *,
    state_pc: int,
    state_ime: int = IME_DISABLED,
    state_halt: int = HALT_RUNNING,
    state_phase: int,
    bus_resp: int,
    irq_pending: int = 0,
) -> dict[str, int | bool]:
    dut.state_pc_i.value = state_pc & 0xFFFF
    dut.state_sp_i.value = 0xFFFE
    dut.state_a_i.value = 0x12
    dut.state_f_i.value = 0xA0
    dut.state_ime_i.value = state_ime & 0x3
    dut.state_halt_i.value = state_halt & 0x3
    dut.state_phase_i.value = state_phase & 0xF
    dut.bus_resp_i.value = bus_resp & 0xFF
    dut.irq_pending_i.value = irq_pending & 0x1F
    await Timer(1, units="ns")
    return decode_output(int(dut.output__.value))


def assert_fields(name: str, actual: dict[str, int | bool], **expected: int | bool) -> None:
    for key, value in expected.items():
        assert actual[key] == value, f"{name}: {key} expected {value!r} got {actual[key]!r}"


@cocotb.test()
async def test_halt_execute_sets_halt_bug_pending_when_ime_disabled_and_no_irq_pending(dut):
    actual = await sample(dut, state_pc=0x0701, state_phase=PHASE_EXECUTE, bus_resp=0x76)
    assert_fields(
        "halt_bug_enter",
        actual,
        next_pc=0x0701,
        next_ime=IME_DISABLED,
        next_halt=HALT_BUG_PENDING,
        next_phase_kind=PHASE_FETCH,
        bus_req_kind=BUS_REQ_IDLE,
        commit_present=True,
        pc_write_valid=False,
    )


@cocotb.test()
async def test_halt_bug_fetch_replays_single_byte_opcode_without_incrementing_pc(dut):
    actual = await sample(
        dut,
        state_pc=0x0701,
        state_halt=HALT_BUG_PENDING,
        state_phase=PHASE_FETCH,
        bus_resp=0x00,
    )
    assert_fields(
        "halt_bug_nop",
        actual,
        next_pc=0x0701,
        next_halt=HALT_RUNNING,
        next_phase_kind=PHASE_FETCH,
        next_opcode=0x00,
        bus_req_kind=BUS_REQ_READ,
        bus_req_addr=0x0701,
        commit_present=True,
        pc_write_valid=False,
    )


@cocotb.test()
async def test_halt_bug_only_duplicates_first_byte_of_multi_byte_instruction(dut):
    actual = await sample(
        dut,
        state_pc=0x0702,
        state_halt=HALT_BUG_PENDING,
        state_phase=PHASE_FETCH,
        bus_resp=0x3E,
    )
    assert_fields(
        "halt_bug_ld_a_d8",
        actual,
        next_pc=0x0702,
        next_halt=HALT_RUNNING,
        next_phase_kind=PHASE_READ_IMM8,
        next_opcode=0x3E,
        bus_req_kind=BUS_REQ_READ,
        bus_req_addr=0x0702,
        commit_present=True,
        pc_write_valid=False,
    )


@cocotb.test()
async def test_halt_bug_does_not_trigger_when_ime_enabled(dut):
    actual = await sample(
        dut,
        state_pc=0x0703,
        state_ime=IME_ENABLED,
        state_phase=PHASE_EXECUTE,
        bus_resp=0x76,
    )
    assert_fields(
        "halt_normal_ime_enabled",
        actual,
        next_pc=0x0703,
        next_ime=IME_ENABLED,
        next_halt=HALT_HALTED,
        next_phase_kind=PHASE_HALTED,
        bus_req_kind=BUS_REQ_IDLE,
        commit_present=True,
        pc_write_valid=False,
    )


@cocotb.test()
async def test_halt_bug_does_not_trigger_when_irq_is_already_pending(dut):
    actual = await sample(
        dut,
        state_pc=0x0704,
        state_phase=PHASE_EXECUTE,
        bus_resp=0x76,
        irq_pending=0x04,
    )
    assert_fields(
        "halt_normal_pending_irq",
        actual,
        next_pc=0x0704,
        next_ime=IME_DISABLED,
        next_halt=HALT_HALTED,
        next_phase_kind=PHASE_HALTED,
        bus_req_kind=BUS_REQ_IDLE,
        commit_present=True,
        pc_write_valid=False,
    )
