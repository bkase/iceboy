# top = sim::cpu_test_top::cpu_test_top
from __future__ import annotations

from dataclasses import dataclass
import sys
import warnings
from pathlib import Path

import cocotb
from cocotb.triggers import Timer


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from bench.actions.generators import IeOverrideEvent, IfClearBitsEvent, IfSetBitsEvent, ScheduledEvent, SeededEventScript
from dut_driver import CpuCommitTrace, SimStimulus
from event_script_support import stimulus_from_events
from fixtures import cpu_dut
from rom_runner import BUS_REQ_IDLE, BUS_REQ_READ, BUS_REQ_WRITE, DIV_ADDR, ExternalMemoryBus, IE_ADDR, IF_ADDR, TAC_ADDR, TIMA_ADDR, TMA_ADDR
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
    ie: int
    iflags: int
    div: int
    tima: int
    tma: int
    tac: int


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
        elif kind == "IfClearBitsEvent":
            parts.append(f"IF&=~0x{event.bits:02X}")
        else:
            parts.append(kind)
    return ", ".join(parts)


def format_cycle(obs: CycleObservation) -> str:
    ack = "-"
    if obs.pre.irq_ack_valid:
        ack = irq_name(obs.pre.irq_ack_bit)
    return (
        f"[CYCLE {obs.index:02d}] "
        f"pre(pc=0x{obs.pre.pc:04X} phase={phase_name(obs.pre.phase_kind)} "
        f"ime={ime_name(obs.pre.ime_state)} halt={halt_name(obs.pre.halt_state)} "
        f"pending=0x{obs.pre.irq_pending:02X} ack={ack} bus={format_bus(obs.pre, obs.bus_read_data)} "
        f"io(IF=0x{obs.iflags:02X} IE=0x{obs.ie:02X} DIV=0x{obs.div:02X} TIMA=0x{obs.tima:02X} TMA=0x{obs.tma:02X} TAC=0x{obs.tac:02X})) "
        f"events={format_events(obs.events)} "
        f"-> post(pc=0x{obs.post.pc:04X} phase={phase_name(obs.post.phase_kind)} "
        f"ime={ime_name(obs.post.ime_state)} halt={halt_name(obs.post.halt_state)} "
        f"pending=0x{obs.post.irq_pending:02X})"
    )


def format_scenario_trace(
    scenario: str,
    *,
    setup: str,
    inject: str,
    trace: list[CycleObservation],
    passed: bool,
) -> str:
    lines = [
        f"[SCENARIO] {scenario}",
        f"[SETUP] {setup}",
        f"[INJECT] {inject}",
    ]
    lines.extend(format_cycle(obs) for obs in trace)
    lines.append(f"[{'PASS' if passed else 'FAIL'}] {scenario}")
    return "\n".join(lines)


def require_scenario(
    condition: bool,
    *,
    scenario: str,
    setup: str,
    inject: str,
    trace: list[CycleObservation],
    message: str,
) -> None:
    if condition:
        return
    raise AssertionError(f"{message}\n{format_scenario_trace(scenario, setup=setup, inject=inject, trace=trace, passed=False)}")


def first_index(trace: list[CycleObservation], predicate) -> int | None:
    for obs in trace:
        if predicate(obs):
            return obs.index
    return None


def ack_indices(trace: list[CycleObservation], ack_bit: int) -> list[int]:
    return [obs.index for obs in trace if obs.pre.irq_ack_valid and obs.pre.irq_ack_bit == ack_bit]


def build_case_rom(title: str, program: bytes, *, patches: dict[int, bytes] | None = None) -> bytes:
    rom = build_rom(title, program)
    return apply_rom_patches(rom, patches or {})


def scheduled(commit_index: int, event: object) -> ScheduledEvent:
    return ScheduledEvent(commit_index=commit_index, event=event)


def script(name: str, *events: ScheduledEvent) -> SeededEventScript:
    return SeededEventScript(seed=0, events=tuple(events), source=name)


