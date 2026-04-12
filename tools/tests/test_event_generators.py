from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bench.actions.generators import (
    JoypadButtons,
    JoypadButtonsEvent,
    SeededEventScript,
    load_action_script,
)
from tools.write_action_script_joypad_schedule import compile_joypad_schedule


class EventGeneratorTest(unittest.TestCase):
    def test_striped_generator_is_deterministic_for_same_seed(self) -> None:
        rom = {
            "id": "ALU_LOOP",
            "timeout_commits": 80,
            "action_script": None,
            "action_gen": {"name": "striped", "seed": 7},
        }
        left = SeededEventScript.from_manifest_entry(rom)
        right = SeededEventScript.from_manifest_entry(rom)
        self.assertEqual(left, right)
        self.assertTrue(left.events)

    def test_striped_generator_changes_when_seed_changes(self) -> None:
        left = SeededEventScript.from_manifest_entry(
            {
                "id": "ALU_LOOP",
                "timeout_commits": 80,
                "action_script": None,
                "action_gen": {"name": "striped", "seed": 1},
            }
        )
        right = SeededEventScript.from_manifest_entry(
            {
                "id": "ALU_LOOP",
                "timeout_commits": 80,
                "action_script": None,
                "action_gen": {"name": "striped", "seed": 2},
            }
        )
        self.assertNotEqual(left.events, right.events)

    def test_action_script_supports_commit_and_checkpoint_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "events.yaml"
            script_path.write_text(
                """\
seed: 11
events:
  - commit_index: 3
    event:
      kind: joypad_buttons
      buttons: [a]
  - checkpoint: __checkpoint_boot
    event:
      kind: joypad_buttons
      buttons: []
""",
                encoding="utf-8",
            )
            script = load_action_script(script_path)

            self.assertEqual(script.seed, 11)
            self.assertEqual(
                script.events_for_commit(3),
                (JoypadButtonsEvent(JoypadButtons.from_pressed(["a"])),),
            )
            self.assertEqual(
                script.events_for_checkpoint("__checkpoint_boot"),
                (JoypadButtonsEvent(JoypadButtons()),),
            )

    def test_compile_joypad_schedule_carries_state_across_frames(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "events.yaml"
            script_path.write_text(
                """\
seed: 0
events:
  - commit_index: 0
    event:
      kind: joypad_buttons
      buttons: [left]
  - commit_index: 2
    event:
      kind: joypad_buttons
      buttons: []
  - commit_index: 4
    event:
      kind: joypad_buttons
      buttons: [start, select]
""",
                encoding="utf-8",
            )

            schedule = compile_joypad_schedule(script_path, frame_count=6)

            self.assertEqual(schedule, [0x20, 0x20, 0x00, 0x00, 0x03, 0x03])

    def test_compile_joypad_schedule_rejects_non_joypad_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "events.yaml"
            script_path.write_text(
                """\
seed: 0
events:
  - commit_index: 0
    event:
      kind: if_set_bits
      bits: 16
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Unsupported scripted event"):
                compile_joypad_schedule(script_path, frame_count=1)


if __name__ == "__main__":
    unittest.main()
