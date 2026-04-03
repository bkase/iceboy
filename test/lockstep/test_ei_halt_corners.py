# top = sim::cpu_test_top::cpu_test_top
from __future__ import annotations

import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

import cocotb
from cocotb.triggers import Timer


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from bench.actions.generators import IeOverrideEvent, IfSetBitsEvent, ScheduledEvent, SeededEventScript
from dut_driver import CpuCommitTrace, SimStimulus
from event_script_support import stimulus_from_events
from fixtures import cpu_dut
from rom_runner import BUS_REQ_IDLE, BUS_REQ_READ, BUS_REQ_WRITE, ExternalMemoryBus
from roms.build_micro_rom import apply_rom_patches, build_rom
from spec.profiles import ResetProfile


warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")

ROM_BASE = 0x0150

IME_DISABLED = 0
IME_PENDING_ENABLE = 1
IME_ENABLED = 2

HALT_RUNNING = 0
HALT_HALTED = 1
HALT_BUG_PENDING = 2

PHASE_FETCH = 0
PHASE_HALTED = 1
PHASE_EXECUTE = 2
PHASE_SERVICE_INTERRUPT = 9

IRQ_VBLANK = 0x01
IRQ_TIMER = 0x04

VBLANK_ACK_BIT = 0
TIMER_ACK_BIT = 2


@dataclass(frozen=True)
class CycleObservation:
    index: int
    pre: CpuCommitTrace
    post: CpuCommitTrace
    bus_read_data: int
    events: tuple[object, ...]


def scheduled(commit_index: int, event: object) -> ScheduledEvent:
    return ScheduledEvent(commit_index=commit_index, event=event)


def script(name: str, *events: ScheduledEvent) -> SeededEventScript:
    return SeededEventScript(seed=0, events=tuple(events), source=name)


def build_case_rom(title: str, program: bytes, *, patches: dict[int, bytes] | None = None) -> bytes:
    rom = build_rom(title, program)
    return apply_rom_patches(rom, patches) if patches else rom


def ime_name(value: int) -> str:
    return {
        IME_DISABLED: "Disabled",
        IME_PENDING_ENABLE: "PendingEnable",
        IME_ENABLED: "Enabled",
    }.get(value, f"ime<{value}>")


def halt_name(value: int) -> str:
    return {
        HALT_RUNNING: "Running",
        HALT_HALTED: "Halted",
        HALT_BUG_PENDING: "HaltBugPending",
    }.get(value, f"halt<{value}>")


def phase_name(value: int) -> str:
    return {
        PHASE_FETCH: "Fetch",
        PHASE_HALTED: "Halted",
        PHASE_EXECUTE: "Execute",
        PHASE_SERVICE_INTERRUPT: "ServiceInterrupt",
    }.get(value, f"Phase<{value}>")


def irq_name(ack_bit: int) -> str:
    return {
        VBLANK_ACK_BIT: "VBlank",
        TIMER_ACK_BIT: "Timer",
    }.get(ack_bit, f"irq<{ack_bit}>")


def format_bus(trace: CpuCommitTrace, bus_read_data: int) -> str:
    if trace.bus_req_kind == BUS_REQ_READ:
        return f"Read(0x{trace.bus_req_addr:04X}) -> 0x{bus_read_data:02X}"
    if trace.bus_req_kind == BUS_REQ_WRITE:
        return f"Write(0x{trace.bus_req_addr:04X}, 0x{trace.bus_req_data:02X})"
    return "Idle"


def format_events(events: tuple[object, ...]) -> str:
    if not events:
        return "-"
    parts = []
    for event in events:
        kind = type(event).__name__
        if kind == "IeOverrideEvent":
            parts.append(f"IE=0x{event.value:02X}")
        elif kind == "IfSetBitsEvent":
            parts.append(f"IF|=0x{event.bits:02X}")
        else:
            parts.append(kind)
    return ", ".join(parts)


