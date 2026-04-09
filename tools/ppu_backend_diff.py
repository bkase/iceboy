from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
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
    sim_array_capture: Path | None
    inferred_ram_capture: Path | None
    sim_array_generator: "BackendDiffGenerator | None"
    inferred_ram_generator: "BackendDiffGenerator | None"
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


@dataclass(frozen=True)
class BackendDiffGenerator:
    runner: str
    target: str
    dots: int = 8


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


def _parse_generator(raw: object) -> BackendDiffGenerator | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("scenario generator must be a mapping")
    runner = str(raw.get("runner", ""))
    target = str(raw.get("target", ""))
    if not runner or not target:
        raise ValueError("scenario generator requires runner and target")
    dots_raw = raw.get("dots", 8)
    dots = int(dots_raw)
    if dots <= 0:
        raise ValueError("scenario generator dots must be positive")
    return BackendDiffGenerator(runner=runner, target=target, dots=dots)


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
                sim_array_capture=(
                    None if raw.get("sim_array_capture") is None else _resolve_path(path.parent, raw["sim_array_capture"])
                ),
                inferred_ram_capture=(
                    None
                    if raw.get("inferred_ram_capture") is None
                    else _resolve_path(path.parent, raw["inferred_ram_capture"])
                ),
                sim_array_generator=_parse_generator(raw.get("sim_array_generator")),
                inferred_ram_generator=_parse_generator(raw.get("inferred_ram_generator")),
                scopes=_parse_scopes(raw["scopes"]),
            )
        )
    return tuple(scenarios)


def load_capture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def materialize_capture(
    scenario: BackendDiffScenario,
    side: str,
    *,
    temp_dir: Path,
) -> Path:
    capture = getattr(scenario, f"{side}_capture")
    generator = getattr(scenario, f"{side}_generator")
    if capture is not None and generator is None:
        return capture
    if generator is None:
        raise ValueError(f"{scenario.name} {side} requires either a capture path or a generator")
    if generator.runner != "swim":
        raise ValueError(f"unsupported backend diff generator runner: {generator.runner}")

    target = temp_dir / f"{scenario.name}_{side}.json"
    env = os.environ.copy()
    env["ICEBOY_BACKEND_DIFF_CAPTURE_PATH"] = str(target)
    env["ICEBOY_BACKEND_DIFF_SCENARIO"] = scenario.name
    env["ICEBOY_BACKEND_DIFF_BACKEND"] = side
    env["ICEBOY_BACKEND_DIFF_CAPTURE_DOTS"] = str(generator.dots)
    subprocess.run(
        [str(Path.home() / ".cargo" / "bin" / "swim"), "test", generator.target],
        cwd=ROOT,
        env=env,
        check=True,
    )
    return target


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
    with tempfile.TemporaryDirectory(prefix="iceboy-backend-diff-") as tmpdir:
        temp_root = Path(tmpdir)
        sim_array = load_capture(materialize_capture(scenario, "sim_array", temp_dir=temp_root))
        inferred_ram = load_capture(materialize_capture(scenario, "inferred_ram", temp_dir=temp_root))
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
