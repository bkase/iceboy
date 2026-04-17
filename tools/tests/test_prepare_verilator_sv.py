from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

import sys

sys.path.insert(0, str(ROOT / "tools"))

from prepare_verilator_sv import (
    append_missing_button_bank_aliases,
    build_verilator_source,
    sanitize_verilator_source,
    write_sanitized_verilog,
)


class PrepareVerilatorSvTest(unittest.TestCase):
    def test_rewrites_long_repeated_concat_assignments(self) -> None:
        repeated = ", ".join(["foo"] * 8192)
        text = f"assign bar = {{{repeated}}};\n"
        sanitized, rewritten = sanitize_verilator_source(text)
        self.assertEqual(rewritten, 1)
        self.assertEqual(sanitized, "assign bar = {8192{foo}};\n")

    def test_leaves_short_or_non_uniform_concat_lines_unchanged(self) -> None:
        short = "assign bar = {foo, foo, foo};\n"
        mixed = "assign baz = {" + ", ".join(["foo", "bar"] * 5000) + "};\n"
        sanitized, rewritten = sanitize_verilator_source(short + mixed)
        self.assertEqual(rewritten, 0)
        self.assertEqual(sanitized, short + mixed)

    def test_build_verilator_source_appends_swim_verilog_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            src = root / "build" / "spade.sv"
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text("module top;\nendmodule\n", encoding="utf-8")
            extra = root / "test" / "harness" / "verilog" / "extra.v"
            extra.parent.mkdir(parents=True, exist_ok=True)
            extra.write_text("module extra;\nendmodule\n", encoding="utf-8")
            (root / "swim.toml").write_text(
                '[verilog]\n'
                'sources = ["test/harness/verilog/extra.v"]\n',
                encoding="utf-8",
            )

            combined = build_verilator_source(src, root)

        self.assertIn("module top;", combined)
        self.assertIn("module extra;", combined)
        self.assertIn("begin included verilog", combined)

    def test_write_sanitized_verilog_appends_extra_sources_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            src = root / "build" / "spade.sv"
            dst = root / "build" / "spade.verilator.sv"
            src.parent.mkdir(parents=True, exist_ok=True)
            repeated = ", ".join(["foo"] * 8192)
            src.write_text(f"assign bar = {{{repeated}}};\n", encoding="utf-8")
            extra = root / "test" / "harness" / "verilog" / "extra.v"
            extra.parent.mkdir(parents=True, exist_ok=True)
            extra.write_text("module extra;\nendmodule\n", encoding="utf-8")
            (root / "swim.toml").write_text(
                '[verilog]\n'
                'sources = ["test/harness/verilog/extra.v"]\n',
                encoding="utf-8",
            )

            rewritten = write_sanitized_verilog(src, dst, root=root)
            output = dst.read_text(encoding="utf-8")

        self.assertEqual(rewritten, 1)
        self.assertIn("{8192{foo}}", output)
        self.assertIn("module extra;", output)

    def test_appends_missing_button_bank_aliases_for_generated_module_ids(self) -> None:
        base = (
            "module button_bank_raw_impl;\nendmodule\n\n"
            "module \\iceboy::periph::button_bank::button_bank_raw[3253];\nendmodule\n\n"
            "\\iceboy::periph::button_bank::button_bank_raw[3254] alias_inst();\n"
        )

        rewritten, added = append_missing_button_bank_aliases(base)

        self.assertEqual(added, 1)
        self.assertIn("module \\iceboy::periph::button_bank::button_bank_raw[3254]", rewritten)
        self.assertEqual(rewritten.count("button_bank_raw[3254]"), 2)


if __name__ == "__main__":
    unittest.main()
