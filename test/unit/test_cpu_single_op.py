# top = sim::cpu_test_top::cpu_test_top
from __future__ import annotations

import sys
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path

import cocotb
from cocotb.triggers import ReadOnly, Timer


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from assertions import assert_registers_match, format_register_diff
from bench.pyboy.oracle import CommitPoint, PyBoyOracle, RegisterState
from dut_driver import SimStimulus
from fixtures import cpu_dut
from rom_runner import BUS_REQ_IDLE, BUS_REQ_READ, BUS_REQ_WRITE, ExternalMemoryBus
from roms.build_micro_rom import build_rom
from spec.sm83_opcodes import CB_PREFIXED_BY_OPCODE, UNPREFIXED_BY_OPCODE
from spec.profiles import ModelProfile, ResetProfile


warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")

ROM_BASE = 0x0150


@dataclass(frozen=True)
class ExpectedBusCycle:
    kind: int
    addr: int
    data: int | None = None
    resp: int | None = None


@dataclass(frozen=True)
class SingleOpCase:
    title: str
    scope: str
    program: bytes
    target_pc: int
    commit_addr: int
    expected_mcycles: int
    expected_bus: tuple[ExpectedBusCycle, ...] = ()
    expected_wram: tuple[tuple[int, int], ...] = ()
    expected_registers: RegisterState | None = None


@dataclass(frozen=True)
class ObservedBusCycle:
    pc_before: int
    kind: int
    addr: int
    data: int
    resp: int
    pc_after: int


def decode_dut_registers(arch_state_value: int) -> RegisterState:
    regs = (arch_state_value >> 4) & ((1 << 96) - 1)
    return RegisterState(
        a=(regs >> 88) & 0xFF,
        f=(regs >> 80) & 0xFF,
        b=(regs >> 72) & 0xFF,
        c=(regs >> 64) & 0xFF,
        d=(regs >> 56) & 0xFF,
        e=(regs >> 48) & 0xFF,
        hl=(regs >> 32) & 0xFFFF,
        sp=(regs >> 16) & 0xFFFF,
        pc=regs & 0xFFFF,
    )


def unprefixed_case(
    *,
    title: str,
    scope: str,
    setup: bytes,
    target: bytes,
    opcode: int,
    cycle_variant: int = 0,
    expected_steps: int | None = None,
    expected_bus: tuple[ExpectedBusCycle, ...] = (),
    expected_wram: tuple[tuple[int, int], ...] = (),
    expected_registers: RegisterState | None = None,
) -> SingleOpCase:
    metadata = UNPREFIXED_BY_OPCODE[opcode]
    target_pc = ROM_BASE + len(setup)
    commit_addr = target_pc + metadata.length_bytes
    return SingleOpCase(
        title=title,
        scope=scope,
        program=setup + target + bytes([0x00, 0x18, 0xFE]),
        target_pc=target_pc,
        commit_addr=commit_addr,
        expected_mcycles=expected_steps if expected_steps is not None else metadata.cycles_tstates[cycle_variant] // 4,
        expected_bus=expected_bus,
        expected_wram=expected_wram,
        expected_registers=expected_registers,
    )


def cb_case(
    *,
    title: str,
    scope: str,
    setup: bytes,
    cb_opcode: int,
    expected_steps: int | None = None,
    expected_registers: RegisterState | None = None,
) -> SingleOpCase:
    metadata = CB_PREFIXED_BY_OPCODE[cb_opcode]
    target_pc = ROM_BASE + len(setup)
    return SingleOpCase(
        title=title,
        scope=scope,
        program=setup + bytes([0xCB, cb_opcode, 0x00, 0x18, 0xFE]),
        target_pc=target_pc,
        commit_addr=target_pc + metadata.length_bytes,
        expected_mcycles=expected_steps if expected_steps is not None else metadata.cycles_tstates[0] // 4,
        expected_registers=expected_registers,
    )


def build_case_rom(case: SingleOpCase) -> bytes:
    return build_rom(case.title, case.program)


