"""Divergence artifact management for oracle comparisons."""

from __future__ import annotations

import json
import importlib.util
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence, TextIO

from bench.pyboy.hook_driver import LockstepMismatch, LockstepResult
from bench.pyboy.oracle import OracleCommit
from bench.pyboy.replay import ReplayCapsule


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
class CommitWindowEntry:
    commit_index: int
    expected: OracleCommit
    actual: OracleCommit | None


@dataclass(frozen=True)
class DivergenceArtifacts:
    mismatch: LockstepMismatch
    commit_window: tuple[CommitWindowEntry, ...]
    replay_capsule: ReplayCapsule

    def summary(self) -> str:
        return (
            f"Lockstep divergence at commit {self.mismatch.commit_index}: "
            f"{self.mismatch.expected.label or '<unlabeled>'} field mismatch.\n"
            f"expected={self.mismatch.expected}\n"
            f"actual={self.mismatch.actual}"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "mismatch": {
                "commit_index": self.mismatch.commit_index,
                "expected": asdict(self.mismatch.expected),
                "actual": asdict(self.mismatch.actual),
            },
            "commit_window": [
                {
                    "commit_index": entry.commit_index,
                    "expected": asdict(entry.expected),
                    "actual": asdict(entry.actual) if entry.actual is not None else None,
                }
                for entry in self.commit_window
            ],
            "replay_capsule": self.replay_capsule.to_dict(),
        }


@dataclass(frozen=True)
class ArtifactFiles:
    summary_path: Path
    json_path: Path
    waveform_path: Path | None
    oracle_snapshot_path: Path | None
    divergence_window_path: Path | None


def build_divergence_artifacts(
    expected_commits: Sequence[OracleCommit],
    result: LockstepResult,
    replay_capsule: ReplayCapsule,
    *,
    window_radius: int = 5,
) -> DivergenceArtifacts:
    if result.mismatch is None:
        raise ValueError("LockstepResult must contain a mismatch to build divergence artifacts")

    mismatch_index = result.mismatch.commit_index
    start = max(0, mismatch_index - window_radius)
    end = min(len(expected_commits), mismatch_index + window_radius + 1)

    window = []
    for commit_index in range(start, end):
        actual = result.commits[commit_index] if commit_index < len(result.commits) else None
        window.append(
            CommitWindowEntry(
                commit_index=commit_index,
                expected=expected_commits[commit_index],
                actual=actual,
            )
        )

    return DivergenceArtifacts(
        mismatch=result.mismatch,
        commit_window=tuple(window),
        replay_capsule=replay_capsule,
    )


def emit_divergence_artifacts(
    artifacts: DivergenceArtifacts,
    artifact_dir: str | Path,
    *,
    waveform_path: str | Path | None = None,
    oracle_snapshot: bytes | None = None,
    stderr: TextIO | None = None,
) -> ArtifactFiles:
    destination = Path(artifact_dir)
    destination.mkdir(parents=True, exist_ok=True)

    summary_path = destination / "divergence_summary.txt"
    summary_text = artifacts.summary()
    summary_path.write_text(summary_text + "\n", encoding="utf-8")

    json_path = destination / "divergence.json"
    json_path.write_text(json.dumps(artifacts.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    copied_waveform: Path | None = None
    divergence_window_path: Path | None = None
    if waveform_path is not None:
        write_divergence_window_metadata = _load_harness_symbol(
            "waveform_config.py",
            "write_divergence_window_metadata",
        )
        source = Path(waveform_path)
        copied_waveform = destination / source.name
        shutil.copy2(source, copied_waveform)
        divergence_window_path = write_divergence_window_metadata(
            "lockstep_divergence",
            artifacts.mismatch.commit_index,
            artifact_root=destination,
            waveform_path=copied_waveform,
        )

    snapshot_path: Path | None = None
    if oracle_snapshot is not None:
        snapshot_path = destination / "oracle_snapshot.bin"
        snapshot_path.write_bytes(oracle_snapshot)

    stream = stderr if stderr is not None else sys.stderr
    stream.write(summary_text + "\n")

    return ArtifactFiles(
        summary_path=summary_path,
        json_path=json_path,
        waveform_path=copied_waveform,
        oracle_snapshot_path=snapshot_path,
        divergence_window_path=divergence_window_path,
    )