def format_cycle(obs: CycleObservation) -> str:
    ack = "-"
    if obs.pre.irq_ack_valid:
        ack = irq_name(obs.pre.irq_ack_bit)
    return (
        f"[M#{obs.index:02d}] "
        f"pre(pc=0x{obs.pre.pc:04X} phase={phase_name(obs.pre.phase_kind)} "
        f"ime={ime_name(obs.pre.ime_state)} halt={halt_name(obs.pre.halt_state)} "
        f"pending=0x{obs.pre.irq_pending:02X} ack={ack} bus={format_bus(obs.pre, obs.bus_read_data)}) "
        f"events={format_events(obs.events)} "
        f"-> post(pc=0x{obs.post.pc:04X} phase={phase_name(obs.post.phase_kind)} "
        f"ime={ime_name(obs.post.ime_state)} halt={halt_name(obs.post.halt_state)} "
        f"pending=0x{obs.post.irq_pending:02X})"
    )


def format_trace(trace: list[CycleObservation]) -> str:
    return "\n".join(format_cycle(obs) for obs in trace)


def require(condition: bool, trace: list[CycleObservation], message: str) -> None:
    if not condition:
        raise AssertionError(f"{message}\n{format_trace(trace)}")


def first_index(trace: list[CycleObservation], predicate) -> int | None:
    for obs in trace:
        if predicate(obs):
            return obs.index
    return None


def ack_indices(trace: list[CycleObservation], ack_bit: int) -> list[int]:
    return [obs.index for obs in trace if obs.pre.irq_ack_valid and obs.pre.irq_ack_bit == ack_bit]


async def boot_driver(dut, rom_bytes: bytes):
    driver = cpu_dut(dut)
    await driver.reset(ResetProfile.SkipBoot)
    await Timer(1, units="ns")
    return driver, ExternalMemoryBus(rom_bytes)


async def collect_case_trace(
    dut,
    rom_bytes: bytes,
    event_script: SeededEventScript,
    *,
    capture_cycles: int,
    start_addr: int = ROM_BASE,
) -> list[CycleObservation]:
    driver, memory = await boot_driver(dut, rom_bytes)
    trace: list[CycleObservation] = []
    started = False
    local_index = 0

    for _ in range(256):
        pre = driver.observe()
        if not started and pre.bus_req_kind == BUS_REQ_READ and pre.bus_req_addr == start_addr:
            started = True

        events = event_script.events_for_commit(local_index) if started else ()
        stimulus = stimulus_from_events(events) if started else SimStimulus.idle()
        bus_read_data = memory.read(pre.bus_req_addr) if pre.bus_req_kind == BUS_REQ_READ else 0
        pending_write = (pre.bus_req_addr, pre.bus_req_data) if pre.bus_req_kind == BUS_REQ_WRITE else None
        post = await driver.step_mcycle(stimulus=stimulus, bus_read_data=bus_read_data, irq_pending=0)
        if pending_write is not None:
            memory.write(pending_write[0], pending_write[1])
        await Timer(1, units="ns")

        if not started:
            continue

        trace.append(
            CycleObservation(
                index=local_index,
                pre=pre,
                post=post,
                bus_read_data=bus_read_data,
                events=tuple(events),
            )
        )
        local_index += 1
        if local_index >= capture_cycles:
            break

    require(bool(trace), trace, f"never reached program entry 0x{start_addr:04X}")
    return trace


