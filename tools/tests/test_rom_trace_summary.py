from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from rom_trace_summary import summarize_rom_trace


SYM_TEXT = """\
00:01ea FrameLoop.row_loop
00:0246 WaitForMode3
00:0250 DelayCancel
"""


class RomTraceSummaryTest(unittest.TestCase):
    def test_summarize_rom_trace_reports_label_hits_and_row_milestones(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sym_path = root / "fixture.sym"
            trace_path = root / "fixture.trace.jsonl"
            sym_path.write_text(SYM_TEXT, encoding="utf-8")
            trace_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "cycle": 10,
                                "pc": 0x01EA,
                                "ppu_ly": 40,
                                "ppu_mode": 1,
                                "line_obj_count": 0,
                                "scanout_y": 40,
                                "scanout_x": 0,
                                "scanout_source": 0,
                                "bus_req_addr": 0,
                                "preview_bus_req_addr": 0,
                            }
                        ),
                        json.dumps(
                            {
                                "cycle": 20,
                                "pc": 0x0246,
                                "ppu_ly": 40,
                                "ppu_mode": 3,
                                "line_obj_count": 1,
                                "slot0_x": 128,
                                "slot0_oam_index": 0,
                                "scanout_y": 40,
                                "scanout_x": 120,
                                "scanout_source": 2,
                                "scanout_shade": 3,
                                "line_summary_mode3_len": 184,
                                "bus_req_addr": 0,
                                "preview_bus_req_addr": 0xFF40,
                                "preview_bus_req_data": 0x91,
                            }
                        ),
                        json.dumps(
                            {
                                "cycle": 21,
                                "pc": 0x0250,
                                "ppu_ly": 40,
                                "ppu_mode": 3,
                                "line_obj_count": 1,
                                "slot0_x": 128,
                                "slot0_oam_index": 0,
                                "scanout_y": 40,
                                "scanout_x": 124,
                                "scanout_source": 2,
                                "scanout_shade": 3,
                                "bus_req_addr": 0xFF40,
                                "bus_req_data": 0x91,
                                "preview_bus_req_addr": 0xFF40,
                                "preview_bus_req_data": 0x91,
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = summarize_rom_trace(
                trace_path,
                sym_path,
                line=40,
                labels=("FrameLoop.row_loop", "WaitForMode3", "DelayCancel"),
            )

            self.assertEqual(summary["labels"]["FrameLoop.row_loop"]["pc"], "0x01ea")
            self.assertEqual(summary["labels"]["WaitForMode3"]["cycle"], 20)
            self.assertEqual(summary["labels"]["DelayCancel"]["labels"], ["DelayCancel"])
            self.assertEqual(summary["label_stats"]["FrameLoop.row_loop"]["count"], 1)
            self.assertEqual(summary["label_stats"]["WaitForMode3"]["first"]["cycle"], 20)
            self.assertEqual(summary["label_stats"]["DelayCancel"]["last"]["pc"], "0x0250")
            self.assertEqual(summary["milestones"]["first_selected_object"]["cycle"], 20)
            self.assertEqual(summary["milestones"]["first_object_scanout"]["scanout_x"], 120)
            self.assertEqual(summary["milestones"]["first_lcdc_write"]["bus_req_addr"], "0xff40")
            self.assertEqual(summary["milestones"]["first_lcdc_preview_write"]["preview_bus_req_data"], "0x91")
            self.assertEqual(summary["milestones"]["line_summary"]["line_summary_mode3_len"], 184)
            self.assertEqual(summary["spans"]["mode3"]["scanout_width"], 5)
            self.assertEqual(summary["spans"]["mode3"]["min_scanout_x"], 120)
            self.assertEqual(summary["spans"]["mode3"]["max_scanout_x"], 124)
            self.assertEqual(summary["spans"]["mode3"]["cycle_width"], 2)
            self.assertEqual(summary["spans"]["object_scanout"]["count"], 2)

    def test_cli_emits_json_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sym_path = root / "fixture.sym"
            trace_path = root / "fixture.trace.jsonl"
            sym_path.write_text(SYM_TEXT, encoding="utf-8")
            trace_path.write_text(
                json.dumps(
                    {
                        "cycle": 10,
                        "pc": 0x0246,
                        "ppu_ly": 40,
                        "ppu_mode": 3,
                        "line_obj_count": 1,
                        "scanout_y": 40,
                        "scanout_x": 120,
                        "scanout_source": 2,
                        "line_summary_mode3_len": 176,
                        "bus_req_addr": 0xFF40,
                        "bus_req_data": 0x91,
                        "preview_bus_req_addr": 0xFF40,
                        "preview_bus_req_data": 0x91,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "rom_trace_summary.py"),
                    f"--trace={trace_path}",
                    f"--sym={sym_path}",
                    "--line=40",
                    "--label=WaitForMode3",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            parsed = json.loads(completed.stdout)
            self.assertEqual(parsed["labels"]["WaitForMode3"]["pc"], "0x0246")
            self.assertEqual(parsed["label_stats"]["WaitForMode3"]["count"], 1)
            self.assertEqual(parsed["milestones"]["first_lcdc_write"]["bus_req_data"], "0x91")
            self.assertEqual(parsed["milestones"]["line_summary"]["line_summary_mode3_len"], 176)
            self.assertEqual(parsed["spans"]["mode3"]["scanout_width"], 1)
            self.assertEqual(parsed["spans"]["mode3"]["cycle_width"], 1)


if __name__ == "__main__":
    unittest.main()
