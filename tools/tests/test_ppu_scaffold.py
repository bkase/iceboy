from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROOT_MAIN_PATH = ROOT / "src" / "main.spade"
PPU_MAIN_PATH = ROOT / "src" / "ppu" / "main.spade"
PPU_SEM_MAIN_PATH = ROOT / "src" / "ppu" / "sem" / "main.spade"
PPU_RTL_MAIN_PATH = ROOT / "src" / "ppu" / "rtl" / "main.spade"
PPU_RTL_CORE_PATH = ROOT / "src" / "ppu" / "rtl" / "core.spade"
PPU_RTL_CORE_TEST_TOP_PATH = ROOT / "src" / "ppu" / "rtl" / "core_test_top.spade"
PPU_RTL_FIFO_PATH = ROOT / "src" / "ppu" / "rtl" / "fifo.spade"
PPU_RTL_FETCHER_PATH = ROOT / "src" / "ppu" / "rtl" / "fetcher.spade"
PPU_RTL_FETCHER_TEST_TOP_PATH = ROOT / "src" / "ppu" / "rtl" / "fetcher_test_top.spade"
PPU_RTL_IRQ_PATH = ROOT / "src" / "ppu" / "rtl" / "irq.spade"
PPU_RTL_IRQ_TEST_TOP_PATH = ROOT / "src" / "ppu" / "rtl" / "irq_test_top.spade"
PPU_RTL_REGS_PATH = ROOT / "src" / "ppu" / "rtl" / "regs.spade"
PPU_RTL_TILE_PATH = ROOT / "src" / "ppu" / "rtl" / "tile.spade"
PPU_RTL_TILE_TEST_TOP_PATH = ROOT / "src" / "ppu" / "rtl" / "tile_test_top.spade"
PPU_RTL_TIMING_PATH = ROOT / "src" / "ppu" / "rtl" / "timing.spade"
PPU_RTL_TIMING_TEST_TOP_PATH = ROOT / "src" / "ppu" / "rtl" / "timing_test_top.spade"
PPU_EVENTS_PATH = ROOT / "src" / "ppu" / "sem" / "events.spade"
PPU_MEMORY_PATH = ROOT / "src" / "ppu" / "sem" / "memory.spade"
PPU_OBSERVE_PATH = ROOT / "src" / "ppu" / "sem" / "observe.spade"
PPU_TYPES_PATH = ROOT / "src" / "ppu" / "sem" / "types.spade"
PPU_PROFILES_PATH = ROOT / "src" / "ppu" / "sem" / "profiles.spade"
PPU_SAMPLE_PATH = ROOT / "src" / "ppu" / "sem" / "sample.spade"
PPU_SCANOUT_PATH = ROOT / "src" / "ppu" / "sem" / "scanout.spade"
PPU_STEP_PATH = ROOT / "src" / "ppu" / "sem" / "step.spade"
PPU_STIMULUS_PATH = ROOT / "src" / "ppu" / "sem" / "stimulus.spade"


