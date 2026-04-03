# top = cpu::semantics_misc_test_top::semantics_misc_test_top
import cocotb
from cocotb.triggers import Timer


PHASE_FETCH = 0
PHASE_HALTED = 1
PHASE_EXECUTE = 2
PHASE_SERVICE_INTERRUPT = 9
IME_DISABLED = 0
IME_PENDING_ENABLE = 1
IME_ENABLED = 2
HALT_RUNNING = 0
HALT_HALTED = 1
BUS_REQ_READ = 1
BUS_REQ_IDLE = 0


def decode_output(output_value: int) -> dict[str, int | bool]:
    return {
        "next_pc": (output_value >> 112) & 0xFFFF,
        "next_sp": (output_value >> 96) & 0xFFFF,
        "next_a": (output_value >> 88) & 0xFF,
        "next_f": (output_value >> 80) & 0xFF,
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
    state_pc: int = 0x0100,
    state_sp: int = 0xFFFE,
    state_a: int = 0x12,
    state_f: int = 0xA0,
    state_ime: int = IME_DISABLED,
    state_halt: int = HALT_RUNNING,
    state_phase: int = PHASE_FETCH,
    bus_resp: int,
    irq_pending: int = 0,
) -> dict[str, int | bool]:
    dut.state_pc_i.value = state_pc & 0xFFFF
    dut.state_sp_i.value = state_sp & 0xFFFF
    dut.state_a_i.value = state_a & 0xFF
    dut.state_f_i.value = state_f & 0xFF
    dut.state_ime_i.value = state_ime & 0x3
    dut.state_halt_i.value = state_halt & 0x3
    dut.state_phase_i.value = state_phase & 0xF
    dut.bus_resp_i.value = bus_resp & 0xFF
    dut.irq_pending_i.value = irq_pending & 0x1F
    await Timer(1, units="ns")
    return decode_output(int(dut.output__.value))


def log_case(name: str, expected: dict[str, int | bool], actual: dict[str, int | bool]) -> None:
    diff = {
        key: {"expected": expected[key], "actual": actual[key]}
        for key in expected
        if actual.get(key) != expected[key]
    }
    cocotb.log.info("instruction=%s expected=%s actual=%s diff=%s", name, expected, actual, diff or "none")


def assert_snapshot(name: str, expected: dict[str, int | bool], actual: dict[str, int | bool]) -> None:
    log_case(name, expected, actual)
    for key, value in expected.items():
        assert actual[key] == value, f"{name}: {key} expected {value:#x} got {actual[key]!r}"


@cocotb.test()
async def test_nop_completes_pending_ei_enable(dut):
    actual = await sample(dut, state_pc=0x0100, state_a=0x34, state_f=0xB0, state_ime=IME_PENDING_ENABLE, bus_resp=0x00)
    expected = {
        "next_pc": 0x0101,
        "next_sp": 0xFFFE,
        "next_a": 0x34,
        "next_f": 0xB0,
        "next_ime": IME_ENABLED,
        "next_halt": HALT_RUNNING,
        "next_phase_kind": PHASE_FETCH,
        "next_opcode": 0x00,
        "bus_req_kind": BUS_REQ_READ,
        "bus_req_addr": 0x0100,
        "commit_present": True,
        "pc_write_valid": True,
        "pc_write": 0x0101,
    }
    assert_snapshot("NOP", expected, actual)


@cocotb.test()
async def test_di_disables_ime_immediately(dut):
    actual = await sample(dut, state_pc=0x0200, state_ime=2, bus_resp=0xF3)
    expected = {
        "next_pc": 0x0201,
        "next_ime": IME_DISABLED,
        "next_halt": HALT_RUNNING,
        "next_phase_kind": PHASE_FETCH,
        "next_opcode": 0xF3,
        "bus_req_kind": BUS_REQ_READ,
        "bus_req_addr": 0x0200,
        "commit_present": True,
        "pc_write_valid": True,
        "pc_write": 0x0201,
    }
    assert_snapshot("DI", expected, actual)


@cocotb.test()
async def test_ei_marks_pending_enable_immediately(dut):
    actual = await sample(dut, state_pc=0x0201, state_ime=IME_DISABLED, bus_resp=0xFB)
    expected = {
        "next_pc": 0x0202,
        "next_ime": IME_PENDING_ENABLE,
        "next_halt": HALT_RUNNING,
        "next_phase_kind": PHASE_FETCH,
        "next_opcode": 0xFB,
        "bus_req_kind": BUS_REQ_READ,
        "bus_req_addr": 0x0201,
        "commit_present": True,
        "pc_write_valid": True,
        "pc_write": 0x0202,
    }
    assert_snapshot("EI", expected, actual)


