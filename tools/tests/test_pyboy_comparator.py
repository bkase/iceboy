from __future__ import annotations

import unittest

from bench.pyboy.comparator import CompareField, compare_commit
from bench.pyboy.oracle import BusRequest, BusResponse, OracleCommit, RegisterState
from bench.pyboy.trace_formatter import format_compare_result, format_trace
from test.harness.dut_driver import CpuCommitTrace


def oracle_commit(*, bus_data: int) -> OracleCommit:
    return OracleCommit(
        schema_version=1,
        kind="Checkpoint",
        seq=1,
        label="hook_0150",
        pc_before=0x0150,
        opcode=0x3E,
        registers_after=RegisterState(a=0x42, f=0x80, b=0, c=0, d=0, e=0, hl=0xC000, sp=0xFFFE, pc=0x0152),
        phase_after="HookCheckpoint",
        bus_request=BusRequest(),
        bus_response=BusResponse(kind="data", data=bus_data),
    )


class ComparatorTest(unittest.TestCase):
    def test_bus_response_scope_matches_current_overlap_surface(self) -> None:
        dut = CpuCommitTrace(
            seq=1,
            bus_read_data=0xA5,
            irq_pending=0,
            cpu_arch_time_enable=True,
            freeze_arch_time=False,
            cpu_hold_only=False,
        )
        result = compare_commit(dut, oracle_commit(bus_data=0xA5), (CompareField.BusResponse,))
        self.assertTrue(result.matched)
        self.assertFalse(result.diffs)

    def test_bus_response_scope_reports_first_divergence(self) -> None:
        dut = CpuCommitTrace(
            seq=1,
            bus_read_data=0x3C,
            irq_pending=0,
            cpu_arch_time_enable=True,
            freeze_arch_time=False,
            cpu_hold_only=False,
        )
        result = compare_commit(dut, oracle_commit(bus_data=0xA5), (CompareField.BusResponse,))
        self.assertFalse(result.matched)
        self.assertEqual(result.first_divergent_field, CompareField.BusResponse)
        self.assertIn("bus_resp", result.diffs[0].detail)

    def test_trace_formatter_emits_readable_side_by_side_output(self) -> None:
        dut = CpuCommitTrace(
            seq=2,
            bus_read_data=0x11,
            irq_pending=0x04,
            cpu_arch_time_enable=False,
            freeze_arch_time=True,
            cpu_hold_only=False,
        )
        oracle = oracle_commit(bus_data=0x22)
        result = compare_commit(dut, oracle, (CompareField.BusResponse,))
        report = format_compare_result(result, dut_trace=dut, oracle_state=oracle)
        self.assertIn("DUT:", report)
        self.assertIn("Oracle:", report)
        self.assertIn("bus_resp", report)
        self.assertIn("bus_read_data=0x11", format_trace(dut))


if __name__ == "__main__":
    unittest.main()
