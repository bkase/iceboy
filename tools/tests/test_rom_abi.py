from __future__ import annotations

import unittest
from pathlib import Path

from bench.tools.validate_rom_abi import (
    TEMPLATE_ASM_PATH,
    TEMPLATE_SYM_PATH,
    parse_sym,
    validate_asm_text,
    validate_sym_text,
)


ROOT = Path(__file__).resolve().parents[2]
ROM_ABI_DOC_PATH = ROOT / "spec" / "rom_abi.md"


class RomAbiValidationTest(unittest.TestCase):
    def test_template_fixture_validates(self) -> None:
        validate_sym_text(TEMPLATE_SYM_PATH.read_text(encoding="utf-8"))
        validate_asm_text(TEMPLATE_ASM_PATH.read_text(encoding="utf-8"))

    def test_template_sym_has_required_reserved_labels(self) -> None:
        symbols = parse_sym(TEMPLATE_SYM_PATH.read_text(encoding="utf-8"))
        self.assertIn("__pass", symbols)
        self.assertIn("__fail", symbols)
        self.assertIn("__checkpoint_boot", symbols)
        self.assertIn("__commit_setup", symbols)
        self.assertIn("__inject_begin_buttons", symbols)
        self.assertIn("__inject_end_buttons", symbols)

    def test_document_records_fixed_signature_layout(self) -> None:
        doc = ROM_ABI_DOC_PATH.read_text(encoding="utf-8")
        self.assertIn("0xC000-0xC01F", doc)
        self.assertIn("`__pass`", doc)
        self.assertIn("`__fail`", doc)
        self.assertIn("RGBDS-compatible `.sym`", doc)


if __name__ == "__main__":
    unittest.main()
