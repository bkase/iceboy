from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml

from spec.profiles import MemoryBehaviorProfile, ModelProfile, ResetProfile
from spec.sm83_opcodes import ALL_OPCODES


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COVERAGE_PATH = ROOT / "bench" / "artifacts" / "coverage" / "coverage.json"
ROM_MANIFEST_PATH = ROOT / "bench" / "manifests" / "rom_inventory.yaml"

BUS_REGION_UNIVERSE = (
    "rom",
    "vram",
    "wram",
    "oam",
    "io",
    "hram",
    "cart_ram",
)
INTERRUPT_CAUSE_UNIVERSE = (
    "vblank",
    "stat",
    "timer",
    "serial",
    "joypad",
)


@dataclass(frozen=True)
class SuiteCoverage:
    opcode_families: frozenset[str] = frozenset()
    phase_constructors: frozenset[str] = frozenset()
    bus_regions: frozenset[str] = frozenset()
    interrupt_causes: frozenset[str] = frozenset()
    rom_suites: frozenset[str] = frozenset()
    profile_triples: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CoverageDimension:
    label: str
    universe: tuple[str, ...]
    covered: tuple[str, ...]
    uncovered: tuple[str, ...]

    @property
    def covered_count(self) -> int:
        return len(self.covered)

    @property
    def total_count(self) -> int:
        return len(self.universe)

    def summary_line(self) -> str:
        suffix = "gaps: none" if not self.uncovered else f"gaps: {', '.join(self.uncovered[:5])}"
        if len(self.uncovered) > 5:
            suffix += ", ..."
        return f"{self.label}: {self.covered_count}/{self.total_count} covered ({suffix})"


@dataclass(frozen=True)
class CoverageSnapshot:
    generated_at: str
    passed_suites: tuple[str, ...]
    dimensions: dict[str, CoverageDimension]
    suite_coverage: dict[str, dict[str, list[str]]]

    def to_jsonable(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "passed_suites": list(self.passed_suites),
            "dimensions": {
                key: {
                    "label": dimension.label,
                    "covered": list(dimension.covered),
                    "uncovered": list(dimension.uncovered),
                    "total": list(dimension.universe),
                }
                for key, dimension in self.dimensions.items()
            },
            "suite_coverage": self.suite_coverage,
        }


def _all_opcode_families() -> tuple[str, ...]:
    return tuple(sorted({metadata.family for metadata in ALL_OPCODES}))


def _manifest_rom_entries() -> tuple[dict[str, object], ...]:
    data = yaml.safe_load(ROM_MANIFEST_PATH.read_text(encoding="utf-8"))
    roms = data.get("roms", []) if isinstance(data, dict) else []
    return tuple(entry for entry in roms if isinstance(entry, dict))


def _all_manifest_rom_ids() -> tuple[str, ...]:
    return tuple(str(entry["id"]) for entry in _manifest_rom_entries())


def _all_manifest_profile_triples() -> tuple[str, ...]:
    triples = set()
    for entry in _manifest_rom_entries():
        triples.add(
            format_profile_triple(
                ModelProfile(str(entry["model_profile"])),
                ResetProfile(str(entry["reset_profile"])),
                MemoryBehaviorProfile(str(entry["memory_behavior_profile"])),
            )
        )
    return tuple(sorted(triples))


def format_profile_triple(
    model: ModelProfile | str,
    reset: ResetProfile | str,
    memory_behavior: MemoryBehaviorProfile | str,
) -> str:
    model_value = model.value if isinstance(model, ModelProfile) else ModelProfile(str(model)).value
    reset_value = reset.value if isinstance(reset, ResetProfile) else ResetProfile(str(reset)).value
    memory_value = (
        memory_behavior.value
        if isinstance(memory_behavior, MemoryBehaviorProfile)
        else MemoryBehaviorProfile(str(memory_behavior)).value
    )
    return f"{model_value}/{reset_value}/{memory_value}"


ALL_FAMILIES = _all_opcode_families()
ALL_ROM_SUITES = _all_manifest_rom_ids()
ALL_PROFILE_TRIPLES = _all_manifest_profile_triples()

PHASE_CONSTRUCTOR_UNIVERSE = (
    "skipboot_reset",
    "mcycle_commit",
    "instr_commit",
    "checkpoint_hook",
)


def _families(*names: str) -> frozenset[str]:
    return frozenset(names)


