from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spade_cocotb_smoke import patch_cocotb_config_wrapper
from test.harness.coverage_tracker import report_lines as dynamic_coverage_lines
from test.harness.coverage_tracker import write_coverage_snapshot
from test.harness.logging_std import TestLogger, add_logging_args, logger_from_args


UV = "uv"
SWIM = str(Path.home() / ".cargo" / "bin" / "swim")
PYTHON_LOCK = "toolchain/python.lock"
ENSURE_SWIM_PYTHON_DEPS = ROOT / "tools" / "ensure_swim_python_deps.sh"
TIER_CONFIG_PATH = ROOT / "test" / "tiers.yaml"
FAILED_COUNT_RE = re.compile(r"(\d+)/(\d+)\s+failed")
UNITTEST_RAN_RE = re.compile(r"Ran (\d+) tests? in")
UNITTEST_FAILED_RE = re.compile(r"FAILED \((.*?)\)")


@dataclass(frozen=True)
class SuiteDefinition:
    tier: str
    label: str
    runner: str
    target: str
    nightly_only: bool = False


@dataclass(frozen=True)
class TierDefinition:
    key: str
    label: str


@dataclass(frozen=True)
class SuiteResult:
    definition: SuiteDefinition
    passed: int
    failed: int
    duration_s: float
    exit_code: int
    output: str


@dataclass(frozen=True)
class TierPreset:
    name: str
    tier_keys: tuple[str, ...]
    include_nightly_only: bool = False
    suite_labels: tuple[str, ...] = ()


TIERS: tuple[TierDefinition, ...] = (
    TierDefinition("meta", "Meta/Infrastructure"),
    TierDefinition("unit", "Unit Tests"),
    TierDefinition("formal", "Formal Verification"),
    TierDefinition("rom", "ROM Differential"),
    TierDefinition("lockstep", "Lockstep"),
    TierDefinition("invariant", "Invariant"),
    TierDefinition("power", "Power"),
)

