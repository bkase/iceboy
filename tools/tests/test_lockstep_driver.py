from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass

from bench.pyboy.lockstep_driver import run_lockstep
from bench.pyboy.oracle import BusRequest, BusResponse, OracleCommit, RegisterState
from spec.compare_scopes import CompareField, OracleMode
from test.harness.dut_driver import CpuCommitTrace


@dataclass(frozen=True)
class EmptyScript:
    def events_for_commit(self, commit_index: int) -> tuple[object, ...]:
        return ()


class FakeDutDriver:
    def __init__(self, bus_read_data: int) -> None:
        self._seq = 0
        self.bus_read_data = bus_read_data

    async def step_mcycle(self, *, stimulus, bus_read_data: int, irq_pending: int) -> CpuCommitTrace:
        self._seq += 1
        return CpuCommitTrace(
            seq=self._seq,
            bus_read_data=bus_read_data if bus_read_data is not None else self.bus_read_data,
            irq_pending=irq_pending,
            cpu_arch_time_enable=not stimulus.freeze_arch_time and not stimulus.cpu_hold_only,
            freeze_arch_time=stimulus.freeze_arch_time,
            cpu_hold_only=stimulus.cpu_hold_only,
        )


class FakeOracle:
    def __init__(self, commits: list[OracleCommit]) -> None:
        self._commits = list(commits)
        self.written_events: list[object] = []

    def write_event(self, event: object) -> None:
        self.written_events.append(event)

    def step_commit(self) -> OracleCommit:
        return self._commits.pop(0)


def make_oracle_commit(*, seq: int, bus_data: int) -> OracleCommit:
    return OracleCommit(
        schema_version=1,
        kind="Checkpoint",
        seq=seq,
        label=f"hook_{seq:04d}",
        pc_before=0x0150 + seq,
        opcode=0x00,
        registers_after=RegisterState(a=0, f=0, b=0, c=0, d=0, e=0, hl=0, sp=0xFFFE, pc=0x0150 + seq + 1),
        phase_after="HookCheckpoint",
        bus_request=BusRequest(),
        bus_response=BusResponse(kind="data", data=bus_data),
    )


class LockstepDriverTest(unittest.TestCase):
    def test_run_lockstep_returns_match_for_current_bus_surface(self) -> None:
        oracle = FakeOracle([make_oracle_commit(seq=1, bus_data=0xA5), make_oracle_commit(seq=2, bus_data=0xA5)])
        dut = FakeDutDriver(bus_read_data=0xA5)
        result = asyncio.run(
            run_lockstep(
                oracle,
                dut,
                EmptyScript(),
                OracleMode.MCycleCommit,
                commit_limit=2,
                compare_fields=(CompareField.BusResponse,),
                bus_read_data=0xA5,
            )
        )
        self.assertTrue(result.matched)
        self.assertEqual(len(result.steps), 2)

    def test_run_lockstep_stops_on_first_mismatch_and_formats_report(self) -> None:
        oracle = FakeOracle([make_oracle_commit(seq=1, bus_data=0xA5)])
        dut = FakeDutDriver(bus_read_data=0x3C)
        result = asyncio.run(
            run_lockstep(
                oracle,
                dut,
                EmptyScript(),
                OracleMode.MCycleCommit,
                commit_limit=1,
                compare_fields=(CompareField.BusResponse,),
                bus_read_data=0x3C,
            )
        )
        self.assertFalse(result.matched)
        self.assertIsNotNone(result.mismatch)
        self.assertIn("bus_resp", result.mismatch_report or "")


if __name__ == "__main__":
    unittest.main()