async def step_with_memory(driver, memory: ExternalMemoryBus, stimulus: SimStimulus) -> object:
    pre = driver.observe()
    bus_read_data = memory.read(pre.bus_req_addr) if pre.bus_req_kind == BUS_REQ_READ else 0
    pending_write = None
    if pre.bus_req_kind == BUS_REQ_WRITE:
        pending_write = (pre.bus_req_addr, pre.bus_req_data)
    post = await driver.step_mcycle(stimulus=stimulus, bus_read_data=bus_read_data, irq_pending=0)
    if pending_write is not None:
        memory.write(pending_write[0], pending_write[1])
    return post


def _merge_stimulus(base: SimStimulus, *, if_set_bits: int) -> SimStimulus:
    return SimStimulus(
        joyp_buttons=base.joyp_buttons,
        if_set_bits=(base.if_set_bits | if_set_bits) & 0x1F,
        if_clear_bits=base.if_clear_bits,
        ie_override=base.ie_override,
        dma_start=base.dma_start,
        serial_inject=base.serial_inject,
        freeze_arch_time=base.freeze_arch_time,
        cpu_hold_only=base.cpu_hold_only,
    )


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

    for _ in range(512):
        pre = driver.observe()
        if not started and pre.bus_req_kind == BUS_REQ_READ and pre.bus_req_addr == start_addr:
            started = True

        events = event_script.events_for_commit(local_index) if started else ()
        base_stimulus = stimulus_from_events(events) if started else SimStimulus.idle()
        ie = memory.read(IE_ADDR)
        iflags = memory.read(IF_ADDR)
        div = memory.read(DIV_ADDR)
        tima = memory.read(TIMA_ADDR)
        tma = memory.read(TMA_ADDR)
        tac = memory.read(TAC_ADDR)
        bus_read_data = memory.read(pre.bus_req_addr) if pre.bus_req_kind == BUS_REQ_READ else 0
        write_en = pre.bus_req_kind == BUS_REQ_WRITE
        write_addr = pre.bus_req_addr if write_en else 0
        write_data = pre.bus_req_data if write_en else 0
        if_set_bits = memory.next_if_set_bits(write_en=write_en, write_addr=write_addr, write_data=write_data)
        pending_write = (pre.bus_req_addr, pre.bus_req_data) if write_en else None
        post = await driver.step_mcycle(
            stimulus=_merge_stimulus(base_stimulus, if_set_bits=if_set_bits),
            bus_read_data=bus_read_data,
            irq_pending=0,
        )
        if pending_write is not None and write_addr not in (0xFF04, 0xFF05, 0xFF06, 0xFF07, 0xFF0F, 0xFFFF):
            memory.write(pending_write[0], pending_write[1])
        memory.advance_cycle(
            write_en=write_en,
            write_addr=write_addr,
            write_data=write_data,
            if_set_bits=(base_stimulus.if_set_bits | if_set_bits) & 0x1F,
            irq_ack_valid=bool(pre.irq_ack_valid),
            irq_ack_bit=pre.irq_ack_bit,
        )
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
                ie=ie,
                iflags=iflags,
                div=div,
                tima=tima,
                tma=tma,
                tac=tac,
            )
        )
        local_index += 1
        if local_index >= capture_cycles:
            break

    if not trace:
        raise AssertionError(f"never reached program entry 0x{start_addr:04X}")
    return trace


@cocotb.test()
async def test_interrupt_injection_if_set_and_clear_via_stimulus(dut):
    driver, memory = await boot_driver(dut, build_rom("IRQ_IDLE", bytes([0x00, 0x18, 0xFD])))

    await step_with_memory(driver, memory, SimStimulus(ie_override=0x01, if_set_bits=0x01))
    armed = await step_with_memory(driver, memory, SimStimulus.idle())
    assert armed.irq_pending == 0x01

    await step_with_memory(driver, memory, SimStimulus(if_clear_bits=0x01))
    cleared = await step_with_memory(driver, memory, SimStimulus.idle())
    assert cleared.irq_pending == 0x00