@cocotb.test()
async def test_ei_halt_services_after_halt_enters_stopped_window(dut):
    trace = await collect_case_trace(
        dut,
        build_case_rom("EIHALT1", bytes([0xFB, 0x76, 0x00, 0x18, 0xFE])),
        script(
            "ei_halt",
            scheduled(0, IeOverrideEvent(value=IRQ_TIMER)),
            scheduled(3, IfSetBitsEvent(bits=IRQ_TIMER)),
        ),
        capture_cycles=8,
    )

    require(trace[1].pre.ime_state == IME_PENDING_ENABLE, trace, "EI should leave the next fetch pending-enabled")
    require(trace[2].pre.phase_kind == PHASE_EXECUTE, trace, "HALT should execute in its own m-cycle")
    require(trace[2].pre.ime_state == IME_PENDING_ENABLE, trace, "HALT execute must still see PendingEnable")
    require(trace[3].pre.phase_kind == PHASE_HALTED, trace, "HALT should enter the halted phase before service")
    require(trace[3].pre.halt_state == HALT_HALTED, trace, "HALT should latch halted state")
    require(trace[3].pre.ime_state == IME_ENABLED, trace, "IME should become enabled only after HALT has started")
    require(trace[4].pre.phase_kind == PHASE_HALTED, trace, "interrupt should wake from the halted phase")
    require(trace[4].pre.irq_pending == IRQ_TIMER, trace, "timer IF should be visible one cycle after injection")
    require(trace[4].pre.irq_ack_valid and trace[4].pre.irq_ack_bit == TIMER_ACK_BIT, trace, "halt wake should ack timer")
    require(trace[5].pre.phase_kind == PHASE_SERVICE_INTERRUPT, trace, "halt wake should enter interrupt service")
    require(trace[5].pre.ime_state == IME_DISABLED, trace, "service entry should disable IME")


@cocotb.test()
async def test_ei_nop_halt_enables_before_halt_and_services_one_cycle_later(dut):
    trace = await collect_case_trace(
        dut,
        build_case_rom("EINOPHALT", bytes([0xFB, 0x00, 0x76, 0x00, 0x18, 0xFE])),
        script(
            "ei_nop_halt",
            scheduled(0, IeOverrideEvent(value=IRQ_TIMER)),
            scheduled(4, IfSetBitsEvent(bits=IRQ_TIMER)),
        ),
        capture_cycles=9,
    )

    require(trace[1].pre.ime_state == IME_PENDING_ENABLE, trace, "EI should set PendingEnable immediately")
    require(trace[2].pre.ime_state == IME_ENABLED, trace, "NOP should complete the delayed EI enable")
    require(trace[3].pre.phase_kind == PHASE_EXECUTE, trace, "HALT should still consume an execute m-cycle")
    require(trace[3].pre.ime_state == IME_ENABLED, trace, "HALT should begin after IME is fully enabled")
    require(trace[4].pre.phase_kind == PHASE_HALTED, trace, "HALT should park in the halted phase")
    require(first_index(trace, lambda obs: obs.pre.irq_ack_valid and obs.pre.irq_ack_bit == TIMER_ACK_BIT) == 5, trace, "timer service should start one cycle after IF is injected into the halted state")


@cocotb.test()
async def test_di_halt_with_pending_interrupt_triggers_halt_bug_without_service(dut):
    trace = await collect_case_trace(
        dut,
        build_case_rom("DIHALT", bytes([0xF3, 0x76, 0x00, 0x18, 0xFE])),
        script(
            "di_halt_pending",
            scheduled(0, IeOverrideEvent(value=IRQ_TIMER)),
            scheduled(0, IfSetBitsEvent(bits=IRQ_TIMER)),
        ),
        capture_cycles=7,
    )

    require(trace[1].pre.irq_pending == IRQ_TIMER, trace, "pending interrupt should already be visible by HALT fetch")
    require(trace[2].pre.phase_kind == PHASE_EXECUTE, trace, "HALT should still execute once before wake")
    require(trace[2].pre.ime_state == IME_DISABLED, trace, "DI should keep IME disabled")
    require(trace[3].pre.phase_kind == PHASE_FETCH, trace, "halt bug should replay the following fetch without entering halted")
    require(trace[3].pre.halt_state == HALT_BUG_PENDING, trace, "halt bug state should be visible on the replayed fetch")
    require(trace[3].pre.bus_req_kind == BUS_REQ_READ and trace[3].pre.bus_req_addr == ROM_BASE + 2, trace, "halt bug should fetch the next opcode once without incrementing PC")
    require(trace[4].pre.phase_kind == PHASE_FETCH, trace, "normal fetch should resume after the replayed opcode")
    require(trace[4].pre.halt_state == HALT_RUNNING, trace, "halt bug should clear after the replayed fetch")
    require(trace[4].pre.bus_req_kind == BUS_REQ_READ and trace[4].pre.bus_req_addr == ROM_BASE + 2, trace, "normal fetch should then refetch the same byte and advance PC")
    require(first_index(trace, lambda obs: obs.pre.irq_ack_valid) is None, trace, "no interrupt service should start while IME is disabled")
    require(any(obs.pre.bus_req_kind == BUS_REQ_READ and obs.pre.bus_req_addr == ROM_BASE + 3 for obs in trace[5:]), trace, "execution should resume past the duplicated opcode after the halt bug replay")


