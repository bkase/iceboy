from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CPU_MAIN_PATH = ROOT / "src" / "cpu" / "main.spade"
CPU_CONTROL_PATH = ROOT / "src" / "cpu" / "control.spade"
CPU_SEMANTICS_PATH = ROOT / "src" / "cpu" / "semantics.spade"
CPU_SEMANTICS_ALU_TOP_PATH = ROOT / "src" / "cpu" / "semantics_alu_test_top.spade"
CPU_SEMANTICS_FLOW_TOP_PATH = ROOT / "src" / "cpu" / "semantics_flow_test_top.spade"
CPU_SEMANTICS_LOAD_TOP_PATH = ROOT / "src" / "cpu" / "semantics_load_test_top.spade"
CPU_SEMANTICS_TOP_PATH = ROOT / "src" / "cpu" / "semantics_test_top.spade"
CPU_SEMANTICS_WORDALU_TOP_PATH = ROOT / "src" / "cpu" / "semantics_wordalu_test_top.spade"
SWIM_LOCK_PATH = ROOT / "swim.lock"


class CpuSemanticsContractTest(unittest.TestCase):
    def test_cpu_module_exports_semantics_modules(self) -> None:
        text = CPU_MAIN_PATH.read_text(encoding="utf-8")
        self.assertIn("pub mod control;", text)
        self.assertIn("pub mod semantics;", text)
        self.assertIn("pub mod semantics_alu_test_top;", text)
        self.assertIn("pub mod semantics_flow_test_top;", text)
        self.assertIn("pub mod semantics_load_test_top;", text)
        self.assertIn("pub mod semantics_test_top;", text)
        self.assertIn("pub mod semantics_wordalu_test_top;", text)

    def test_control_module_exposes_load_phase_helpers(self) -> None:
        text = CPU_CONTROL_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub fn hl_post_adjust(regs: Registers, addressing: AddressingMode) -> uint<16>",
            "pub fn loadish_fetch_phase(op: DecodedOp, regs: Registers) -> Phase",
            "pub fn aluish_fetch_phase(op: DecodedOp, regs: Registers) -> Phase",
            "pub fn control_flow_fetch_phase(op: DecodedOp, regs: Registers) -> Phase",
            "pub fn control_flow_fetch_pc_write(op: DecodedOp, regs: Registers) -> Option<uint<16>>",
            "pub fn word_alu_fetch_phase(op: DecodedOp) -> Phase",
            "Imm8Cont::AluImm8",
            "Imm8Cont::RelativeJump",
            "Imm8Cont::AddSpDisp",
            "Imm16Cont::JumpAbs",
            "Imm16Cont::CallTarget",
            "ReadCont::AluFromMem",
            "ReadCont::PopLo",
            "Imm8Cont::StoreToHl",
            "Imm16Cont::StoreSpToAddr",
        ]:
            self.assertIn(symbol, text)

    def test_semantics_module_exposes_delta_and_phase_dispatch(self) -> None:
        text = CPU_SEMANTICS_PATH.read_text(encoding="utf-8")
        for symbol in [
            "pub fn apply_delta(state: CpuState, delta: CpuDelta) -> CpuState",
            "pub fn step_mcycle(state: CpuState, input: MicroInput) -> MicroOutput",
            "fn handle_fetch(state: CpuState, input: MicroInput) -> MicroOutput",
            "fn handle_read_imm8(state: CpuState, input: MicroInput, k: Imm8Cont) -> MicroOutput",
            "fn handle_read_imm16_lo(state: CpuState, input: MicroInput, k: Imm16Cont) -> MicroOutput",
            "fn handle_read_imm16_hi(state: CpuState, input: MicroInput, lo: uint<8>, k: Imm16HiCont) -> MicroOutput",
            "fn handle_read_mem(state: CpuState, input: MicroInput, addr: uint<16>, k: ReadCont) -> MicroOutput",
            "fn handle_write_mem(state: CpuState, input: MicroInput, addr: uint<16>, data: uint<8>, k: WriteCont) -> MicroOutput",
            "fn handle_execute(state: CpuState, input: MicroInput, op: DecodedOp) -> MicroOutput",
            "fn handle_halted(state: CpuState, input: MicroInput) -> MicroOutput",
            "fn execute_alu_delta(state: CpuState, kind: AluKind, dst: Operand8, src: Operand8, addressing: AddressingMode) -> CpuDelta",
            "fn execute_misc_delta(state: CpuState, kind: MiscKind) -> CpuDelta",
            "fn execute_bitop_delta(",
            "fn execute_control_flow_delta(",
            "fn execute_stack_delta(",
            "fn condition_matches(regs: Registers, condition: Option<ConditionCode>) -> bool",
            "fn fetch_imm_hi_seed(decoded: DecodedOp, phase_write: Option<Phase>) -> Option<uint<8>>",
            "fn execute_word_alu_delta(",
            "ReadCont::AluFromMem$(kind)",
            "Imm8Cont::AluImm8$(kind)",
            "Imm8Cont::RelativeJump =>",
            "Imm8Cont::AddSpDisp =>",
            "Imm16Cont::JumpAbs =>",
            "Imm16Cont::CallTarget =>",
            "Imm16HiCont::JumpAbs$(lo) =>",
            "Imm16HiCont::CallTarget$(lo) =>",
            "WriteCont::PushHi$(next_pc) =>",
            "ControlTarget::Return$(enable_interrupts)",
            "aluish_fetch_phase(decoded, state.arch.regs)",
            "control_flow_fetch_pc_write(decoded, state.arch.regs)",
            "control_flow_fetch_phase(decoded, state.arch.regs)",
            "word_alu_fetch_phase(decoded)",
            "BusReq::Read$(addr: state.arch.regs.pc)",
            "some_u16(trunc(state.arch.regs.pc + 1u16))",
            "mask_f(select_u8(writes.f, regs.f))",
            "CpuState(next_arch, next_micro)",
            "Phase::Fetch => handle_fetch(state, input)",
            "Phase::Halted => handle_halted(state, input)",
            "Phase::ReadImm8$(k) => handle_read_imm8(state, input, k)",
            "Phase::ReadImm16Lo$(k) => handle_read_imm16_lo(state, input, k)",
            "Phase::ReadMem$(addr, k) => handle_read_mem(state, input, addr, k)",
            "Phase::WriteMem$(addr, data, k) => handle_write_mem(state, input, addr, data, k)",
            "Phase::Execute$(op) => handle_execute(state, input, op)",
        ]:
            self.assertIn(symbol, text)

    def test_semantics_flow_test_top_exposes_controlflow_projection_surface(self) -> None:
        text = CPU_SEMANTICS_FLOW_TOP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "entity semantics_flow_test_top(",
            "state_ime_i: uint<2>",
            "Imm8Cont::RelativeJump",
            "Imm16Cont::JumpAbs",
            "Imm16Cont::CallTarget",
            "WriteCont::PushHi",
            "fn ime_code(ime: ImeState) -> uint<2>",
            "zext(ime_code(next_state.arch.ime_state)) << 152",
            "zext(next_state.micro.imm_hi) << 128",
        ]:
            self.assertIn(symbol, text)

    def test_semantics_alu_test_top_exposes_temp_and_alu_continuations(self) -> None:
        text = CPU_SEMANTICS_ALU_TOP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "entity semantics_alu_test_top(",
            "state_temp_i: uint<16>",
            "Imm8Cont::AluImm8",
            "ReadCont::AluFromMem",
            "let micro = CpuMicroState(phase, state_opcode_i, state_imm_lo_i, 0u8, decoded, state_temp_i);",
            "zext(next_state.micro.temp) << 112",
        ]:
            self.assertIn(symbol, text)

    def test_semantics_wordalu_test_top_exposes_word_alu_subphase_surface(self) -> None:
        text = CPU_SEMANTICS_WORDALU_TOP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "entity semantics_wordalu_test_top(",
            "state_imm_hi_i: uint<8>",
            "Imm8Cont::AddSpDisp",
            "let micro = CpuMicroState(phase, state_opcode_i, state_imm_lo_i, state_imm_hi_i, decoded, state_temp_i);",
            "zext(next_state.micro.imm_hi) << 128",
            "zext(next_state.micro.temp) << 112",
        ]:
            self.assertIn(symbol, text)

    def test_semantics_load_test_top_exposes_phase_projection_surface(self) -> None:
        text = CPU_SEMANTICS_LOAD_TOP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "entity semantics_load_test_top(",
            "let step = step_mcycle(state, MicroInput(BusResp$(data: bus_resp_i), IrqPending$(pending: irq_pending_i)));",
            "let next_state = apply_delta(state, step.delta);",
            "fn phase_projection(phase: Phase) -> (uint<4>, uint<4>, uint<16>, uint<8>, uint<8>, uint<16>)",
            "fn write_cont_from_inputs(code: uint<4>, cont_data: uint<8>, aux: uint<16>) -> WriteCont",
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
