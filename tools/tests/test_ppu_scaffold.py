from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROOT_MAIN_PATH = ROOT / "src" / "main.spade"
PPU_MAIN_PATH = ROOT / "src" / "ppu" / "main.spade"
PPU_SEM_MAIN_PATH = ROOT / "src" / "ppu" / "sem" / "main.spade"
PPU_EVENTS_PATH = ROOT / "src" / "ppu" / "sem" / "events.spade"
PPU_MEMORY_PATH = ROOT / "src" / "ppu" / "sem" / "memory.spade"
PPU_TYPES_PATH = ROOT / "src" / "ppu" / "sem" / "types.spade"
PPU_PROFILES_PATH = ROOT / "src" / "ppu" / "sem" / "profiles.spade"
PPU_SAMPLE_PATH = ROOT / "src" / "ppu" / "sem" / "sample.spade"


class PpuScaffoldTest(unittest.TestCase):
    def test_root_module_exports_ppu_tree(self) -> None:
        self.assertIn("mod ppu;", ROOT_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod sem;", PPU_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod events;", PPU_SEM_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod memory;", PPU_SEM_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod profiles;", PPU_SEM_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod sample;", PPU_SEM_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod types;", PPU_SEM_MAIN_PATH.read_text(encoding="utf-8"))

    def test_ppu_event_bridge_surface_matches_architecture_contract(self) -> None:
        text = PPU_EVENTS_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub struct VideoCoord",
            "frame: uint<32>",
            "line: uint<8>",
            "dot: uint<9>",
            "pub mod mmio {",
            "pub enum MmioReg",
            "Lcdc,",
            "Stat,",
            "Scy,",
            "Scx,",
            "Lyc,",
            "Wy,",
            "Wx,",
            "Bgp,",
            "Obp0,",
            "Obp1,",
            "pub struct MmioWrite",
            "target: MmioReg",
            "value: uint<8>",
            "pub enum PpuEventKind",
            "MmioWrite { write: mmio::MmioWrite }",
            "DmaStart { source_high: uint<8> }",
            "ForceLcdPower { enabled: bool }",
            "pub struct TimedPpuEvent",
            "seq: uint<64>",
            "at: VideoCoord",
            "kind: PpuEventKind",
            "pub struct OamDmaState",
            "active: bool",
            "source_high: uint<8>",
            "pub struct DotInput",
            "bus_events: [TimedPpuEvent; 4]",
            "bus_event_count: uint<4>",
            "mem_resp: PpuMemResp",
            "dma_state: OamDmaState",
            "pub fn zero_video_coord() -> VideoCoord",
            "pub fn zero_mmio_write() -> MmioWrite",
            "pub fn idle_timed_ppu_event() -> TimedPpuEvent",
            "pub fn idle_oam_dma_state() -> OamDmaState",
            "pub fn idle_dot_input() -> DotInput",
        ]:
            self.assertIn(symbol, text)

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

    def test_ppu_memory_surface_matches_architecture_contract(self) -> None:
        text = PPU_MEMORY_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub enum MemRegion",
            "Vram,",
            "Oam,",
            "pub enum MemClient",
            "BgFetcher,",
            "ObjFetcher,",
            "OamScanner,",
            "Dma,",
            "pub enum PpuMemKind",
            "Read,",
            "Write { data: uint<8> }",
            "pub struct MemTxnTag",
            "region: MemRegion",
            "client: MemClient",
            "id: uint<4>",
            "pub enum VideoBlockReason",
            "CpuBlockedByMode2,",
            "CpuBlockedByMode3,",
            "CpuBlockedByOamDma,",
            "PpuBlockedByOwnership,",
            "pub enum PpuMemResult",
            "Ok { data: uint<8> }",
            "UndefinedRead { reason: VideoBlockReason }",
            "pub struct PpuMemReq",
            "kind: PpuMemKind",
            "addr: uint<16>",
            "pub struct PpuMemResp",
            "result: PpuMemResult",
            "pub struct PendingRead",
            "epoch: uint<4>",
            "pub fn zero_mem_txn_tag() -> MemTxnTag",
            "pub fn idle_ppu_mem_req() -> PpuMemReq",
            "pub fn idle_ppu_mem_resp() -> PpuMemResp",
            "pub fn idle_pending_read() -> PendingRead",
        ]:
            self.assertIn(symbol, text)

    def test_ppu_sampling_surface_matches_architecture_contract(self) -> None:
        text = PPU_SAMPLE_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub struct PpuRenderInputs",
            "scx_fetch: uint<8>",
            "scy_fetch: uint<8>",
            "scx_low3_line: uint<3>",
            "wx_live: uint<8>",
            "wy_triggered_this_frame: bool",
            "bgp_pop: uint<8>",
            "obp0_pop: uint<8>",
            "obp1_pop: uint<8>",
            "lyc_eq_live: bool",
            "pub fn sample_mode2_state(visible: PpuVisibleState, sampled: PpuSamplingState) -> PpuSamplingState",
            "scx_low3_line: trunc(visible.regs.scx)",
            "wy_triggered_this_frame: sampled.wy_triggered_this_frame || visible.ly == visible.regs.wy",
            "window_enable_at_mode2_start: visible.regs.lcdc.win_enable",
            "pub fn sample_render_inputs(",
            "phase: PpuPhase",
            "PpuPhase::Transfer$(x_out: _, discard_scx: _)",
            "lyc_eq_live: visible.ly == visible.regs.lyc",
        ]:
            self.assertIn(symbol, text)


if __name__ == "__main__":
    unittest.main()
