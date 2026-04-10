from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from compare_row_loop_timing import compare_row_loop_timing, main
from bench.pyboy.oracle import HookTimingCapture, LineModeTimingCapture


class CompareRowLoopTimingTest(unittest.TestCase):
    def test_compare_row_loop_timing_combines_pyboy_and_native_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rom = Path(tmpdir) / "scene.gb"
            sym = Path(tmpdir) / "scene.sym"
            trace = Path(tmpdir) / "scene.trace.jsonl"
            rom.write_bytes(b"")
            sym.write_text("", encoding="utf-8")
            trace.write_text("", encoding="utf-8")

            with patch("compare_row_loop_timing.capture_checkpoint_hook_timings") as capture, patch(
                "compare_row_loop_timing.capture_checkpoint_line_mode_timing"
            ) as line_timing, patch(
                "compare_row_loop_timing.summarize_rom_trace"
            ) as summarize:
                capture.return_value = (
                    HookTimingCapture(
                        seq=0,
                        frame=1,
                        label="WaitForMode3",
                        pc=0x0246,
                        ly=80,
                        stat=0x82,
                        lcdc=0x93,
                        scx=0,
                        scy=0,
                        wx=0,
                        wy=0,
                    ),
                    HookTimingCapture(
                        seq=1,
                        frame=1,
                        label="WriteObjOff",
                        pc=0x01D5,
                        ly=80,
                        stat=0x83,
                        lcdc=0x91,
                        scx=0,
                        scy=0,
                        wx=0,
                        wy=0,
                    ),
                )
                line_timing.return_value = LineModeTimingCapture(
                    line=80,
                    mode2_len_dots=80,
                    mode3_len_dots=170,
                    hblank_len_dots=206,
                )
                summarize.return_value = {
                    "label_stats": {"WaitForMode3": {"count": 2}},
                    "milestones": {"first_lcdc_write": {"scanout_x": 106}},
                    "spans": {
                        "mode3": {"scanout_width": 57, "cycle_width": 61},
                        "object_scanout": {"scanout_width": 8, "cycle_width": 11},
                    },
                }

                summary = compare_row_loop_timing(
                    rom_path=rom,
                    sym_path=sym,
                    trace_path=trace,
                    line=80,
                    labels=("WaitForMode3", "DelayCancel"),
                    write_pc=0x01D5,
                )

        self.assertEqual(summary["line"], 80)
        self.assertEqual(summary["write_pc"], "0x01d5")
        self.assertEqual(summary["labels"], ["WaitForMode3", "DelayCancel"])
        self.assertEqual(summary["pyboy"][0]["label"], "WaitForMode3")
        self.assertEqual(summary["pyboy_line_timing"]["mode3_len_dots"], 170)
        self.assertEqual(summary["pyboy_label_stats"]["WaitForMode3"]["count"], 1)
        self.assertEqual(summary["pyboy_label_stats"]["WriteObjOff"]["first"]["pc"], 0x01D5)
        self.assertEqual(summary["native"]["label_stats"]["WaitForMode3"]["count"], 2)
        self.assertEqual(summary["native"]["milestones"]["first_lcdc_write"]["scanout_x"], 106)
        self.assertEqual(summary["native_gap_analysis"]["mode3_scanout_width"], 57)
        self.assertEqual(summary["native_gap_analysis"]["mode3_cycle_width"], 61)
        self.assertEqual(summary["native_gap_analysis"]["object_scanout_width"], 8)
        self.assertEqual(summary["native_gap_analysis"]["object_scanout_cycle_width"], 11)
        capture.assert_called_once()
        line_timing.assert_called_once()
        summarize.assert_called_once()

    def test_main_prints_json_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rom = Path(tmpdir) / "scene.gb"
            sym = Path(tmpdir) / "scene.sym"
            trace = Path(tmpdir) / "scene.trace.jsonl"
            rom.write_bytes(b"")
            sym.write_text("", encoding="utf-8")
            trace.write_text("", encoding="utf-8")

            with patch("compare_row_loop_timing.compare_row_loop_timing") as compare:
                compare.return_value = {"line": 40, "pyboy": [], "native": {}}
                stdout = io.StringIO()
                argv = sys.argv
                try:
                    sys.argv = [
                        "compare_row_loop_timing.py",
                        f"--rom={rom}",
                        f"--sym={sym}",
                        f"--trace={trace}",
                        "--line=40",
                        "--label=WaitForMode3",
                        "--write-pc=0x1f8",
                    ]
                    with patch("sys.stdout", stdout):
                        self.assertEqual(main(), 0)
                finally:
                    sys.argv = argv

        self.assertEqual(json.loads(stdout.getvalue()), {"line": 40, "pyboy": [], "native": {}})


if __name__ == "__main__":
    unittest.main()
