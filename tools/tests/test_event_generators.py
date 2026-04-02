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


if __name__ == "__main__":
    unittest.main()
