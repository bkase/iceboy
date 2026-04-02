"""Hook-driven lockstep adapter built on top of the PyBoy oracle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from bench.actions.generators import SimEvent
from bench.pyboy.hooks import HookManifest
from bench.pyboy.oracle import OracleCommit, PyBoyOracle
from spec.profiles import ModelProfile, ResetProfile


@dataclass(frozen=True)
class LockstepMismatch:
    commit_index: int
    expected: OracleCommit
    actual: OracleCommit


@dataclass(frozen=True)
class LockstepResult:
    matched: bool
    commits: tuple[OracleCommit, ...]
    mismatch: LockstepMismatch | None = None


class HookDriver:
    def __init__(self, oracle: PyBoyOracle, manifest: HookManifest) -> None:
        self.oracle = oracle
        self.manifest = manifest

    @classmethod
    def from_manifest(
        cls,
        rom_path: str | Path,
        manifest: HookManifest,
        *,
        max_frames_per_commit: int = 180,
    ) -> "HookDriver":
        oracle = PyBoyOracle(
            rom_path,
            sym_path=manifest.sym_path,
            commit_points=manifest.commit_points(),
            max_frames_per_commit=max_frames_per_commit,
        )
        return cls(oracle=oracle, manifest=manifest)

    def __enter__(self) -> "HookDriver":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        self.oracle.close()

    def reset(self, model_profile: ModelProfile | str, reset_profile: ResetProfile | str) -> None:
        self.oracle.reset(model_profile, reset_profile)

    def step_commit(self) -> OracleCommit:
        return self.oracle.step_commit()

    def write_event(self, ev: SimEvent) -> None:
        self.oracle.write_event(ev)

    def snapshot(self) -> bytes:
        return self.oracle.snapshot()

    def restore(self, snapshot: bytes) -> None:
        self.oracle.restore(snapshot)

    def collect_commits(self, limit: int) -> tuple[OracleCommit, ...]:
        commits = []
        for _ in range(limit):
            commit = self.step_commit()
            commits.append(commit)
            if self._is_terminal(commit):
                break
        return tuple(commits)

    def compare_commits(self, expected_commits: Iterable[OracleCommit]) -> LockstepResult:
        commits = []
        for commit_index, expected in enumerate(expected_commits):
            actual = self.step_commit()
            commits.append(actual)
            if actual != expected:
                return LockstepResult(
                    matched=False,
                    commits=tuple(commits),
                    mismatch=LockstepMismatch(
                        commit_index=commit_index,
                        expected=expected,
                        actual=actual,
                    ),
                )
            if self._is_terminal(actual):
                break
        return LockstepResult(matched=True, commits=tuple(commits))

    def _is_terminal(self, commit: OracleCommit) -> bool:
        if commit.label is None:
            return False
        labels = set(commit.label.split("|"))
        return any(label in labels for label in self.manifest.terminal_labels())
