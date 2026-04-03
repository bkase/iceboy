from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CPU_MAIN_PATH = ROOT / "src" / "cpu" / "main.spade"
CPU_CORE_PATH = ROOT / "src" / "cpu" / "core.spade"
CPU_FORMAL_TOP_PATH = ROOT / "src" / "cpu" / "formal_invariants_top.spade"


class CpuCoreStubContractTest(unittest.TestCase):
    def test_cpu_module_exports_core_submodule(self) -> None:
        text = CPU_MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn("pub mod core;", text)
        self.assertIn("pub mod formal_invariants_top;", text)

    def test_cpu_core_contract_matches_semantic_wrapper_signature(self) -> None:
        text = CPU_CORE_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub struct CpuCoreOut",
            "commit_seq: uint<64>",
            "regs: Registers",
            "ime_state: ImeState",
            "halt_state: HaltState",
            "phase: Phase",
            "pc: uint<16>",
            "f_low_nibble_zero: bool",
            "bus_req_kind: uint<2>",
            "bus_req_addr: uint<16>",
            "bus_req_data: uint<8>",
            "irq_ack_valid: bool",
            "irq_ack_bit: uint<3>",
            "fn skipboot_pc() -> uint<16>",
            "fn skipboot_sp() -> uint<16>",
            "fn skipboot_regs() -> Registers",
            "fn skipboot_arch_state() -> CpuArchState",
            "0x0100u16",
            "0xfffeu16",
            "0x01u8",
            "0xb0u8",
            "0x13u8",
            "0xd8u8",
            "0x4du8",
            "pub entity cpu_core(",
            ") -> CpuCoreOut",
            "decl arch_state;",
            "decl micro_state;",
            "let state = CpuState(arch_state, micro_state);",
            "let step = step_mcycle(state, MicroInput(bus_resp, irq_pending));",
            "let next_state = apply_delta(state, step.delta);",
            "reg(clk) arch_state: CpuArchState reset(rst: skipboot_arch_state()) =",
            "reg(clk) micro_state: CpuMicroState reset(rst: initial_cpu_micro_state()) =",
            "reg(clk) commit_seq: uint<64> reset(rst: 0u64) =",
            "m_ce: bool",
            "bus_resp: BusResp",
            "irq_pending: IrqPending",
            "if m_ce { next_state.arch } else { arch_state }",
            "if m_ce { next_state.micro } else { micro_state }",
            "if m_ce { trunc(commit_seq + 1u64) } else { commit_seq }",
            "let visible_arch = arch_state;",
            "let visible_phase = micro_state.phase;",
            "let visible_bus_req = if m_ce { step.bus_req } else { BusReq::Idle };",
            "let visible_irq_ack = if m_ce { step.irq_ack } else { no_irq_ack() };",
            "let visible_f = visible_arch.regs.f;",
            "regs: visible_arch.regs",
            "ime_state: visible_arch.ime_state",
            "halt_state: visible_arch.halt_state",
            "phase: visible_phase",
            "f_low_nibble_zero: mask_f(visible_f) == visible_f",
            "bus_req_kind: bus_req_kind(visible_bus_req)",
            "bus_req_addr: bus_req_addr(visible_bus_req)",
            "bus_req_data: bus_req_data(visible_bus_req)",
            "irq_ack_valid: match visible_irq_ack.ack_bit {",
            "irq_ack_bit: match visible_irq_ack.ack_bit {",
        ]:
            self.assertIn(symbol, text)

    def test_formal_top_exposes_core_invariant_surface(self) -> None:
        text = CPU_FORMAL_TOP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub entity cpu_f_low_nibble_top(",
            "pub entity cpu_reset_top(",
            "pub entity cpu_hold_top(",
            "fn ime_code(ime: ImeState) -> uint<2>",
            "fn halt_code(halt: HaltState) -> uint<2>",
            "fn phase_code(phase: Phase) -> uint<4>",
            "bus_resp: BusResp",
            "irq_pending: IrqPending",
            "let cpu = inst cpu_core(clk, rst, m_ce, bus_resp, irq_pending);",
            "cpu.f_low_nibble_zero",
            "cpu.regs.a == 0x01u8",
            "cpu.regs.pc == 0x0100u16",
            "ime_code(cpu.ime_state) == 0u2",
            "halt_code(cpu.halt_state) == 0u2",
            "phase_code(cpu.phase) == 0u4",
            "cpu.bus_req_kind == 1u2",
            "cpu.bus_req_addr == 0x0100u16",
            "let cpu = inst cpu_core(clk, rst, false, bus_resp, irq_pending);",
            "(zext(cpu.regs.a) << 92)",
            "| zext(cpu.bus_req_kind)",
        ]:
            self.assertIn(symbol, text)


if __name__ == "__main__":
    unittest.main()
