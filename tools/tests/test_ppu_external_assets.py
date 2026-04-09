from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "bench" / "manifests" / "ppu_external_suites.yaml"
SUITE_OWNED_README = ROOT / "bench" / "expected" / "suite_owned" / "README.md"
HUMAN_REVIEWED_README = ROOT / "bench" / "expected" / "human_reviewed" / "README.md"
MOONEYE_README = ROOT / "bench" / "external" / "mooneye-test-suite" / "README.md"
MOONEYE_PPU_ROOT = ROOT / "bench" / "external" / "mooneye-test-suite" / "acceptance" / "ppu"
MEALYBUG_README = ROOT / "bench" / "external" / "mealybug-tearoom-tests" / "README.md"
MEALYBUG_PPU_ROOT = ROOT / "bench" / "external" / "mealybug-tearoom-tests" / "ppu"
DMG_ACID2_ROM = ROOT / "bench" / "external" / "dmg-acid2" / "dmg-acid2.gb"


class PpuExternalAssetsTest(unittest.TestCase):
    maxDiff = None

    def load_manifest(self) -> dict:
        return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_manifest_pins_expected_external_suites(self) -> None:
        manifest = self.load_manifest()
        self.assertEqual(manifest["schema_version"], 1)
        suites = {entry["id"]: entry for entry in manifest["suites"]}
        self.assertEqual(
            set(suites),
            {"mooneye-test-suite", "mealybug-tearoom-tests", "dmg-acid2", "cgb-acid2"},
        )

        mooneye = suites["mooneye-test-suite"]
        self.assertEqual(
            mooneye["suite_classes"],
            {
                "acceptance": "acceptance/ppu",
                "emulator-only": "emulator-only",
                "manual-only": "manual-only",
                "misc": "misc/ppu",
            },
        )

        for suite in suites.values():
            self.assertRegex(suite["source_rev"], r"^[0-9a-f]{40}$")
            self.assertEqual(suite["license"], "MIT")

        self.assertEqual(suites["cgb-acid2"]["status"], "deferred")

    def test_suite_owned_artifacts_exist_with_declared_counts(self) -> None:
        manifest = self.load_manifest()
        suites = {entry["id"]: entry for entry in manifest["suites"]}

        mealybug_dir = ROOT / suites["mealybug-tearoom-tests"]["local_expected"]["path"]
        self.assertTrue(mealybug_dir.is_dir())
        screenshots = sorted(path.name for path in mealybug_dir.glob("*.png"))
        self.assertEqual(len(screenshots), 24)
        self.assertIn("m2_win_en_toggle.png", screenshots)
        self.assertIn("m3_window_timing.png", screenshots)
        self.assertEqual(
            suites["mealybug-tearoom-tests"]["local_expected"]["image_normalization"]["shades"],
            [0x00, 0x55, 0xAA, 0xFF],
        )

        acid2_path = ROOT / suites["dmg-acid2"]["local_expected"]["path"]
        self.assertTrue(acid2_path.is_file())
        self.assertEqual(
            suites["dmg-acid2"]["local_expected"]["image_normalization"]["shades"],
            [0x00, 0x55, 0xAA, 0xFF],
        )

    def test_expected_roots_are_documented(self) -> None:
        self.assertIn("ppu_external_suites.yaml", SUITE_OWNED_README.read_text(encoding="utf-8"))
        self.assertIn("No human-reviewed PPU artifacts are pinned yet", HUMAN_REVIEWED_README.read_text(encoding="utf-8"))

    def test_mooneye_wave_a_acceptance_subset_is_vendored_offline(self) -> None:
        self.assertIn("443f6e1f2a8d83ad9da051cbb960311c5aaaea66", MOONEYE_README.read_text(encoding="utf-8"))
        expected = {
            "vblank_stat_intr-GS.gb",
            "stat_lyc_onoff.gb",
            "stat_irq_blocking.gb",
            "lcdon_timing-GS.gb",
            "lcdon_write_timing-GS.gb",
        }
        self.assertEqual({path.name for path in MOONEYE_PPU_ROOT.glob("*.gb")}, expected)

    def test_mealybug_wave_b_canary_subset_is_vendored_offline(self) -> None:
        self.assertIn("70e88fb90b59d19dfbb9c3ac36c64105202bb1f4", MEALYBUG_README.read_text(encoding="utf-8"))
        expected = {
            "m2_win_en_toggle.gb",
            "m3_bgp_change.gb",
            "m3_scx_high_5_bits.gb",
            "m3_scx_low_3_bits.gb",
            "m3_window_timing.gb",
        }
        self.assertEqual({path.name for path in MEALYBUG_PPU_ROOT.glob("*.gb")}, expected)

    def test_dmg_acid2_rom_is_vendored_offline(self) -> None:
        self.assertTrue(DMG_ACID2_ROM.is_file())
        self.assertGreater(DMG_ACID2_ROM.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