def format_bus_cycle(cycle: ObservedBusCycle) -> str:
    if cycle.kind == BUS_REQ_READ:
        bus = f"Read(0x{cycle.addr:04X}) -> 0x{cycle.resp:02X}"
    elif cycle.kind == BUS_REQ_WRITE:
        bus = f"Write(0x{cycle.addr:04X}, 0x{cycle.data:02X})"
    else:
        bus = "Idle"
    return f"pc_before=0x{cycle.pc_before:04X} bus={bus} pc_after=0x{cycle.pc_after:04X}"


def format_cycle_log(cycles: list[ObservedBusCycle]) -> str:
    return "\n".join(
        f"  [M-CYCLE {index}] {format_bus_cycle(cycle)}"
        for index, cycle in enumerate(cycles, start=1)
    )


def assert_bus_matches(case: SingleOpCase, observed: list[ObservedBusCycle]) -> None:
    if not case.expected_bus:
        return
    actual = observed[: len(case.expected_bus)]
    if len(actual) != len(case.expected_bus):
        raise AssertionError(
            f"{case.scope}: expected {len(case.expected_bus)} bus cycles, saw {len(actual)}\n{format_cycle_log(observed)}"
        )
    for index, (expected, cycle) in enumerate(zip(case.expected_bus, actual, strict=True), start=1):
        if expected.kind != cycle.kind or expected.addr != cycle.addr:
            raise AssertionError(
                f"{case.scope}: bus cycle {index} mismatch\n"
                f"expected kind={expected.kind} addr=0x{expected.addr:04X}\n"
                f"actual   kind={cycle.kind} addr=0x{cycle.addr:04X}\n"
                f"{format_cycle_log(observed)}"
            )
        if expected.data is not None and expected.data != cycle.data:
            raise AssertionError(
                f"{case.scope}: bus cycle {index} data mismatch expected=0x{expected.data:02X} actual=0x{cycle.data:02X}\n"
                f"{format_cycle_log(observed)}"
            )
        if expected.resp is not None and expected.resp != cycle.resp:
            raise AssertionError(
                f"{case.scope}: bus cycle {index} response mismatch expected=0x{expected.resp:02X} actual=0x{cycle.resp:02X}\n"
                f"{format_cycle_log(observed)}"
            )


def oracle_expected(case: SingleOpCase, rom_bytes: bytes) -> RegisterState:
    with tempfile.TemporaryDirectory() as tmpdir:
        rom_path = Path(tmpdir) / f"{case.title.lower()}.gb"
        sym_path = rom_path.with_suffix(".sym")
        rom_path.write_bytes(rom_bytes)
        sym_path.write_text(
            f"00:{case.commit_addr:04X} __target_commit\n",
            encoding="utf-8",
        )
        with PyBoyOracle(
            rom_path,
            sym_path=sym_path,
            commit_points=(CommitPoint(bank=0, addr=case.commit_addr, label="__target_commit"),),
        ) as oracle:
            oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)
            return oracle.step_commit().registers_after


async def run_case(dut, case: SingleOpCase) -> tuple[RegisterState, RegisterState, list[ObservedBusCycle], ExternalMemoryBus]:
    rom_bytes = build_case_rom(case)
    driver = cpu_dut(dut)
    await driver.reset(ResetProfile.SkipBoot)
    await Timer(1, units="ns")

    memory = ExternalMemoryBus(rom_bytes)
    observed: list[ObservedBusCycle] = []
    collecting = False
    remaining = case.expected_mcycles

    for _ in range(64):
        pre = driver.observe()
        bus_read_data = memory.read(pre.bus_req_addr) if pre.bus_req_kind == BUS_REQ_READ else 0
        pending_write = None
        if pre.bus_req_kind == BUS_REQ_WRITE:
            pending_write = (pre.bus_req_addr, pre.bus_req_data)
        if not collecting and pre.bus_req_kind == BUS_REQ_READ and pre.bus_req_addr == case.target_pc:
            collecting = True

        post = await driver.step_mcycle(
            stimulus=SimStimulus.idle(),
            bus_read_data=bus_read_data,
            irq_pending=0,
        )
        if pending_write is not None:
            memory.write(pending_write[0], pending_write[1])
        await Timer(1, units="ns")

        if not collecting:
            continue

        observed.append(
            ObservedBusCycle(
                pc_before=pre.pc,
                kind=pre.bus_req_kind,
                addr=pre.bus_req_addr,
                data=pre.bus_req_data,
                resp=bus_read_data,
                pc_after=post.pc,
            )
        )
        remaining -= 1
        if remaining == 0:
            break

    if not collecting:
        raise AssertionError(f"{case.scope}: never fetched target opcode at 0x{case.target_pc:04X}")
    if remaining != 0:
        raise AssertionError(
            f"{case.scope}: expected {case.expected_mcycles} m-cycles, only captured {len(observed)}\n"
            f"{format_cycle_log(observed)}"
        )

    await ReadOnly()
    actual = decode_dut_registers(int(dut.cpu_core_0.arch_state.value))
    await Timer(1, units="ps")
    expected = oracle_expected(case, rom_bytes)
    return expected, actual, observed, memory


