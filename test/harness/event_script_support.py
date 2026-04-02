from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
HARNESS = ROOT / "test" / "harness"
for entry in [ROOT, HARNESS]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from dut_driver import CpuCommitTrace, JoypadState, SimStimulus


JOYPAD_ORDER = ("up", "down", "left", "right", "a", "b", "start", "select")


def striped_manifest_entry(*, seed: int, rom_id: str = "ALU_LOOP", timeout_commits: int = 80) -> dict[str, object]:
    return {
        "id": rom_id,
        "timeout_commits": timeout_commits,
        "action_script": None,
        "action_gen": {"name": "striped", "seed": seed},
    }


def _joypad_state_from_mapping(values: Mapping[str, Any]) -> JoypadState:
    return JoypadState(**{name: bool(values.get(name, False)) for name in JOYPAD_ORDER})


def striped_stimulus_schedule(*, seed: int, rom_id: str = "ALU_LOOP", timeout_commits: int = 80) -> dict[int, SimStimulus]:
    rng = random.Random(f"{rom_id}:{seed}")
    max_commit = min(timeout_commits, 256)
    stride = 19 + (seed % 7)
    start = 3 + (seed % 5)

    schedule: dict[int, SimStimulus] = {}
    commit_index = start
    while commit_index < max_commit:
        button = JOYPAD_ORDER[rng.randrange(len(JOYPAD_ORDER))]
        schedule[commit_index] = SimStimulus(joyp_buttons=_joypad_state_from_mapping({button: True}))
        if commit_index + 1 < max_commit:
            schedule[commit_index + 1] = SimStimulus(joyp_buttons=JoypadState())
        commit_index += stride
    return schedule


def stimulus_from_events(events: Sequence[Any]) -> SimStimulus:
    joyp_buttons: JoypadState | None = None
    if_set_bits = 0
    if_clear_bits = 0
    ie_override: int | None = None
    dma_start: int | None = None
    serial_inject: int | None = None
    freeze_arch_time = False
    cpu_hold_only = False

    for event in events:
        kind = type(event).__name__
        if kind == "JoypadButtonsEvent":
            joyp_buttons = _joypad_state_from_mapping(vars(event.joyp_buttons))
            continue
        if kind == "IfSetBitsEvent":
            if_set_bits |= event.bits & 0x1F
            continue
        if kind == "IfClearBitsEvent":
            if_clear_bits |= event.bits & 0x1F
            continue
        if kind == "IeOverrideEvent":
            ie_override = event.value & 0x1F
            continue
        if kind == "DmaStartEvent":
            dma_start = event.source_high & 0xFF
            continue
        if kind == "SerialInjectEvent":
            serial_inject = event.value & 0xFF
            continue
        if kind == "FreezeArchTimeEvent":
            freeze_arch_time = event.enabled
            continue
        if kind == "CpuHoldOnlyEvent":
            cpu_hold_only = event.enabled
            continue
        if kind in ("MemoryWriteEvent", "RawInputEvent"):
            raise NotImplementedError(f"{kind} cannot be applied to cpu_test_top stimulus ports")
        raise TypeError(f"Unsupported simulation event: {type(event)!r}")

    return SimStimulus(
        joyp_buttons=joyp_buttons,
        if_set_bits=if_set_bits,
        if_clear_bits=if_clear_bits,
        ie_override=ie_override,
        dma_start=dma_start,
        serial_inject=serial_inject,
        freeze_arch_time=freeze_arch_time,
        cpu_hold_only=cpu_hold_only,
    )


def predicted_traces_for_schedule(
    schedule: Mapping[int, SimStimulus],
    commit_count: int,
    *,
    bus_read_data: int = 0,
    irq_pending: int = 0,
) -> tuple[CpuCommitTrace, ...]:
    traces = []
    commit_seq = 0
    pc = 0x0100
    for commit_index in range(commit_count):
        stimulus = schedule.get(commit_index, SimStimulus.idle())
        cpu_arch_time_enable = not stimulus.freeze_arch_time and not stimulus.cpu_hold_only
        if cpu_arch_time_enable:
            commit_seq += 1
            pc = (pc + 1) & 0xFFFF
        traces.append(
            CpuCommitTrace(
                seq=commit_index + 1,
                bus_read_data=bus_read_data & 0xFF,
                irq_pending=irq_pending & 0x1F,
                cpu_arch_time_enable=cpu_arch_time_enable,
                freeze_arch_time=stimulus.freeze_arch_time,
                cpu_hold_only=stimulus.cpu_hold_only,
                commit_seq=commit_seq,
                pc=pc,
            )
        )
    return tuple(traces)


def predicted_traces_for_script(
    script: Any,
    commit_count: int,
    *,
    bus_read_data: int = 0,
    irq_pending: int = 0,
) -> tuple[CpuCommitTrace, ...]:
    traces = []
    commit_seq = 0
    pc = 0x0100
    for commit_index in range(commit_count):
        stimulus = stimulus_from_events(script.events_for_commit(commit_index))
        cpu_arch_time_enable = not stimulus.freeze_arch_time and not stimulus.cpu_hold_only
        if cpu_arch_time_enable:
            commit_seq += 1
            pc = (pc + 1) & 0xFFFF
        traces.append(
            CpuCommitTrace(
                seq=commit_index + 1,
                bus_read_data=bus_read_data & 0xFF,
                irq_pending=irq_pending & 0x1F,
                cpu_arch_time_enable=cpu_arch_time_enable,
                freeze_arch_time=stimulus.freeze_arch_time,
                cpu_hold_only=stimulus.cpu_hold_only,
                commit_seq=commit_seq,
                pc=pc,
            )
        )
    return tuple(traces)