@cocotb.test()
async def test_interrupt_injection_ie_override_masks_pending_bits(dut):
    driver, memory = await boot_driver(dut, build_rom("IRQ_MASK", bytes([0x00, 0x18, 0xFD])))

    await step_with_memory(driver, memory, SimStimulus(ie_override=0x04, if_set_bits=0x05))
    masked = await step_with_memory(driver, memory, SimStimulus.idle())
    assert masked.irq_pending == 0x04

    await step_with_memory(driver, memory, SimStimulus(ie_override=0x01))
    remasked = await step_with_memory(driver, memory, SimStimulus.idle())
    assert remasked.irq_pending == 0x01


@cocotb.test()
async def test_interrupt_injection_seeded_script_applies_per_commit_index(dut):
    driver, memory = await boot_driver(dut, build_rom("IRQ_SCRIPT", bytes([0x00, 0x18, 0xFD])))
    event_script = script(
        "irq_script",
        scheduled(0, IeOverrideEvent(value=0x01)),
        scheduled(1, IfSetBitsEvent(bits=0x01)),
        scheduled(3, IfClearBitsEvent(bits=0x01)),
    )

    observations = []
    for commit_index in range(5):
        observations.append(
            await step_with_memory(
                driver,
                memory,
                stimulus_from_events(event_script.events_for_commit(commit_index)),
            )
        )

    assert [obs.irq_pending for obs in observations] == [0x00, 0x00, 0x01, 0x01, 0x00]


@cocotb.test()
async def test_interrupt_injection_stimulus_and_direct_irq_pending_coexist(dut):
    driver, memory = await boot_driver(dut, build_rom("IRQ_COEX", bytes([0x00, 0x18, 0xFD])))

    await step_with_memory(driver, memory, SimStimulus(ie_override=0x02, if_set_bits=0x02))
    pre = driver.observe()
    bus_read_data = memory.read(pre.bus_req_addr) if pre.bus_req_kind == BUS_REQ_READ else 0
    if pre.bus_req_kind == BUS_REQ_WRITE:
        memory.write(pre.bus_req_addr, pre.bus_req_data)
    post = await driver.step_mcycle(stimulus=SimStimulus.idle(), bus_read_data=bus_read_data, irq_pending=0x08)
    assert post.irq_pending == 0x0A


@cocotb.test()
async def test_interrupt_injection_basic_dispatch_logs_service_sequence(dut):
    scenario = "basic_interrupt_dispatch"
    setup = "ROM executes EI/NOP loop, timer vector RETI, IE overridden to timer"
    inject = "Inject IF bit 2 after EI so service starts on the next eligible fetch"
    trace = await collect_case_trace(
        dut,
        build_case_rom("IRQDISP", bytes([0xFB, 0x00, 0x18, 0xFD]), patches={0x0050: bytes([0xD9])}),
        script(
            scenario,
            scheduled(0, IeOverrideEvent(value=IRQ_TIMER)),
            scheduled(1, IfSetBitsEvent(bits=IRQ_TIMER)),
        ),
        capture_cycles=10,
    )

    ack_index = first_index(trace, lambda obs: obs.pre.irq_ack_valid and obs.pre.irq_ack_bit == TIMER_ACK_BIT)
    require_scenario(ack_index is not None, scenario=scenario, setup=setup, inject=inject, trace=trace, message="timer interrupt should be acknowledged")
    require_scenario(trace[ack_index].pre.irq_pending == IRQ_TIMER, scenario=scenario, setup=setup, inject=inject, trace=trace, message="timer IF should be pending at acknowledge time")
    require_scenario(any(obs.pre.bus_req_kind == BUS_REQ_READ and obs.pre.bus_req_addr == 0x0050 for obs in trace[ack_index + 1 :]), scenario=scenario, setup=setup, inject=inject, trace=trace, message="service sequence should fetch the timer vector")