async def assert_case_matches_oracle(dut, case: SingleOpCase) -> None:
    expected, actual, observed, memory = await run_case(dut, case)
    if case.expected_registers is not None and expected != case.expected_registers:
        raise AssertionError(
            f"{case.scope}: oracle sanity mismatch\n"
            f"{format_register_diff(case.expected_registers, expected)}"
        )
    try:
        assert_registers_match(expected, actual, case.scope)
    except AssertionError as exc:
        raise AssertionError(f"{exc}\n{format_cycle_log(observed)}") from exc
    assert_bus_matches(case, observed)
    for addr, value in case.expected_wram:
        actual_value = memory.read(addr)
        if actual_value != value:
            raise AssertionError(
                f"{case.scope}: WRAM mismatch at 0x{addr:04X} expected=0x{value:02X} actual=0x{actual_value:02X}\n"
                f"{format_cycle_log(observed)}"
            )


LD_B_N8 = unprefixed_case(
    title="SOP_LDB",
    scope="single_op.ld_b_n8",
    setup=b"",
    target=bytes([0x06, 0x42]),
    opcode=0x06,
    expected_registers=RegisterState(a=0x01, f=0xB0, b=0x42, c=0x13, d=0x00, e=0xD8, hl=0x014D, sp=0xFFFE, pc=0x0152),
)

LD_HL_N8 = unprefixed_case(
    title="SOP_STHL",
    scope="single_op.ld_hl_n8",
    setup=bytes([0x21, 0x34, 0xC1]),
    target=bytes([0x36, 0xAB]),
    opcode=0x36,
    expected_bus=(
        ExpectedBusCycle(kind=BUS_REQ_READ, addr=0x0153, resp=0x36),
        ExpectedBusCycle(kind=BUS_REQ_READ, addr=0x0154, resp=0xAB),
        ExpectedBusCycle(kind=BUS_REQ_WRITE, addr=0xC134, data=0xAB),
    ),
    expected_wram=((0xC134, 0xAB),),
    expected_registers=RegisterState(a=0x01, f=0xB0, b=0x00, c=0x13, d=0x00, e=0xD8, hl=0xC134, sp=0xFFFE, pc=0x0155),
)

POP_AF_MASKS_LOW_NIBBLE = unprefixed_case(
    title="SOP_POPAF",
    scope="single_op.pop_af_masks_low_nibble",
    setup=bytes([0x31, 0x00, 0xC1, 0x21, 0xFF, 0x3F, 0xE5]),
    target=bytes([0xF1]),
    opcode=0xF1,
    expected_registers=RegisterState(a=0x3F, f=0xF0, b=0x00, c=0x13, d=0x00, e=0xD8, hl=0x3FFF, sp=0xC100, pc=0x0158),
)

RLCA_ZERO_CLEARS_Z = unprefixed_case(
    title="SOP_RLCA",
    scope="single_op.rlca_zero_clears_z",
    setup=bytes([0x3E, 0x00]),
    target=bytes([0x07]),
    opcode=0x07,
    expected_steps=2,
    expected_registers=RegisterState(a=0x00, f=0x00, b=0x00, c=0x13, d=0x00, e=0xD8, hl=0x014D, sp=0xFFFE, pc=0x0153),
)

