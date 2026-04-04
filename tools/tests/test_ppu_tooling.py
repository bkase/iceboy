from __future__ import annotations

import json
import unittest

from bench.ref.ppu_ref import ForceLcdPower, MmioReg, MmioWrite, TimedPpuEvent, VideoCoord
from spec.profiles import BehaviorConfig, BehaviorFeature, ModelProfile, ResetProfile
from tools.compare_oracles import PpuCompareScope, compare_oracle_streams
from tools.render_line_narrative import LineNarrativeContext, render_line_narrative
from tools.replay_capsule import PpuReplayCapsule, REPLAY_CAPSULE_SCHEMA_PATH


class PpuToolingTest(unittest.TestCase):
    def build_capsule(self) -> PpuReplayCapsule:
        return PpuReplayCapsule(
            rom_id="WAVE_A_TIMER",
            model_profile=ModelProfile.DMG,
            reset_profile=ResetProfile.SkipBoot,
            behavior_config=BehaviorConfig(
                model=ModelProfile.DMG,
                features=(BehaviorFeature.DmgStatWriteQuirk,),
            ),
            random_seed=7,
            raster_event_log=(
                TimedPpuEvent(
                    seq=1,
                    at=VideoCoord(frame=0, line=0, dot=0),
                    kind=ForceLcdPower(enabled=True),
                ),
                TimedPpuEvent(
                    seq=2,
                    at=VideoCoord(frame=0, line=0, dot=12),
                    kind=MmioWrite(target=MmioReg.Stat, value=0x48),
                ),
            ),
            first_bad_coord=None,
        )

    def test_replay_capsule_round_trips_with_behavior_config_and_raster_events(self) -> None:
        capsule = self.build_capsule()
        self.assertEqual(PpuReplayCapsule.from_json(capsule.to_json()), capsule)
        self.assertEqual(PpuReplayCapsule.from_yaml(capsule.to_yaml()), capsule)

    def test_replay_capsule_schema_includes_ppu_specific_fields(self) -> None:
        schema = json.loads(REPLAY_CAPSULE_SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertIn("behavior_config", schema["properties"])
        self.assertIn("raster_event_log", schema["properties"])
        self.assertIn("first_bad_coord", schema["properties"])

    def test_compare_oracles_reports_first_bad_field_for_dot_commit(self) -> None:
        expected = [{"mode_after": "OamScan", "ly_after": 0, "stat_line_after": False}]
        actual = [{"mode_after": "Transfer", "ly_after": 0, "stat_line_after": False}]
        result = compare_oracle_streams("ref", expected, "dut", actual, PpuCompareScope.DotCommit)
        self.assertFalse(result.matched)
        self.assertEqual(result.first_bad_index, 0)
        self.assertEqual(result.field_path, "mode_after")
        self.assertEqual(result.expected, {"ref": "OamScan"})
        self.assertEqual(result.actual, {"dut": "Transfer"})

    def test_compare_oracles_reports_length_mismatch_for_frame_hash(self) -> None:
        result = compare_oracle_streams("ref", [0x1234], "dut", [0x1234, 0x5678], PpuCompareScope.FrameHash)
        self.assertFalse(result.matched)
        self.assertEqual(result.field_path, "length")
        self.assertEqual(result.expected, {"ref": 1})
        self.assertEqual(result.actual, {"dut": 2})

    def test_render_line_narrative_emits_human_readable_context(self) -> None:
        narrative = render_line_narrative(
            LineNarrativeContext(
                frame=0,
                line=37,
                dot=112,
                scope="dot_commit",
                first_differing_semantic_event="WindowRestart",
                last_matching_fetch_epoch=9,
                object_selection_tickets=(2, 7),
                window_active=True,
                access_outcomes=("cpu blocked by mode3", "fetch granted"),
                causal_chain=("window retrigger", "stale pre-restart read", "mixer mismatch"),
            )
        )
        self.assertIn("frame 0, line 37, dot 112", narrative)
        self.assertIn("First differing semantic event: WindowRestart", narrative)
        self.assertIn("Last matching fetch epoch: 9", narrative)
        self.assertIn("Object selection tickets: 2, 7", narrative)
        self.assertIn("Window active: yes", narrative)
        self.assertIn("cpu blocked by mode3", narrative)
        self.assertIn("window retrigger -> stale pre-restart read -> mixer mismatch", narrative)


if __name__ == "__main__":
    unittest.main()