SUITES: tuple[SuiteDefinition, ...] = (
    SuiteDefinition("meta", "test_logging_std.py", "python", "tools.tests.test_logging_std"),
    SuiteDefinition("meta", "test_harness_base.py", "python", "tools.tests.test_harness_base"),
    SuiteDefinition("meta", "test_profiles.py", "python", "tools.tests.test_profiles"),
    SuiteDefinition("meta", "test_sim_scaffolds.py", "python", "tools.tests.test_sim_scaffolds"),
    SuiteDefinition("meta", "test_event_generators.py", "python", "tools.tests.test_event_generators"),
    SuiteDefinition(
        "meta",
        "test_event_script_determinism.py",
        "python",
        "tools.tests.test_event_script_determinism",
    ),
    SuiteDefinition("meta", "test_lockstep_driver.py", "python", "tools.tests.test_lockstep_driver"),
    SuiteDefinition("meta", "test_pyboy_oracle.py", "python", "tools.tests.test_pyboy_oracle"),
    SuiteDefinition("meta", "test_pyboy_comparator.py", "python", "tools.tests.test_pyboy_comparator"),
    SuiteDefinition(
        "meta",
        "test_reset_profile_support.py",
        "python",
        "tools.tests.test_reset_profile_support",
    ),
    SuiteDefinition("meta", "test_waveform_config.py", "python", "tools.tests.test_waveform_config"),
    SuiteDefinition(
        "meta",
        "test_spade_cocotb_pipeline.py",
        "python",
        "tools.tests.test_spade_cocotb_pipeline",
    ),
    SuiteDefinition("meta", "test_verilator_backend.py", "python", "tools.tests.test_verilator_backend"),
    SuiteDefinition("meta", "test_local_entrypoints.py", "python", "tools.tests.test_local_entrypoints"),
    SuiteDefinition("meta", "test_gate_milestone_a.py", "python", "tools.tests.test_gate_milestone_a"),
    SuiteDefinition("meta", "test_coverage_tracker.py", "python", "tools.tests.test_coverage_tracker"),
    SuiteDefinition("meta", "test_rom_runner.py", "python", "tools.tests.test_rom_runner"),
    SuiteDefinition("meta", "test_e2e_smoke.py", "swim", "test_e2e_smoke"),
    SuiteDefinition("meta", "test_cpu_types.py", "python", "tools.tests.test_cpu_types"),
    SuiteDefinition("meta", "test_cpu_debug.py", "python", "tools.tests.test_cpu_debug"),
    SuiteDefinition("meta", "test_cpu_regs.py", "python", "tools.tests.test_cpu_regs"),
    SuiteDefinition("meta", "test_cpu_alu.py", "python", "tools.tests.test_cpu_alu"),
    SuiteDefinition("meta", "test_cpu_decode_types.py", "python", "tools.tests.test_cpu_decode_types"),
    SuiteDefinition("meta", "test_cpu_decode.py", "python", "tools.tests.test_cpu_decode"),
    SuiteDefinition("meta", "test_cpu_core_stub.py", "python", "tools.tests.test_cpu_core_stub"),
    SuiteDefinition("meta", "test_cpu_semantics.py", "python", "tools.tests.test_cpu_semantics"),
    SuiteDefinition("meta", "test_bus_types.py", "python", "tools.tests.test_bus_types"),
    SuiteDefinition("meta", "test_membus_scaffold.py", "python", "tools.tests.test_membus_scaffold"),
    SuiteDefinition("meta", "test_timebase_scaffold.py", "python", "tools.tests.test_timebase_scaffold"),
    SuiteDefinition("unit", "test_sm83_opcodes.py", "python", "tools.tests.test_sm83_opcodes"),
    SuiteDefinition(
        "unit",
        "test_decode_completeness.py",
        "python",
        "tools.tests.test_decode_completeness",
    ),
    SuiteDefinition(
        "unit",
        "test_alu_generated_vectors.py",
        "python",
        "tools.tests.test_alu_generated_vectors",
    ),
    SuiteDefinition("unit", "test_reference_specs.py", "python", "tools.tests.test_reference_specs"),
    SuiteDefinition("unit", "test_rom_abi.py", "python", "tools.tests.test_rom_abi"),
    SuiteDefinition("unit", "test_pyboy_hooks.py", "python", "tools.tests.test_pyboy_hooks"),
    SuiteDefinition("unit", "test_pyboy_replay.py", "python", "tools.tests.test_pyboy_replay"),
    SuiteDefinition(
        "unit",
        "test_divergence_artifacts.py",
        "python",
        "tools.tests.test_divergence_artifacts",
    ),
    SuiteDefinition("unit", "test_main.py", "swim", "test_main"),
    SuiteDefinition("unit", "test_alu.py", "swim", "test_alu"),
    SuiteDefinition("unit", "test_alu_nightly.py", "swim", "test_alu_nightly", nightly_only=True),
    SuiteDefinition("unit", "test_bus_fabric.py", "swim", "test_bus_fabric"),
    SuiteDefinition("unit", "test_decode.py", "swim", "test_decode"),
    SuiteDefinition("unit", "test_decode_cb.py", "swim", "test_decode_cb"),
    SuiteDefinition("unit", "test_membus.py", "swim", "test_membus"),
    SuiteDefinition("unit", "test_misc_instructions.py", "swim", "test_misc_instructions"),
    SuiteDefinition("unit", "test_regs.py", "swim", "test_regs"),
    SuiteDefinition("unit", "test_semantics.py", "swim", "test_semantics"),
    SuiteDefinition("unit", "test_semantics_alu.py", "swim", "test_semantics_alu"),
    SuiteDefinition("unit", "test_semantics_cb.py", "swim", "test_semantics_cb"),
    SuiteDefinition("unit", "test_semantics_flow.py", "swim", "test_semantics_flow"),
    SuiteDefinition("unit", "test_semantics_loads.py", "swim", "test_semantics_loads"),
    SuiteDefinition("unit", "test_semantics_wordalu.py", "swim", "test_semantics_wordalu"),
    SuiteDefinition("unit", "test_timebase.py", "swim", "test_timebase"),
    SuiteDefinition("formal", "cpu_invariants.sby", "shell", "tools/run_formal_cpu_invariants.sh"),
    SuiteDefinition("formal", "cpu_reset.sby", "shell", "tools/run_formal_cpu_reset.sh"),
    SuiteDefinition("formal", "cpu_hold.sby", "shell", "tools/run_formal_cpu_hold.sh"),
    SuiteDefinition("rom", "test_alu16_sp.py", "swim", "test_alu16_sp"),
    SuiteDefinition("rom", "test_alu_flags.py", "swim", "test_alu_flags"),
    SuiteDefinition("rom", "test_alu_loop.py", "swim", "test_alu_loop"),
    SuiteDefinition("rom", "test_cb_bitops.py", "swim", "test_cb_bitops"),
    SuiteDefinition("rom", "test_flow_stack.py", "swim", "test_flow_stack"),
    SuiteDefinition("rom", "test_loads_basic.py", "swim", "test_loads_basic"),
    SuiteDefinition("rom", "test_mem_rwb.py", "swim", "test_mem_rwb"),
    SuiteDefinition("lockstep", "test_cpu_lockstep.py", "swim", "test_cpu_lockstep"),
    SuiteDefinition("invariant", "test_cpu_invariants_loads.py", "swim", "test_cpu_invariants_loads"),
    SuiteDefinition("invariant", "test_cpu_invariants_flow.py", "swim", "test_cpu_invariants_flow"),
    SuiteDefinition("invariant", "test_arch_time_invariants.py", "swim", "test_arch_time_invariants"),
)