CB_RLC_A_ZERO_SETS_Z = cb_case(
    title="SOP_CBRLCA",
    scope="single_op.cb_rlc_a_zero_sets_z",
    setup=bytes([0x3E, 0x00]),
    cb_opcode=0x07,
    expected_registers=RegisterState(a=0x00, f=0x80, b=0x00, c=0x13, d=0x00, e=0xD8, hl=0x014D, sp=0xFFFE, pc=0x0154),
)

ADD_SP_E8_NEGATIVE = unprefixed_case(
    title="SOP_ADDSP",
    scope="single_op.add_sp_e8_negative",
    setup=b"",
    target=bytes([0xE8, 0xF8]),
    opcode=0xE8,
    expected_registers=RegisterState(a=0x01, f=0x30, b=0x00, c=0x13, d=0x00, e=0xD8, hl=0x014D, sp=0xFFF6, pc=0x0152),
)

DEC_B = unprefixed_case(
    title="SOP_DECB",
    scope="single_op.dec_b",
    setup=bytes([0x06, 0x10]),
    target=bytes([0x05]),
    opcode=0x05,
    expected_steps=2,
)

ADD_A_B = unprefixed_case(
    title="SOP_ADDB",
    scope="single_op.add_a_b",
    setup=bytes([0x06, 0x01]),
    target=bytes([0x80]),
    opcode=0x80,
    expected_steps=2,
)

AND_A_B = unprefixed_case(
    title="SOP_ANDB",
    scope="single_op.and_a_b",
    setup=bytes([0x06, 0x0F, 0x3E, 0xF0]),
    target=bytes([0xA0]),
    opcode=0xA0,
    expected_steps=2,
)

XOR_A_B = unprefixed_case(
    title="SOP_XORB",
    scope="single_op.xor_a_b",
    setup=bytes([0x06, 0xFF]),
    target=bytes([0xA8]),
    opcode=0xA8,
    expected_steps=2,
)

OR_A_B = unprefixed_case(
    title="SOP_ORB",
    scope="single_op.or_a_b",
    setup=bytes([0x06, 0x80]),
    target=bytes([0xB0]),
    opcode=0xB0,
    expected_steps=2,
)

CP_A_B = unprefixed_case(
    title="SOP_CPB",
    scope="single_op.cp_a_b",
    setup=bytes([0x06, 0x01]),
    target=bytes([0xB8]),
    opcode=0xB8,
    expected_steps=2,
)

DAA_AFTER_ADD = unprefixed_case(
    title="SOP_DAAADD",
    scope="single_op.daa_after_add",
    setup=bytes([0x3E, 0x09, 0xC6, 0x09]),
    target=bytes([0x27]),
    opcode=0x27,
    expected_steps=2,
    expected_registers=RegisterState(a=0x18, f=0x00, b=0x00, c=0x13, d=0x00, e=0xD8, hl=0x014D, sp=0xFFFE, pc=0x0155),
)

DAA_AFTER_SUB = unprefixed_case(
    title="SOP_DAASUB",
    scope="single_op.daa_after_sub",
    setup=bytes([0x3E, 0x10, 0xD6, 0x01]),
    target=bytes([0x27]),
    opcode=0x27,
    expected_steps=2,
    expected_registers=RegisterState(a=0x09, f=0x40, b=0x00, c=0x13, d=0x00, e=0xD8, hl=0x014D, sp=0xFFFE, pc=0x0155),
)

JR_NZ_NOT_TAKEN = unprefixed_case(
    title="SOP_JRNZ",
    scope="single_op.jr_nz_not_taken",
    setup=b"",
    target=bytes([0x20, 0x02]),
    opcode=0x20,
    cycle_variant=0,
    expected_registers=RegisterState(a=0x01, f=0xB0, b=0x00, c=0x13, d=0x00, e=0xD8, hl=0x014D, sp=0xFFFE, pc=0x0152),
)

