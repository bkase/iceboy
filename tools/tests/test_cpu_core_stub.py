from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CPU_MAIN_PATH = ROOT / "src" / "cpu" / "main.spade"
CPU_CORE_PATH = ROOT / "src" / "cpu" / "core.spade"


class CpuCoreStubContractTest(unittest.TestCase):
    def test_cpu_module_exports_core_submodule(self) -> None:
        text = CPU_MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn("pub mod core;", text)

    def test_cpu_core_stub_contract_matches_phase_two_signature(self) -> None:
        text = CPU_CORE_PATH.read_text(encoding="utf-8")
        for symbol in [
            "fn skipboot_registers() -> Registers",
            "a: 0x01u8",
            "f: 0xb0u8",
            "c: 0x13u8",
            "e: 0xd8u8",
            "sp: 0xfffeu16",
            "pc: 0x0100u16",
            "fn stub_advance_registers(regs: Registers) -> Registers",
            "fn make_arch_state(regs: Registers, ime_state: ImeState, halt_state: HaltState) -> CpuArchState",
            "pc: trunc(regs.pc + 1u16)",
            "reg(clk) regs: Registers reset(rst: skipboot_registers()) =",
            "reg(clk) ime_state: ImeState reset(rst: ImeState::Disabled) =",
            "reg(clk) halt_state: HaltState reset(rst: HaltState::Running) =",
            "reg(clk) phase: Phase reset(rst: Phase::Fetch) =",
            "reg(clk) decoded: DecodedOp reset(rst: invalid_decoded_op()) =",
            "reg(clk) temp: uint<16> reset(rst: 0u16) =",
            "reg(clk) commit_seq: uint<64> reset(rst: 0u64) =",
            "temp + 1u16",
            "fn stub_commit_trace(",
            "entity cpu_core(",
            "m_ce: bool",
            "bus_resp: BusResp",
            "irq_pending: IrqPending",
            ") -> (BusReq, CommitTrace)",
            "if m_ce { stub_advance_registers(regs) } else { regs }",
            "if m_ce { trunc(commit_seq + 1u64) } else { commit_seq }",
            "(idle_bus_req(), stub_commit_trace(committed_seq, committed_arch, committed_phase, bus_resp))",
        ]:
            self.assertIn(symbol, text)


if __name__ == "__main__":
    unittest.main()