def build_parser() -> argparse.ArgumentParser:
    parser = add_logging_args(
        argparse.ArgumentParser(description="Run Iceboy verification tiers from a single entry point.")
    )
    parser.add_argument("--tier", help="Comma-separated tier keys to run.")
    parser.add_argument("--quick", action="store_true", help="Run the fast subset (meta + unit).")
    parser.add_argument("--nightly", action="store_true", help="Include nightly-only suites.")
    parser.add_argument("--sim", choices=("icarus", "verilator"), default="icarus")
    parser.add_argument("--coverage", action="store_true", help="Print tier and suite coverage.")
    parser.add_argument("--junit-xml", type=Path, help="Write a JUnit XML report.")
    return parser


def load_tier_config(path: Path = TIER_CONFIG_PATH) -> dict[str, object]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def preset_map(tier_config: dict[str, object]) -> dict[str, TierPreset]:
    presets = {}
    raw_presets = tier_config.get("presets", {})
    if not isinstance(raw_presets, dict):
        return presets
    for name, raw in raw_presets.items():
        if not isinstance(raw, dict):
            continue
        presets[str(name)] = TierPreset(
            name=str(name),
            tier_keys=tuple(str(item) for item in raw.get("tier_keys", [])),
            include_nightly_only=bool(raw.get("include_nightly_only", False)),
            suite_labels=tuple(str(item) for item in raw.get("suite_labels", [])),
        )
    return presets


def parse_requested_tiers(args: argparse.Namespace, tier_config: dict[str, object] | None = None) -> list[str]:
    presets = preset_map(tier_config or load_tier_config())
    if args.quick:
        return ["meta", "unit"]
    if args.tier:
        expanded = []
        for item in [item.strip() for item in args.tier.split(",") if item.strip()]:
            preset = presets.get(item)
            if preset is not None:
                for tier_key in preset.tier_keys:
                    if tier_key not in expanded:
                        expanded.append(tier_key)
                continue
            if item not in expanded:
                expanded.append(item)
        return expanded
    return [tier.key for tier in TIERS]


def requested_preset_names(args: argparse.Namespace, tier_config: dict[str, object] | None = None) -> list[str]:
    if not args.tier:
        return []
    presets = preset_map(tier_config or load_tier_config())
    return [item for item in [part.strip() for part in args.tier.split(",") if part.strip()] if item in presets]


def include_nightly(args: argparse.Namespace, tier_config: dict[str, object] | None = None) -> bool:
    if args.nightly:
        return True
    presets = preset_map(tier_config or load_tier_config())
    return any(presets[name].include_nightly_only for name in requested_preset_names(args, tier_config))


