"""Async lockstep orchestration between a DUT driver and the oracle."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from bench.pyboy.comparator import CompareResult, compare_commit
from bench.pyboy.hooks import HookManifest, build_hook_manifest
from bench.pyboy.hook_driver import HookDriver
from bench.pyboy.trace_formatter import format_compare_result
from spec.compare_scopes import CompareField, OracleMode, comparison_fields_for_mode


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())


def _load_harness_symbol(filename: str, symbol: str):
    module_path = ROOT / "test" / "harness" / filename
    spec = importlib.util.spec_from_file_location(f"_iceboy_{module_path.stem}", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load harness module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return getattr(module, symbol)


@dataclass(frozen=True)
class LockstepStep:
    commit_index: int
    dut_trace: Any
    oracle_state: Any
    comparison: CompareResult


@dataclass(frozen=True)
class TestResult:
    matched: bool
    steps: tuple[LockstepStep, ...]
    mismatch: LockstepStep | None = None
    mismatch_report: str | None = None


def load_rom(
    rom_path: str | Path,
    *,
    sym_path: str | Path | None = None,
    checkpoint_symbols: Iterable[str] = (),
    max_frames_per_commit: int = 180,
) -> tuple[HookDriver, HookManifest]:
    resolved_sym = Path(sym_path) if sym_path is not None else Path(rom_path).with_suffix(".sym")
    manifest = build_hook_manifest(resolved_sym, checkpoint_symbols=tuple(checkpoint_symbols))
    return HookDriver.from_manifest(rom_path, manifest, max_frames_per_commit=max_frames_per_commit), manifest


async def run_lockstep(
    oracle: Any,
    dut_driver: Any,
    event_script: Any,
    oracle_mode: OracleMode,
    *,
    commit_limit: int,
    compare_fields: Iterable[CompareField] | None = None,
    bus_read_data: int = 0,
    irq_pending: int = 0,
) -> TestResult:
    fields = tuple(compare_fields) if compare_fields is not None else tuple(comparison_fields_for_mode(oracle_mode))
    steps = []
    stimulus_from_events = _load_harness_symbol("event_script_support.py", "stimulus_from_events")

    for commit_index in range(commit_limit):
        events = event_script.events_for_commit(commit_index) if event_script is not None else ()
        for event in events:
            oracle.write_event(event)

        stimulus = stimulus_from_events(events)
        if oracle_mode is OracleMode.InstrCommit and hasattr(dut_driver, "step_instruction"):
            dut_trace = await dut_driver.step_instruction()
        else:
            dut_trace = await dut_driver.step_mcycle(
                stimulus=stimulus,
                bus_read_data=bus_read_data,
                irq_pending=irq_pending,
            )
        oracle_state = oracle.step_commit()
        comparison = compare_commit(dut_trace, oracle_state, fields)
        step = LockstepStep(
            commit_index=commit_index,
            dut_trace=dut_trace,
            oracle_state=oracle_state,
            comparison=comparison,
        )
        steps.append(step)
        if not comparison.matched:
            return TestResult(
                matched=False,
                steps=tuple(steps),
                mismatch=step,
                mismatch_report=format_compare_result(comparison, dut_trace=dut_trace, oracle_state=oracle_state),
            )

    return TestResult(matched=True, steps=tuple(steps))
