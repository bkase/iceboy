# top = sim::cpu_test_top::cpu_test_top
from __future__ import annotations

from dataclasses import dataclass
import sys
from pathlib import Path

import cocotb
from cocotb.triggers import ReadOnly, Timer


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from dut_driver import CpuCommitTrace, SimStimulus
from fixtures import cpu_dut
from rom_runner import BUS_REQ_IDLE, BUS_REQ_READ, BUS_REQ_WRITE, ExternalMemoryBus
from roms.build_micro_rom import apply_rom_patches, build_rom
from spec.profiles import ResetProfile


ROM_BASE = 0x0150

IME_ENABLED = 2

HALT_HALTED = 1
HALT_RUNNING = 0

PHASE_HALTED = 1
PHASE_SERVICE_INTERRUPT = 9

IRQ_TIMER = 0x04
TIMER_ACK_BIT = 2

QUIESCENT_CYCLES = 6


@dataclass(frozen=True)
class HaltSnapshot:
    index: int
    pre: CpuCommitTrace
    arch_state: str
    micro_state: str
    next_state: str
    step_value: str
    commit_seq_internal: int
    bus_read_data: int


def build_case_rom() -> bytes:
    rom = build_rom("HALTQUIE", bytes([0xFB, 0x00, 0x76, 0x00, 0x18, 0xFE]))
    return apply_rom_patches(rom, {0x0050: bytes([0xD9])})


async def boot_driver(dut):
    driver = cpu_dut(dut)
    await driver.reset(ResetProfile.SkipBoot)
    await Timer(1, units="ns")
    return driver


async def sample_snapshot(dut, driver, *, index: int, bus_read_data: int) -> HaltSnapshot:
    await ReadOnly()
    snapshot = HaltSnapshot(
        index=index,
        pre=driver.observe(),
        arch_state=str(dut.cpu_core_0.arch_state.value),
        micro_state=str(dut.cpu_core_0.micro_state.value),
        next_state=str(dut.cpu_core_0.next_state.value),
        step_value=str(dut.cpu_core_0.step.value),
        commit_seq_internal=int(dut.cpu_core_0.commit_seq.value),
        bus_read_data=bus_read_data,
    )
    await Timer(1, units="ps")
    return snapshot


def format_bus(trace: CpuCommitTrace, bus_read_data: int) -> str:
    if trace.bus_req_kind == BUS_REQ_READ:
        return f"Read(0x{trace.bus_req_addr:04X}) -> 0x{bus_read_data:02X}"
    if trace.bus_req_kind == BUS_REQ_WRITE:
        return f"Write(0x{trace.bus_req_addr:04X}, 0x{trace.bus_req_data:02X})"
    return "Idle"


def _short_bits(value: str, *, keep: int = 16) -> str:
    if len(value) <= keep * 2:
        return value
    return f"{value[:keep]}...{value[-keep:]}"


def format_snapshot(snapshot: HaltSnapshot) -> str:
    pre = snapshot.pre
    return (
        f"[M#{snapshot.index:02d}] "
        f"pc=0x{pre.pc:04X} phase={pre.phase_kind} halt={pre.halt_state} ime={pre.ime_state} "
        f"pending=0x{pre.irq_pending:02X} ack={int(pre.irq_ack_valid)}:{pre.irq_ack_bit} "
        f"bus={format_bus(pre, snapshot.bus_read_data)} "
        f"arch={_short_bits(snapshot.arch_state)} micro={_short_bits(snapshot.micro_state)} "
        f"next={_short_bits(snapshot.next_state)} step={_short_bits(snapshot.step_value)} "
        f"commit_seq={snapshot.commit_seq_internal}"
    )


def format_trace(trace: list[HaltSnapshot]) -> str:
    return "\n".join(format_snapshot(snapshot) for snapshot in trace)


def require(condition: bool, trace: list[HaltSnapshot], message: str) -> None:
    if condition:
        return
    raise AssertionError(f"{message}\n{format_trace(trace)}")


def drive_memory(memory: ExternalMemoryBus, pre: CpuCommitTrace) -> tuple[int, tuple[int, int] | None]:
    bus_read_data = memory.read(pre.bus_req_addr) if pre.bus_req_kind == BUS_REQ_READ else 0
    pending_write = (pre.bus_req_addr, pre.bus_req_data) if pre.bus_req_kind == BUS_REQ_WRITE else None
    return bus_read_data, pending_write