@cocotb.test()
async def test_interrupt_injection_ei_delay_precision_defers_service_until_after_nop(dut):
    scenario = "ei_delay_precision"
    setup = "ROM executes EI; NOP; NOP loop with timer vector RETI"
    inject = "Inject timer IF on the EI commit and verify service waits until after the NOP completes"
    trace = await collect_case_trace(
        dut,
        build_case_rom("EIDELAYI", bytes([0xFB, 0x00, 0x00, 0x18, 0xFD]), patches={0x0050: bytes([0xD9])}),
        script(
            scenario,
            scheduled(0, IeOverrideEvent(value=IRQ_TIMER)),
            scheduled(0, IfSetBitsEvent(bits=IRQ_TIMER)),
        ),
        capture_cycles=8,
    )

    ack_index = first_index(trace, lambda obs: obs.pre.irq_ack_valid and obs.pre.irq_ack_bit == TIMER_ACK_BIT)
    require_scenario(ack_index == 2, scenario=scenario, setup=setup, inject=inject, trace=trace, message="interrupt should not service until the instruction after EI has completed")
    require_scenario(trace[1].pre.ime_state == IME_PENDING_ENABLE, scenario=scenario, setup=setup, inject=inject, trace=trace, message="NOP fetch should still see IME pending enable")
    require_scenario(trace[1].pre.irq_pending == IRQ_TIMER, scenario=scenario, setup=setup, inject=inject, trace=trace, message="timer IF should already be pending during the delayed-enable window")
    require_scenario(not trace[1].pre.irq_ack_valid, scenario=scenario, setup=setup, inject=inject, trace=trace, message="interrupt must not acknowledge during the delayed-enable instruction")


@cocotb.test()
async def test_interrupt_injection_halt_wake_ime_enabled_services_interrupt(dut):
    scenario = "halt_wake_ime_enabled"
    setup = "ROM executes EI; NOP; HALT; NOP loop so IME is enabled before HALT"
    inject = "Inject timer IF into the halted state and verify wake plus service"
    trace = await collect_case_trace(
        dut,
        build_case_rom("HALTWKIM", bytes([0xFB, 0x00, 0x76, 0x00, 0x18, 0xFE]), patches={0x0050: bytes([0xD9])}),
        script(
            scenario,
            scheduled(0, IeOverrideEvent(value=IRQ_TIMER)),
            scheduled(4, IfSetBitsEvent(bits=IRQ_TIMER)),
        ),
        capture_cycles=10,
    )

    require_scenario(trace[4].pre.phase_kind == PHASE_HALTED, scenario=scenario, setup=setup, inject=inject, trace=trace, message="HALT should park in the halted phase before the wake")
    require_scenario(trace[4].pre.halt_state == HALT_HALTED, scenario=scenario, setup=setup, inject=inject, trace=trace, message="HALT should latch the halted state")
    require_scenario(trace[4].pre.ime_state == IME_ENABLED, scenario=scenario, setup=setup, inject=inject, trace=trace, message="IME should already be enabled while halted")
    require_scenario(first_index(trace, lambda obs: obs.pre.irq_ack_valid and obs.pre.irq_ack_bit == TIMER_ACK_BIT) == 5, scenario=scenario, setup=setup, inject=inject, trace=trace, message="halted wake should acknowledge timer on the next cycle")