def _profiles(*triples: str) -> frozenset[str]:
    return frozenset(triples)


CPU_BRING_UP_PROFILE = format_profile_triple(
    ModelProfile.DMG,
    ResetProfile.SkipBoot,
    MemoryBehaviorProfile.DmgConservative,
)

SUITE_COVERAGE: dict[str, SuiteCoverage] = {
    "test_sm83_opcodes.py": SuiteCoverage(opcode_families=frozenset(ALL_FAMILIES)),
    "test_decode_completeness.py": SuiteCoverage(opcode_families=frozenset(ALL_FAMILIES)),
    "test_alu_generated_vectors.py": SuiteCoverage(opcode_families=_families("ADD", "SUB", "AND", "OR", "XOR", "CP", "INC", "DEC")),
    "test_pyboy_oracle.py": SuiteCoverage(
        phase_constructors=frozenset({"checkpoint_hook"}),
        bus_regions=frozenset({"rom", "wram"}),
        rom_suites=frozenset({"ALU_LOOP"}),
        profile_triples=_profiles(CPU_BRING_UP_PROFILE),
    ),
    "test_pyboy_replay.py": SuiteCoverage(
        phase_constructors=frozenset({"checkpoint_hook"}),
        bus_regions=frozenset({"rom", "wram"}),
        rom_suites=frozenset({"ALU_LOOP"}),
        profile_triples=_profiles(CPU_BRING_UP_PROFILE),
    ),
    "test_event_script_determinism.py": SuiteCoverage(
        phase_constructors=frozenset({"mcycle_commit"}),
        bus_regions=frozenset({"io", "wram"}),
        interrupt_causes=frozenset({"serial", "joypad"}),
        rom_suites=frozenset({"ALU_LOOP"}),
        profile_triples=_profiles(CPU_BRING_UP_PROFILE),
    ),
    "test_reset_profile_support.py": SuiteCoverage(
        phase_constructors=frozenset({"skipboot_reset"}),
        profile_triples=_profiles(CPU_BRING_UP_PROFILE),
    ),
    "test_reset_profile.py": SuiteCoverage(
        phase_constructors=frozenset({"skipboot_reset"}),
        profile_triples=_profiles(CPU_BRING_UP_PROFILE),
    ),
    "test_cpu_lockstep.py": SuiteCoverage(
        phase_constructors=frozenset({"instr_commit"}),
        bus_regions=frozenset({"rom", "wram"}),
        rom_suites=frozenset({"ALU_LOOP"}),
        profile_triples=_profiles(CPU_BRING_UP_PROFILE),
    ),
    "test_cpu_single_op.py": SuiteCoverage(
        opcode_families=_families("load", "memory_load", "stack", "bitops", "alu16", "alu8", "control_flow"),
        phase_constructors=frozenset({"instr_commit"}),
        bus_regions=frozenset({"rom", "wram"}),
        profile_triples=_profiles(CPU_BRING_UP_PROFILE),
    ),
    "test_loads_basic.py": SuiteCoverage(
        phase_constructors=frozenset({"checkpoint_hook"}),
        bus_regions=frozenset({"rom", "wram", "hram"}),
        rom_suites=frozenset({"LOADS_BASIC"}),
        profile_triples=_profiles(CPU_BRING_UP_PROFILE),
    ),
    "test_alu_flags.py": SuiteCoverage(
        phase_constructors=frozenset({"checkpoint_hook"}),
        bus_regions=frozenset({"rom", "wram", "hram"}),
        rom_suites=frozenset({"ALU_FLAGS"}),
        profile_triples=_profiles(CPU_BRING_UP_PROFILE),
    ),
    "test_alu16_sp.py": SuiteCoverage(
        phase_constructors=frozenset({"checkpoint_hook"}),
        bus_regions=frozenset({"rom", "wram", "hram"}),
        rom_suites=frozenset({"ALU16_SP"}),
        profile_triples=_profiles(CPU_BRING_UP_PROFILE),
    ),
    "test_flow_stack.py": SuiteCoverage(
        phase_constructors=frozenset({"checkpoint_hook"}),
        bus_regions=frozenset({"rom", "wram", "hram"}),
        rom_suites=frozenset({"FLOW_STACK"}),
        profile_triples=_profiles(CPU_BRING_UP_PROFILE),
    ),
    "test_cb_bitops.py": SuiteCoverage(
        phase_constructors=frozenset({"checkpoint_hook"}),
        bus_regions=frozenset({"rom", "wram", "hram"}),
        rom_suites=frozenset({"CB_BITOPS"}),
        profile_triples=_profiles(CPU_BRING_UP_PROFILE),
    ),
    "test_mem_rwb.py": SuiteCoverage(
        phase_constructors=frozenset({"checkpoint_hook"}),
        bus_regions=frozenset({"rom", "wram", "hram"}),
        rom_suites=frozenset({"MEM_RWB"}),
        profile_triples=_profiles(CPU_BRING_UP_PROFILE),
    ),
    "test_alu_loop.py": SuiteCoverage(
        phase_constructors=frozenset({"checkpoint_hook"}),
        bus_regions=frozenset({"rom", "wram", "hram"}),
        rom_suites=frozenset({"ALU_LOOP"}),
        profile_triples=_profiles(CPU_BRING_UP_PROFILE),
    ),
    "test_cpu_invariants_loads.py": SuiteCoverage(opcode_families=_families("load", "memory_load")),
    "test_cpu_invariants_flow.py": SuiteCoverage(opcode_families=_families("control_flow")),
    "test_arch_time_invariants.py": SuiteCoverage(
        phase_constructors=frozenset({"skipboot_reset", "mcycle_commit"}),
        profile_triples=_profiles(CPU_BRING_UP_PROFILE),
    ),
}


