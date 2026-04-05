from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SIM_TYPES_PATH = ROOT / "src" / "sim" / "types.spade"
SIM_MAIN_PATH = ROOT / "src" / "sim" / "main.spade"
CPU_TOP_PATH = ROOT / "src" / "sim" / "cpu_test_top.spade"
BOARD_TOP_PATH = ROOT / "src" / "board" / "icebreaker_top.spade"
PPU_TEST_TOP_PATH = ROOT / "src" / "sim" / "ppu_test_top.spade"
PPU_STATE_TOP_PATH = ROOT / "src" / "sim" / "ppu_state_top.spade"
SEMANTIC_OBSERVE_TOP_PATH = ROOT / "src" / "sim" / "semantic_observe_top.spade"
SOC_TOP_PATH = ROOT / "src" / "sim" / "soc_lockstep_top.spade"
TRACE_OBSERVE_TOP_PATH = ROOT / "src" / "sim" / "trace_observe_top.spade"
SOC_ROM_TOP_PATH = ROOT / "src" / "sim" / "soc_rom_top.spade"
SOC_ROM_TOP_WRAPPER_PATH = ROOT / "test" / "harness" / "verilog" / "soc_rom_top_verilator_wrapper.sv"


class SimScaffoldTest(unittest.TestCase):
    def test_hardware_top_stays_debug_free(self) -> None:
        text = BOARD_TOP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "#[no_mangle(all)]",
            "entity icebreaker_top(",
            "entity hardware_core(",
            "let tb = inst timebase(",
            "let cpu = inst cpu_core(",
            "let (bus_resp_next, bus_obs) = inst membus(",
            "MemoryBehaviorProfile::DmgConservative",
            "set LEDR_N = heartbeat_led(tb.sys_counter);",
            "set LEDG_N = cpu_running_led(cpu.halt_state);",
        ]:
            self.assertIn(symbol, text)
        for forbidden in [
            "SimStimulus",
            "CommitTrace",
            "DebugTrace",
            "PpuDebugTrace",
            "BusObs$(",
            "SocLockstepTopOut",
        ]:
            self.assertNotIn(forbidden, text)

    def test_sim_stimulus_fields_match_architecture_contract(self) -> None:
        text = SIM_TYPES_PATH.read_text(encoding="utf-8")
        for field in [
            "joyp_buttons: Option<JoypButtons>",
            "if_set_bits: uint<5>",
            "if_clear_bits: uint<5>",
            "ie_override: Option<uint<5>>",
            "dma_start: Option<uint<8>>",
            "serial_inject: Option<uint<8>>",
            "freeze_arch_time: bool",
            "cpu_hold_only: bool",
        ]:
            self.assertIn(field, text)

    def test_sim_top_scaffolds_exist_with_stable_entity_names(self) -> None:
        sim_main_text = SIM_MAIN_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub mod ppu_support;",
            "pub mod ppu_test_top;",
            "pub mod semantic_observe_top;",
            "pub mod trace_observe_top;",
            "pub mod ppu_state_top;",
            "pub mod soc_rom_top;",
        ]:
            self.assertIn(symbol, sim_main_text)
        text = CPU_TOP_PATH.read_text(encoding="utf-8")
        self.assertIn("entity cpu_test_top(", text)
        for symbol in [
            "ime_state: uint<2>",
            "halt_state: uint<2>",
            "phase_kind: uint<4>",
            "commit_seq: uint<64>",
            "pc: uint<16>",
            "bus_req_kind: uint<2>",
            "bus_req_addr: uint<16>",
            "bus_req_data: uint<8>",
            "bus_region: uint<4>",
            "bus_owner: uint<2>",
            "bus_blocked: bool",
            "let cpu = inst cpu_core(",
            "let bus_obs = observe_req(",
            "let periph_m_ce = peripheral_arch_time_enable(stimulus);",
            "ime_state: encode_ime(cpu.ime_state)",
            "halt_state: encode_halt(cpu.halt_state)",
            "phase_kind: encode_phase(cpu.phase)",
            "stimulus.if_set_bits",
            "stimulus.if_clear_bits",
            "cpu.irq_ack_valid",
            "metric_total_cycles",
            "metric_bus_active_cycles",
            "metric_alu_active_cycles",
            "metric_halt_quiescent_cycles",
            "metric_reg_pc_we_cycles",
        ]:
            self.assertIn(symbol, text)
        ppu_test_text = PPU_TEST_TOP_PATH.read_text(encoding="utf-8")
        self.assertIn("entity ppu_test_top(", ppu_test_text)
        for symbol in [
            "stimulus: RasterStimulus",
            "mem_resp: PpuMemResp",
            "dma_state: OamDmaState",
            "commit_seq: uint<64>",
            "phase_kind: uint<3>",
            "mode_kind: uint<3>",
            "state: PpuState",
            "state_export: PpuSimSnapshot",
            "let (bus_events, bus_event_count) = timed_events_from_stimulus(video_now, commit_seq, stimulus);",
            "let step = step_dot(",
            "semantic_valid: semantic_valid(visible.semantic)",
            "line_summary_valid: line_summary_valid(visible.line_summary)",
        ]:
            self.assertIn(symbol, ppu_test_text)
        semantic_text = SEMANTIC_OBSERVE_TOP_PATH.read_text(encoding="utf-8")
        self.assertIn("entity semantic_observe_top(", semantic_text)
        for symbol in [
            "bus_events: [TimedPpuEvent; 4]",
            "bus_event_count: uint<4>",
            "semantic: PpuSemanticCommit",
            "line_summary: LineSummary",
            "state_after: PpuState",
            "phase_kind: uint<3>",
            "mode_kind: uint<3>",
        ]:
            self.assertIn(symbol, semantic_text)
        trace_text = TRACE_OBSERVE_TOP_PATH.read_text(encoding="utf-8")
        self.assertIn("entity trace_observe_top(", trace_text)
        for symbol in [
            "trace_valid: bool",
            "trace: PpuDebugTrace",
            "trace_valid: dot_ce",
            "ppu_debug_trace(video_now, visible)",
        ]:
            self.assertIn(symbol, trace_text)
        state_text = PPU_STATE_TOP_PATH.read_text(encoding="utf-8")
        self.assertIn("entity ppu_state_top(", state_text)
        for symbol in [
            "stimulus: RasterStimulus",
            "snapshot_export_valid: bool",
            "snapshot_export: PpuSimSnapshot",
            "semantic: PpuSemanticCommit",
            "line_summary: LineSummary",
            "let imported_state = match stimulus.state_import {",
        ]:
            self.assertIn(symbol, state_text)
        soc_text = SOC_TOP_PATH.read_text(encoding="utf-8")
        self.assertIn("entity soc_lockstep_top(", soc_text)
        for symbol in [
            "ppu_mode: uint<3>",
            "ppu_ly: uint<8>",
            "ppu_stat: uint<8>",
            "ppu_dot_in_line: uint<9>",
            "ppu_vblank_req: bool",
            "ppu_stat_req: bool",
            "commit_seq: uint<64>",
            "cpu_b: uint<8>",
            "cpu_c: uint<8>",
            "cpu_d: uint<8>",
            "cpu_e: uint<8>",
            "cpu_h: uint<8>",
            "cpu_l: uint<8>",
            "sys_counter: uint<32>",
            "m_ce: bool",
            "bus_region: uint<4>",
            "irq_ack_valid: bool",
            "irq_ack_bit: uint<3>",
            "let tb = inst timebase(",
            "let cpu = inst cpu_core(",
            "let (ppu_bus_events, ppu_bus_event_count) = inst ppu_event_bridge(",
            "let ppu = inst ppu_core(",
            "scanout_or_blank(ppu.scanout, ppu.trace.ly_after)",
            "semantic_valid(ppu.trace.semantic)",
            "irq_ack_valid: cpu.irq_ack_valid",
            "irq_ack_bit: cpu.irq_ack_bit",
            "metric_total_cycles",
            "metric_bus_active_cycles",
            "metric_alu_active_cycles",
            "metric_halt_quiescent_cycles",
            "metric_reg_pc_we_cycles",
        ]:
            self.assertIn(symbol, soc_text)
        soc_rom_text = SOC_ROM_TOP_PATH.read_text(encoding="utf-8")
        self.assertIn("entity soc_rom_top(", soc_rom_text)
        for symbol in [
            "ppu_vblank_req_window: bool",
            "ppu_stat_req_window: bool",
            "ppu_vblank_req: bool",
            "ppu_stat_req: bool",
            "ppu_mode: uint<3>",
            "ppu_ly: uint<8>",
            "ppu_stat: uint<8>",
            "irq_ack_valid: bool",
            "irq_ack_bit: uint<3>",
            "pc: uint<16>",
            "cpu_a: uint<8>",
            "cpu_b: uint<8>",
            "cpu_c: uint<8>",
            "cpu_d: uint<8>",
            "cpu_e: uint<8>",
            "cpu_h: uint<8>",
            "cpu_l: uint<8>",
            "bus_req_kind: uint<2>",
            "bus_req_addr: uint<16>",
            "bus_req_data: uint<8>",
            "t_index: uint<2>",
            "m_ce: bool",
            "preview_bus_req_kind: uint<2>",
            "preview_bus_req_addr: uint<16>",
            "preview_bus_req_data: uint<8>",
            "if_reg: uint<5>",
            "ie_reg: uint<5>",
            "let cpu_ppu_if_bits = ppu_irq_if_bits(ppu_vblank_req_accum, ppu_stat_req_accum);",
            "let effective_if = (if_reg & 0b11100u5) | zext(ppu_if_latch_low2);",
            "let cpu_irq_pending = IrqPending$(pending: irq_pending | (ie_reg & effective_if));",
            "fn ppu_irq_if_bits(vblank_req: bool, stat_req: bool) -> uint<5>",
            "let tb = inst timebase(",
            "let cpu = inst cpu_core(",
            "let (ppu_bus_events, ppu_bus_event_count) = inst ppu_event_bridge(",
            "let ppu = inst ppu_core(",
            "cpu.preview_bus_req_kind",
            "cpu.preview_bus_req_addr",
            "cpu.preview_bus_req_data",
        ]:
            self.assertIn(symbol, soc_rom_text)
        wrapper_text = SOC_ROM_TOP_WRAPPER_PATH.read_text(encoding="utf-8")
        self.assertIn("module soc_rom_top_verilator_wrapper", wrapper_text)
        self.assertIn("output [161:0] output__", wrapper_text)
        self.assertIn("\\iceboy::sim::soc_rom_top::soc_rom_top  impl (", wrapper_text)
        self.assertIn(".if_reg_i(if_reg_i)", wrapper_text)
        self.assertIn(".ie_reg_i(ie_reg_i)", wrapper_text)
        self.assertIn(".output__(output__)", wrapper_text)


if __name__ == "__main__":
    unittest.main()
