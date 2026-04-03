from __future__ import annotations

import json
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TRACKER_PATH = ROOT / "test" / "harness" / "coverage_tracker.py"


def _load_tracker_module():
    spec = importlib.util.spec_from_file_location("iceboy_coverage_tracker", TRACKER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load coverage tracker module from {TRACKER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


coverage_tracker = _load_tracker_module()
build_coverage_snapshot = coverage_tracker.build_coverage_snapshot
report_lines = coverage_tracker.report_lines
opcode_family_counts = coverage_tracker.opcode_family_counts
opcode_family_count_lines = coverage_tracker.opcode_family_count_lines
write_coverage_snapshot = coverage_tracker.write_coverage_snapshot


class CoverageTrackerTest(unittest.TestCase):
    def test_snapshot_aggregates_known_suite_dimensions(self) -> None:
        snapshot = build_coverage_snapshot(
            [
                "test_sm83_opcodes.py",
                "test_event_script_determinism.py",
                "test_reset_profile.py",
                "test_cpu_lockstep.py",
                "test_interrupt_injection.py",
            ]
        )
        opcode_dimension = snapshot.dimensions["opcode_families"]
        self.assertGreater(opcode_dimension.covered_count, 0)
        self.assertEqual(opcode_dimension.covered_count, opcode_dimension.total_count)
        self.assertIn("joypad", snapshot.dimensions["interrupt_causes"].covered)
        self.assertIn("vblank", snapshot.dimensions["interrupt_causes"].covered)
        self.assertIn("ALU_LOOP", snapshot.dimensions["rom_suites"].covered)
        self.assertIn("DMG/SkipBoot/DmgConservative", snapshot.dimensions["profile_triples"].covered)

    def test_report_lines_surface_gaps(self) -> None:
        snapshot = build_coverage_snapshot(["test_reset_profile.py"])
        lines = report_lines(snapshot)
        self.assertIn("Phase/continuation constructors", lines[1])
        self.assertTrue(any("gaps:" in line for line in lines))
        self.assertTrue(any("Opcode families" in line for line in lines))

    def test_write_snapshot_persists_json_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "coverage.json"
            snapshot = write_coverage_snapshot(["test_cpu_lockstep.py"], destination=destination)
            payload = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(payload["generated_at"], snapshot.generated_at)
            self.assertEqual(payload["passed_suites"], ["test_cpu_lockstep.py"])
            self.assertIn("dimensions", payload)

    def test_opcode_family_counts_cover_milestone_b_gate_suites(self) -> None:
        suites = ["test_alu.py", "test_decode.py", "test_decode_cb.py", "test_cpu_single_op.py"]
        counts = opcode_family_counts(suites)
        self.assertTrue(all(count > 0 for count in counts.values()), counts)
        self.assertGreaterEqual(counts["bitops"], 3)
        self.assertEqual(opcode_family_count_lines(suites)[0], "alu16: 3 suite(s)")


if __name__ == "__main__":
    unittest.main()
