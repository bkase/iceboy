# top = cpu::semantics_test_top::semantics_test_top
import cocotb
from cocotb.triggers import Timer


def decode_output(output_value: int) -> dict[str, int | bool]:
    return {
        "apply_pc": (output_value >> 112) & 0xFFFF,
        "apply_sp": (output_value >> 96) & 0xFFFF,
        "apply_a": (output_value >> 88) & 0xFF,
        "apply_f": (output_value >> 80) & 0xFF,
        "apply_phase": (output_value >> 78) & 0x3,
        "apply_opcode": (output_value >> 70) & 0xFF,
        "step_commit_present": bool((output_value >> 69) & 0x1),
        "step_bus_req_kind": (output_value >> 67) & 0x3,
        "step_bus_req_addr": (output_value >> 51) & 0xFFFF,
        "step_pc_write_valid": bool((output_value >> 50) & 0x1),
        "step_pc_write": (output_value >> 34) & 0xFFFF,
        "step_phase_write_valid": bool((output_value >> 33) & 0x1),
        "step_phase_write": (output_value >> 31) & 0x3,
        "step_opcode_write_valid": bool((output_value >> 30) & 0x1),
        "step_opcode_write": (output_value >> 22) & 0xFF,
    }


async def sample(
    dut,
    *,
    state_pc: int = 0x0100,
    state_sp: int = 0xFFFE,
    state_a: int = 0x12,
    state_f: int = 0xA0,
    state_opcode: int = 0x00,
    state_phase: int = 0,
    bus_resp: int = 0xA5,
    irq_pending: int = 0,
    delta_a_we: bool = False,
    delta_a: int = 0,
    delta_f_we: bool = False,
    delta_f: int = 0,
    delta_pc_we: bool = False,
    delta_pc: int = 0,
    delta_phase_we: bool = False,
    delta_phase: int = 0,
    delta_opcode_we: bool = False,
    delta_opcode: int = 0,
) -> dict[str, int | bool]:
    dut.state_pc_i.value = state_pc & 0xFFFF
    dut.state_sp_i.value = state_sp & 0xFFFF
    dut.state_a_i.value = state_a & 0xFF
    dut.state_f_i.value = state_f & 0xFF
    dut.state_opcode_i.value = state_opcode & 0xFF
    dut.state_phase_i.value = state_phase & 0x3
    dut.bus_resp_i.value = bus_resp & 0xFF
    dut.irq_pending_i.value = irq_pending & 0x1F
    dut.delta_a_we_i.value = int(delta_a_we)
    dut.delta_a_i.value = delta_a & 0xFF
    dut.delta_f_we_i.value = int(delta_f_we)
    dut.delta_f_i.value = delta_f & 0xFF
    dut.delta_pc_we_i.value = int(delta_pc_we)
    dut.delta_pc_i.value = delta_pc & 0xFFFF
    dut.delta_phase_we_i.value = int(delta_phase_we)
    dut.delta_phase_i.value = delta_phase & 0x3
    dut.delta_opcode_we_i.value = int(delta_opcode_we)
    dut.delta_opcode_i.value = delta_opcode & 0xFF
    await Timer(1, units="ns")
    return decode_output(int(dut.output__.value))


@cocotb.test()
async def test_apply_delta_updates_only_selected_fields_and_masks_f(dut):
    snapshot = await sample(
        dut,
        state_pc=0x1234,
        state_sp=0xABCD,
        state_a=0x11,
        state_f=0x80,
        state_opcode=0x44,
        state_phase=0,
        delta_a_we=True,
        delta_a=0x7E,
        delta_f_we=True,
        delta_f=0x5F,
        delta_pc_we=True,
        delta_pc=0x4567,
        delta_phase_we=True,
        delta_phase=1,
        delta_opcode_we=True,
        delta_opcode=0x9A,
    )

    assert snapshot["apply_pc"] == 0x4567
    assert snapshot["apply_sp"] == 0xABCD
    assert snapshot["apply_a"] == 0x7E
    assert snapshot["apply_f"] == 0x50
    assert snapshot["apply_phase"] == 1
    assert snapshot["apply_opcode"] == 0x9A


@cocotb.test()
async def test_step_mcycle_fetch_issues_read_and_advances_pc_delta(dut):
    snapshot = await sample(dut, state_pc=0x0100, state_phase=0, bus_resp=0xC3)

    assert snapshot["step_commit_present"] is True
    assert snapshot["step_bus_req_kind"] == 1
    assert snapshot["step_bus_req_addr"] == 0x0100
    assert snapshot["step_pc_write_valid"] is True
    assert snapshot["step_pc_write"] == 0x0101
    assert snapshot["step_phase_write_valid"] is False
    assert snapshot["step_opcode_write_valid"] is True
    assert snapshot["step_opcode_write"] == 0xC3


@cocotb.test()
async def test_step_mcycle_halted_holds_state_and_bus_quiet(dut):
    snapshot = await sample(dut, state_pc=0x0200, state_phase=1, bus_resp=0x55)

    assert snapshot["step_commit_present"] is True
    assert snapshot["step_bus_req_kind"] == 0
    assert snapshot["step_bus_req_addr"] == 0
    assert snapshot["step_pc_write_valid"] is False
    assert snapshot["step_phase_write_valid"] is False
    assert snapshot["step_opcode_write_valid"] is False
