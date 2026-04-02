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
    coverage_lines,
    parse_requested_tiers,
    parse_suite_counts,
    selected_tiers,
    write_junit_xml,
)


class RunTestsTest(unittest.TestCase):
    def test_quick_mode_selects_meta_and_unit(self) -> None:
        args = build_parser().parse_args(["--quick"])
        tiers = parse_requested_tiers(args)
        self.assertEqual(tiers, ["meta", "unit"])
        self.assertEqual([tier.key for tier in selected_tiers(tiers)], ["meta", "unit"])

    def test_parse_suite_counts_for_python_and_swim(self) -> None:
        python_output = "Ran 3 tests in 0.001s\n\nOK\n"
        swim_output = "ok  test/test_main.py 0/2 failed\n"
        self.assertEqual(
            parse_suite_counts(SuiteDefinition("meta", "py", "python", "mod"), python_output, 0),
            (3, 0),
        )
        self.assertEqual(
            parse_suite_counts(SuiteDefinition("unit", "swim", "swim", "test_main"), swim_output, 0),
            (2, 0),
        )

    def test_coverage_lines_report_implemented_tiers(self) -> None:
        lines = coverage_lines(selected_tiers(["meta", "unit", "formal"]), nightly=False)
        self.assertEqual(lines[0], "Implemented tiers: 2/3")
        self.assertIn("Meta/Infrastructure: 11 suite(s)", lines)
        self.assertIn("Unit Tests: 9 suite(s)", lines)
        self.assertIn("Formal Verification: 0 suite(s)", lines)

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
