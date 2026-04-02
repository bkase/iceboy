"""Replay capsule schema for deterministic PyBoy-driven failures."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import yaml

from bench.pyboy.hooks import HookManifest
from bench.pyboy.oracle import ButtonEvent, MemoryWriteEvent, RawInputEvent, SimEvent
from spec.profiles import MemoryBehaviorProfile, ModelProfile, ResetProfile


@dataclass(frozen=True)
class ReplayEvent:
    commit_index: int
    event: SimEvent


@dataclass(frozen=True)
class FirstDivergence:
    commit_index: int
    field: str
    expected: Any
    actual: Any


@dataclass(frozen=True)
class ReplayCapsule:
    rom_id: str
    model_profile: ModelProfile
    reset_profile: ResetProfile
    memory_behavior_profile: MemoryBehaviorProfile
    random_seed: int
    event_log: tuple[ReplayEvent, ...]
    sym_sha256: str
    hook_manifest_id: str
    first_divergence: FirstDivergence | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "rom_id": self.rom_id,
            "model_profile": self.model_profile.value,
            "reset_profile": self.reset_profile.value,
            "memory_behavior_profile": self.memory_behavior_profile.value,
            "random_seed": self.random_seed,
            "event_log": [
                {
                    "commit_index": entry.commit_index,
                    "event": encode_sim_event(entry.event),
                }
                for entry in self.event_log
            ],
            "sym_sha256": self.sym_sha256,
            "hook_manifest_id": self.hook_manifest_id,
            "first_divergence": (
                {
                    "commit_index": self.first_divergence.commit_index,
                    "field": self.first_divergence.field,
                    "expected": self.first_divergence.expected,
                    "actual": self.first_divergence.actual,
                }
                if self.first_divergence is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReplayCapsule":
        first_divergence_data = data.get("first_divergence")
        return cls(
            rom_id=str(data["rom_id"]),
            model_profile=ModelProfile(str(data["model_profile"])),
            reset_profile=ResetProfile(str(data["reset_profile"])),
            memory_behavior_profile=MemoryBehaviorProfile(str(data["memory_behavior_profile"])),
            random_seed=int(data["random_seed"]),
            event_log=tuple(
                ReplayEvent(
                    commit_index=int(entry["commit_index"]),
                    event=decode_sim_event(entry["event"]),
                )
                for entry in data["event_log"]
            ),
            sym_sha256=str(data["sym_sha256"]),
            hook_manifest_id=str(data["hook_manifest_id"]),
            first_divergence=(
                FirstDivergence(
                    commit_index=int(first_divergence_data["commit_index"]),
                    field=str(first_divergence_data["field"]),
                    expected=first_divergence_data["expected"],
                    actual=first_divergence_data["actual"],
                )
                if first_divergence_data is not None
                else None
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "ReplayCapsule":
        return cls.from_dict(json.loads(text))

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.to_dict(), sort_keys=False)

    @classmethod
    def from_yaml(cls, text: str) -> "ReplayCapsule":
        data = yaml.safe_load(text)
        return cls.from_dict(data)


def encode_sim_event(event: SimEvent) -> dict[str, Any]:
    if isinstance(event, ButtonEvent):
        return {
            "kind": "button",
            "button": event.button,
            "action": event.action,
            "delay": event.delay,
        }
    if isinstance(event, MemoryWriteEvent):
        return {
            "kind": "memory_write",
            "addr": event.addr,
            "value": event.value,
            "bank": event.bank,
        }
    if isinstance(event, RawInputEvent):
        return {
            "kind": "raw_input",
            "event": event.event,
            "delay": event.delay,
        }
    raise TypeError(f"Unsupported simulation event: {type(event)!r}")


def decode_sim_event(data: dict[str, Any]) -> SimEvent:
    kind = str(data["kind"])
    if kind == "button":
        return ButtonEvent(
            button=str(data["button"]),
            action=str(data["action"]),
            delay=int(data["delay"]),
        )
    if kind == "memory_write":
        bank = data.get("bank")
        return MemoryWriteEvent(
            addr=int(data["addr"]),
            value=int(data["value"]),
            bank=int(bank) if bank is not None else None,
        )
    if kind == "raw_input":
        return RawInputEvent(
            event=int(data["event"]),
            delay=int(data["delay"]),
        )
    raise ValueError(f"Unsupported simulation event kind: {kind}")


def build_hook_manifest_id(manifest: HookManifest) -> str:
    serialized_targets = [
        {
            "bank": target.bank,
            "addr": target.addr,
            "labels": list(target.labels),
        }
        for target in manifest.targets
    ]
    payload = {
        "sym_sha256": manifest.sym_sha256,
        "targets": serialized_targets,
    }
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()
