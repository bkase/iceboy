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

    def test_cpu_core_contract_matches_semantic_wrapper_signature(self) -> None:
        text = CPU_CORE_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub struct CpuCoreOut",
            "commit_seq: uint<64>",
            "pc: uint<16>",
            "bus_req_kind: uint<2>",
            "bus_req_addr: uint<16>",
            "bus_req_data: uint<8>",
            "fn skipboot_pc() -> uint<16>",
            "fn skipboot_sp() -> uint<16>",
            "fn skipboot_arch_state() -> CpuArchState",
            "0x0100u16",
            "0xfffeu16",
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
            "let visible_bus_req = if m_ce { step.bus_req } else { BusReq::Idle };",
            "bus_req_kind: bus_req_kind(visible_bus_req)",
            "bus_req_addr: bus_req_addr(visible_bus_req)",
            "bus_req_data: bus_req_data(visible_bus_req)",
        ]:
            self.assertIn(symbol, text)


if __name__ == "__main__":
    unittest.main()
