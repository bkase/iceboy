from __future__ import annotations

from enum import Enum


class CommitKind(str, Enum):
    MCycle = "mcycle"
    InstrCommit = "instr_commit"
    InterruptAck = "interrupt_ack"
    Checkpoint = "checkpoint"


class OracleMode(str, Enum):
    Unit = "unit"
    InstrCommit = "instr_commit"
    MCycleCommit = "mcycle_commit"
    Checkpoint = "checkpoint"
    FrameSemantic = "frame_semantic"
    FrameHash = "frame_hash"
    SerialTerminal = "serial_terminal"


class CompareField(str, Enum):
    TargetValue = "target_value"
    Registers = "registers"
    Flags = "flags"
    ProgramCounter = "pc"
    StackPointer = "sp"
    ImeState = "ime_state"
    HaltState = "halt_state"
    MicroState = "micro_state"
    BusRequest = "bus_req"
    BusResponse = "bus_resp"
    MemTouch = "mem_touch"
    IoTouch = "io_touch"
    CheckpointTag = "checkpoint_tag"
    WramSignature = "wram_signature"
    FrameSemantic = "frame_semantic"
    FrameHash = "frame_hash"
    SerialOutput = "serial_output"


INSTR_COMMIT_FIELDS = frozenset(
    {
        CompareField.Registers,
        CompareField.Flags,
        CompareField.ProgramCounter,
        CompareField.StackPointer,
        CompareField.ImeState,
        CompareField.HaltState,
    }
)

COMPARISON_FIELDS_BY_COMMIT_KIND = {
    CommitKind.MCycle: INSTR_COMMIT_FIELDS
    | {
        CompareField.MicroState,
        CompareField.BusRequest,
        CompareField.BusResponse,
        CompareField.MemTouch,
        CompareField.IoTouch,
    },
    CommitKind.InstrCommit: INSTR_COMMIT_FIELDS,
    CommitKind.InterruptAck: INSTR_COMMIT_FIELDS | {CompareField.IoTouch},
    CommitKind.Checkpoint: INSTR_COMMIT_FIELDS | {CompareField.CheckpointTag, CompareField.WramSignature},
}

COMPARISON_FIELDS_BY_ORACLE_MODE = {
    OracleMode.Unit: frozenset({CompareField.TargetValue}),
    OracleMode.InstrCommit: COMPARISON_FIELDS_BY_COMMIT_KIND[CommitKind.InstrCommit],
    OracleMode.MCycleCommit: COMPARISON_FIELDS_BY_COMMIT_KIND[CommitKind.MCycle],
    OracleMode.Checkpoint: COMPARISON_FIELDS_BY_COMMIT_KIND[CommitKind.Checkpoint],
    OracleMode.FrameSemantic: frozenset({CompareField.FrameSemantic}),
    OracleMode.FrameHash: frozenset({CompareField.FrameHash}),
    OracleMode.SerialTerminal: frozenset({CompareField.SerialOutput}),
}

DEFAULT_COMMIT_KIND_BY_ORACLE_MODE = {
    OracleMode.Unit: None,
    OracleMode.InstrCommit: CommitKind.InstrCommit,
    OracleMode.MCycleCommit: CommitKind.MCycle,
    OracleMode.Checkpoint: CommitKind.Checkpoint,
    OracleMode.FrameSemantic: CommitKind.Checkpoint,
    OracleMode.FrameHash: CommitKind.Checkpoint,
    OracleMode.SerialTerminal: None,
}


def comparison_fields_for_mode(mode: OracleMode) -> frozenset[CompareField]:
    return COMPARISON_FIELDS_BY_ORACLE_MODE[mode]


def comparison_fields_for_commit_kind(kind: CommitKind) -> frozenset[CompareField]:
    return COMPARISON_FIELDS_BY_COMMIT_KIND[kind]


__all__ = [
    "COMPARISON_FIELDS_BY_COMMIT_KIND",
    "COMPARISON_FIELDS_BY_ORACLE_MODE",
    "DEFAULT_COMMIT_KIND_BY_ORACLE_MODE",
    "CommitKind",
    "CompareField",
    "OracleMode",
    "comparison_fields_for_commit_kind",
    "comparison_fields_for_mode",
]
