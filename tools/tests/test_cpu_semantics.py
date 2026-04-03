from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CPU_MAIN_PATH = ROOT / "src" / "cpu" / "main.spade"
CPU_SEMANTICS_PATH = ROOT / "src" / "cpu" / "semantics.spade"
CPU_SEMANTICS_TOP_PATH = ROOT / "src" / "cpu" / "semantics_test_top.spade"
SWIM_LOCK_PATH = ROOT / "swim.lock"


class CpuSemanticsContractTest(unittest.TestCase):
    def test_cpu_module_exports_semantics_modules(self) -> None:
        text = CPU_MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn("pub mod semantics;", text)
        self.assertIn("pub mod semantics_test_top;", text)

    def test_semantics_module_exposes_delta_and_phase_dispatch(self) -> None:
        text = CPU_SEMANTICS_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub fn apply_delta(state: CpuState, delta: CpuDelta) -> CpuState",
            "pub fn step_mcycle(state: CpuState, input: MicroInput) -> MicroOutput",
            "fn handle_fetch(state: CpuState, input: MicroInput) -> MicroOutput",
            "fn handle_halted(state: CpuState, input: MicroInput) -> MicroOutput",
            "BusReq::Read$(addr: state.arch.regs.pc)",
            "Option::Some(trunc(state.arch.regs.pc + 1u16))",
            "mask_f(select_u8(writes.f, regs.f))",
            "CpuState(next_arch, next_micro)",
            "Phase::Fetch => handle_fetch(state, input)",
            "Phase::Halted => handle_halted(state, input)",
        ]:
            self.assertIn(symbol, text)

    def test_semantics_test_top_exposes_apply_and_step_signals(self) -> None:
        text = CPU_SEMANTICS_TOP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "entity semantics_test_top(",
            "let applied = apply_delta(state, delta);",
            "let step = step_mcycle(state, MicroInput(BusResp$(data: bus_resp_i), IrqPending$(pending: irq_pending_i)));",
            "bus_req_kind(step.bus_req)",
            "step.delta.pc_write",
            "step.delta.micro_write.opcode_latch",
        ]:
            self.assertIn(symbol, text)

    def test_swim_lock_pins_local_compiler_fix_commit(self) -> None:
        text = SWIM_LOCK_PATH.read_text(encoding="utf-8")
        self.assertIn('commit = "308fa38f5c0caed7b6dbf7db9ac84050f6d6992a"', text)
