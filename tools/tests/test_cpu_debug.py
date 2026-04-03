from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CPU_MAIN_PATH = ROOT / "src" / "cpu" / "main.spade"
CPU_DEBUG_PATH = ROOT / "src" / "cpu" / "debug.spade"


class CpuDebugContractTest(unittest.TestCase):
    def test_cpu_module_exports_debug_submodule(self) -> None:
        text = CPU_MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn("pub mod debug;", text)

    def test_commit_and_debug_trace_contracts_live_in_debug_module(self) -> None:
        text = CPU_DEBUG_PATH.read_text(encoding="utf-8")

        for symbol in [
            "enum CommitKind",
            "MCycle",
            "InstrCommit",
            "InterruptAck",
            "Checkpoint",
            "enum MemTouchKind",
            "struct MemTouch",
            "struct IoTouch",
            "struct CommitTrace",
            "pc_before: uint<16>",
            "opcode: Option<uint<8>>",
            "arch_after: CpuArchState",
            "phase_after: Phase",
            "bus_req: BusReq",
            "bus_resp: BusResp",
            "mem_touch: Option<MemTouch>",
            "io_touch: Option<IoTouch>",
            "struct DebugTrace",
            "struct Sideband",
            "bus_obs: Option<BusObs>",
            "debug_trace: Option<DebugTrace>",
            "struct MicroOutput",
            "delta: CpuDelta",
            "irq_ack: IrqAck",
            "commit: Option<CommitTrace>",
            "sideband: Option<Sideband>",
            "pub fn idle_sideband() -> Sideband",
            "pub fn idle_micro_output() -> MicroOutput",
            "irq_ack: no_irq_ack()",
        ]:
            self.assertIn(symbol, text)


if __name__ == "__main__":
    unittest.main()
