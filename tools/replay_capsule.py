from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from bench.ref.ppu_ref import ForceLcdPower, MmioReg, MmioWrite, TimedPpuEvent, VideoCoord
from spec.profiles import BehaviorConfig, MemoryBehaviorProfile, ModelProfile, ResetProfile


ROOT = Path(__file__).resolve().parents[1]
REPLAY_CAPSULE_SCHEMA_PATH = ROOT / "bench" / "schemas" / "replay_capsule.schema.json"
ZERO_SHA256 = "0" * 64


@dataclass(frozen=True)
class FirstBadCoord:
    frame: int
    line: int
    dot: int
    scope: str


@dataclass(frozen=True)
class PpuReplayCapsule:
    rom_id: str
    model_profile: ModelProfile
    reset_profile: ResetProfile
    behavior_config: BehaviorConfig
    random_seed: int
    raster_event_log: tuple[TimedPpuEvent, ...]
    first_bad_coord: FirstBadCoord | None = None
    memory_behavior_profile: MemoryBehaviorProfile = MemoryBehaviorProfile.DmgConservative
    sym_sha256: str = ZERO_SHA256
    hook_manifest_id: str = ZERO_SHA256
    first_divergence: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "rom_id": self.rom_id,
            "model_profile": self.model_profile.value,
            "reset_profile": self.reset_profile.value,
            "memory_behavior_profile": self.memory_behavior_profile.value,
            "random_seed": self.random_seed,
            "event_log": [],
            "sym_sha256": self.sym_sha256,
            "hook_manifest_id": self.hook_manifest_id,
            "first_divergence": self.first_divergence,
            "behavior_config": self.behavior_config.as_manifest_fields(),
            "raster_event_log": [encode_timed_ppu_event(event) for event in self.raster_event_log],
            "first_bad_coord": (
                {
                    "frame": self.first_bad_coord.frame,
                    "line": self.first_bad_coord.line,
                    "dot": self.first_bad_coord.dot,
                    "scope": self.first_bad_coord.scope,
                }
                if self.first_bad_coord is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PpuReplayCapsule":
        first_bad_coord = data.get("first_bad_coord")
        return cls(
            rom_id=str(data["rom_id"]),
            model_profile=ModelProfile(str(data["model_profile"])),
            reset_profile=ResetProfile(str(data["reset_profile"])),
            memory_behavior_profile=MemoryBehaviorProfile(str(data.get("memory_behavior_profile", "DmgConservative"))),
            behavior_config=BehaviorConfig.from_mapping(data["behavior_config"]),
            random_seed=int(data["random_seed"]),
            raster_event_log=tuple(decode_timed_ppu_event(event) for event in data.get("raster_event_log", [])),
            sym_sha256=str(data.get("sym_sha256", ZERO_SHA256)),
            hook_manifest_id=str(data.get("hook_manifest_id", ZERO_SHA256)),
            first_divergence=data.get("first_divergence"),
            first_bad_coord=(
                FirstBadCoord(
                    frame=int(first_bad_coord["frame"]),
                    line=int(first_bad_coord["line"]),
                    dot=int(first_bad_coord["dot"]),
                    scope=str(first_bad_coord["scope"]),
                )
                if first_bad_coord is not None
                else None
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "PpuReplayCapsule":
        return cls.from_dict(json.loads(text))

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.to_dict(), sort_keys=False)

    @classmethod
    def from_yaml(cls, text: str) -> "PpuReplayCapsule":
        data = yaml.safe_load(text)
        return cls.from_dict(data)


def encode_timed_ppu_event(event: TimedPpuEvent) -> dict[str, Any]:
    kind = event.kind
    if isinstance(kind, MmioWrite):
        kind_data = {"type": "MmioWrite", "target": kind.target.value, "value": kind.value}
    elif isinstance(kind, ForceLcdPower):
        kind_data = {"type": "ForceLcdPower", "enabled": kind.enabled}
    else:
        raise TypeError(f"unsupported timed PPU event kind: {type(kind)!r}")

    return {
        "seq": event.seq,
        "at": {"frame": event.at.frame, "line": event.at.line, "dot": event.at.dot},
        "kind": kind_data,
    }


def decode_timed_ppu_event(data: dict[str, Any]) -> TimedPpuEvent:
    kind_data = data["kind"]
    kind_type = str(kind_data["type"])
    if kind_type == "MmioWrite":
        kind: object = MmioWrite(target=MmioReg(str(kind_data["target"])), value=int(kind_data["value"]))
    elif kind_type == "ForceLcdPower":
        kind = ForceLcdPower(enabled=bool(kind_data["enabled"]))
    else:
        raise ValueError(f"unsupported timed PPU event kind: {kind_type}")
    at = data["at"]
    return TimedPpuEvent(
        seq=int(data["seq"]),
        at=VideoCoord(frame=int(at["frame"]), line=int(at["line"]), dot=int(at["dot"])),
        kind=kind,
    )


__all__ = [
    "FirstBadCoord",
    "PpuReplayCapsule",
    "REPLAY_CAPSULE_SCHEMA_PATH",
    "decode_timed_ppu_event",
    "encode_timed_ppu_event",
]