@cocotb.test()
async def test_stop_stub_behaves_like_two_byte_nop(dut):
    actual = await sample(dut, state_pc=0x0300, state_a=0x56, state_f=0x80, bus_resp=0x10)
    expected = {
        "next_pc": 0x0302,
        "next_sp": 0xFFFE,
        "next_a": 0x56,
        "next_f": 0x80,
        "next_ime": IME_DISABLED,
        "next_halt": HALT_RUNNING,
        "next_phase_kind": PHASE_FETCH,
        "next_opcode": 0x10,
        "bus_req_kind": BUS_REQ_READ,
        "bus_req_addr": 0x0300,
        "commit_present": True,
        "pc_write_valid": True,
        "pc_write": 0x0302,
    }
    assert_snapshot("STOP", expected, actual)


@cocotb.test()
async def test_misc_alu_controls_route_into_execute_phase(dut):
    for opcode, name in ((0x27, "DAA"), (0x2F, "CPL"), (0x37, "SCF"), (0x3F, "CCF")):
        actual = await sample(dut, state_pc=0x0400, bus_resp=opcode)
        expected = {
            "next_pc": 0x0401,
            "next_phase_kind": PHASE_EXECUTE,
            "next_opcode": opcode,
            "bus_req_kind": BUS_REQ_READ,
            "bus_req_addr": 0x0400,
            "commit_present": True,
            "pc_write_valid": True,
            "pc_write": 0x0401,
        }
        assert_snapshot(name, expected, actual)


@cocotb.test()
async def test_halt_fetch_routes_into_execute_phase(dut):
    actual = await sample(dut, state_pc=0x0500, state_ime=IME_DISABLED, bus_resp=0x76)
    expected = {
        "next_pc": 0x0501,
        "next_ime": IME_DISABLED,
        "next_halt": HALT_RUNNING,
        "next_phase_kind": PHASE_EXECUTE,
        "next_opcode": 0x76,
        "bus_req_kind": BUS_REQ_READ,
        "bus_req_addr": 0x0500,
        "commit_present": True,
        "pc_write_valid": True,
        "pc_write": 0x0501,
    }
    assert_snapshot("HALT_FETCH", expected, actual)


@cocotb.test()
async def test_halt_execute_enters_halted_state(dut):
    actual = await sample(
        dut,
        state_pc=0x0501,
        state_ime=IME_DISABLED,
        state_halt=HALT_RUNNING,
        state_phase=PHASE_EXECUTE,
        bus_resp=0x76,
    )
    expected = {
        "next_pc": 0x0501,
        "next_ime": IME_DISABLED,
        "next_halt": HALT_HALTED,
        "next_phase_kind": PHASE_HALTED,
        "bus_req_kind": BUS_REQ_IDLE,
        "bus_req_addr": 0x0000,
        "commit_present": True,
        "pc_write_valid": False,
    }
    assert_snapshot("HALT_EXECUTE", expected, actual)


@cocotb.test()
async def test_halted_state_stays_quiet_without_pending_irq(dut):
    actual = await sample(
        dut,
        state_pc=0x0600,
        state_ime=IME_DISABLED,
        state_halt=HALT_HALTED,
        state_phase=PHASE_HALTED,
        bus_resp=0xAA,
        irq_pending=0,
    )
    expected = {
        "next_pc": 0x0600,
        "next_ime": IME_DISABLED,
        "next_halt": HALT_HALTED,
        "next_phase_kind": PHASE_HALTED,
        "bus_req_kind": BUS_REQ_IDLE,
        "bus_req_addr": 0x0000,
        "commit_present": True,
        "pc_write_valid": False,
    }
    assert_snapshot("HALT_IDLE", expected, actual)


@cocotb.test()
async def test_halted_state_resumes_fetch_when_pending_irq_and_ime_disabled(dut):
    actual = await sample(
        dut,
        state_pc=0x0601,
        state_ime=IME_DISABLED,
        state_halt=HALT_HALTED,
        state_phase=PHASE_HALTED,
        bus_resp=0x00,
        irq_pending=0x04,
    )
    expected = {
        "next_pc": 0x0601,
        "next_ime": IME_DISABLED,
        "next_halt": HALT_RUNNING,
        "next_phase_kind": PHASE_FETCH,
        "bus_req_kind": BUS_REQ_IDLE,
        "bus_req_addr": 0x0000,
        "commit_present": True,
        "pc_write_valid": False,
    }
    assert_snapshot("HALT_WAKE_DISABLED", expected, actual)


@cocotb.test()
async def test_halted_state_transitions_to_service_when_pending_irq_and_ime_enabled(dut):
    actual = await sample(
        dut,
        state_pc=0x0602,
        state_ime=IME_ENABLED,
        state_halt=HALT_HALTED,
        state_phase=PHASE_HALTED,
        bus_resp=0x00,
        irq_pending=0x04,
    )
    expected = {
        "next_pc": 0x0602,
        "next_ime": IME_DISABLED,
        "next_halt": HALT_RUNNING,
        "next_phase_kind": PHASE_SERVICE_INTERRUPT,
        "bus_req_kind": BUS_REQ_IDLE,
        "bus_req_addr": 0x0000,
        "commit_present": True,
        "pc_write_valid": False,
    }
    assert_snapshot("HALT_WAKE_ENABLED", expected, actual)