def _suite_coverage_dict(coverage: SuiteCoverage) -> dict[str, list[str]]:
    data = asdict(coverage)
    return {key: sorted(value) for key, value in data.items() if value}


def build_coverage_snapshot(passed_suite_labels: Iterable[str]) -> CoverageSnapshot:
    passed = tuple(sorted(set(passed_suite_labels)))
    covered_by_dimension: dict[str, set[str]] = {
        "opcode_families": set(),
        "phase_constructors": set(),
        "bus_regions": set(),
        "interrupt_causes": set(),
        "rom_suites": set(),
        "profile_triples": set(),
    }
    suite_coverage: dict[str, dict[str, list[str]]] = {}
    for label in passed:
        coverage = SUITE_COVERAGE.get(label, SuiteCoverage())
        suite_coverage[label] = _suite_coverage_dict(coverage)
        covered_by_dimension["opcode_families"].update(coverage.opcode_families)
        covered_by_dimension["phase_constructors"].update(coverage.phase_constructors)
        covered_by_dimension["bus_regions"].update(coverage.bus_regions)
        covered_by_dimension["interrupt_causes"].update(coverage.interrupt_causes)
        covered_by_dimension["rom_suites"].update(coverage.rom_suites)
        covered_by_dimension["profile_triples"].update(coverage.profile_triples)

    universes = {
        "opcode_families": ("Opcode families", ALL_FAMILIES),
        "phase_constructors": ("Phase/continuation constructors", PHASE_CONSTRUCTOR_UNIVERSE),
        "bus_regions": ("Bus regions", BUS_REGION_UNIVERSE),
        "interrupt_causes": ("Interrupt causes", INTERRUPT_CAUSE_UNIVERSE),
        "rom_suites": ("ROM suites", ALL_ROM_SUITES),
        "profile_triples": ("Reset/model profiles", ALL_PROFILE_TRIPLES),
    }

    dimensions = {}
    for key, (label, universe) in universes.items():
        covered = tuple(sorted(item for item in covered_by_dimension[key] if item in universe))
        uncovered = tuple(item for item in universe if item not in covered)
        dimensions[key] = CoverageDimension(
            label=label,
            universe=tuple(universe),
            covered=covered,
            uncovered=uncovered,
        )

    return CoverageSnapshot(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        passed_suites=passed,
        dimensions=dimensions,
        suite_coverage=suite_coverage,
    )


def write_coverage_snapshot(
    passed_suite_labels: Iterable[str],
    *,
    destination: Path = DEFAULT_COVERAGE_PATH,
) -> CoverageSnapshot:
    snapshot = build_coverage_snapshot(passed_suite_labels)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(snapshot.to_jsonable(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot


def report_lines(snapshot: CoverageSnapshot) -> list[str]:
    ordered_keys = (
        "opcode_families",
        "phase_constructors",
        "bus_regions",
        "interrupt_causes",
        "rom_suites",
        "profile_triples",
    )
    return [snapshot.dimensions[key].summary_line() for key in ordered_keys]
