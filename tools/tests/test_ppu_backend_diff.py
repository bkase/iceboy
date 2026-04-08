from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from tools.compare_oracles import PpuCompareScope
from tools.ppu_backend_diff import compare_manifest, load_manifest


class PpuBackendDiffTest(unittest.TestCase):
    def test_load_manifest_resolves_capture_paths_and_scopes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            left = root / "left.json"
            right = root / "right.json"
            payload = {"dot_commit": [], "scanline_summary": [], "frame_hash": []}
            left.write_text(json.dumps(payload), encoding="utf-8")
            right.write_text(json.dumps(payload), encoding="utf-8")
            manifest = root / "manifest.yaml"
            manifest.write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "scenarios": [
                            {
                                "name": "demo",
                                "description": "demo",
                                "sim_array_capture": "left.json",
                                "inferred_ram_capture": "right.json",
                                "scopes": ["dot_commit", "frame_hash"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            scenarios = load_manifest(manifest)

        self.assertEqual(len(scenarios), 1)
        self.assertEqual(scenarios[0].name, "demo")
        self.assertEqual(scenarios[0].sim_array_capture.name, "left.json")
        self.assertEqual(scenarios[0].inferred_ram_capture.name, "right.json")
        self.assertEqual(scenarios[0].scopes, (PpuCompareScope.DotCommit, PpuCompareScope.FrameHash))

    def test_compare_manifest_reports_first_backend_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            left = root / "left.json"
            right = root / "right.json"
            left.write_text(
                json.dumps(
                    {
                        "dot_commit": [{"mode_after": "OamScan"}],
                        "scanline_summary": [],
                        "frame_hash": [0],
                    }
                ),
                encoding="utf-8",
            )
            right.write_text(
                json.dumps(
                    {
                        "dot_commit": [{"mode_after": "Transfer"}],
                        "scanline_summary": [],
                        "frame_hash": [0],
                    }
                ),
                encoding="utf-8",
            )
            manifest = root / "manifest.yaml"
            manifest.write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "scenarios": [
                            {
                                "name": "demo",
                                "description": "demo",
                                "sim_array_capture": "left.json",
                                "inferred_ram_capture": "right.json",
                                "scopes": ["dot_commit"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            outcomes = compare_manifest(manifest)

        self.assertEqual(len(outcomes), 1)
        self.assertFalse(outcomes[0].matched)
        self.assertEqual(outcomes[0].scope, PpuCompareScope.DotCommit)
        self.assertEqual(outcomes[0].field_path, "mode_after")


if __name__ == "__main__":
    unittest.main()
