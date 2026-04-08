from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.compare_oracles import PpuCompareScope, compare_oracle_streams


DEFAULT_MANIFEST = ROOT / "bench" / "manifests" / "ppu_backend_diff_scenarios.yaml"


@dataclass(frozen=True)
class BackendDiffScenario:
    name: str
    description: str
    sim_array_capture: Path
    inferred_ram_capture: Path
    scopes: tuple[PpuCompareScope, ...]


@dataclass(frozen=True)
class BackendDiffOutcome:
    scenario: str
    scope: PpuCompareScope
    matched: bool
    first_bad_index: int | None
    field_path: str | None
    expected: Any
    actual: Any


def _resolve_path(base: Path, raw: object) -> Path:
    if not isinstance(raw, str) or not raw:
        raise ValueError("scenario capture path must be a non-empty string")
    path = Path(raw)
    if not path.is_absolute():
        path = (base / path).resolve()
    return path


def _parse_scopes(raw: object) -> tuple[PpuCompareScope, ...]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("scenario scopes must be a non-empty list")
    scopes: list[PpuCompareScope] = []
    for entry in raw:
        scopes.append(PpuCompareScope(str(entry)))
    return tuple(scopes)


def load_manifest(path: Path = DEFAULT_MANIFEST) -> tuple[BackendDiffScenario, ...]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("backend diff manifest must be a mapping")
    scenarios_raw = data.get("scenarios")
    if not isinstance(scenarios_raw, list) or not scenarios_raw:
        raise ValueError("backend diff manifest requires a non-empty scenarios list")

    scenarios: list[BackendDiffScenario] = []
    for raw in scenarios_raw:
        if not isinstance(raw, dict):
            raise ValueError("backend diff scenario entries must be mappings")
        scenarios.append(
            BackendDiffScenario(
                name=str(raw["name"]),
                description=str(raw["description"]),
                sim_array_capture=_resolve_path(path.parent, raw["sim_array_capture"]),
                inferred_ram_capture=_resolve_path(path.parent, raw["inferred_ram_capture"]),
                scopes=_parse_scopes(raw["scopes"]),
            )
        )
    return tuple(scenarios)


def load_capture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _stream_for_scope(capture: dict[str, Any], scope: PpuCompareScope) -> list[Any]:
    key = {
        PpuCompareScope.DotCommit: "dot_commit",
        PpuCompareScope.ScanlineSummary: "scanline_summary",
        PpuCompareScope.FrameHash: "frame_hash",
    }[scope]
    stream = capture.get(key, [])
    if not isinstance(stream, list):
        raise ValueError(f"capture key {key} must be a list")
    return stream


def compare_scenario(scenario: BackendDiffScenario) -> tuple[BackendDiffOutcome, ...]:
    sim_array = load_capture(scenario.sim_array_capture)
    inferred_ram = load_capture(scenario.inferred_ram_capture)
    outcomes: list[BackendDiffOutcome] = []
    for scope in scenario.scopes:
        result = compare_oracle_streams(
            "sim_array",
            _stream_for_scope(sim_array, scope),
            "inferred_ram",
            _stream_for_scope(inferred_ram, scope),
            scope,
        )
        outcomes.append(
            BackendDiffOutcome(
                scenario=scenario.name,
                scope=scope,
                matched=result.matched,
                first_bad_index=result.first_bad_index,
                field_path=result.field_path,
                expected=result.expected,
                actual=result.actual,
            )
        )
    return tuple(outcomes)


def compare_manifest(path: Path = DEFAULT_MANIFEST, *, scenario_name: str | None = None) -> tuple[BackendDiffOutcome, ...]:
    scenarios = load_manifest(path)
    if scenario_name is not None:
        scenarios = tuple(scenario for scenario in scenarios if scenario.name == scenario_name)
        if not scenarios:
            raise ValueError(f"unknown backend diff scenario: {scenario_name}")
    outcomes: list[BackendDiffOutcome] = []
    for scenario in scenarios:
        outcomes.extend(compare_scenario(scenario))
    return tuple(outcomes)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Compare PPU backend-diff capture streams.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--scenario", help="Run a single named scenario")
    parser.add_argument("--json", action="store_true", help="Emit JSON outcomes")
    args = parser.parse_args()

    outcomes = compare_manifest(args.manifest, scenario_name=args.scenario)
    if args.json:
        print(json.dumps([asdict(item) for item in outcomes], indent=2, sort_keys=True))
    else:
        for outcome in outcomes:
            status = "PASS" if outcome.matched else "FAIL"
            print(f"[{status}] {outcome.scenario} {outcome.scope.value}")
            if not outcome.matched:
                print(f"  first_bad_index={outcome.first_bad_index}")
                print(f"  field_path={outcome.field_path}")
                print(f"  expected={outcome.expected}")
                print(f"  actual={outcome.actual}")
    return 0 if all(item.matched for item in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
