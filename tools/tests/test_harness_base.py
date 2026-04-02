from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "test" / "harness"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assertions import assert_commit_trace_match, assert_registers_match, format_register_diff
from dut_driver import CpuCommitTrace, JoypadState, SimStimulus, SoCLockstepObservation, encode_profiles
from fixtures import event_script, rom_loader
from spec.profiles import CPU_BRING_UP_PROFILES


@dataclass(frozen=True)
class Registers:
    a: int
    f: int


class HarnessBaseTest(unittest.TestCase):
    def test_sim_stimulus_encoding_matches_low_level_contract(self) -> None:
        stimulus = SimStimulus(
            joyp_buttons=JoypadState(a=True, start=True),
            if_set_bits=0x12,
            if_clear_bits=0x03,
            ie_override=0x1B,
            dma_start=0x80,
            serial_inject=0x55,
            freeze_arch_time=True,
            cpu_hold_only=False,
        )
        encoded = stimulus.encode()
        self.assertEqual(encoded & 0b11, 0b10)
        self.assertEqual((encoded >> 31) & 0x1F, 0x12)
        self.assertEqual((encoded >> 26) & 0x1F, 0x03)
        self.assertEqual((encoded >> 20) & 0x3F, 0x3B)
        self.assertEqual((encoded >> 11) & 0x1FF, 0x180)
        self.assertEqual((encoded >> 2) & 0x1FF, 0x155)

    def test_cpu_and_soc_output_decoders_are_stable(self) -> None:
        cpu = CpuCommitTrace.from_output(
            (0x12 << 58)
            | (0x1234 << 42)
            | (0x2 << 40)
            | (0x4567 << 24)
            | (0x89 << 16)
            | (0xA5 << 8)
            | (0x12 << 3)
            | 0b100,
            seq=7,
        )
        self.assertEqual(cpu.seq, 7)
        self.assertEqual(cpu.commit_seq, 0x12)
        self.assertEqual(cpu.pc, 0x1234)
        self.assertEqual(cpu.bus_req_kind, 0x2)
        self.assertEqual(cpu.bus_req_addr, 0x4567)
        self.assertEqual(cpu.bus_req_data, 0x89)
        self.assertEqual(cpu.bus_read_data, 0xA5)
        self.assertEqual(cpu.irq_pending, 0x12)
        self.assertTrue(cpu.cpu_arch_time_enable)
        self.assertFalse(cpu.freeze_arch_time)
        self.assertFalse(cpu.cpu_hold_only)

        soc = SoCLockstepObservation.from_output(
            (0x12 << 135)
            | (0x3456 << 119)
            | (0x2 << 117)
            | (0x789A << 101)
            | (0xBC << 93)
            | (0x11223344 << 61)
            | (0x1 << 59)
            | (0x1234567 << 29)
            | (0x1 << 28)
            | (0x3 << 24)
            | (0x2 << 22)
            | (0x1 << 21)
            | (1 << 19)
            | (0 << 17)
            | (1 << 15)
            | (1 << 14)
            | (0 << 13)
            | (0x07 << 8)
            | 0x44
        )
        self.assertEqual(soc.commit_seq, 0x12)
        self.assertEqual(soc.pc, 0x3456)
        self.assertEqual(soc.bus_req_kind, 0x2)
        self.assertEqual(soc.bus_req_addr, 0x789A)
        self.assertEqual(soc.bus_req_data, 0xBC)
        self.assertEqual(soc.sys_counter, 0x11223344)
        self.assertEqual(soc.t_index, 0x1)
        self.assertEqual(soc.m_index, 0x1234567)
        self.assertTrue(soc.m_ce)
        self.assertEqual(soc.bus_region, 0x3)
        self.assertEqual(soc.bus_owner, 0x2)
        self.assertTrue(soc.bus_blocked)
        self.assertEqual(soc.model_profile, 1)
        self.assertEqual(soc.memory_behavior_profile, 1)
        self.assertTrue(soc.cpu_arch_time_enable)
        self.assertEqual(soc.irq_pending, 0x07)
        self.assertEqual(soc.bus_read_data, 0x44)

    def test_assertion_helpers_report_mismatches(self) -> None:
        self.assertEqual(format_register_diff(Registers(a=1, f=2), Registers(a=1, f=2)), "no register differences")
        with self.assertRaisesRegex(AssertionError, "flags"):
            assert_commit_trace_match(
                CpuCommitTrace(seq=1, bus_read_data=1, irq_pending=0, cpu_arch_time_enable=True, freeze_arch_time=False, cpu_hold_only=False),
                CpuCommitTrace(seq=1, bus_read_data=2, irq_pending=0, cpu_arch_time_enable=True, freeze_arch_time=False, cpu_hold_only=False),
                "flags",
            )
        with self.assertRaisesRegex(AssertionError, "register mismatch"):
            assert_registers_match(Registers(a=1, f=2), Registers(a=1, f=3), "cpu")

    def test_fixture_helpers_resolve_profiles_and_event_scripts(self) -> None:
        entry = {
            "id": "JOY_DIVERGE_PERSIST",
            "path": "bench/roms/out/JOY_DIVERGE_PERSIST.gb",
            **CPU_BRING_UP_PROFILES.as_manifest_fields(),
            "timeout_commits": 32,
            "action_gen": {"name": "striped", "seed": 3},
        }
        loaded = rom_loader(entry, repo_root=ROOT)
        self.assertEqual(loaded.rom_id, "JOY_DIVERGE_PERSIST")
        self.assertTrue(str(loaded.rom_path).endswith("JOY_DIVERGE_PERSIST.gb"))
        self.assertEqual(encode_profiles(loaded.profiles), 0)

        script_a = event_script(11, entry)
        script_b = event_script(11, entry)
        self.assertEqual(script_a.events, script_b.events)
        self.assertEqual(script_a.seed, 11)


if __name__ == "__main__":
    unittest.main()