@cocotb.test()
async def test_interrupt_injection_halt_with_pending_and_ime_disabled_triggers_halt_bug(dut):
    scenario = "halt_bug_pending_irq"
    setup = "ROM executes DI; HALT; NOP loop with timer IE/IF already pending"
    inject = "Inject IE and IF at commit 0 so HALT executes with IME disabled and a pending interrupt"
    trace = await collect_case_trace(
        dut,
        build_case_rom("HALTBUGI", bytes([0xF3, 0x76, 0x00, 0x18, 0xFE])),
        script(
            scenario,
            scheduled(0, IeOverrideEvent(value=IRQ_TIMER)),
            scheduled(0, IfSetBitsEvent(bits=IRQ_TIMER)),
        ),
        capture_cycles=8,
    )

    require_scenario(trace[1].pre.irq_pending == IRQ_TIMER, scenario=scenario, setup=setup, inject=inject, trace=trace, message="timer IF should already be pending by HALT fetch")
    require_scenario(trace[2].pre.phase_kind == PHASE_EXECUTE, scenario=scenario, setup=setup, inject=inject, trace=trace, message="HALT should execute in its own cycle")
    require_scenario(trace[3].pre.halt_state == HALT_BUG_PENDING and trace[3].pre.phase_kind == PHASE_FETCH, scenario=scenario, setup=setup, inject=inject, trace=trace, message="halt bug should replay the following fetch instead of entering the halted phase")
    require_scenario(trace[3].pre.bus_req_kind == BUS_REQ_READ and trace[3].pre.bus_req_addr == ROM_BASE + 2, scenario=scenario, setup=setup, inject=inject, trace=trace, message="halt bug replay should read the next opcode without incrementing PC")
    require_scenario(trace[4].pre.bus_req_kind == BUS_REQ_READ and trace[4].pre.bus_req_addr == ROM_BASE + 2, scenario=scenario, setup=setup, inject=inject, trace=trace, message="the duplicated fetch should be followed by a normal refetch of the same byte")
    require_scenario(all(not obs.pre.irq_ack_valid for obs in trace), scenario=scenario, setup=setup, inject=inject, trace=trace, message="halt bug path must not acknowledge the interrupt while IME is disabled")


@cocotb.test()
async def test_interrupt_injection_halt_without_pending_stays_halted_without_bus_activity(dut):
    scenario = "halt_no_pending"
    setup = "DI keeps IME disabled before HALT with no IE/IF bits armed"
    inject = "No interrupt injection"
    trace = await collect_case_trace(
        dut,
        build_case_rom(
            "HALTIDLE",
            bytes(
                [
                    0xAF,
                    0xEA, 0x0F, 0xFF,
                    0xEA, 0xFF, 0xFF,
                    0xF3,
                    0x76,
                    0x00,
                    0x18, 0xFE,
                ]
            ),
        ),
        script(scenario),
        capture_cycles=16,
    )

    halted_index = first_index(trace, lambda obs: obs.pre.phase_kind == PHASE_HALTED and obs.pre.halt_state == HALT_HALTED)
    require_scenario(halted_index is not None, scenario=scenario, setup=setup, inject=inject, trace=trace, message="HALT with IME disabled and no pending IRQ should enter the halted phase")
    require_scenario(all(obs.pre.phase_kind == PHASE_HALTED for obs in trace[halted_index:]), scenario=scenario, setup=setup, inject=inject, trace=trace, message="CPU should remain in the halted phase without a pending interrupt")
    require_scenario(all(obs.pre.halt_state == HALT_HALTED for obs in trace[halted_index:]), scenario=scenario, setup=setup, inject=inject, trace=trace, message="halted state should remain latched indefinitely")
    require_scenario(all(obs.pre.bus_req_kind == BUS_REQ_IDLE for obs in trace[halted_index:]), scenario=scenario, setup=setup, inject=inject, trace=trace, message="halted idle path should not generate bus traffic")
    require_scenario(all(not obs.pre.irq_ack_valid for obs in trace), scenario=scenario, setup=setup, inject=inject, trace=trace, message="no interrupt should be acknowledged")


