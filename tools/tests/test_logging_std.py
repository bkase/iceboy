from __future__ import annotations

import argparse
import io
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
from test.harness.logging_std import FailureArtifacts, TestLogger, add_logging_args, logger_from_args


class LoggingStdTest(unittest.TestCase):
    def test_normal_output_is_hierarchical(self) -> None:
        stream = io.StringIO()
        logger = TestLogger(suite_name="test_alu.py", stream=stream, color=False)
        logger.suite()
        case_logger = logger.bind_case("test_add8_basic")
        case_logger.step("Initialize DUT with A=0x0F, B=0x01")
        case_logger.check("Result", expected="0x10", actual="0x10")
        case_logger.pass_case(0.003)
        logger.summary(passed=1, failed=0, duration_s=0.01)

        text = stream.getvalue()
        self.assertIn("[SUITE] test_alu.py", text)
        self.assertIn("[CASE] test_add8_basic", text)
        self.assertIn("[STEP] Initialize DUT with A=0x0F, B=0x01", text)
        self.assertIn("[CHECK] Result: expected=0x10 actual=0x10 OK", text)
        self.assertIn("[PASS] test_add8_basic (0.003s)", text)
        self.assertIn("[SUMMARY] test_alu.py: 1/1 passed, 0 failed (0.01s)", text)

    def test_quiet_mode_keeps_failures_and_summary(self) -> None:
        stream = io.StringIO()
        logger = TestLogger(suite_name="test_alu.py", stream=stream, level="QUIET", color=False)
        case_logger = logger.bind_case("test_add8_overflow")
        case_logger.step("hidden step")
        case_logger.check("Z flag", expected=1, actual=0)
        case_logger.fail_case(
            "Z flag mismatch",
            contexts={"Opcode": "ADD A,B (0x80)", "Inputs": "A=0xFF B=0x01"},
        )
        logger.summary(passed=0, failed=1, duration_s=0.15)

        text = stream.getvalue()
        self.assertNotIn("hidden step", text)
        self.assertIn("[CHECK] Z flag: expected=1 actual=0 FAIL", text)
        self.assertIn("[FAIL] test_add8_overflow -- Z flag mismatch", text)
        self.assertIn("[CONTEXT] Opcode: ADD A,B (0x80)", text)
        self.assertIn("[SUMMARY] test_alu.py: 0/1 passed, 1 failed (0.15s)", text)

    def test_json_output_is_machine_parseable(self) -> None:
        stream = io.StringIO()
        logger = TestLogger(
            suite_name="test_alu.py",
            case_name="test_add8_basic",
            stream=stream,
            json_mode=True,
        )
        logger.step("Execute ADD A,B")
        logger.check("H flag", expected=1, actual=1)

        events = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual(events[0]["event"], "step")
        self.assertEqual(events[0]["suite"], "test_alu.py")
        self.assertEqual(events[0]["case"], "test_add8_basic")
        self.assertEqual(events[1]["event"], "check")
        self.assertIn("expected=1 actual=1 OK", events[1]["message"])

    def test_failure_artifacts_and_parser_flags(self) -> None:
        parser = add_logging_args(argparse.ArgumentParser(add_help=False))
        args = parser.parse_args(["--log-level", "TRACE", "--json"])
        stream = io.StringIO()
        logger = logger_from_args(args, suite_name="test_alu.py", case_name="test_fail", stream=stream)
        logger.fail_case(
            "register mismatch",
            artifacts=FailureArtifacts(
                divergent_field="flags.z",
                waveform_path="build/test_fail/dump.vcd",
                replay_capsule="build/test_fail/replay.json",
            ),
        )

        events = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual(args.log_level, "TRACE")
        self.assertTrue(args.json)
        self.assertEqual(events[0]["event"], "fail")
        self.assertEqual(events[1]["message"], "divergent_field: flags.z")
        self.assertEqual(events[2]["message"], "waveform_path: build/test_fail/dump.vcd")
        self.assertEqual(events[3]["message"], "replay_capsule: build/test_fail/replay.json")


if __name__ == "__main__":
    unittest.main()
