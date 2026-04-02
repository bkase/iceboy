"""Human-readable formatting for lockstep traces and diffs."""

from __future__ import annotations

from typing import Any

from bench.pyboy.comparator import CompareResult


def format_trace(value: Any) -> str:
    if hasattr(value, "registers_after"):
        registers = value.registers_after
        return (
            f"seq={getattr(value, 'seq', '?')} "
            f"pc_before=0x{int(getattr(value, 'pc_before', 0)):04X} "
            f"opcode={_format_optional_hex(getattr(value, 'opcode', None), width=2)} "
            f"a=0x{int(registers.a):02X} f=0x{int(registers.f):02X} "
            f"sp=0x{int(registers.sp):04X} pc=0x{int(registers.pc):04X}"
        )
    if hasattr(value, "bus_read_data"):
        return (
            f"seq={int(getattr(value, 'seq', 0))} "
            f"commit_seq={int(getattr(value, 'commit_seq', 0))} "
            f"pc=0x{int(getattr(value, 'pc', 0)):04X} "
            f"bus_req_kind={int(getattr(value, 'bus_req_kind', 0))} "
            f"bus_read_data=0x{int(getattr(value, 'bus_read_data')):02X} "
            f"irq_pending=0x{int(getattr(value, 'irq_pending')):02X} "
            f"cpu_arch_time_enable={bool(getattr(value, 'cpu_arch_time_enable'))} "
            f"freeze_arch_time={bool(getattr(value, 'freeze_arch_time'))} "
            f"cpu_hold_only={bool(getattr(value, 'cpu_hold_only'))}"
        )
    return repr(value)


def format_compare_result(result: CompareResult, *, dut_trace: Any, oracle_state: Any) -> str:
    lines = [
        f"DUT:    {format_trace(dut_trace)}",
        f"Oracle: {format_trace(oracle_state)}",
    ]
    if result.matched:
        lines.append("DIFF:   no differences")
        return "\n".join(lines)
    lines.append("DIFF:")
    for diff in result.diffs:
        lines.append(f"  - {diff.detail}")
    return "\n".join(lines)


def _format_optional_hex(value: Any, *, width: int) -> str:
    if value is None:
        return "None"
    return f"0x{int(value):0{width}X}"
