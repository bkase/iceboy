from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROOT_MAIN_PATH = ROOT / "src" / "main.spade"
PPU_MAIN_PATH = ROOT / "src" / "ppu" / "main.spade"
PPU_SEM_MAIN_PATH = ROOT / "src" / "ppu" / "sem" / "main.spade"
PPU_TYPES_PATH = ROOT / "src" / "ppu" / "sem" / "types.spade"


class PpuScaffoldTest(unittest.TestCase):
    def test_root_module_exports_ppu_tree(self) -> None:
        self.assertIn("mod ppu;", ROOT_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod sem;", PPU_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod types;", PPU_SEM_MAIN_PATH.read_text(encoding="utf-8"))

    def test_ppu_type_surface_matches_architecture_contract(self) -> None:
        text = PPU_TYPES_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub enum PpuMode",
            "pub struct Lcdc",
            "pub struct StatSelect",
            "pub struct PpuRegs",
            "pub struct PpuVisibleState",
            "pub struct PpuStatusState",
            "phase: PpuPhase",
            "pub enum LcdRunState",
            "pub enum PpuPhase",
            "Transfer { x_out: uint<8>, discard_scx: uint<3> }",
            "pub enum WindowState",
            "ActiveOnLine { win_x: uint<5>, win_line: uint<8> }",
            "pub struct PpuSamplingState",
            "pub struct PpuRenderState",
            "dot_in_line: uint<9>",
            "line_objs: LineObjList",
            "fetcher: FetcherState",
            "bg_fifo: BgFifo",
            "obj_fifo: ObjFifo",
            "pub struct PpuState",
            "pub fn initial_ppu_state() -> PpuState",
            "pub fn visible_mode(status: PpuStatusState) -> PpuMode",
            "pub fn lcd_enabled(status: PpuStatusState, regs: PpuRegs) -> bool",
            "LcdRunState::Disabled => PpuMode::LcdOff",
        ]:
            self.assertIn(symbol, text)


if __name__ == "__main__":
    unittest.main()
