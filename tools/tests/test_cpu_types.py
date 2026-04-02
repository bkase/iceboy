from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CPU_TYPES_PATH = ROOT / "src" / "cpu" / "types.spade"


class CpuTypesContractTest(unittest.TestCase):
    def test_cpu_state_enums_and_structs_match_phase_two_contract(self) -> None:
        text = CPU_TYPES_PATH.read_text(encoding="utf-8")

        for symbol in [
            "enum ImeState",
            "PendingEnable",
            "enum HaltState",
            "HaltBugPending",
            "struct Registers",
            "struct CpuArchState",
            "struct CpuMicroState",
            "struct CpuState",
            "enum PrefixKind",
            "enum Phase",
            "FetchPrefix { prefix: PrefixKind }",
            "ReadImm8 { k: Imm8Cont }",
            "ReadImm16Lo { k: Imm16Cont }",
            "ReadImm16Hi { lo: uint<8>, k: Imm16HiCont }",
            "ReadMem { addr: uint<16>, k: ReadCont }",
            "WriteMem { addr: uint<16>, data: uint<8>, k: WriteCont }",
            "Execute { op: DecodedOp }",
            "ServiceInterrupt { irq: IrqSel, subphase: IrqPhase }",
            "enum ReadCont",
            "LoadReg8 { dst: R8 }",
            "AluFromMem { kind: AluKind }",
            "enum WriteCont",
            "PushHi { next_pc: uint<16> }",
            "PushLo { low: uint<8>, target: uint<16> }",
            "enum Imm8Cont",
            "enum Imm16Cont",
            "enum Imm16HiCont",
            "enum IrqSel",
            "enum IrqPhase",
            "struct IrqPending",
            "struct IrqAck",
            "struct MicroInput",
            "struct MicroOutput",
            "struct RegWriteSet",
            "struct MicroWriteSet",
            "struct CpuDelta",
            "pub fn initial_cpu_state() -> CpuState",
            "pub fn idle_cpu_delta() -> CpuDelta",
            "pub fn idle_micro_output() -> MicroOutput",
        ]:
            self.assertIn(symbol, text)

    def test_cpu_types_file_keeps_profile_contract_and_local_placeholders(self) -> None:
        text = CPU_TYPES_PATH.read_text(encoding="utf-8")

        for symbol in [
            "enum ModelProfile",
            "enum ResetProfile",
            "enum MemoryBehaviorProfile",
            "struct SimulationProfiles",
            "enum BusReqKind",
            "struct BusReq",
            "enum BusRespKind",
            "struct BusResp",
            "enum CommitKind",
            "struct CommitTrace",
            "struct Sideband",
        ]:
            self.assertIn(symbol, text)


if __name__ == "__main__":
    unittest.main()
