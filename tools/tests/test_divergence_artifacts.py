from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from bench.actions.generators import JoypadButtons, JoypadButtonsEvent
from bench.pyboy.checkpoints import build_divergence_artifacts, emit_divergence_artifacts
from bench.pyboy.hook_driver import LockstepMismatch, LockstepResult
from bench.pyboy.hooks import build_hook_manifest
from bench.pyboy.oracle import BusRequest, BusResponse, OracleCommit, RegisterState
from bench.pyboy.replay import FirstDivergence, ReplayCapsule, ReplayEvent, build_hook_manifest_id
from spec.profiles import MemoryBehaviorProfile, ModelProfile, ResetProfile


SYMBOL_TEXT = """\
00:0150 __checkpoint_boot
00:0152 __commit_setup
00:0154 __pass
00:0156 __fail
"""


def make_commit(seq: int, pc: int, label: str) -> OracleCommit:
    return OracleCommit(
        schema_version=1,
        kind="Checkpoint",
        seq=seq,
        label=label,
        pc_before=pc,
        opcode=0x00,
        registers_after=RegisterState(a=seq, f=0, b=0, c=0, d=0, e=0, hl=0, sp=0xFFFE, pc=pc),
        phase_after="HookCheckpoint",
        bus_request=BusRequest(),
        bus_response=BusResponse(),
    )


class DivergenceArtifactsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.sym_path = Path(cls._tmpdir.name) / "artifacts.sym"
        cls.sym_path.write_text(SYMBOL_TEXT, encoding="utf-8")
        cls.manifest = build_hook_manifest(cls.sym_path)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmpdir.cleanup()

    def build_capsule(self) -> ReplayCapsule:
        return ReplayCapsule(
            rom_id="ALU_LOOP",
            model_profile=ModelProfile.DMG,
            reset_profile=ResetProfile.SkipBoot,
            memory_behavior_profile=MemoryBehaviorProfile.DmgConservative,
            random_seed=7,
            event_log=(ReplayEvent(commit_index=3, event=JoypadButtonsEvent(JoypadButtons.from_pressed(["a"]))),),
            sym_sha256=self.manifest.sym_sha256,
            hook_manifest_id=build_hook_manifest_id(self.manifest),
            first_divergence=FirstDivergence(
                commit_index=2,
                field="registers_after.a",
                expected=0x02,
                actual=0x09,
            ),
        )

    def test_build_divergence_artifacts_captures_window(self) -> None:
        expected = tuple(make_commit(i, 0x0150 + i, f"commit_{i}") for i in range(6))
        actual = list(expected)
        actual[2] = make_commit(2, 0x0152, "commit_2_bad")
        result = LockstepResult(
            matched=False,
            commits=tuple(actual[:3]),
            mismatch=LockstepMismatch(commit_index=2, expected=expected[2], actual=actual[2]),
        )

        artifacts = build_divergence_artifacts(expected, result, self.build_capsule(), window_radius=1)

        self.assertEqual([entry.commit_index for entry in artifacts.commit_window], [1, 2, 3])
        self.assertEqual(artifacts.commit_window[1].actual, actual[2])
        self.assertIn("commit 2", artifacts.summary())

    def test_emit_divergence_artifacts_writes_summary_json_waveform_and_snapshot(self) -> None:
        expected = tuple(make_commit(i, 0x0150 + i, f"commit_{i}") for i in range(4))
        actual = list(expected)
        actual[1] = make_commit(1, 0x0151, "commit_1_bad")
        result = LockstepResult(
            matched=False,
            commits=tuple(actual[:2]),
            mismatch=LockstepMismatch(commit_index=1, expected=expected[1], actual=actual[1]),
        )
        artifacts = build_divergence_artifacts(expected, result, self.build_capsule(), window_radius=1)

        with tempfile.TemporaryDirectory() as tmpdir:
            waveform_source = Path(tmpdir) / "failure.fst"
            waveform_source.write_bytes(b"waveform")
            stderr = io.StringIO()

            files = emit_divergence_artifacts(
                artifacts,
                Path(tmpdir) / "artifacts",
                waveform_path=waveform_source,
                oracle_snapshot=b"snapshot",
                stderr=stderr,
            )

            self.assertTrue(files.summary_path.exists())
            self.assertTrue(files.json_path.exists())
            self.assertTrue(files.waveform_path is not None and files.waveform_path.exists())
            self.assertTrue(files.oracle_snapshot_path is not None and files.oracle_snapshot_path.exists())
            self.assertIn("Lockstep divergence at commit 1", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