@cocotb.test()
async def test_ei_interrupt_pending_during_next_instruction_fires_before_halt_fetch(dut):
    halt_addr = ROM_BASE + 2
    trace = await collect_case_trace(
        dut,
        build_case_rom("EIBEFHALT", bytes([0xFB, 0x00, 0x76, 0x00, 0x18, 0xFE])),
        script(
            "ei_interrupt_before_halt",
            scheduled(0, IeOverrideEvent(value=IRQ_TIMER)),
            scheduled(1, IfSetBitsEvent(bits=IRQ_TIMER)),
        ),
        capture_cycles=7,
    )

    require(trace[2].pre.phase_kind == PHASE_FETCH, trace, "interrupt should become visible on the fetch after the delayed-enable instruction")
    require(trace[2].pre.ime_state == IME_ENABLED, trace, "IME should be enabled by the time the following fetch starts")
    require(trace[2].pre.irq_pending == IRQ_TIMER, trace, "timer IF should be pending on the following fetch")
    require(trace[2].pre.irq_ack_valid and trace[2].pre.irq_ack_bit == TIMER_ACK_BIT, trace, "interrupt should preempt the HALT fetch")
    require(trace[3].pre.phase_kind == PHASE_SERVICE_INTERRUPT, trace, "interrupt should enter service before HALT executes")
    require(first_index(trace, lambda obs: obs.pre.phase_kind == PHASE_EXECUTE) is None, trace, "HALT must never reach execute when the interrupt wins the following fetch")
    require(all(not (obs.pre.bus_req_kind == BUS_REQ_READ and obs.pre.bus_req_addr == halt_addr) for obs in trace[2:]), trace, "HALT opcode fetch should be suppressed once the interrupt becomes serviceable")


@cocotb.test()
async def test_reti_reenables_ime_and_allows_immediate_refire_before_mainline_fetch(dut):
    trace = await collect_case_trace(
        dut,
        build_case_rom(
            "RETIREFIRE",
            bytes([0xFB, 0x76, 0x00, 0x18, 0xFE]),
            patches={0x0040: bytes([0xD9])},
        ),
        script(
            "reti_refire",
            scheduled(0, IeOverrideEvent(value=IRQ_VBLANK | IRQ_TIMER)),
            scheduled(3, IfSetBitsEvent(bits=IRQ_VBLANK)),
            scheduled(8, IfSetBitsEvent(bits=IRQ_TIMER)),
        ),
        capture_cycles=22,
    )

    vblank_acks = ack_indices(trace, VBLANK_ACK_BIT)
    timer_acks = ack_indices(trace, TIMER_ACK_BIT)
    require(vblank_acks == [4], trace, "first interrupt should be the initial vblank wake from HALT")
    require(len(timer_acks) == 1, trace, "timer should refire exactly once after RETI")
    reti_fetch_index = first_index(trace, lambda obs: obs.pre.bus_req_kind == BUS_REQ_READ and obs.pre.bus_req_addr == 0x0040)
    require(reti_fetch_index is not None, trace, "first handler must fetch RETI from the vblank vector")
    require(timer_acks[0] > reti_fetch_index, trace, "second interrupt should not service until after RETI has executed")
    require(all(not (obs.pre.bus_req_kind == BUS_REQ_READ and obs.pre.bus_req_addr == ROM_BASE + 2) for obs in trace[reti_fetch_index: timer_acks[0]]), trace, "immediate refire should happen before mainline execution resumes after RETI")


