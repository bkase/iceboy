from __future__ import annotations

import io
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from run_tests import (
    SuiteDefinition,
    SuiteResult,
    TIERS,
    build_parser,
    command_env,
    coverage_lines,
    include_nightly,
    load_tier_config,
    parse_requested_tiers,
    parse_suite_counts,
    requested_preset_names,
    selected_tiers,
    suites_for_tier,
    write_junit_xml,
)


class RunTestsTest(unittest.TestCase):
    def test_quick_mode_selects_meta_and_unit(self) -> None:
        args = build_parser().parse_args(["--quick"])
        tiers = parse_requested_tiers(args, load_tier_config())
        self.assertEqual(tiers, ["meta", "unit"])
        self.assertEqual([tier.key for tier in selected_tiers(tiers)], ["meta", "unit"])

    def test_named_presets_expand_and_nightly_preset_enables_nightly_suites(self) -> None:
        config = load_tier_config()
        smoke_args = build_parser().parse_args(["--tier", "smoke"])
        nightly_args = build_parser().parse_args(["--tier", "nightly"])
        self.assertEqual(requested_preset_names(smoke_args, config), ["smoke"])
        self.assertEqual(parse_requested_tiers(smoke_args, config), ["meta"])
        self.assertTrue(include_nightly(nightly_args, config))

    def test_parse_suite_counts_for_python_swim_and_shell(self) -> None:
        python_output = "Ran 3 tests in 0.001s\n\nOK\n"
        swim_output = "ok  test/test_main.py 0/2 failed\n"
        shell_output = "SBY PASS\n"
        self.assertEqual(
            parse_suite_counts(SuiteDefinition("meta", "py", "python", "mod"), python_output, 0),
            (3, 0),
        )
        self.assertEqual(
            parse_suite_counts(SuiteDefinition("unit", "swim", "swim", "test_main"), swim_output, 0),
            (2, 0),
        )
        self.assertEqual(
            parse_suite_counts(SuiteDefinition("formal", "cpu_invariants.sby", "shell", "tools/run_formal_cpu_invariants.sh"), shell_output, 0),
            (1, 0),
        )

    def test_coverage_lines_report_implemented_tiers(self) -> None:
        lines = coverage_lines(selected_tiers(["meta", "unit", "formal", "lockstep"]), nightly=False)
        self.assertEqual(lines[0], "Implemented tiers: 4/4")
        self.assertIn("Meta/Infrastructure: 31 suite(s)", lines)
        self.assertIn("Unit Tests: 47 suite(s)", lines)
        self.assertIn("Formal Verification: 6 suite(s)", lines)
        self.assertIn("Lockstep: 4 suite(s)", lines)

    def test_command_env_propagates_requested_simulator(self) -> None:
        env = command_env(sim="verilator")
        self.assertEqual(env["SIM"], "verilator")
        self.assertEqual(env["ICEBOY_SMOKE_SIM"], "verilator")
        self.assertNotIn("ICEBOY_NIGHTLY", env)

    def test_nightly_suite_selection_and_env_flag(self) -> None:
        unit_labels = [suite.label for suite in suites_for_tier("unit", nightly=False)]
        nightly_labels = [suite.label for suite in suites_for_tier("unit", nightly=True)]
        self.assertNotIn("test_alu_nightly.py", unit_labels)
        self.assertIn("test_alu_nightly.py", nightly_labels)

        env = command_env(sim="icarus", nightly=True)
        self.assertEqual(env["ICEBOY_NIGHTLY"], "1")

    def test_rom_tier_includes_wave_a_ppu_rom_and_mooneye_suites(self) -> None:
        rom_labels = [suite.label for suite in suites_for_tier("rom", nightly=False)]
        self.assertIn("test_ppu_wave_a.py", rom_labels)
        self.assertIn("test_ppu_wave_a_mooneye.py", rom_labels)
        self.assertIn("test_ppu_wave_b.py", rom_labels)
        mooneye_suite = next(suite for suite in suites_for_tier("rom", nightly=False) if suite.label == "test_ppu_wave_a_mooneye.py")
        self.assertEqual(mooneye_suite.runner, "shell")
        self.assertEqual(mooneye_suite.target, "tools/run_ppu_wave_a_mooneye_verilator.sh")

    def test_write_junit_xml_emits_parseable_report(self) -> None:
        results = [
            SuiteResult(
                definition=SuiteDefinition("meta", "test_logging_std.py", "python", "tools.tests.test_logging_std"),
                passed=4,
                failed=0,
                duration_s=0.1,
                exit_code=0,
                output="OK",
            ),
            SuiteResult(
                definition=SuiteDefinition("unit", "test_main.py", "swim", "test_main"),
                passed=2,
                failed=0,
                duration_s=0.2,
                exit_code=0,
                output="0/2 failed",
            ),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "junit.xml"
            write_junit_xml(results, target)
            root = ET.parse(target).getroot()
            self.assertEqual(root.tag, "testsuites")
            suites = root.findall("testsuite")
            self.assertEqual(len(suites), 2)
            self.assertEqual(suites[0].attrib["name"], TIERS[0].label)


if __name__ == "__main__":
    unittest.main()