def selected_tiers(requested: Iterable[str]) -> list[TierDefinition]:
    requested_set = set(requested)
    return [tier for tier in TIERS if tier.key in requested_set]


def suites_for_tier(tier: str, *, nightly: bool) -> list[SuiteDefinition]:
    suites = [suite for suite in SUITES if suite.tier == tier]
    if not nightly:
        suites = [suite for suite in suites if not suite.nightly_only]
    return suites


def command_env(*, sim: str, nightly: bool = False) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"/opt/homebrew/bin:{env.get('PATH', '')}"
    env["SIM"] = sim
    env["ICEBOY_SMOKE_SIM"] = sim
    if nightly:
        env["ICEBOY_NIGHTLY"] = "1"
    return env


def suite_command(definition: SuiteDefinition) -> list[str]:
    if definition.runner == "python":
        return [UV, "run", "--with-requirements", PYTHON_LOCK, "python", "-m", "unittest", definition.target]
    if definition.runner == "swim":
        return [SWIM, "test", definition.target]
    if definition.runner == "shell":
        return ["bash", definition.target]
    raise ValueError(f"Unsupported runner: {definition.runner}")


def parse_suite_counts(definition: SuiteDefinition, output: str, exit_code: int) -> tuple[int, int]:
    if definition.runner == "swim":
        match = FAILED_COUNT_RE.search(output)
        if match:
            failed = int(match.group(1))
            total = int(match.group(2))
            return total - failed, failed
        return (1, 0) if exit_code == 0 else (0, 1)
    if definition.runner == "shell":
        return (1, 0) if exit_code == 0 else (0, 1)

    ran_match = UNITTEST_RAN_RE.search(output)
    total = int(ran_match.group(1)) if ran_match else 1
    if exit_code == 0:
        return total, 0

    failed = 0
    failed_match = UNITTEST_FAILED_RE.search(output)
    if failed_match:
        for part in failed_match.group(1).split(","):
            _, value = part.strip().split("=")
            failed += int(value)
    else:
        failed = 1
    return max(total - failed, 0), failed