JR_Z_TAKEN = SingleOpCase(
    title="SOP_JRZ",
    scope="single_op.jr_z_taken",
    program=bytes([0x28, 0x02, 0x00, 0x00, 0x00, 0x18, 0xFE]),
    target_pc=ROM_BASE,
    commit_addr=ROM_BASE + 4,
    expected_mcycles=UNPREFIXED_BY_OPCODE[0x28].cycles_tstates[1] // 4,
    expected_registers=RegisterState(a=0x01, f=0xB0, b=0x00, c=0x13, d=0x00, e=0xD8, hl=0x014D, sp=0xFFFE, pc=0x0154),
)

INC_HL_RMW = unprefixed_case(
    title="SOP_INCHL",
    scope="single_op.inc_hl_rmw",
    setup=bytes([0x21, 0x23, 0xC1, 0x36, 0x0F]),
    target=bytes([0x34]),
    opcode=0x34,
    expected_steps=4,
    expected_bus=(
        ExpectedBusCycle(kind=BUS_REQ_READ, addr=0x0155, resp=0x34),
        ExpectedBusCycle(kind=BUS_REQ_READ, addr=0xC123, resp=0x0F),
        ExpectedBusCycle(kind=BUS_REQ_IDLE, addr=0x0000),
        ExpectedBusCycle(kind=BUS_REQ_WRITE, addr=0xC123, data=0x10),
    ),
    expected_wram=((0xC123, 0x10),),
    expected_registers=RegisterState(a=0x01, f=0x30, b=0x00, c=0x13, d=0x00, e=0xD8, hl=0xC123, sp=0xFFFE, pc=0x0156),
)


@cocotb.test()
async def test_ld_b_n8_matches_pyboy_oracle(dut):
    await assert_case_matches_oracle(dut, LD_B_N8)


@cocotb.test()
async def test_ld_hl_n8_writes_correct_address_and_data(dut):
    await assert_case_matches_oracle(dut, LD_HL_N8)


@cocotb.test()
async def test_pop_af_masks_f_low_nibble(dut):
    await assert_case_matches_oracle(dut, POP_AF_MASKS_LOW_NIBBLE)


@cocotb.test()
async def test_rlca_keeps_z_cleared_for_zero_input(dut):
    await assert_case_matches_oracle(dut, RLCA_ZERO_CLEARS_Z)


@cocotb.test()
async def test_cb_rlc_a_sets_z_for_zero_input(dut):
    await assert_case_matches_oracle(dut, CB_RLC_A_ZERO_SETS_Z)


@cocotb.test()
async def test_add_sp_e8_negative_matches_pyboy_oracle(dut):
    await assert_case_matches_oracle(dut, ADD_SP_E8_NEGATIVE)


@cocotb.test()
async def test_dec_b_matches_pyboy_oracle(dut):
    await assert_case_matches_oracle(dut, DEC_B)


@cocotb.test()
async def test_add_a_b_matches_pyboy_oracle(dut):
    await assert_case_matches_oracle(dut, ADD_A_B)


@cocotb.test()
async def test_and_a_b_matches_pyboy_oracle(dut):
    await assert_case_matches_oracle(dut, AND_A_B)


@cocotb.test()
async def test_xor_a_b_matches_pyboy_oracle(dut):
    await assert_case_matches_oracle(dut, XOR_A_B)


@cocotb.test()
async def test_or_a_b_matches_pyboy_oracle(dut):
    await assert_case_matches_oracle(dut, OR_A_B)


@cocotb.test()
async def test_cp_a_b_matches_pyboy_oracle(dut):
    await assert_case_matches_oracle(dut, CP_A_B)


@cocotb.test()
async def test_daa_matches_pyboy_after_add_and_subtract_paths(dut):
    await assert_case_matches_oracle(dut, DAA_AFTER_ADD)
    await assert_case_matches_oracle(dut, DAA_AFTER_SUB)


@cocotb.test()
async def test_conditional_jr_uses_taken_and_not_taken_cycle_counts(dut):
    await assert_case_matches_oracle(dut, JR_NZ_NOT_TAKEN)
    await assert_case_matches_oracle(dut, JR_Z_TAKEN)


@cocotb.test()
async def test_inc_hl_uses_read_modify_write_bus_sequence(dut):
    await assert_case_matches_oracle(dut, INC_HL_RMW)
