from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


class ProgramIcebreakerAssetsTest(unittest.TestCase):
    def test_program_script_and_variant_wrapper_are_checked_in(self) -> None:
        common_text = (TOOLS / "entrypoint_common.sh").read_text(encoding="utf-8")
        script_text = (TOOLS / "program_icebreaker.sh").read_text(encoding="utf-8")
        build_variant_text = (TOOLS / "build_icebreaker_variant.sh").read_text(encoding="utf-8")

        self.assertIn('iceboy_resolve_command "ICEBOY_ICEPROG_BIN"', common_text)
        self.assertIn("usage: tools/program_icebreaker.sh [options]", script_text)
        self.assertIn('ICEBOY_ICEPROG_BIN', script_text)
        self.assertIn('--check-device', script_text)
        self.assertIn('resolve_latest_bitstream', script_text)
        self.assertIn('build/bitstreams/*.bin', script_text)
        self.assertIn('iceprog could not find or talk to an attached iCEBreaker', script_text)
        self.assertIn('"${ICEPROG_BIN}" -t', script_text)
        self.assertIn('"${ICEPROG_BIN}" "${BIN_FILE}"', script_text)
        self.assertIn('PROGRAM_SCRIPT="${ICEBOY_ROOT}/tools/program_icebreaker.sh"', build_variant_text)
        self.assertIn('--program', build_variant_text)