def run_suite(definition: SuiteDefinition, *, sim: str, logger: TestLogger, nightly: bool) -> SuiteResult:
    env = command_env(sim=sim, nightly=nightly and definition.nightly_only)
    if definition.runner == "swim":
        patch_cocotb_config_wrapper()
        provisioned = subprocess.run(
            [str(ENSURE_SWIM_PYTHON_DEPS)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        if provisioned.returncode != 0:
            logger.fail_case(
                "failed to provision swim python dependencies",
                contexts={"output": "\n".join(part for part in [provisioned.stdout, provisioned.stderr] if part).strip()},
            )
            raise RuntimeError("failed to provision swim python dependencies")

    command = suite_command(definition)
    logger.step(f"Running {definition.label}: {' '.join(command)}")
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    duration_s = time.monotonic() - started
    output = "\n".join(part for part in [completed.stdout, completed.stderr] if part).strip()
    passed, failed = parse_suite_counts(definition, output, completed.returncode)
    suite_logger = TestLogger(suite_name=definition.label, stream=logger.stream, level=logger.level, json_mode=logger.json_mode)
    suite_logger.summary(passed=passed, failed=failed, duration_s=duration_s)
    if completed.returncode != 0:
        logger.fail_case(
            f"{definition.label} failed",
            duration_s=duration_s,
            contexts={"command": " ".join(command), "output": output},
        )
        raise RuntimeError(f"{definition.label} failed")
    return SuiteResult(
        definition=definition,
        passed=passed,
        failed=failed,
        duration_s=duration_s,
        exit_code=completed.returncode,
        output=output,
    )


def coverage_lines(tiers: list[TierDefinition], *, nightly: bool) -> list[str]:
    implemented = 0
    lines = []
    for tier in tiers:
        suites = suites_for_tier(tier.key, nightly=nightly)
        if suites:
            implemented += 1
        lines.append(f"{tier.label}: {len(suites)} suite(s)")
    lines.insert(0, f"Implemented tiers: {implemented}/{len(tiers)}")
    return lines


def configured_coverage_report_lines(tier_config: dict[str, object]) -> list[str]:
    lines = []
    raw = tier_config.get("coverage_report", [])
    if not isinstance(raw, list):
        return lines
    for item in raw:
        if not isinstance(item, dict):
            continue
        lines.append(f"{item['label']}: {item['value']}")
    return lines


def xfail_lines(tier_config: dict[str, object]) -> list[str]:
    lines = []
    raw = tier_config.get("xfail", [])
    if not isinstance(raw, list):
        return lines
    for item in raw:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"{item['suite']}: strict={item['strict']} bead={item['bead']} reason={item['reason']}"
        )
    return lines


def write_junit_xml(results: list[SuiteResult], target: Path) -> None:
    testsuites = ET.Element("testsuites")
    for tier in TIERS:
        tier_results = [result for result in results if result.definition.tier == tier.key]
        if not tier_results:
            continue
        suite_elem = ET.SubElement(
            testsuites,
            "testsuite",
            name=tier.label,
            tests=str(len(tier_results)),
            failures=str(sum(1 for result in tier_results if result.failed)),
        )
        for result in tier_results:
            case_elem = ET.SubElement(
                suite_elem,
                "testcase",
                classname=tier.key,
                name=result.definition.label,
                time=f"{result.duration_s:.3f}",
            )
            if result.failed:
                failure = ET.SubElement(case_elem, "failure", message="suite failed")
                failure.text = result.output
            system_out = ET.SubElement(case_elem, "system-out")
            system_out.text = result.output

    target.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(testsuites).write(target, encoding="utf-8", xml_declaration=True)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    tier_config = load_tier_config()
    tiers = selected_tiers(parse_requested_tiers(args, tier_config))
    nightly_enabled = include_nightly(args, tier_config)
    logger = logger_from_args(args, suite_name="ICEBOY VERIFICATION SUITE", stream=sys.stdout)
    logger.suite()

    preset_names = requested_preset_names(args, tier_config)
    if preset_names:
        logger.context("tier_presets", ", ".join(preset_names))
    for line in xfail_lines(tier_config):
        logger.context("xfail", line)

    results: list[SuiteResult] = []
    total_started = time.monotonic()
    for index, tier in enumerate(tiers, start=1):
        logger.step(f"[TIER {index}/{len(tiers)}] {tier.label}")
        tier_suites = suites_for_tier(tier.key, nightly=nightly_enabled)
        if not tier_suites:
            logger.context(tier.label, "no suites implemented")
            continue
        for definition in tier_suites:
            results.append(run_suite(definition, sim=args.sim, logger=logger, nightly=nightly_enabled))

    total_duration = time.monotonic() - total_started
    total_passed = sum(result.passed for result in results)
    total_failed = sum(result.failed for result in results)
    logger.summary(passed=total_passed, failed=total_failed, duration_s=total_duration)
    coverage_snapshot = write_coverage_snapshot(
        [result.definition.label for result in results if result.failed == 0]
    )

    if args.coverage:
        coverage_logger = TestLogger(
            suite_name="ICEBOY COVERAGE",
            stream=sys.stdout,
            level=logger.level,
            json_mode=logger.json_mode,
        )
        coverage_logger.suite()
        for line in coverage_lines(tiers, nightly=nightly_enabled):
            coverage_logger.context("coverage", line)
        for line in dynamic_coverage_lines(coverage_snapshot):
            coverage_logger.context("coverage", line)
        for line in configured_coverage_report_lines(tier_config):
            coverage_logger.context("coverage", line)

    if any(name in {"full", "nightly"} for name in preset_names):
        coverage_logger = TestLogger(
            suite_name="ICEBOY COVERAGE",
            stream=sys.stdout,
            level=logger.level,
            json_mode=logger.json_mode,
        )
        coverage_logger.suite()
        for line in dynamic_coverage_lines(coverage_snapshot):
            coverage_logger.context("coverage", line)
        for line in configured_coverage_report_lines(tier_config):
            coverage_logger.context("coverage", line)

    if args.junit_xml:
        write_junit_xml(results, args.junit_xml)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
