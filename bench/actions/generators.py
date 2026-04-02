"""Seeded deterministic event scripts for DUT/oracle perturbation."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence, Union

import yaml


ROOT = Path(__file__).resolve().parents[2]
JOYPAD_ORDER = ("up", "down", "left", "right", "a", "b", "start", "select")


@dataclass(frozen=True)
class JoypadButtons:
    up: bool = False
    down: bool = False
    left: bool = False
    right: bool = False
    a: bool = False
    b: bool = False
    start: bool = False
    select: bool = False

    @classmethod
    def from_pressed(cls, pressed: Sequence[str]) -> "JoypadButtons":
        values = {name: False for name in JOYPAD_ORDER}
        for name in pressed:
            normalized = str(name).lower()
            if normalized not in values:
                raise ValueError(f"Unsupported joypad button: {name}")
            values[normalized] = True
        return cls(**values)

    def pressed_buttons(self) -> tuple[str, ...]:
        return tuple(name for name in JOYPAD_ORDER if getattr(self, name))


@dataclass(frozen=True)
class JoypadButtonsEvent:
    joyp_buttons: JoypadButtons


@dataclass(frozen=True)
class IfSetBitsEvent:
    bits: int


@dataclass(frozen=True)
class IfClearBitsEvent:
    bits: int


@dataclass(frozen=True)
class IeOverrideEvent:
    value: int


@dataclass(frozen=True)
class DmaStartEvent:
    source_high: int


@dataclass(frozen=True)
class SerialInjectEvent:
    value: int


@dataclass(frozen=True)
class FreezeArchTimeEvent:
    enabled: bool = True


@dataclass(frozen=True)
class CpuHoldOnlyEvent:
    enabled: bool = True


@dataclass(frozen=True)
class MemoryWriteEvent:
    addr: int
    value: int
    bank: int | None = None


@dataclass(frozen=True)
class RawInputEvent:
    event: int
    delay: int = 0


SimEvent = Union[
    JoypadButtonsEvent,
    IfSetBitsEvent,
    IfClearBitsEvent,
    IeOverrideEvent,
    DmaStartEvent,
    SerialInjectEvent,
    FreezeArchTimeEvent,
    CpuHoldOnlyEvent,
    MemoryWriteEvent,
    RawInputEvent,
]


@dataclass(frozen=True)
class ScheduledEvent:
    event: SimEvent
    commit_index: int | None = None
    checkpoint: str | None = None

    def __post_init__(self) -> None:
        keyed_by_commit = self.commit_index is not None
        keyed_by_checkpoint = self.checkpoint is not None
        if keyed_by_commit == keyed_by_checkpoint:
            raise ValueError("ScheduledEvent must use exactly one of commit_index or checkpoint")

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"event": encode_sim_event(self.event)}
        if self.commit_index is not None:
            payload["commit_index"] = self.commit_index
        if self.checkpoint is not None:
            payload["checkpoint"] = self.checkpoint
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ScheduledEvent":
        return cls(
            commit_index=int(data["commit_index"]) if data.get("commit_index") is not None else None,
            checkpoint=str(data["checkpoint"]) if data.get("checkpoint") is not None else None,
            event=decode_sim_event(data["event"]),
        )


@dataclass(frozen=True)
class SeededEventScript:
    seed: int
    events: tuple[ScheduledEvent, ...]
    source: str

    @classmethod
    def from_manifest_entry(
        cls,
        rom: Mapping[str, object],
        *,
        repo_root: str | Path | None = None,
    ) -> "SeededEventScript":
        root = Path(repo_root) if repo_root is not None else ROOT
        action_script = rom.get("action_script")
        action_gen = rom.get("action_gen")
        if action_script and action_gen:
            raise ValueError("rom entry must not define both action_script and action_gen")
        if action_script:
            return cls.from_action_script(root / str(action_script))
        if action_gen:
            generator_name = str(action_gen["name"])
            seed = int(action_gen["seed"])
            if generator_name != "striped":
                raise ValueError(f"Unsupported action generator: {generator_name}")
            timeout_commits = int(rom["timeout_commits"])
            rom_id = str(rom["id"])
            events = tuple(_generate_striped_events(rom_id=rom_id, seed=seed, timeout_commits=timeout_commits))
            return cls(seed=seed, events=events, source=f"action_gen:{generator_name}")
        return cls(seed=0, events=(), source="empty")

    @classmethod
    def from_action_script(cls, path: str | Path) -> "SeededEventScript":
        script_path = Path(path)
        data = yaml.safe_load(script_path.read_text(encoding="utf-8"))
        events = tuple(ScheduledEvent.from_dict(item) for item in data.get("events", []))
        return cls(seed=int(data.get("seed", 0)), events=events, source=str(script_path))

    def events_for_commit(self, commit_index: int) -> tuple[SimEvent, ...]:
        return tuple(event.event for event in self.events if event.commit_index == commit_index)

    def events_for_checkpoint(self, checkpoint: str) -> tuple[SimEvent, ...]:
        return tuple(event.event for event in self.events if event.checkpoint == checkpoint)

    def to_dict(self) -> dict[str, object]:
        return {
            "seed": self.seed,
            "source": self.source,
            "events": [event.to_dict() for event in self.events],
        }

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.to_dict(), sort_keys=False)


def encode_sim_event(event: SimEvent) -> dict[str, Any]:
    if isinstance(event, JoypadButtonsEvent):
        return {"kind": "joypad_buttons", "buttons": list(event.joyp_buttons.pressed_buttons())}
    if isinstance(event, IfSetBitsEvent):
        return {"kind": "if_set_bits", "bits": event.bits}
    if isinstance(event, IfClearBitsEvent):
        return {"kind": "if_clear_bits", "bits": event.bits}
    if isinstance(event, IeOverrideEvent):
        return {"kind": "ie_override", "value": event.value}
    if isinstance(event, DmaStartEvent):
        return {"kind": "dma_start", "source_high": event.source_high}
    if isinstance(event, SerialInjectEvent):
        return {"kind": "serial_inject", "value": event.value}
    if isinstance(event, FreezeArchTimeEvent):
        return {"kind": "freeze_arch_time", "enabled": event.enabled}
    if isinstance(event, CpuHoldOnlyEvent):
        return {"kind": "cpu_hold_only", "enabled": event.enabled}
    if isinstance(event, MemoryWriteEvent):
        return {"kind": "memory_write", "addr": event.addr, "value": event.value, "bank": event.bank}
    if isinstance(event, RawInputEvent):
        return {"kind": "raw_input", "event": event.event, "delay": event.delay}
    raise TypeError(f"Unsupported simulation event: {type(event)!r}")


def decode_sim_event(data: Mapping[str, Any]) -> SimEvent:
    kind = str(data["kind"])
    if kind == "joypad_buttons":
        return JoypadButtonsEvent(JoypadButtons.from_pressed(data.get("buttons", [])))
    if kind == "if_set_bits":
        return IfSetBitsEvent(bits=int(data["bits"]))
    if kind == "if_clear_bits":
        return IfClearBitsEvent(bits=int(data["bits"]))
    if kind == "ie_override":
        return IeOverrideEvent(value=int(data["value"]))
    if kind == "dma_start":
        return DmaStartEvent(source_high=int(data["source_high"]))
    if kind == "serial_inject":
        return SerialInjectEvent(value=int(data["value"]))
    if kind == "freeze_arch_time":
        return FreezeArchTimeEvent(enabled=bool(data.get("enabled", True)))
    if kind == "cpu_hold_only":
        return CpuHoldOnlyEvent(enabled=bool(data.get("enabled", True)))
    if kind == "memory_write":
        bank = data.get("bank")
        return MemoryWriteEvent(
            addr=int(data["addr"]),
            value=int(data["value"]),
            bank=int(bank) if bank is not None else None,
        )
    if kind == "raw_input":
        return RawInputEvent(event=int(data["event"]), delay=int(data.get("delay", 0)))
    raise ValueError(f"Unsupported simulation event kind: {kind}")


def load_action_script(path: str | Path) -> SeededEventScript:
    return SeededEventScript.from_action_script(path)


def save_action_script(path: str | Path, script: SeededEventScript) -> None:
    Path(path).write_text(script.to_yaml(), encoding="utf-8")


def _generate_striped_events(*, rom_id: str, seed: int, timeout_commits: int) -> list[ScheduledEvent]:
    rng = random.Random(f"{rom_id}:{seed}")
    max_commit = min(timeout_commits, 256)
    stride = 19 + (seed % 7)
    start = 3 + (seed % 5)

    events: list[ScheduledEvent] = []
    commit_index = start
    while commit_index < max_commit:
        button = JOYPAD_ORDER[rng.randrange(len(JOYPAD_ORDER))]
        events.append(
            ScheduledEvent(
                commit_index=commit_index,
                event=JoypadButtonsEvent(JoypadButtons.from_pressed([button])),
            )
        )
        if commit_index + 1 < max_commit:
            events.append(
                ScheduledEvent(
                    commit_index=commit_index + 1,
                    event=JoypadButtonsEvent(JoypadButtons()),
                )
            )
        commit_index += stride
    return events
