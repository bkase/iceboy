from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROOT_MAIN_PATH = ROOT / "src" / "main.spade"
PPU_MAIN_PATH = ROOT / "src" / "ppu" / "main.spade"
PPU_SEM_MAIN_PATH = ROOT / "src" / "ppu" / "sem" / "main.spade"
PPU_TYPES_PATH = ROOT / "src" / "ppu" / "sem" / "types.spade"
PPU_PROFILES_PATH = ROOT / "src" / "ppu" / "sem" / "profiles.spade"


class PpuScaffoldTest(unittest.TestCase):
    def test_root_module_exports_ppu_tree(self) -> None:
        self.assertIn("mod ppu;", ROOT_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod sem;", PPU_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod profiles;", PPU_SEM_MAIN_PATH.read_text(encoding="utf-8"))
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

    def test_ppu_profile_surface_matches_architecture_contract(self) -> None:
        text = PPU_PROFILES_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub enum ModelProfile",
            "DMG,",
            "CGB,",
            "pub enum SocRevision",
            "DMG0,",
            "CGBD,",
            "pub enum BehaviorFeature",
            "DmgStatWriteQuirk,",
            "PreCgbdScyBitplaneDesync,",
            "Wx0Stutter,",
            "Wx166NextLine,",
            "WindowRetriggerGlitch,",
            "ObjFetchCancelTiming,",
            "DmgOamDmaBasic,",
            "DmgOamDmaStrict,",
            "ExactBlockedReadMaterialization,",
            "pub struct BehaviorFeatureSet",
            "bits: uint<9>",
            "pub struct BehaviorConfig",
            "soc_revision: Option<SocRevision>",
            "features: BehaviorFeatureSet",
            "pub fn empty_behavior_feature_set() -> BehaviorFeatureSet",
            "pub fn default_behavior_config(model: ModelProfile) -> BehaviorConfig",
            "pub fn dmg_behavior_config() -> BehaviorConfig",
            "pub fn behavior_feature_mask(feature: BehaviorFeature) -> uint<9>",
            "pub fn feature_enabled(features: BehaviorFeatureSet, feature: BehaviorFeature) -> bool",
            "pub fn enable_feature(features: BehaviorFeatureSet, feature: BehaviorFeature) -> BehaviorFeatureSet",
        ]:
            self.assertIn(symbol, text)


if __name__ == "__main__":
    unittest.main()
