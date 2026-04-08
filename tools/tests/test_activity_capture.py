from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

import sys

sys.path.insert(0, str(ROOT / "tools"))

import activity_capture


SIMPLE_VCD = """$date
    today
$end
$version
    test
$end
$timescale
    1ps
$end
$scope module top $end
$var wire 1 ! clk_i $end
$var wire 1 " data $end
$upscope $end
$enddefinitions $end
#0
$dumpvars
0!
0"
$end
#5
1!
1"
#10
0!
#15
1!
0"
#20
0!
"""


class ActivityCaptureTest(unittest.TestCase):
    def test_parse_vcd_activity_counts_scalar_toggles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vcd = Path(tmpdir) / "simple.vcd"
            vcd.write_text(SIMPLE_VCD, encoding="utf-8")
            duration_ps, signals = activity_capture.parse_vcd_activity(vcd)

        self.assertEqual(duration_ps, 20)
        data = next(signal for signal in signals if signal.path.endswith(".data"))
        clk = next(signal for signal in signals if signal.path.endswith(".clk_i"))
        self.assertEqual(data.toggles, 2)
        self.assertEqual(data.t0_ps, 10)
        self.assertEqual(data.t1_ps, 10)
        self.assertEqual(clk.toggles, 4)

    def test_summarize_window_filters_reportable_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            vcd = root / "simple.vcd"
            fst = root / "simple.fst"
            vcd.write_text(SIMPLE_VCD, encoding="utf-8")
            fst.write_bytes(b"fst")
            spec = activity_capture.WindowSpec(
                name="demo",
                description="demo window",
                run="demo",
                command=("swim", "test", "demo"),
                wave_glob="build/demo/*.fst",
            )
            summary = activity_capture.summarize_window(spec, fst_path=fst, vcd_path=vcd)

        self.assertEqual(summary.reportable_signal_count, 1)
        self.assertEqual(summary.top_signals[0].path, "top.data")
        self.assertEqual(summary.reportable_total_toggles, 2)

    def test_comparison_payload_reports_delta_against_baseline(self) -> None:
        current = {
            "windows": {
                "demo": {
                    "reportable_total_toggles": 12,
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "windows": {
                            "demo": {
                                "reportable_total_toggles": 10,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            payload = activity_capture.comparison_payload(current, baseline)

        self.assertEqual(payload["status"], "compared")
        self.assertEqual(payload["windows"]["demo"]["delta_reportable_total_toggles"], 2)


if __name__ == "__main__":
    unittest.main()
