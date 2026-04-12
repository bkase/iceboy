from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"

sys.path.insert(0, str(TOOLS))

import vcd_to_sigrok


SIMPLE_LCD_VCD = """$date
    today
$end
$version
    test
$end
$timescale 1ns $end
$scope module top $end
$var wire 1 ! LCD_SCK $end
$var wire 1 " LCD_MOSI $end
$var wire 1 # LCD_CS $end
$var wire 1 $ LCD_DC $end
$var wire 1 % EXTRA0 $end
$var wire 1 & EXTRA1 $end
$var wire 1 ' EXTRA2 $end
$var wire 1 ( EXTRA3 $end
$var wire 1 ) EXTRA4 $end
$upscope $end
$enddefinitions $end
#0
$dumpvars
0!
0"
1#
0$
0%
0&
0'
0(
0)
$end
#5
1!
1"
0#
1$
1%
0&
1'
0(
1)
#10
0!
0"
1#
0$
0%
1&
0'
1(
0)
#15
1!
1"
0#
1$
1%
1&
1'
1(
1)
"""


class VcdToSigrokTest(unittest.TestCase):
    def test_write_sigrok_session_emits_decoder_friendly_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            vcd_path = root / "lcd.vcd"
            out_path = root / "lcd.sr"
            vcd_path.write_text(SIMPLE_LCD_VCD, encoding="utf-8")

            capture = vcd_to_sigrok.build_capture(
                vcd_path,
                requested_signals=("LCD_SCK", "LCD_MOSI", "LCD_CS", "LCD_DC"),
                samplerate_hz=None,
            )
            vcd_to_sigrok.write_sigrok_session(out_path, capture)

            self.assertEqual(capture.sample_period_ps, 5_000)
            self.assertEqual(capture.samplerate_hz, 200_000_000)
            self.assertEqual(capture.unit_size, 1)

            with zipfile.ZipFile(out_path, "r") as archive:
                self.assertEqual(sorted(archive.namelist()), ["logic-1", "metadata", "version"])
                self.assertEqual(archive.read("version"), b"2\n")
                self.assertEqual(archive.read("logic-1"), bytes([0x20, 0xD0, 0x20, 0xD0]))
                metadata = archive.read("metadata").decode("utf-8")

        self.assertIn("capturefile=logic-1", metadata)
        self.assertIn("samplerate=200 MHz", metadata)
        self.assertIn("unitsize=1", metadata)
        self.assertIn("probe1=LCD_SCK", metadata)
        self.assertIn("probe2=LCD_MOSI", metadata)
        self.assertIn("probe3=LCD_CS", metadata)
        self.assertIn("probe4=LCD_DC", metadata)
        self.assertNotIn("probe1=top.LCD_SCK", metadata)

    def test_build_capture_packs_more_than_eight_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            vcd_path = Path(tmpdir) / "lcd.vcd"
            vcd_path.write_text(SIMPLE_LCD_VCD, encoding="utf-8")

            capture = vcd_to_sigrok.build_capture(
                vcd_path,
                requested_signals=(
                    "LCD_SCK",
                    "LCD_MOSI",
                    "LCD_CS",
                    "LCD_DC",
                    "EXTRA0",
                    "EXTRA1",
                    "EXTRA2",
                    "EXTRA3",
                    "EXTRA4",
                ),
                samplerate_hz=None,
            )

        self.assertEqual(capture.unit_size, 2)
        self.assertEqual(
            capture.samples,
            bytes(
                [
                    0x20,
                    0x00,
                    0xDA,
                    0x80,
                    0x25,
                    0x00,
                    0xDF,
                    0x80,
                ]
            ),
        )


if __name__ == "__main__":
    unittest.main()
