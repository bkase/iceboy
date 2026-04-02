from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bench.pyboy.hooks import build_hook_manifest
from bench.pyboy.oracle import ButtonEvent, MemoryWriteEvent, RawInputEvent
from bench.pyboy.replay import (
    FirstDivergence,
    ReplayCapsule,
    ReplayEvent,
    build_hook_manifest_id,
)
from spec.profiles import MemoryBehaviorProfile, ModelProfile, ResetProfile


SYMBOL_TEXT = """\
00:0150 __checkpoint_boot
00:0152 __commit_setup
00:0154 __pass
00:0156 __fail
"""


class ReplayCapsuleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.sym_path = Path(cls._tmpdir.name) / "capsule.sym"
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
            event_log=(
                ReplayEvent(commit_index=3, event=ButtonEvent(button="a", action="tap", delay=2)),
                ReplayEvent(commit_index=9, event=MemoryWriteEvent(addr=0xC100, value=0x34)),
                ReplayEvent(commit_index=12, event=RawInputEvent(event=5, delay=1)),
            ),
            sym_sha256=self.manifest.sym_sha256,
            hook_manifest_id=build_hook_manifest_id(self.manifest),
            first_divergence=FirstDivergence(
                commit_index=14,
                field="registers_after.a",
                expected=0x42,
                actual=0x00,
            ),
        )

    def test_capsule_round_trips_through_json(self) -> None:
        capsule = self.build_capsule()
        encoded = capsule.to_json()
        decoded = ReplayCapsule.from_json(encoded)
        self.assertEqual(decoded, capsule)

    def test_capsule_round_trips_through_yaml(self) -> None:
        capsule = self.build_capsule()
        encoded = capsule.to_yaml()
        decoded = ReplayCapsule.from_yaml(encoded)
        self.assertEqual(decoded, capsule)

    def test_hook_manifest_identity_changes_with_target_set(self) -> None:
        manifest_a = build_hook_manifest(self.sym_path)
        manifest_b_path = Path(self._tmpdir.name) / "capsule_b.sym"
        manifest_b_path.write_text(
            SYMBOL_TEXT + "00:0158 __checkpoint_extra\n",
            encoding="utf-8",
        )
        manifest_b = build_hook_manifest(manifest_b_path)

        self.assertNotEqual(build_hook_manifest_id(manifest_a), build_hook_manifest_id(manifest_b))


if __name__ == "__main__":
    unittest.main()
