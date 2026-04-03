from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CPU_MAIN_PATH = ROOT / "src" / "cpu" / "main.spade"
CPU_CONTROL_PATH = ROOT / "src" / "cpu" / "control.spade"
CPU_SEMANTICS_PATH = ROOT / "src" / "cpu" / "semantics.spade"
CPU_SEMANTICS_ALU_TOP_PATH = ROOT / "src" / "cpu" / "semantics_alu_test_top.spade"
CPU_SEMANTICS_CB_TOP_PATH = ROOT / "src" / "cpu" / "semantics_cb_test_top.spade"
CPU_SEMANTICS_FLOW_TOP_PATH = ROOT / "src" / "cpu" / "semantics_flow_test_top.spade"
CPU_SEMANTICS_INTERRUPT_TOP_PATH = ROOT / "src" / "cpu" / "semantics_interrupt_test_top.spade"
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
        self.assertIn("pub mod semantics_cb_test_top;", text)
        self.assertIn("pub mod semantics_flow_test_top;", text)
        self.assertIn("pub mod semantics_interrupt_test_top;", text)
        self.assertIn("pub mod semantics_load_test_top;", text)
        self.assertIn("pub mod semantics_misc_test_top;", text)
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
            "pub fn cb_prefixed_fetch_phase(op: DecodedOp, regs: Registers) -> Phase",
            "pub fn word_alu_fetch_phase(op: DecodedOp) -> Phase",
            "Imm8Cont::AluImm8",
            "Imm8Cont::RelativeJump",
            "Imm8Cont::AddSpDisp",
            "Imm16Cont::JumpAbs",
            "Imm16Cont::CallTarget",
            "ReadCont::AluFromMem",
            "ReadCont::BitOpFromMem",
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
            "fn handle_fetch_prefix(state: CpuState, input: MicroInput, prefix: PrefixKind) -> MicroOutput",
            "fn handle_read_imm8(state: CpuState, input: MicroInput, k: Imm8Cont) -> MicroOutput",
            "fn handle_read_imm16_lo(state: CpuState, input: MicroInput, k: Imm16Cont) -> MicroOutput",
            "fn handle_read_imm16_hi(state: CpuState, input: MicroInput, lo: uint<8>, k: Imm16HiCont) -> MicroOutput",
            "fn handle_read_mem(state: CpuState, input: MicroInput, addr: uint<16>, k: ReadCont) -> MicroOutput",
            "fn handle_write_mem(state: CpuState, input: MicroInput, addr: uint<16>, data: uint<8>, k: WriteCont) -> MicroOutput",
            "fn handle_service_interrupt(state: CpuState, input: MicroInput, irq: IrqSel, subphase: IrqPhase) -> MicroOutput",
            "fn handle_execute(state: CpuState, input: MicroInput, op: DecodedOp) -> MicroOutput",
            "fn handle_halted(state: CpuState, input: MicroInput) -> MicroOutput",
            "fn any_irq_pending(irq_pending: IrqPending) -> bool",
            "fn irq_sel_from_pending(pending: uint<5>) -> lib::cpu::types::IrqSel",
            "fn irq_vector(irq: IrqSel) -> uint<16>",
            "fn irq_ack_for_sel(irq: IrqSel) -> IrqAck",
            "fn service_entry_output(state: CpuState, input: MicroInput, irq: IrqSel) -> MicroOutput",
            "fn execute_alu_delta(state: CpuState, kind: AluKind, dst: Operand8, src: Operand8, addressing: AddressingMode) -> CpuDelta",
            "fn halt_enter_delta(state: CpuState, irq_pending: IrqPending) -> CpuDelta",
            "fn execute_misc_delta(state: CpuState, irq_pending: IrqPending, kind: MiscKind) -> CpuDelta",
            "fn execute_bitop_delta(",
            "fn execute_bitop_result(",
            "fn bit_res_set_kind(kind: BitOpKind) -> BitResSetKind",
            "fn execute_control_flow_delta(",
            "fn execute_stack_delta(",
            "fn condition_matches(regs: Registers, condition: Option<ConditionCode>) -> bool",
            "fn fetch_imm_hi_seed(decoded: DecodedOp, phase_write: Option<Phase>) -> Option<uint<8>>",
            "fn misc_fetch_pc_write(op: DecodedOp, pc: uint<16>) -> Option<uint<16>>",
            "fn interrupt_control_fetch_ime_write(op: DecodedOp) -> Option<ImeState>",
            "fn execute_word_alu_delta(",
            "ReadCont::AluFromMem$(kind)",
            "ReadCont::BitOpFromMem$(kind, bit_index, zero_on_result) =>",
            "Imm8Cont::AluImm8$(kind)",
            "Imm8Cont::RelativeJump =>",
            "Imm8Cont::AddSpDisp =>",
            "Imm16Cont::JumpAbs =>",
            "Imm16Cont::CallTarget =>",
            "Imm16HiCont::JumpAbs$(lo) =>",
            "Imm16HiCont::CallTarget$(lo) =>",
            "WriteCont::PushHi$(next_pc) =>",
            "ControlTarget::Return$(enable_interrupts)",
            "MiscKind::Stop => some_u16(trunc(pc + 2u16))",
            "DecodedOp::InterruptControl$(enable, addressing) => {",
            "Option::Some(ImeState::PendingEnable)",
            "MiscKind::Halt => halt_enter_delta(state, irq_pending)",
            "Option::Some(HaltState::Halted)",
            "Option::Some(HaltState::HaltBugPending)",
            "fn halt_bug_fetch_delta(state: CpuState, opcode: uint<8>) -> CpuDelta",
            "Phase::ServiceInterrupt$(irq: irq, subphase: IrqPhase::Delay1)",
            "MicroOutput$(delta: delta, bus_req: bus_req, irq_ack: irq_ack, commit: Option::Some(commit), sideband: Option::None)",
            "aluish_fetch_phase(decoded, state.arch.regs)",
            "cb_prefixed_fetch_phase(decoded, state.arch.regs)",
            "control_flow_fetch_pc_write(decoded, state.arch.regs)",
            "control_flow_fetch_phase(decoded, state.arch.regs)",
            "word_alu_fetch_phase(decoded)",
            "Phase::FetchPrefix$(prefix) => handle_fetch_prefix(state, input, prefix)",
            "BusReq::Read$(addr: state.arch.regs.pc)",
            "some_u16(trunc(state.arch.regs.pc + 1u16))",
            "mask_f(select_u8(writes.f, regs.f))",
            "CpuState(next_arch, next_micro)",
            "Phase::Fetch => handle_fetch(state, input)",
            "Phase::ServiceInterrupt$(irq, subphase) => handle_service_interrupt(state, input, irq, subphase)",
            "Phase::Halted => handle_halted(state, input)",
            "Phase::ReadImm8$(k) => handle_read_imm8(state, input, k)",
            "Phase::ReadImm16Lo$(k) => handle_read_imm16_lo(state, input, k)",
            "Phase::ReadMem$(addr, k) => handle_read_mem(state, input, addr, k)",
            "Phase::WriteMem$(addr, data, k) => handle_write_mem(state, input, addr, data, k)",
            "Phase::Execute$(op) => handle_execute(state, input, op)",
        ]:
            self.assertIn(symbol, text)

    def test_semantics_misc_test_top_exposes_single_cycle_misc_projection_surface(self) -> None:
        text = (ROOT / "src" / "cpu" / "semantics_misc_test_top.spade").read_text(encoding="utf-8")
        for symbol in [
            "entity semantics_misc_test_top(",
            "state_ime_i: uint<2>",
            "state_halt_i: uint<2>",
            "state_phase_i: uint<4>",
            "fn ime_from_code(code: uint<2>) -> ImeState",
            "fn ime_code(ime: ImeState) -> uint<2>",
            "fn halt_code(halt: HaltState) -> uint<2>",
            "fn halt_from_code(code: uint<2>) -> HaltState",
            "fn phase_from_code(code: uint<4>, opcode: uint<8>) -> Phase",
            "fn phase_kind(phase: Phase) -> uint<4>",
            "let next_state = apply_delta(state, step.delta);",
            "zext(ime_code(next_state.arch.ime_state)) << 78",
            "zext(phase_kind(next_state.micro.phase)) << 72",
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

    def test_semantics_interrupt_test_top_exposes_service_projection_surface(self) -> None:
        text = CPU_SEMANTICS_INTERRUPT_TOP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "entity semantics_interrupt_test_top(",
            "state_irq_sel_i: uint<3>",
            "state_irq_phase_i: uint<3>",
            "fn irq_sel_from_code(code: uint<3>) -> IrqSel",
            "fn irq_phase_from_code(code: uint<3>) -> IrqPhase",
            "fn phase_from_inputs(kind: uint<2>, irq_sel: uint<3>, irq_phase: uint<3>) -> Phase",
            "step.irq_ack.ack_bit",
            "zext(next_phase_kind(next_state.micro.phase)) << 88",
            "zext(next_irq_phase_code(next_state.micro.phase)) << 82",
        ]:
            self.assertIn(symbol, text)

    def test_semantics_cb_test_top_exposes_prefix_and_bitop_projection_surface(self) -> None:
        text = CPU_SEMANTICS_CB_TOP_PATH.read_text(encoding="utf-8")
        for symbol in [
            "entity semantics_cb_test_top(",
            "Phase::FetchPrefix$(prefix: prefix_from_code(cont_code))",
            "ReadCont::BitOpFromMem$(kind: bitop_kind_from_code(trunc(cont_data)), bit_index: bit_index_from_code(data), zero_on_result: true)",
            "Phase::FetchPrefix$(prefix) => (1u4, prefix_code(prefix), 0u16, 0u8, 0u8, 0u16)",
            "ReadCont::BitOpFromMem$(kind, bit_index, zero_on_result) =>",
            "let decoded = decode_for_state(state_opcode_i, state_phase_kind_i);",
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
