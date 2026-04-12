from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


class IcebreakerAluLoopVerilatorAssetsTest(unittest.TestCase):
    def test_native_runner_assets_exist_and_reference_board_top(self) -> None:
        wrapper = ROOT / "test" / "harness" / "verilog" / "icebreaker_alu_loop_top_verilator_wrapper.sv"
        main_cpp = TOOLS / "verilator" / "icebreaker_alu_loop_main.cpp"
        runner = TOOLS / "run_icebreaker_alu_loop_verilator.sh"
        export_tool = TOOLS / "export_alu_loop_oracle.py"
        reference = ROOT / "bench" / "ref" / "alu_loop.py"

        self.assertTrue(wrapper.is_file())
        self.assertTrue(main_cpp.is_file())
        self.assertTrue(runner.is_file())
        self.assertTrue(export_tool.is_file())
        self.assertTrue(reference.is_file())

        wrapper_text = wrapper.read_text(encoding="utf-8")
        self.assertIn("module icebreaker_alu_loop_top_verilator_wrapper", wrapper_text)
        self.assertIn("icebreaker_alu_loop_top impl", wrapper_text)
        self.assertIn("cpu_core_0.output__", wrapper_text)
        self.assertIn("wire rst = 1'b0;", wrapper_text)

        main_text = main_cpp.read_text(encoding="utf-8")
        self.assertIn("--expected-trace=", main_text)
        self.assertIn("board top did not begin committing before reset timeout", main_text)
        self.assertIn("matched ", main_text)
        self.assertIn("return 2;", main_text)

        runner_text = runner.read_text(encoding="utf-8")
        self.assertIn("tools/export_alu_loop_oracle.py", runner_text)
        self.assertIn("icebreaker_alu_loop_top_verilator_wrapper", runner_text)
        self.assertIn("--expected-trace=${EXPECTED_TRACE}", runner_text)
        self.assertIn("ICEBOY_ALU_LOOP_MAX_MCYCLES", runner_text)

        export_text = export_tool.read_text(encoding="utf-8")
        self.assertIn('default="ALU_LOOP"', export_text)
        self.assertIn("write_expected_trace", export_text)
        self.assertIn("ExpectedCheckpoint", export_text)

        reference_text = reference.read_text(encoding="utf-8")
        self.assertIn("expected_checkpoints()", reference_text)
        self.assertIn("__checkpoint_loop_body|__checkpoint_loop_body.loop", reference_text)


if __name__ == "__main__":
    unittest.main()
