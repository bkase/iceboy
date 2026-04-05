from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

import sys

sys.path.insert(0, str(ROOT / "tools"))

from prepare_verilator_sv import sanitize_verilator_source


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


if __name__ == "__main__":
    unittest.main()
