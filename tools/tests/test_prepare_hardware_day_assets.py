from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


class PrepareHardwareDayAssetsTest(unittest.TestCase):
    def test_prepare_hardware_day_wrapper_is_checked_in(self) -> None:
        script_text = (TOOLS / "prepare_hardware_day.sh").read_text(encoding="utf-8")

        self.assertIn("usage: tools/prepare_hardware_day.sh [options]", script_text)
        self.assertIn('BUILD_SCRIPT="${ICEBOY_ROOT}/tools/build_icebreaker_variant.sh"', script_text)
        self.assertIn('--out-dir "${ICEBOY_ROOT}/build/bitstreams"', script_text)
        self.assertIn('--synth-dir "${ICEBOY_ROOT}/build/bitstreams/synth_${artifact_stem}"', script_text)
        self.assertIn('"lcd_test_pattern"', script_text)
        self.assertIn('"alu_loop_icebreaker"', script_text)
        self.assertIn('"bg_static_icebreaker"', script_text)
        self.assertIn('"joypad_smoke_icebreaker"', script_text)
        self.assertIn('"uart_rom_icebreaker"', script_text)
        self.assertIn('--nextpnr-report-name "${artifact_stem}.nextpnr-report.json"', script_text)
        self.assertIn('--nextpnr-log-name "${artifact_stem}.nextpnr.log"', script_text)
        self.assertIn('--rom-image "bg_static"', script_text)
        self.assertIn('--rom-image "joypad_bg_smoke"', script_text)
        self.assertIn('--skip-build', script_text)
