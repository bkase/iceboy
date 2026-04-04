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


class SocRevision(str, Enum):
    DMG0 = "DMG0"
    DMGA = "DMGA"
    DMGB = "DMGB"
    DMGC = "DMGC"
    MGB = "MGB"
    SGB = "SGB"
    SGB2 = "SGB2"
    CGB0 = "CGB0"
    CGBA = "CGBA"
    CGBB = "CGBB"
    CGBC = "CGBC"
    CGBD = "CGBD"
    CGBE = "CGBE"


class BehaviorFeature(str, Enum):
    DmgStatWriteQuirk = "DmgStatWriteQuirk"
    PreCgbdScyBitplaneDesync = "PreCgbdScyBitplaneDesync"
    Wx0Stutter = "Wx0Stutter"
    Wx166NextLine = "Wx166NextLine"
    WindowRetriggerGlitch = "WindowRetriggerGlitch"
    ObjFetchCancelTiming = "ObjFetchCancelTiming"
    DmgOamDmaBasic = "DmgOamDmaBasic"
    DmgOamDmaStrict = "DmgOamDmaStrict"
    ExactBlockedReadMaterialization = "ExactBlockedReadMaterialization"


@dataclass(frozen=True)
class BehaviorConfig:
    model: ModelProfile
    soc_revision: SocRevision | None = None
    features: tuple[BehaviorFeature, ...] = ()

    @classmethod
    def from_mapping(cls, source: Mapping[str, object]) -> "BehaviorConfig":
        raw_soc_revision = source.get("soc_revision")
        raw_features = source.get("features", ())
        if not isinstance(raw_features, (list, tuple)):
            raise TypeError("BehaviorConfig.features must be a sequence")
        return cls(
            model=ModelProfile(str(source["model"])),
            soc_revision=None if raw_soc_revision is None else SocRevision(str(raw_soc_revision)),
            features=tuple(BehaviorFeature(str(feature)) for feature in raw_features),
        )

    def as_manifest_fields(self) -> dict[str, object]:
        return {
            "model": self.model.value,
            "soc_revision": None if self.soc_revision is None else self.soc_revision.value,
            "features": [feature.value for feature in self.features],
        }


def default_behavior_config(model: ModelProfile) -> BehaviorConfig:
    return BehaviorConfig(model=model)


def dmg_behavior_config() -> BehaviorConfig:
    return default_behavior_config(ModelProfile.DMG)


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
