from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROOT_MAIN_PATH = ROOT / "src" / "main.spade"
VIDEO_MAIN_PATH = ROOT / "src" / "video" / "main.spade"
ACCESS_PATH = ROOT / "src" / "video" / "access.spade"
ACCESS_TEST_TOP_PATH = ROOT / "src" / "video" / "access_test_top.spade"
FRAME_SINK_PATH = ROOT / "src" / "video" / "frame_sink.spade"
FRAME_SINK_TEST_TOP_PATH = ROOT / "src" / "video" / "frame_sink_test_top.spade"


class VideoScaffoldTest(unittest.TestCase):
    def test_root_exports_video_tree(self) -> None:
        self.assertIn("mod video;", ROOT_MAIN_PATH.read_text(encoding="utf-8"))
        text = VIDEO_MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn("pub mod access;", text)
        self.assertIn("pub mod access_test_top;", text)
        self.assertIn("pub mod frame_sink;", text)
        self.assertIn("pub mod frame_sink_test_top;", text)

    def test_access_policy_surface_matches_contract(self) -> None:
        text = ACCESS_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub fn access_block_reason(",
            "ownership_granted: bool",
            "pub fn blocked_access_result(kind: PpuMemKind, reason: VideoBlockReason) -> PpuMemResult",
            "pub fn granted_access_result(kind: PpuMemKind, read_data: uint<8>) -> PpuMemResult",
            "pub fn evaluate_access(",
            "VideoBlockReason::CpuBlockedByMode2",
            "VideoBlockReason::CpuBlockedByMode3",
            "VideoBlockReason::CpuBlockedByOamDma",
            "VideoBlockReason::PpuBlockedByOwnership",
            "PpuMemResult::UndefinedRead$(reason: reason)",
            "PpuMemResult::Denied",
            "PpuMemResult::Ok$(data: read_data)",
        ]:
            self.assertIn(symbol, text)

    def test_access_test_top_exposes_stable_projection(self) -> None:
        text = ACCESS_TEST_TOP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub entity access_test_top(",
            "ownership_granted_i: bool",
            "read_data_i: uint<8>",
            "write_data_i: uint<8>",
            ") -> uint<21>",
            "let resp = evaluate_access(",
            "PpuMemResult::Ok$(data: data) => (0u2, data, 0u3)",
            "PpuMemResult::Denied => (1u2, 0u8, 0u3)",
            "PpuMemResult::UndefinedRead$(reason: reason) => (2u2, 0u8, reason_bits(reason))",
        ]:
            self.assertIn(symbol, text)

    def test_frame_sink_surface_matches_contract(self) -> None:
        text = FRAME_SINK_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub struct PixelReference",
            "pub struct LineSummary",
            "pixel_count: uint<8>",
            "blank_count: uint<8>",
            "line_hash: uint<32>",
            "full_width: bool",
            "pub struct FrameSummary",
            "line_count: uint<8>",
            "frame_hash: uint<32>",
            "full_frame: bool",
            "pub struct LineSinkState",
            "pub struct FrameSinkState",
            "pub struct HashSinkState",
            "rolling_hash: uint<32>",
            "pub struct DiffSinkState",
            "pub fn blank_reason_bits(reason: BlankReason) -> uint<2>",
            "pub fn zero_pixel_reference() -> PixelReference",
            "pub fn zero_line_summary() -> LineSummary",
            "pub fn zero_frame_summary() -> FrameSummary",
            "pub fn initial_line_sink_state() -> LineSinkState",
            "pub fn initial_frame_sink_state() -> FrameSinkState",
            "pub fn initial_hash_sink_state() -> HashSinkState",
            "pub fn initial_diff_sink_state() -> DiffSinkState",
            "pub fn pixel_sample(emit: PixelEmit) -> uint<8>",
            "pub fn line_boundary_summary(state: LineSinkState, event: ScanoutEvent) -> Option<LineSummary>",
            "pub fn advance_line_sink(",
            "pub fn advance_frame_sink(",
            "pub fn advance_hash_sink(state: HashSinkState, event: ScanoutEvent) -> HashSinkState",
            "pub fn advance_diff_sink(",
        ]:
            self.assertIn(symbol, text)

    def test_frame_sink_test_top_exposes_stable_projection(self) -> None:
        text = FRAME_SINK_TEST_TOP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub entity frame_sink_test_top(",
            "event_kind_i: uint<2>",
            "ref_valid_i: bool",
            ") -> uint<466>",
            "let line_summary_opt = line_boundary_summary(line_state, event);",
            "let next_line_state = advance_line_sink(line_state, event, reference);",
            "let (next_frame_state, frame_summary_opt) = advance_frame_sink(frame_state, line_summary_opt, event);",
            "let next_hash_state = advance_hash_sink(hash_state, event);",
            "let raw_next_diff_state = advance_diff_sink(diff_state, event, reference);",
        ]:
            self.assertIn(symbol, text)


if __name__ == "__main__":
    unittest.main()
