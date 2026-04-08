from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
ROM_INVENTORY_PATH = ROOT / "bench" / "manifests" / "rom_inventory.yaml"
ROM_SCHEMA_PATH = ROOT / "bench" / "manifests" / "rom_schema.yaml"
SCHEMAS_DIR = ROOT / "bench" / "schemas"


class RomManifestSchemaTest(unittest.TestCase):
    def test_inventory_declares_shared_artifact_schemas(self) -> None:
        inventory = yaml.safe_load(ROM_INVENTORY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(inventory["schema_version"], 2)
        self.assertEqual(
            inventory["artifact_schemas"],
            {
                "replay_capsule": "bench/schemas/replay_capsule.schema.json",
                "oracle_capture": "bench/schemas/oracle_capture.schema.json",
                "line_summary": "bench/schemas/line_summary.schema.json",
            },
        )

    def test_json_schema_artifacts_exist_and_pin_schema_version(self) -> None:
        for name in ("replay_capsule", "oracle_capture", "line_summary"):
            path = SCHEMAS_DIR / f"{name}.schema.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertEqual(payload["type"], "object")
            self.assertEqual(payload["properties"]["schema_version"]["const"], 1)

    def test_schema_lists_ppu_metadata_fields(self) -> None:
        schema = yaml.safe_load(ROM_SCHEMA_PATH.read_text(encoding="utf-8"))
        required = set(schema["inventory_contract"]["rom_entry_required"])
        for field_name in (
            "rom_sha256",
            "build_flavor",
            "memory_backend",
            "behavior_config",
            "rule_confidence",
            "allowed_uncertainty",
            "raster_event_coord_space",
            "expected_soc_revisions",
            "required_behavior_features",
            "forbidden_behavior_features",
        ):
            self.assertIn(field_name, required)

    def test_wave_a_ppu_timing_entries_use_frame_semantic_defaults(self) -> None:
        inventory = yaml.safe_load(ROM_INVENTORY_PATH.read_text(encoding="utf-8"))
        roms = {rom["id"]: rom for rom in inventory["roms"]}

        for rom_id in (
            "PPU_OFF_ON_BASIC",
            "LY_LYC_BASIC",
            "STAT_MODE_SEQ",
            "VBLANK_IRQ_BASIC",
            "VRAM_OAM_GATING",
        ):
            rom = roms[rom_id]
            self.assertEqual(rom["oracle_mode"], "frame_semantic")
            self.assertEqual(rom["compare_scope"]["domains"], ["frame_semantic"])
            self.assertEqual(rom["behavior_config"], {"model": "DMG", "soc_revision": None, "features": []})
            self.assertEqual(rom["raster_event_coord_space"], "frame_line_dot")
            self.assertRegex(rom["rom_sha256"], r"^[0-9a-f]{64}$")

    def test_wave_a_ppu_timing_entries_have_matching_rom_sources(self) -> None:
        inventory = yaml.safe_load(ROM_INVENTORY_PATH.read_text(encoding="utf-8"))
        roms = {rom["id"]: rom for rom in inventory["roms"]}

        for rom_id in (
            "PPU_OFF_ON_BASIC",
            "LY_LYC_BASIC",
            "STAT_MODE_SEQ",
            "VBLANK_IRQ_BASIC",
            "VRAM_OAM_GATING",
        ):
            rom_path = ROOT / roms[rom_id]["path"]
            self.assertEqual(rom_path.parent, ROOT / "bench" / "roms" / "out")
            asm_path = ROOT / "bench" / "roms" / f"{rom_id}.asm"
            self.assertTrue(asm_path.exists(), f"missing source for {rom_id}: {asm_path}")

    def test_wave_b_bg_window_entries_use_frame_hash_defaults(self) -> None:
        inventory = yaml.safe_load(ROM_INVENTORY_PATH.read_text(encoding="utf-8"))
        roms = {rom["id"]: rom for rom in inventory["roms"]}

        self.assertEqual(roms["PPU_STAT_IRQ"]["oracle_mode"], "frame_semantic")
        self.assertEqual(roms["PPU_STAT_IRQ"]["compare_scope"]["domains"], ["frame_semantic"])

        for rom_id in (
            "BG_STATIC",
            "BG_SCROLL_WRAP",
            "BG_SIGNED_ADDR",
            "WINDOW_BASIC",
            "WINDOW_LINE_COUNTER",
            "WINDOW_WX_WY_EDGE",
            "WINDOW_WX0_STUTTER",
            "WINDOW_WX166_NEXTLINE",
            "WINDOW_WX_RETRIGGER_GLITCH",
            "WINDOW_WINEN_TOGGLE_REARM",
            "PPU_SPRITES",
        ):
            rom = roms[rom_id]
            self.assertEqual(rom["oracle_mode"], "frame_hash")
            self.assertEqual(rom["compare_scope"]["domains"], ["frame_hash"])
            self.assertEqual(rom["raster_event_coord_space"], "frame_line_dot")

        self.assertEqual(roms["WINDOW_WX0_STUTTER"]["required_behavior_features"], ["Wx0Stutter"])
        self.assertEqual(roms["WINDOW_WX166_NEXTLINE"]["required_behavior_features"], ["Wx166NextLine"])
        self.assertEqual(
            roms["WINDOW_WX_RETRIGGER_GLITCH"]["required_behavior_features"],
            ["WindowRetriggerGlitch"],
        )

    def test_wave_b_entries_have_matching_rom_sources(self) -> None:
        inventory = yaml.safe_load(ROM_INVENTORY_PATH.read_text(encoding="utf-8"))
        roms = {rom["id"]: rom for rom in inventory["roms"]}

        for rom_id in (
            "BG_STATIC",
            "BG_SCROLL_WRAP",
            "BG_SIGNED_ADDR",
            "WINDOW_BASIC",
            "WINDOW_LINE_COUNTER",
            "WINDOW_WX_WY_EDGE",
            "WINDOW_WX0_STUTTER",
            "WINDOW_WX166_NEXTLINE",
            "WINDOW_WX_RETRIGGER_GLITCH",
            "WINDOW_WINEN_TOGGLE_REARM",
        ):
            rom_path = ROOT / roms[rom_id]["path"]
            self.assertEqual(rom_path.parent, ROOT / "bench" / "roms" / "out")
            asm_path = ROOT / "bench" / "roms" / f"{rom_id}.asm"
            self.assertTrue(asm_path.exists(), f"missing source for {rom_id}: {asm_path}")

    def test_cpu_instrs_blargg_entry_uses_serial_terminal_contract(self) -> None:
        inventory = yaml.safe_load(ROM_INVENTORY_PATH.read_text(encoding="utf-8"))
        rom = next(entry for entry in inventory["roms"] if entry["id"] == "CPU_INSTRS_BLARGG")

        self.assertEqual(rom["path"], "roms/cpu_instrs.gb")
        self.assertEqual(rom["requires"], ["cpu", "mbc1", "joypad"])
        self.assertEqual(rom["oracle_mode"], "serial_terminal")
        self.assertEqual(rom["compare_scope"]["domains"], ["serial_output"])
        self.assertEqual(rom["pass_condition"]["kind"], "serial_substring")
        self.assertEqual(rom["pass_condition"]["expected_substring"], "Passed all tests")
        self.assertEqual(rom["pass_condition"]["fail_substrings"], ["Failed"])
        self.assertRegex(rom["rom_sha256"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
