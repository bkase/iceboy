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


DEBUG_BUS_VCD = """$date
    today
$end
$version
    test
$end
$timescale 1ns $end
$scope module top $end
$var wire 1 ! DBG_PC0 $end
$var wire 1 \" DBG_PC1 $end
$var wire 1 # DBG_PC2 $end
$var wire 1 $ DBG_PC3 $end
$var wire 1 % DBG_MCE $end
$var wire 1 & DBG_PHASE0 $end
$var wire 1 ' DBG_PHASE1 $end
$var wire 1 ( DBG_PHASE2 $end
$upscope $end
$enddefinitions $end
#0
$dumpvars
0!
0\"
0#
0$
0%
0&
0'
0(
$end
#5
1!
0\"
1#
0$
1%
0&
1'
0(
"""


class DebugBusRunbookAssetsTest(unittest.TestCase):
    def test_debug_bus_docs_and_top_mappings_are_checked_in(self) -> None:
        debug_bus_doc = (ROOT / "docs" / "hardware" / "debug_bus.md").read_text(encoding="utf-8")
        runbook_doc = (ROOT / "docs" / "hardware" / "hardware_day_runbook.md").read_text(encoding="utf-8")
        visible_top = (ROOT / "src" / "board" / "icebreaker_visible_top.spade").read_text(encoding="utf-8")
        uart_top = (ROOT / "src" / "board" / "icebreaker_uart_rom_top.spade").read_text(encoding="utf-8")
        lcd_top = (ROOT / "src" / "board" / "icebreaker_lcd_test_top.spade").read_text(encoding="utf-8")

        self.assertIn("DBG_PC0", debug_bus_doc)
        self.assertIn("PMOD 1B is the logic-analyzer header", debug_bus_doc)
        self.assertIn("icebreaker_alu_loop_top", debug_bus_doc)
        self.assertIn("icebreaker_visible_bg_static_top", debug_bus_doc)
        self.assertIn("icebreaker_uart_rom_top", debug_bus_doc)
        self.assertIn("icebreaker_alu_loop_top", debug_bus_doc)
        self.assertIn("icebreaker_lcd_test_top", debug_bus_doc)
        self.assertIn("tools/vcd_to_sigrok.py", debug_bus_doc)

        self.assertIn("lcd_test_pattern.bin", runbook_doc)
        self.assertIn("alu_loop_icebreaker.bin", runbook_doc)
        self.assertIn("bg_static_icebreaker.bin", runbook_doc)
        self.assertIn("joypad_smoke_icebreaker.bin", runbook_doc)
        self.assertIn("uart_rom_icebreaker.bin", runbook_doc)
        self.assertIn("python tools/upload_rom_icebreaker.py --rom bench/roms/out/bg_static.gb", runbook_doc)

        self.assertIn("set DBG_PC0 = framebuffer.reader_active;", visible_top)
        self.assertIn("set DBG_MCE = lcd.init_done;", visible_top)
        self.assertIn("set DBG_PHASE2 = scanout_is_frame_start(scanout_i);", visible_top)

        self.assertIn("set DBG_PC0 = false;", uart_top)
        self.assertIn("set DBG_PHASE1 = cpu_halted_i;", uart_top)
        self.assertIn("set DBG_PHASE2 = scanout_valid(scanout_i);", uart_top)
        self.assertIn("set DEBUG_GPIO0 = upload_hold_i;", uart_top)

        self.assertIn("set DBG_PC0 = (frame_index_reg & 0x1u32) != 0u32;", lcd_top)
        self.assertIn("set DBG_MCE = lcd.init_done;", lcd_top)
        self.assertIn("set DEBUG_GPIO0 = frame_start_pulse;", lcd_top)

    def test_vcd_to_sigrok_labels_standard_debug_bus_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            vcd_path = root / "debug_bus.vcd"
            out_path = root / "debug_bus.sr"
            vcd_path.write_text(DEBUG_BUS_VCD, encoding="utf-8")

            capture = vcd_to_sigrok.build_capture(
                vcd_path,
                requested_signals=(
                    "DBG_PC0",
                    "DBG_PC1",
                    "DBG_PC2",
                    "DBG_PC3",
                    "DBG_MCE",
                    "DBG_PHASE0",
                    "DBG_PHASE1",
                    "DBG_PHASE2",
                ),
                samplerate_hz=None,
            )
            vcd_to_sigrok.write_sigrok_session(out_path, capture)

            with zipfile.ZipFile(out_path, "r") as archive:
                metadata = archive.read("metadata").decode("utf-8")

        self.assertIn("probe1=DBG_PC0", metadata)
        self.assertIn("probe2=DBG_PC1", metadata)
        self.assertIn("probe3=DBG_PC2", metadata)
        self.assertIn("probe4=DBG_PC3", metadata)
        self.assertIn("probe5=DBG_MCE", metadata)
        self.assertIn("probe6=DBG_PHASE0", metadata)
        self.assertIn("probe7=DBG_PHASE1", metadata)
        self.assertIn("probe8=DBG_PHASE2", metadata)
