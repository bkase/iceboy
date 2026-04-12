from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


class PackIcebreakerBitstreamAssetsTest(unittest.TestCase):
    def test_pack_script_and_entrypoint_helpers_are_checked_in(self) -> None:
        common_text = (TOOLS / "entrypoint_common.sh").read_text(encoding="utf-8")
        script_text = (TOOLS / "pack_icebreaker_bitstream.sh").read_text(encoding="utf-8")
        build_variant_text = (TOOLS / "build_icebreaker_variant.sh").read_text(encoding="utf-8")

        self.assertIn('iceboy_resolve_command "ICEBOY_ICEPACK_BIN"', common_text)
        self.assertIn('iceboy_resolve_command "ICEBOY_ICETIME_BIN"', common_text)
        self.assertIn("usage: tools/pack_icebreaker_bitstream.sh --asc <path> --out <path>", script_text)
        self.assertIn('ICEBOY_ICEPACK_BIN', script_text)
        self.assertIn('ICEBOY_ICETIME_BIN', script_text)
        self.assertIn('--icetime', script_text)
        self.assertIn('Packed bitstream:', script_text)
        self.assertIn('"${ICEPACK_BIN}" "${ASC_FILE}" "${OUT_FILE}"', script_text)
        self.assertIn('"${ICETIME_BIN}" -d up5k -p "${PCF_FILE}" "${ASC_FILE}"', script_text)
        self.assertIn('PACK_SCRIPT="${ICEBOY_ROOT}/tools/pack_icebreaker_bitstream.sh"', build_variant_text)
        self.assertIn('--pack', build_variant_text)