@cocotb.test()
async def test_interrupt_injection_priority_logs_ack_order(dut):
    scenario = "interrupt_priority"
    setup = "EI/HALT loop with both VBlank and Timer enabled, both vectors RETI"
    inject = "Inject IF bits 0 and 2 together while halted"
    trace = await collect_case_trace(
        dut,
        build_case_rom(
            "IRQPRIO",
            bytes([0xFB, 0x76, 0x00, 0x18, 0xFE]),
            patches={0x0040: bytes([0xD9]), 0x0050: bytes([0xD9])},
        ),
        script(
            scenario,
            scheduled(0, IeOverrideEvent(value=IRQ_VBLANK | IRQ_TIMER)),
            scheduled(3, IfSetBitsEvent(bits=IRQ_VBLANK | IRQ_TIMER)),
        ),
        capture_cycles=24,
    )

    vblank_acks = ack_indices(trace, VBLANK_ACK_BIT)
    timer_acks = ack_indices(trace, TIMER_ACK_BIT)
    require_scenario(bool(vblank_acks), scenario=scenario, setup=setup, inject=inject, trace=trace, message="vblank should be acknowledged")
    require_scenario(bool(timer_acks), scenario=scenario, setup=setup, inject=inject, trace=trace, message="timer should be acknowledged after vblank")
    require_scenario(vblank_acks[0] < timer_acks[0], scenario=scenario, setup=setup, inject=inject, trace=trace, message="higher-priority vblank should service before timer")


@cocotb.test()
async def test_interrupt_injection_ei_followed_by_di_blocks_service(dut):
    scenario = "ei_di_interaction"
    setup = "ROM executes EI; DI; NOP; NOP loop with timer vector RETI"
    inject = "Inject timer IF after DI and verify no service starts"
    trace = await collect_case_trace(
        dut,
        build_case_rom("EIDIIRQ", bytes([0xFB, 0xF3, 0x00, 0x00, 0x18, 0xFC]), patches={0x0050: bytes([0xD9])}),
        script(
            scenario,
            scheduled(0, IeOverrideEvent(value=IRQ_TIMER)),
            scheduled(2, IfSetBitsEvent(bits=IRQ_TIMER)),
        ),
        capture_cycles=10,
    )

    require_scenario(all(not obs.pre.irq_ack_valid for obs in trace), scenario=scenario, setup=setup, inject=inject, trace=trace, message="EI immediately followed by DI must keep interrupts blocked")
    require_scenario(any(obs.pre.irq_pending == IRQ_TIMER for obs in trace), scenario=scenario, setup=setup, inject=inject, trace=trace, message="timer IF should still become pending")


@cocotb.test()
async def test_interrupt_injection_multicycle_instruction_defers_service_until_completion(dut):
    scenario = "interrupt_during_multicycle_instruction"
    setup = "ROM executes EI; NOP; LD (0xC000),A; NOP loop with timer vector RETI"
    inject = "Inject timer IF during the immediate-byte portion of LD (a16),A and verify service waits until the writeback completes"
    trace = await collect_case_trace(
        dut,
        build_case_rom("IRQMULTI", bytes([0xFB, 0x00, 0xEA, 0x00, 0xC0, 0x00, 0x18, 0xFD]), patches={0x0050: bytes([0xD9])}),
        script(
            scenario,
            scheduled(0, IeOverrideEvent(value=IRQ_TIMER)),
            scheduled(3, IfSetBitsEvent(bits=IRQ_TIMER)),
        ),
        capture_cycles=10,
    )

    ack_index = first_index(trace, lambda obs: obs.pre.irq_ack_valid and obs.pre.irq_ack_bit == TIMER_ACK_BIT)
    require_scenario(ack_index == 6, scenario=scenario, setup=setup, inject=inject, trace=trace, message="interrupt should service on the first fetch after the multi-cycle instruction completes")
    require_scenario(trace[5].pre.bus_req_kind == BUS_REQ_WRITE and trace[5].pre.bus_req_addr == 0xC000, scenario=scenario, setup=setup, inject=inject, trace=trace, message="LD (a16),A should reach its writeback cycle before service begins")
    require_scenario(all(not obs.pre.irq_ack_valid for obs in trace[:ack_index]), scenario=scenario, setup=setup, inject=inject, trace=trace, message="interrupt must not acknowledge during the instruction's internal cycles")


