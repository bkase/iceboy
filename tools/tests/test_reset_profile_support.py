from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "test" / "harness"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reset_profile_support import DMG_SKIPBOOT_EXPECTED_STATE, capture_dut_reset_state, expected_reset_state_for
from spec.profiles import MemoryBehaviorProfile, ModelProfile, ResetProfile, SimulationProfiles


class ResetProfileSupportTest(unittest.TestCase):
    def test_dmg_skipboot_contract_matches_expected_post_boot_values(self) -> None:
        expected = expected_reset_state_for()
        self.assertEqual(expected, DMG_SKIPBOOT_EXPECTED_STATE)
        self.assertEqual((expected.a, expected.f), (0x01, 0xB0))
        self.assertEqual((expected.b, expected.c), (0x00, 0x13))
        self.assertEqual((expected.d, expected.e), (0x00, 0xD8))
        self.assertEqual((expected.h, expected.l), (0x01, 0x4D))
        self.assertEqual((expected.sp, expected.pc), (0xFFFE, 0x0100))
        self.assertEqual((expected.ie, expected.if_), (0x00, 0xE1))
        self.assertFalse(expected.ime_enabled)
        self.assertEqual((expected.tima, expected.tma, expected.tac), (0x00, 0x00, 0x00))
        self.assertEqual((expected.joyp, expected.lcdc, expected.stat), (0xCF, 0x91, 0x85))

    def test_only_dmg_skipboot_is_defined_in_the_scaffold(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "DMG \\+ SkipBoot"):
            expected_reset_state_for(
                SimulationProfiles(
                    model=ModelProfile.CGB,
                    reset=ResetProfile.SkipBoot,
                    memory_behavior=MemoryBehaviorProfile.DmgConservative,
                )
            )

    def test_dut_capture_surface_stays_explicitly_stubbed(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "cpu_test_top does not yet expose architectural reset state"):
            capture_dut_reset_state(object())


if __name__ == "__main__":
    unittest.main()
