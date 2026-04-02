from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "test" / "harness"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.pyboy.oracle import CommitPoint, PyBoyOracle
from event_script_support import predicted_traces_for_script, stimulus_from_events, striped_manifest_entry, striped_stimulus_schedule
from fixtures import event_script
from roms.build_micro_rom import build_alu_loop
from spec.profiles import ModelProfile, ResetProfile


HOOK_ADDRS = (0x0150, 0x0152, 0x0154, 0x0155, 0x0156)


class EventScriptDeterminismTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.rom_path = Path(cls._tmpdir.name) / "alu_loop.gb"
        cls.rom_path.write_bytes(build_alu_loop())
        cls.commit_points = tuple(CommitPoint(bank=0, addr=addr, label=f"hook_{addr:04X}") for addr in HOOK_ADDRS)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmpdir.cleanup()

    def _run_oracle_script(self, *, seed: int, commit_count: int) -> tuple[object, tuple[object, ...], str]:
        manifest_entry = striped_manifest_entry(seed=seed, timeout_commits=max(commit_count + 8, 32))
        script = event_script(seed, manifest_entry)

        with PyBoyOracle(self.rom_path, commit_points=self.commit_points) as oracle:
            oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)
            commits = []
            for commit_index in range(commit_count):
                for ev in script.events_for_commit(commit_index):
                    oracle.write_event(ev)
                commits.append(oracle.step_commit())
            snapshot_hash = hashlib.sha256(oracle.snapshot()).hexdigest()
        return script, tuple(commits), snapshot_hash

    def test_same_seed_replays_identically_through_oracle(self) -> None:
        left = self._run_oracle_script(seed=7, commit_count=5)
        right = self._run_oracle_script(seed=7, commit_count=5)
        self.assertEqual(left, right)

    def test_harness_schedule_matches_generator_commit_indices(self) -> None:
        manifest_entry = striped_manifest_entry(seed=7, timeout_commits=40)
        script = event_script(7, manifest_entry)
        schedule = striped_stimulus_schedule(seed=7, timeout_commits=40)

        self.assertTrue(all(event.commit_index is not None and event.checkpoint is None for event in script.events))
        translated = {
            commit_index: stimulus_from_events(script.events_for_commit(commit_index))
            for commit_index in range(40)
            if script.events_for_commit(commit_index)
        }
        self.assertEqual(translated, schedule)

    def test_same_event_stream_yields_repeatable_comparison_bundle(self) -> None:
        script, commits, _ = self._run_oracle_script(seed=11, commit_count=5)
        replay_script, replay_commits, _ = self._run_oracle_script(seed=11, commit_count=5)

        expected_traces = predicted_traces_for_script(script, 5)
        replay_traces = predicted_traces_for_script(replay_script, 5)
        self.assertEqual(expected_traces, replay_traces)
        self.assertEqual(len(commits), len(expected_traces))
        self.assertEqual(len(replay_commits), len(replay_traces))

        comparison = tuple(
            (commit.seq, commit.pc_before, commit.opcode, trace.cpu_arch_time_enable, trace.freeze_arch_time, trace.cpu_hold_only)
            for commit, trace in zip(commits, expected_traces)
        )
        replay_comparison = tuple(
            (commit.seq, commit.pc_before, commit.opcode, trace.cpu_arch_time_enable, trace.freeze_arch_time, trace.cpu_hold_only)
            for commit, trace in zip(replay_commits, replay_traces)
        )
        self.assertEqual(comparison, replay_comparison)


if __name__ == "__main__":
    unittest.main()
