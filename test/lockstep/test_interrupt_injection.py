# top = sim::cpu_test_top::cpu_test_top
from __future__ import annotations

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
from dut_driver import SimStimulus
from event_script_support import stimulus_from_events
from fixtures import cpu_dut
from rom_runner import BUS_REQ_READ, BUS_REQ_WRITE, ExternalMemoryBus
from roms.build_micro_rom import build_rom
from spec.profiles import ResetProfile


warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")


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


async def boot_driver(dut, rom_bytes: bytes):
    driver = cpu_dut(dut)
    await driver.reset(ResetProfile.SkipBoot)
    await Timer(1, units="ns")
    return driver, ExternalMemoryBus(rom_bytes)


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