@cocotb.test()
async def test_nested_interrupts_can_reenter_from_handler_ei_halt(dut):
    trace = await collect_case_trace(
        dut,
        build_case_rom(
            "NESTIRQ",
            bytes([0xFB, 0x76, 0x00, 0x18, 0xFE]),
            patches={
                0x0040: bytes([0xFB, 0x76, 0xD9]),
                0x0050: bytes([0xD9]),
            },
        ),
        script(
            "nested_interrupts",
            scheduled(0, IeOverrideEvent(value=IRQ_VBLANK | IRQ_TIMER)),
            scheduled(3, IfSetBitsEvent(bits=IRQ_VBLANK)),
            scheduled(13, IfSetBitsEvent(bits=IRQ_TIMER)),
        ),
        capture_cycles=32,
    )

    require(ack_indices(trace, VBLANK_ACK_BIT) == [4], trace, "outer vblank interrupt should service first")
    require(ack_indices(trace, TIMER_ACK_BIT) == [14], trace, "timer should wake the handler's EI+HALT loop")
    require(trace[13].pre.phase_kind == PHASE_HALTED, trace, "handler should be halted before the nested timer arrives")
    require(trace[13].pre.ime_state == IME_ENABLED, trace, "handler EI should fully enable IME before nested wake")
    require(any(obs.pre.bus_req_kind == BUS_REQ_READ and obs.pre.bus_req_addr == 0x0042 for obs in trace[15:]), trace, "nested RETI should return to the outer handler RETI instruction")


@cocotb.test()
async def test_if_set_during_service_stays_pending_until_handler_reti_completes(dut):
    trace = await collect_case_trace(
        dut,
        build_case_rom(
            "IFSVCPEND",
            bytes([0xFB, 0x76, 0x00, 0x18, 0xFE]),
            patches={
                0x0040: bytes([0xD9]),
                0x0050: bytes([0xD9]),
            },
        ),
        script(
            "if_during_service",
            scheduled(0, IeOverrideEvent(value=IRQ_VBLANK | IRQ_TIMER)),
            scheduled(3, IfSetBitsEvent(bits=IRQ_VBLANK)),
            scheduled(6, IfSetBitsEvent(bits=IRQ_TIMER)),
        ),
        capture_cycles=24,
    )

    second_pending_index = first_index(trace, lambda obs: obs.pre.phase_kind == PHASE_SERVICE_INTERRUPT and obs.pre.irq_pending == IRQ_TIMER)
    second_ack_index = first_index(trace, lambda obs: obs.pre.irq_ack_valid and obs.pre.irq_ack_bit == TIMER_ACK_BIT)
    reti_fetch_index = first_index(trace, lambda obs: obs.pre.bus_req_kind == BUS_REQ_READ and obs.pre.bus_req_addr == 0x0040)
    require(second_pending_index is not None, trace, "timer IF should become visible while the first interrupt is still being serviced")
    require(reti_fetch_index is not None, trace, "service should eventually fetch the RETI handler")
    require(second_ack_index is not None, trace, "timer interrupt should eventually be acknowledged")
    require(second_pending_index < reti_fetch_index < second_ack_index, trace, "timer IF should remain pending through service and only ack after RETI re-enables IME")