@cocotb.test()
async def test_interrupt_injection_timer_overflow_logs_exact_pending_cycle(dut):
    scenario = "timer_overflow_timing"
    setup = "ROM primes DIV/TIMA/TMA/TAC so timer overflow should raise IF after a deterministic delay"
    inject = "No external IF injection; timer model alone raises IF"
    trace = await collect_case_trace(
        dut,
        build_case_rom(
            "TMRTRACE",
            bytes(
                [
                    0xF3,        # DI
                    0xAF,        # XOR A
                    0xEA, 0x0F, 0xFF,  # LD (rIF),A
                    0x3E, 0x04,  # LD A,0x04
                    0xEA, 0xFF, 0xFF,  # LD (rIE),A
                    0xAF,        # XOR A
                    0xEA, 0x07, 0xFF,  # LD (rTAC),A
                    0xEA, 0x04, 0xFF,  # LD (rDIV),A
                    0x3E, 0x3C,  # LD A,0x3C
                    0xEA, 0x06, 0xFF,  # LD (rTMA),A
                    0x3E, 0xFC,  # LD A,0xFC
                    0xEA, 0x05, 0xFF,  # LD (rTIMA),A
                    0x3E, 0x05,  # LD A,0x05
                    0xEA, 0x07, 0xFF,  # LD (rTAC),A
                    0x00,        # NOP
                    0x00,        # NOP
                    0x00,        # NOP
                    0x00,        # NOP
                    0x18, 0xFE,  # JR -2
                ]
            ),
        ),
        script(scenario),
        capture_cycles=80,
    )

    pending_index = first_index(trace, lambda obs: obs.pre.irq_pending == IRQ_TIMER)
    require_scenario(pending_index == 59, scenario=scenario, setup=setup, inject=inject, trace=trace, message="timer overflow should raise IF on the exact expected M-cycle")
    require_scenario(trace[pending_index - 1].tima == 0x00, scenario=scenario, setup=setup, inject=inject, trace=trace, message="TIMA should sit at 0x00 during the reload-delay cycle before IF becomes pending")
    require_scenario(trace[pending_index].tima == 0x3C, scenario=scenario, setup=setup, inject=inject, trace=trace, message="TIMA should reload from TMA on the same cycle IF becomes pending")


@cocotb.test()
async def test_interrupt_injection_nested_interrupt_logs_reentry_stack(dut):
    scenario = "nested_interrupt_edge_case"
    setup = "Mainline and vblank handler both use EI/HALT, with VBlank and Timer vectors ending in RETI"
    inject = "Inject VBlank first, then inject Timer while the handler is halted with IME enabled"
    trace = await collect_case_trace(
        dut,
        build_case_rom(
            "NESTIRQI",
            bytes([0xFB, 0x76, 0x00, 0x18, 0xFE]),
            patches={0x0040: bytes([0xFB, 0x76, 0xD9]), 0x0050: bytes([0xD9])},
        ),
        script(
            scenario,
            scheduled(0, IeOverrideEvent(value=IRQ_VBLANK | IRQ_TIMER)),
            scheduled(3, IfSetBitsEvent(bits=IRQ_VBLANK)),
            scheduled(13, IfSetBitsEvent(bits=IRQ_TIMER)),
        ),
        capture_cycles=32,
    )

    vblank_acks = ack_indices(trace, VBLANK_ACK_BIT)
    timer_acks = ack_indices(trace, TIMER_ACK_BIT)
    require_scenario(vblank_acks == [4], scenario=scenario, setup=setup, inject=inject, trace=trace, message="outer VBlank interrupt should service first")
    require_scenario(timer_acks == [14], scenario=scenario, setup=setup, inject=inject, trace=trace, message="Timer interrupt should re-enter from the handler once its EI/HALT window opens")
    require_scenario(trace[13].pre.phase_kind == PHASE_HALTED and trace[13].pre.ime_state == IME_ENABLED, scenario=scenario, setup=setup, inject=inject, trace=trace, message="outer handler should be halted with IME enabled before the nested interrupt arrives")
    require_scenario(any(obs.pre.bus_req_kind == BUS_REQ_READ and obs.pre.bus_req_addr == 0x0042 for obs in trace[15:]), scenario=scenario, setup=setup, inject=inject, trace=trace, message="nested RETI should return to the outer handler before final RETI returns to mainline")
