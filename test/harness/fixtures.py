from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from spec.profiles import CPU_BRING_UP_PROFILES, SimulationProfiles

from dut_driver import CpuTestDriver

if TYPE_CHECKING:
    from bench.actions.generators import SeededEventScript
    from bench.pyboy.oracle import CommitPoint, PyBoyOracle


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class LoadedRom:
    rom_id: str
    rom_path: Path
    profiles: SimulationProfiles
    manifest_entry: Mapping[str, object]


@dataclass(frozen=True)
class LockstepPair:
    dut: CpuTestDriver
    oracle: Any


def cpu_dut(dut: Any, *, logger: Any | None = None) -> CpuTestDriver:
    return CpuTestDriver(dut, logger=logger)


def oracle(
    rom_path: str | Path,
    *,
    commit_points: Sequence[Any] | None = None,
    profiles: SimulationProfiles = CPU_BRING_UP_PROFILES,
) -> Any:
    from bench.pyboy.oracle import PyBoyOracle

    instance = PyBoyOracle(rom_path, commit_points=commit_points or ())
    instance.reset(profiles.model, profiles.reset)
    return instance


def lockstep_pair(
    dut: Any,
    rom_path: str | Path,
    *,
    commit_points: Sequence[Any] | None = None,
    profiles: SimulationProfiles = CPU_BRING_UP_PROFILES,
    logger: Any | None = None,
) -> LockstepPair:
    return LockstepPair(
        dut=cpu_dut(dut, logger=logger),
        oracle=oracle(rom_path, commit_points=commit_points, profiles=profiles),
    )


def rom_loader(manifest_entry: Mapping[str, object], *, repo_root: str | Path | None = None) -> LoadedRom:
    root = Path(repo_root) if repo_root is not None else ROOT
    return LoadedRom(
        rom_id=str(manifest_entry["id"]),
        rom_path=root / str(manifest_entry["path"]),
        profiles=SimulationProfiles.from_mapping(manifest_entry),
        manifest_entry=manifest_entry,
    )


def event_script(seed: int | None, manifest_entry: Mapping[str, object]) -> Any:
    from bench.actions.generators import SeededEventScript

    if seed is None:
        return SeededEventScript.from_manifest_entry(manifest_entry, repo_root=ROOT)

    seeded_entry = dict(manifest_entry)
    action_gen = seeded_entry.get("action_gen")
    if action_gen is not None:
        updated_action_gen = dict(action_gen)
        updated_action_gen["seed"] = seed
        seeded_entry["action_gen"] = updated_action_gen
    elif seeded_entry.get("action_script") is None:
        seeded_entry["action_gen"] = {"name": "striped", "seed": seed}
    return SeededEventScript.from_manifest_entry(seeded_entry, repo_root=ROOT)
