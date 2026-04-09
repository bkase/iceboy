from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from tools.compare_oracles import PpuCompareScope
from tools.ppu_backend_diff import DEFAULT_MANIFEST, compare_manifest, load_manifest, materialize_capture


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
        self.assertIsNone(scenarios[0].sim_array_generator)
        self.assertIsNone(scenarios[0].inferred_ram_generator)
        self.assertEqual(scenarios[0].scopes, (PpuCompareScope.DotCommit, PpuCompareScope.FrameHash))

    def test_load_manifest_supports_live_generators(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = root / "manifest.yaml"
            manifest.write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "scenarios": [
                            {
                                "name": "demo",
                                "description": "demo",
                                "sim_array_generator": {
                                    "runner": "swim",
                                    "target": "test/left.py",
                                    "dots": 12,
                                },
                                "inferred_ram_generator": {
                                    "runner": "swim",
                                    "target": "test/right.py",
                                },
                                "scopes": ["dot_commit"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            scenarios = load_manifest(manifest)

        self.assertEqual(scenarios[0].sim_array_generator.runner, "swim")
        self.assertEqual(scenarios[0].sim_array_generator.target, "test/left.py")
        self.assertEqual(scenarios[0].sim_array_generator.dots, 12)
        self.assertEqual(scenarios[0].inferred_ram_generator.dots, 8)

    def test_materialize_capture_runs_swim_generator_with_capture_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = root / "manifest.yaml"
            manifest.write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "scenarios": [
                            {
                                "name": "demo",
                                "description": "demo",
                                "sim_array_generator": {
                                    "runner": "swim",
                                    "target": "test/capture.py",
                                    "dots": 9,
                                },
                                "inferred_ram_capture": "right.json",
                                "scopes": ["dot_commit"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (root / "right.json").write_text(
                json.dumps({"dot_commit": [], "scanline_summary": [], "frame_hash": []}),
                encoding="utf-8",
            )
            scenario = load_manifest(manifest)[0]
            temp_root = root / "out"
            temp_root.mkdir()

            with mock.patch("tools.ppu_backend_diff.subprocess.run") as run:
                capture_path = materialize_capture(scenario, "sim_array", temp_dir=temp_root)

        self.assertEqual(capture_path, temp_root / "demo_sim_array.json")
        run.assert_called_once()
        args, kwargs = run.call_args
        self.assertEqual(args[0][-2:], ["test", "test/capture.py"])
        self.assertEqual(kwargs["cwd"], Path(__file__).resolve().parents[2])
        self.assertEqual(kwargs["env"]["ICEBOY_BACKEND_DIFF_SCENARIO"], "demo")
        self.assertEqual(kwargs["env"]["ICEBOY_BACKEND_DIFF_BACKEND"], "sim_array")
        self.assertEqual(kwargs["env"]["ICEBOY_BACKEND_DIFF_CAPTURE_DOTS"], "9")
        self.assertEqual(kwargs["env"]["ICEBOY_BACKEND_DIFF_CAPTURE_PATH"], str(temp_root / "demo_sim_array.json"))

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

    def test_default_manifest_uses_live_generators_with_existing_targets(self) -> None:
        scenarios = load_manifest(DEFAULT_MANIFEST)
        self.assertTrue(scenarios)
        scenario = scenarios[0]
        self.assertIsNotNone(scenario.sim_array_generator)
        self.assertIsNotNone(scenario.inferred_ram_generator)
        self.assertIsNone(scenario.sim_array_capture)
        self.assertIsNone(scenario.inferred_ram_capture)
        self.assertGreaterEqual(scenario.sim_array_generator.dots, 456)
        self.assertGreaterEqual(scenario.inferred_ram_generator.dots, 456)
        self.assertTrue((Path(__file__).resolve().parents[2] / scenario.sim_array_generator.target).exists())
        self.assertTrue((Path(__file__).resolve().parents[2] / scenario.inferred_ram_generator.target).exists())


if __name__ == "__main__":
    unittest.main()
