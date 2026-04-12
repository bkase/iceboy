from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class EbrRomProbeAssetsTest(unittest.TestCase):
    def test_probe_top_is_wired_into_mem_phys_module(self) -> None:
        module_text = (ROOT / "src" / "mem" / "phys" / "main.spade").read_text(encoding="utf-8")
        probe_text = (ROOT / "src" / "mem" / "phys" / "ebr_rom_probe_top.spade").read_text(encoding="utf-8")
        doc_text = (ROOT / "docs" / "hardware" / "ebr_rom_synth_probe.md").read_text(encoding="utf-8")

        self.assertIn("pub mod ebr_rom_probe_top;", module_text)
        self.assertIn("clocked_memory_init::<256, 1, 8, uint<32>>", probe_text)
        self.assertIn("addr_i: uint<8>", probe_text)
        self.assertRegex(probe_text, re.compile(r"0x00042021u32,\s+0x00084042u32"))
        self.assertIn("tools/run_ebr_rom_synth_probe.sh", doc_text)
        self.assertIn("SB_RAM40_4K = 0", doc_text)
        self.assertIn("Decision: NO-GO", doc_text)
        self.assertIn("Option b1", doc_text)