class PpuScaffoldTest(unittest.TestCase):
    def test_root_module_exports_ppu_tree(self) -> None:
        self.assertIn("mod ppu;", ROOT_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod sem;", PPU_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod rtl;", PPU_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod core;", PPU_RTL_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod core_test_top;", PPU_RTL_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod fifo;", PPU_RTL_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod fetcher;", PPU_RTL_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod fetcher_test_top;", PPU_RTL_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod irq;", PPU_RTL_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod irq_test_top;", PPU_RTL_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod regs;", PPU_RTL_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod tile;", PPU_RTL_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod tile_test_top;", PPU_RTL_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod timing;", PPU_RTL_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod timing_test_top;", PPU_RTL_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod events;", PPU_SEM_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod memory;", PPU_SEM_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod observe;", PPU_SEM_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod profiles;", PPU_SEM_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod sample;", PPU_SEM_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod scanout;", PPU_SEM_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod step;", PPU_SEM_MAIN_PATH.read_text(encoding="utf-8"))
        self.assertIn("pub mod stimulus;", PPU_SEM_MAIN_PATH.read_text(encoding="utf-8"))
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

    def test_ppu_core_surface_matches_architecture_contract(self) -> None:
        text = PPU_RTL_CORE_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub struct PpuCoreOut",
            "trace: PpuDebugTrace",
            "fn dmg_skipboot_regs() -> PpuRegs",
            "fn dmg_skipboot_state() -> PpuState",
            "pub entity ppu_core(",
            "dot_ce: bool",
            "video_now: VideoCoord",
            "bus_events: [TimedPpuEvent; 4]",
            "bus_event_count: uint<4>",
            "mem_resp: PpuMemResp",
            "dma_state: OamDmaState",
            "let step = step_dot(",
            "reg(clk) state_reg: PpuState reset(rst: dmg_skipboot_state()) = visible_state;",
            "trace: if dot_ce { ppu_debug_trace(video_now, visible) } else { idle_trace_for_state(video_now, visible_state) },",
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
            "pub struct PpuIrqReq",
            "vblank_req: bool",
            "stat_req: bool",
            "pub enum LcdRunState",
            "pub enum PpuPhase",
            "Transfer { x_out: uint<8>, discard_scx: uint<3> }",
            "pub enum WindowState",
            "ActiveOnLine { win_x: uint<5>, win_line: uint<8> }",
            "pub struct SelectedObjTicket",
            "selection_rank: uint<4>",
            "pub enum ObjPaletteSel",
            "Obp0,",
            "Obp1,",
            "pub struct ObjFlags",
            "y_flip: bool",
            "x_flip: bool",
            "palette: ObjPaletteSel",
            "bg_over_obj: bool",
            "pub struct ResolvedObjMeta",
            "ticket: SelectedObjTicket",
            "tile: uint<8>",
            "flags: ObjFlags",
            "row_index: uint<4>",
            "pub struct ObjDrawRank",
            "x: uint<8>",
            "pub struct ObjPixel",
            "color: uint<2>",
            "draw_rank: ObjDrawRank",
            "pub struct PpuSamplingState",
            "pub struct PpuRenderState",
            "dot_in_line: uint<9>",
            "line_objs: LineObjList",
            "fetcher: FetcherState",
            "tile_lo: uint<8>",
            "tile_hi: uint<8>",
            "pending_valid: bool",
            "pending_read: PendingRead",
            "bg_fifo: BgFifo",
            "obj_fifo: ObjFifo",
            "pub struct PpuState",
            "pub fn initial_ppu_state() -> PpuState",
            "pub fn idle_ppu_irq_req() -> PpuIrqReq",
            "pub fn visible_mode(status: PpuStatusState) -> PpuMode",
            "pub fn lcd_enabled(status: PpuStatusState, regs: PpuRegs) -> bool",
            "LcdRunState::Disabled => PpuMode::LcdOff",
            "pub fn zero_obj_flags() -> ObjFlags",
            "pub fn zero_resolved_obj_meta() -> ResolvedObjMeta",
            "pub fn zero_obj_draw_rank() -> ObjDrawRank",
        ]:
            self.assertIn(symbol, text)

    def test_ppu_irq_helpers_match_architecture_contract(self) -> None:
        text = PPU_RTL_IRQ_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub fn lyc_match(regs: PpuRegs, ly: uint<8>) -> bool",
            "pub fn stat_line(regs: PpuRegs, status: PpuStatusState, ly: uint<8>) -> bool",
            "pub fn stat_write_quirk_pulse(features: BehaviorFeatureSet, stat_write_seen: bool) -> bool",
            "feature_enabled(features, BehaviorFeature::DmgStatWriteQuirk) && stat_write_seen",
            "pub fn entered_vblank(prev_status: PpuStatusState, next_status: PpuStatusState) -> bool",
            "!is_vblank_mode(visible_mode(prev_status)) && is_vblank_mode(visible_mode(next_status))",
            "pub fn advance_stat_irq(",
            "(StatIrqState, bool)",
            "pub fn irq_req(",
            "(StatIrqState, PpuIrqReq)",
        ]:
            self.assertIn(symbol, text)

    def test_ppu_irq_test_top_provides_stable_projection(self) -> None:
        text = PPU_RTL_IRQ_TEST_TOP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub entity irq_test_top(",
            "prev_run_i: uint<2>",
            "next_phase_i: uint<3>",
            "prev_line_high_i: bool",
            "stat_write_seen_i: bool",
            "quirk_enable_i: bool",
            ") -> uint<10>",
            "let new_line = stat_line(regs, next_status, ly_i);",
            "let (next_irq_state, edge_req) = advance_stat_irq(",
            "let (_, irq_req_out) = irq_req(prev_status, next_status, regs, ly_i, stat_write_seen_i, features);",
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

    def test_ppu_observability_surface_matches_architecture_contract(self) -> None:
        text = PPU_OBSERVE_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub enum PpuIrqEdge",
            "None,",
            "VBlank,",
            "Stat,",
            "Both,",
            "pub struct PpuSemanticCommit",
            "ly_after: uint<8>",
            "mode_after: PpuMode",
            "stat_line_after: bool",
            "irq_edge: PpuIrqEdge",
            "scanout: Option<ScanoutEvent>",
            "pub enum TransferEvent",
            "BgWarmup,",
            "ScxDiscard { count: uint<3> }",
            "WindowRestart,",
            "ObjFetchStart { oam_index: uint<6> }",
            "ObjFetchCancel,",
            "PixelPop { x: uint<8> }",
            "pub struct TransferDigest",
            "event_count: uint<16>",
            "event_hash: uint<64>",
            "window_restart_count: uint<2>",
            "obj_fetch_count: uint<4>",
            "pub enum StrictnessTier",
            "Stable,",
            "ResearchBacked,",
            "Hypothesis,",
            "pub struct LineSummary",
            "frame: uint<32>",
            "ly: uint<8>",
            "mode3_len: uint<9>",
            "window_start_x: Option<uint<8>>",
            "window_line_after: uint<8>",
            "obj_count: uint<4>",
            "selected_objs: [Option<uint<6>>; 10]",
            "transfer: TransferDigest",
            "line_hash: uint<64>",
            "pub struct PpuMemReqs",
            "count: uint<3>",
            "slots: [PpuMemReq; 4]",
            "pub struct PpuMmioResp",
            "read_valid: bool",
            "read_data: uint<8>",
            "pub struct DotOutput",
            "next_state: PpuState",
            "mem_reqs: PpuMemReqs",
            "mmio_resp: PpuMmioResp",
            "irq_req: PpuIrqReq",
            "semantic: Option<PpuSemanticCommit>",
            "line_summary: Option<LineSummary>",
            "pub struct PpuDebugTrace",
            "at: VideoCoord",
            "dot_in_line_after: uint<9>",
            "run_after: LcdRunState",
            "phase_after: PpuPhase",
            "first_frame_blank_after: bool",
            "stat_readback_after: uint<8>",
            "fetcher: FetcherState",
            "bg_fifo: BgFifo",
            "obj_fifo: ObjFifo",
            "pub fn idle_ppu_irq_edge() -> PpuIrqEdge",
            "pub fn zero_transfer_digest() -> TransferDigest",
            "pub fn empty_line_summary() -> LineSummary",
            "pub fn idle_ppu_mem_reqs() -> PpuMemReqs",
            "pub fn idle_ppu_mmio_resp() -> PpuMmioResp",
            "pub fn idle_ppu_semantic_commit() -> PpuSemanticCommit",
            "pub fn idle_dot_output() -> DotOutput",
            "pub fn idle_dot_output_for_state(state: PpuState) -> DotOutput",
            "pub fn idle_ppu_debug_trace() -> PpuDebugTrace",
        ]:
            self.assertIn(symbol, text)

    def test_ppu_step_surface_matches_architecture_contract(self) -> None:
        text = PPU_STEP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub fn step_dot(state: PpuState, input: DotInput) -> DotOutput",
            "fn fold_events(input: DotInput, regs: PpuRegs) -> (PpuRegs, bool, bool, bool)",
            "let (written_regs, stat_write_seen, force_enable, force_disable) = fold_events(input, state.visible.regs);",
            "let transition_state = handle_lcd_transition(state_with_regs, old_lcdc7, requested_lcd_enable);",
            "let (next_stat_irq, next_irq_req) = irq_req(",
            "DotOutput$(",
            "next_state: final_state",
            "mem_reqs: idle_ppu_mem_reqs()",
            "mmio_resp: idle_ppu_mmio_resp()",
            "irq_req: next_irq_req",
            "scanout: Option::None",
            "semantic: Option::Some(semantic)",
            "line_summary: Option::None",
        ]:
            self.assertIn(symbol, text)

    def test_ppu_core_test_top_provides_stable_projection(self) -> None:
        text = PPU_RTL_CORE_TEST_TOP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub entity core_test_top(",
            "write_valid_i: bool",
            "write_target_i: uint<4>",
            "write_value_i: uint<8>",
            ") -> uint<41>",
            "let core = inst ppu_core(",
            "let trace = core.trace;",
            "zext(encode_phase(trace.phase_after))",
            "(zext(trace.ly_after) << 3)",
            "(zext(trace.dot_in_line_after) << 11)",
            "(zext(encode_mode(trace.mode_after)) << 20)",
            "(zext(encode_run(trace.run_after)) << 26)",
            "(zext(if trace.first_frame_blank_after { 1u1 } else { 0u1 }) << 28)",
            "(zext(trace.stat_readback_after) << 29)",
            "(zext(core.mem_reqs.count) << 37)",
            "std::option::Option::Some(event) => {",
            "(zext(match core.scanout {",
        ]:
            self.assertIn(symbol, text)

    def test_ppu_sampling_surface_matches_architecture_contract(self) -> None:
        text = PPU_SAMPLE_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub struct PpuRenderInputs",
            "lcdc_fetch: Lcdc",
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
            "lcdc_fetch: fetch_regs.lcdc",
            "lyc_eq_live: visible.ly == visible.regs.lyc",
        ]:
            self.assertIn(symbol, text)

    def test_ppu_fetcher_surface_matches_architecture_contract(self) -> None:
        text = PPU_RTL_FETCHER_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub struct BgFetcherOutput",
            "next_state: FetcherState",
            "req_valid: bool",
            "req: PpuMemReq",
            "push_valid: bool",
            "push_row: [uint<2>; 8]",
            "stale_resp: bool",
            "pub fn next_fetcher_epoch(epoch: uint<4>) -> uint<4>",
            "pub fn start_bg_fetcher(state: FetcherState, render: PpuRenderInputs, visible_ly: uint<8>, tile_x: uint<5>) -> FetcherState",
            "pub fn restart_window_fetcher(state: FetcherState, window_line: uint<8>) -> FetcherState",
            "pub fn invalidate_fetcher(",
            "pub fn advance_bg_fetcher(",
            "MemClient::BgFetcher",
            "FetcherStep::GetTile",
            "FetcherStep::GetLo",
            "FetcherStep::GetHi",
            "FetcherStep::Sleep",
            "FetcherStep::Push",
            "state.pending_read.epoch != state.epoch",
            "decode_tile_row(state.tile_lo, state.tile_hi)",
            "bgwin_tile_addr(render.lcdc_fetch, tile_id, row)",
        ]:
            self.assertIn(symbol, text)

    def test_ppu_fetcher_test_top_provides_projection_surface(self) -> None:
        text = PPU_RTL_FETCHER_TEST_TOP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub entity fetcher_test_top(",
            "mode_i: uint<2>",
            "window_line_i: uint<8>",
            "pending_epoch_i: uint<4>",
            "resp_id_i: uint<4>",
            "restart_line_i: bool",
            "window_restart_i: bool",
            "fetch_cancel_i: bool",
            "lcd_disable_i: bool",
            "start_bg_fetcher(state, render, visible_ly_i, tile_x_i)",
            "restart_window_fetcher(state, window_line_i)",
            "advance_bg_fetcher(",
        ]:
            self.assertIn(symbol, text)

    def test_ppu_fifo_surface_matches_architecture_contract(self) -> None:
        text = PPU_RTL_FIFO_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub struct BgFifoPopResult",
            "next_fifo: BgFifo",
            "pixel_valid: bool",
            "pixel: BgPixel",
            "discard_applied: bool",
            "next_discard_scx: uint<3>",
            "pub struct WindowStepOutput",
            "next_state: WindowState",
            "next_window_line: uint<8>",
            "restart_fetcher: bool",
            "clear_bg_fifo: bool",
            "pub struct BgPipeOutput",
            "pub fn bg_fifo_is_empty(fifo: BgFifo) -> bool",
            "pub fn bg_fifo_has_room_for_row(fifo: BgFifo) -> bool",
            "pub fn clear_bg_fifo() -> BgFifo",
            "pub fn push_bg_row(fifo: BgFifo, row: [uint<2>; 8], palette: uint<8>) -> BgFifo",
            "pub fn pop_bg_fifo(fifo: BgFifo, discard_scx: uint<3>) -> BgFifoPopResult",
            "pub fn window_enabled_for_line(sampled: PpuSamplingState) -> bool",
            "pub fn window_triggered(wx_live: uint<8>, x_out: uint<8>) -> bool",
            "pub fn line_start_window_state(",
            "pub fn note_window_tile_push(state: WindowState) -> WindowState",
            "pub fn step_window_state(",
            "WindowState::ArmedThisFrame",
            "WindowState::ActiveOnLine$(win_x: 0u5, win_line: window_line)",
            "pub fn advance_bg_pipe(",
            "let pre_push_fifo = if window_step.clear_bg_fifo { clear_bg_fifo() } else { fifo };",
            "let popped = pop_bg_fifo(next_fifo, discard_scx);",
        ]:
            self.assertIn(symbol, text)

    def test_ppu_stimulus_surface_matches_architecture_contract(self) -> None:
        text = PPU_STIMULUS_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub struct VideoPatch",
            "addr: uint<16>",
            "len: uint<5>",
            "bytes: [uint<8>; 16]",
            "pub struct PpuSimSnapshot",
            "frame: uint<32>",
            "state: PpuState",
            "pub enum VideoAnchor",
            "FrameLineDot { frame: uint<32>, line: uint<8>, dot: uint<9> }",
            "LineStart { line: uint<8> }",
            "ModeEnter { line: uint<8>, mode: PpuMode }",
            "WindowStart { line: uint<8> }",
            "ObjFetchStart { line: uint<8>, oam_index: uint<6> }",
            "PixelX { line: uint<8>, x: uint<8> }",
            "pub struct RasterStimulus",
            "reg_write: Option<MmioWrite>",
            "dma_start: Option<uint<8>>",
            "vram_patch: Option<VideoPatch>",
            "oam_patch: Option<VideoPatch>",
            "state_import: Option<PpuSimSnapshot>",
            "state_export: bool",
            "freeze_dot_ce: bool",
            "break_on_line: Option<uint<8>>",
            "break_on_anchor: Option<VideoAnchor>",
            "pub fn zero_video_patch() -> VideoPatch",
            "pub fn initial_ppu_sim_snapshot() -> PpuSimSnapshot",
            "pub fn zero_video_anchor() -> VideoAnchor",
            "pub fn idle_raster_stimulus() -> RasterStimulus",
            "pub fn single_reg_write_stimulus(write: MmioWrite) -> RasterStimulus",
            "pub fn single_dma_start_stimulus(source_high: uint<8>) -> RasterStimulus",
        ]:
            self.assertIn(symbol, text)

    def test_ppu_scanout_surface_matches_architecture_contract(self) -> None:
        text = PPU_SCANOUT_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub enum PixelSource",
            "Background,",
            "Window,",
            "Object,",
            "pub struct PixelEmit",
            "x: uint<8>",
            "y: uint<8>",
            "shade: uint<2>",
            "source: PixelSource",
            "pub enum BlankReason",
            "LcdDisabled,",
            "WarmupBlankFrame,",
            "NonVisibleLine,",
            "NonVisibleDot,",
            "pub enum ScanoutEvent",
            "Pixel { emit: PixelEmit }",
            "Blank { y: uint<8>, reason: BlankReason }",
            "FrameStart,",
            "LineStart { y: uint<8> }",
            "pub fn zero_pixel_emit() -> PixelEmit",
            "pub fn blank_scanout_event(y: uint<8>, reason: BlankReason) -> ScanoutEvent",
        ]:
            self.assertIn(symbol, text)

    def test_ppu_register_helpers_match_architecture_contract(self) -> None:
        text = PPU_RTL_REGS_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub fn apply_mmio_write(regs: PpuRegs, event: MmioWrite) -> PpuRegs",
            "MmioReg::Lcdc => replace_lcdc(regs, decode_lcdc(event.value))",
            "MmioReg::Stat => replace_stat_select(regs, decode_stat_select(event.value))",
            "MmioReg::Scy =>",
            "MmioReg::Scx =>",
            "MmioReg::Lyc =>",
            "MmioReg::Wy =>",
            "MmioReg::Wx =>",
            "MmioReg::Bgp =>",
            "MmioReg::Obp0 =>",
            "MmioReg::Obp1 =>",
            "pub fn read_stat(regs: PpuRegs, status: PpuStatusState, ly: uint<8>) -> uint<8>",
            "0b1000_0000u8 | pack_stat_select(regs.stat_sel) | lyc_match | mode_bits(mode)",
            "pub fn readback_register(addr: uint<8>, regs: PpuRegs, status: PpuStatusState, ly: uint<8>) -> uint<8>",
            "0x40u8 => pack_lcdc(regs.lcdc)",
            "0x41u8 => read_stat(regs, status, ly)",
            "0x44u8 => ly",
            "0x4Bu8 => regs.wx",
            "_ => 0xffu8",
        ]:
            self.assertIn(symbol, text)

    def test_ppu_tile_helpers_match_architecture_contract(self) -> None:
        text = PPU_RTL_TILE_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub fn decode_tile_row(lo: uint<8>, hi: uint<8>) -> [uint<2>; 8]",
            "decode_pixel(lo, hi, 0x80u8)",
            "decode_pixel(lo, hi, 0x01u8)",
            "pub fn bgwin_tile_addr(lcdc: Lcdc, tile_id: uint<8>, row: uint<3>) -> uint<16>",
            "if lcdc.bgwin_data_hi",
            "0x8000u17",
            "0x8800u17",
            "0x9000u17",
            "pub fn apply_x_flip(row: [uint<2>; 8]) -> [uint<2>; 8]",
            "[row[7], row[6], row[5], row[4], row[3], row[2], row[1], row[0]]",
            "pub fn apply_y_flip(row_idx: uint<4>, obj_size: bool) -> uint<4>",
            "15u4 - row_idx",
            "7u4 - row_idx",
            "pub fn obj_tile_addr(obj_size: bool, tile_id: uint<8>, row: uint<4>, flags: ObjFlags) -> uint<16>",
            "let effective_row = if flags.y_flip { apply_y_flip(row, obj_size) } else { row };",
            "let base_tile = if obj_size { tile_id & 0xfeu8 } else { tile_id };",
            "let next_tile: uint<8> = trunc(base_tile + 1u8);",
            "let tile_index = if obj_size && effective_row >= 8u4 { next_tile } else { base_tile };",
            "0x8000u17",
        ]:
            self.assertIn(symbol, text)

    def test_ppu_tile_test_top_provides_stable_projection(self) -> None:
        text = PPU_RTL_TILE_TEST_TOP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub entity tile_test_top(",
            "lo_i: uint<8>",
            "hi_i: uint<8>",
            "bgwin_data_hi_i: bool",
            "tile_id_i: uint<8>",
            "row_i: uint<4>",
            "obj_size_i: bool",
            "x_flip_i: bool",
            "y_flip_i: bool",
            ") -> uint<68>",
            "let decoded = decode_tile_row(lo_i, hi_i);",
            "let flipped = if x_flip_i { apply_x_flip(decoded) } else { decoded };",
            "let bg_addr = bgwin_tile_addr(build_lcdc(bgwin_data_hi_i), tile_id_i, trunc(row_i));",
            "let y_flipped = apply_y_flip(row_i, obj_size_i);",
            "let obj_addr = obj_tile_addr(obj_size_i, tile_id_i, row_i, build_flags(x_flip_i, y_flip_i));",
        ]:
            self.assertIn(symbol, text)

    def test_ppu_timing_helpers_match_architecture_contract(self) -> None:
        text = PPU_RTL_TIMING_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub fn visible_mode(status: PpuStatusState) -> lib::ppu::sem::types::PpuMode",
            "pub fn lcd_enabled(status: PpuStatusState, regs: PpuRegs) -> bool",
            "pub fn advance_run_state(run: LcdRunState, frame_start: bool) -> LcdRunState",
            "pub fn advance_timing(",
            "state: PpuState",
            "input: lib::ppu::sem::events::DotInput",
            "next_regs: PpuRegs",
            ") -> (PpuPhase, uint<8>, PpuSamplingState, bool, bool)",
            "LcdRunState::WarmupBlankFrame",
            "PpuPhase::Transfer$(x_out: 0u8, discard_scx: sampled.scx_low3_line)",
            "PpuPhase::VBlank$(line: new_ly, dots_left: 456u9)",
            "pub fn handle_lcd_transition(",
            "old_lcdc7: bool",
            "new_lcdc7: bool",
        ]:
            self.assertIn(symbol, text)

    def test_ppu_timing_test_top_provides_stable_projection(self) -> None:
        text = PPU_RTL_TIMING_TEST_TOP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub entity timing_test_top(",
            "run_i: uint<2>",
            "phase_i: uint<3>",
            "ly_i: uint<8>",
            "dot_in_line_i: uint<9>",
            "sampled_scx_low3_i: uint<3>",
            "old_lcdc_enable_i: bool",
            "new_lcdc_enable_i: bool",
            ") -> uint<34>",
            "let (next_phase, next_ly, next_sampled, line_start, frame_start) = advance_timing(",
            "let transitioned = handle_lcd_transition(state, old_lcdc_enable_i, new_lcdc_enable_i);",
            "let next_run = advance_run_state(state.status.run, frame_start);",
        ]:
            self.assertIn(symbol, text)


if __name__ == "__main__":
    unittest.main()