@cocotb.test()
async def test_halt_quiescence_holds_state_idle_until_timer_wake(dut):
    driver = await boot_driver(dut)
    memory = ExternalMemoryBus(build_case_rom())
    trace: list[HaltSnapshot] = []
    halted_window: list[HaltSnapshot] = []
    halted_baseline: HaltSnapshot | None = None
    started = False
    injected_wake = False
    ack_seen = False
    service_seen = False
    local_index = 0

    for _ in range(96):
        visible = driver.observe()
        bus_read_data = memory.read(visible.bus_req_addr) if visible.bus_req_kind == BUS_REQ_READ else 0
        snapshot = await sample_snapshot(dut, driver, index=local_index, bus_read_data=bus_read_data)
        pre = snapshot.pre

        if not started and pre.bus_req_kind == BUS_REQ_READ and pre.bus_req_addr == ROM_BASE:
            started = True

        if not started:
            post = await driver.step_mcycle(
                stimulus=SimStimulus(ie_override=IRQ_TIMER),
                bus_read_data=bus_read_data,
                irq_pending=0,
            )
            if pre.bus_req_kind == BUS_REQ_WRITE:
                memory.write(pre.bus_req_addr, pre.bus_req_data)
            await Timer(1, units="ps")
            local_index += 1
            continue

        trace.append(snapshot)

        if halted_baseline is None and pre.phase_kind == PHASE_HALTED and pre.halt_state == HALT_HALTED:
            halted_baseline = snapshot

        if halted_baseline is not None and not injected_wake and pre.phase_kind == PHASE_HALTED and pre.halt_state == HALT_HALTED:
            halted_window.append(snapshot)
            require(pre.bus_req_kind == BUS_REQ_IDLE, trace, "HALT window must leave the external bus idle")
            require(pre.pc == halted_baseline.pre.pc, trace, "HALT window must keep PC stable")
            require(pre.irq_pending == 0, trace, "HALT window should not arm a wake before the trigger")
            require(pre.irq_ack_valid is False, trace, "HALT window should not acknowledge interrupts before the wake")
            require(pre.ime_state == IME_ENABLED, trace, "HALT window should hold IME enabled after EI+NOP")
            require(snapshot.arch_state == halted_baseline.arch_state, trace, "HALT window must not mutate architectural state")
            require(snapshot.micro_state == halted_baseline.micro_state, trace, "HALT window must keep the micro-state latched")
            require(snapshot.next_state == halted_baseline.next_state, trace, "HALT window next-state projection must stay fixed")
            require(snapshot.step_value == halted_baseline.step_value, trace, "HALT window micro-step/debug output must stay stable")

        stimulus = SimStimulus(ie_override=IRQ_TIMER)
        if halted_baseline is not None and not injected_wake and len(halted_window) >= QUIESCENT_CYCLES:
            stimulus = SimStimulus(ie_override=IRQ_TIMER, if_set_bits=IRQ_TIMER)
            injected_wake = True

        bus_read_data, pending_write = drive_memory(memory, pre)
        post = await driver.step_mcycle(stimulus=stimulus, bus_read_data=bus_read_data, irq_pending=0)
        if pending_write is not None:
            memory.write(pending_write[0], pending_write[1])
        await Timer(1, units="ps")

        if injected_wake and not ack_seen:
            ack_seen = (
                pre.phase_kind == PHASE_HALTED
                and pre.halt_state == HALT_HALTED
                and pre.irq_pending == IRQ_TIMER
                and pre.irq_ack_valid
                and pre.irq_ack_bit == TIMER_ACK_BIT
            )
        elif ack_seen and not service_seen:
            service_seen = (
                pre.phase_kind == PHASE_SERVICE_INTERRUPT
                and pre.halt_state == HALT_RUNNING
                and pre.ime_state != IME_ENABLED
            )

        if service_seen:
            break

        local_index += 1

    require(started, trace, f"never fetched program entry at 0x{ROM_BASE:04X}")
    require(halted_baseline is not None, trace, "program never entered the halted phase")
    require(len(halted_window) >= QUIESCENT_CYCLES, trace, f"expected at least {QUIESCENT_CYCLES} halted quiescent cycles")
    require(ack_seen, trace, "timer wake should acknowledge from the halted phase")
    require(service_seen, trace, "timer wake should transition into interrupt service on the following cycle")
