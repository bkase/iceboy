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

    def test_cpu_core_stub_contract_matches_instantiable_stub_signature(self) -> None:
        text = CPU_CORE_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub struct CpuCoreOut",
            "commit_seq: uint<64>",
            "pc: uint<16>",
            "bus_req_kind: uint<2>",
            "bus_req_addr: uint<16>",
            "bus_req_data: uint<8>",
            "fn skipboot_pc() -> uint<16>",
            "0x0100u16",
            "pub entity cpu_core(",
            ") -> CpuCoreOut",
            "reg(clk) pc: uint<16> reset(rst: skipboot_pc()) =",
            "reg(clk) commit_seq: uint<64> reset(rst: 0u64) =",
            "m_ce: bool",
            "bus_resp: BusResp",
            "irq_pending: IrqPending",
            "if m_ce { trunc(pc + 1u16) } else { pc }",
            "if m_ce { trunc(commit_seq + 1u64) } else { commit_seq }",
            "bus_req_kind: 0u2",
            "bus_req_addr: 0u16",
            "bus_req_data: 0u8",
        ]:
            self.assertIn(symbol, text)


if __name__ == "__main__":
    unittest.main()
