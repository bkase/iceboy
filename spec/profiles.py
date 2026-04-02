from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class ModelProfile(str, Enum):
    DMG = "DMG"
    CGB = "CGB"


class ResetProfile(str, Enum):
    SkipBoot = "SkipBoot"
    RawPowerOn = "RawPowerOn"


class MemoryBehaviorProfile(str, Enum):
    DmgConservative = "DmgConservative"
    DmgRevisionSpecific = "DmgRevisionSpecific"


@dataclass(frozen=True)
class SimulationProfiles:
    model: ModelProfile
    reset: ResetProfile
    memory_behavior: MemoryBehaviorProfile

    @classmethod
    def from_mapping(cls, source: Mapping[str, object]) -> "SimulationProfiles":
        return cls(
            model=ModelProfile(str(source["model_profile"])),
            reset=ResetProfile(str(source["reset_profile"])),
            memory_behavior=MemoryBehaviorProfile(str(source["memory_behavior_profile"])),
        )

    def as_manifest_fields(self) -> dict[str, str]:
        return {
            "model_profile": self.model.value,
            "reset_profile": self.reset.value,
            "memory_behavior_profile": self.memory_behavior.value,
        }


CPU_BRING_UP_PROFILES = SimulationProfiles(
    model=ModelProfile.DMG,
    reset=ResetProfile.SkipBoot,
    memory_behavior=MemoryBehaviorProfile.DmgConservative,
)
