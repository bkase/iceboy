from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


from test.harness.waveform_config import (
    config_from_env,
    export_waveforms,
    locate_waveforms,
    write_divergence_window_metadata,
)


class WaveformConfigTest(unittest.TestCase):
    def test_export_is_disabled_by_default_without_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            harness_root = Path(tmpdir) / "build" / "harness"
            case_dir = harness_root / "test_demo_case"
            case_dir.mkdir(parents=True)
            (case_dir / "demo.fst").write_bytes(b"fst")

            exported = export_waveforms(
                "test_demo",
                failed=False,
                config=config_from_env(env={}, artifact_root=Path(tmpdir) / "waves"),
                harness_root=harness_root,
            )
            self.assertIsNone(exported)

    def test_export_copies_waveforms_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            harness_root = Path(tmpdir) / "build" / "harness"
            case_dir = harness_root / "test_demo_case"
            case_dir.mkdir(parents=True)
            (case_dir / "demo.fst").write_bytes(b"fst")
            (case_dir / "dump.vcd").write_text("$date\n", encoding="utf-8")
            artifact_root = Path(tmpdir) / "waves"

            exported = export_waveforms(
                "test_demo",
                failed=False,
                config=config_from_env(env={"ICEBOY_WAVES": "1"}, artifact_root=artifact_root),
                harness_root=harness_root,
            )
            self.assertIsNotNone(exported)
            assert exported is not None
            self.assertTrue(exported.fst_path is not None and exported.fst_path.exists())
            self.assertTrue(exported.vcd_path is not None and exported.vcd_path.exists())
            manifest = json.loads(exported.metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["test_name"], "test_demo")

    def test_failure_promotes_waveform_even_when_normal_export_is_off(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            harness_root = Path(tmpdir) / "build" / "harness"
            case_dir = harness_root / "test_demo_case"
            case_dir.mkdir(parents=True)
            (case_dir / "demo.fst").write_bytes(b"fst")

            exported = export_waveforms(
                "test_demo",
                failed=True,
                config=config_from_env(env={}, artifact_root=Path(tmpdir) / "waves"),
                harness_root=harness_root,
            )
            self.assertIsNotNone(exported)
            assert exported is not None
            self.assertTrue(exported.fst_path is not None and exported.fst_path.exists())

    def test_divergence_window_metadata_records_requested_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_divergence_window_metadata(
                "cpu_lockstep",
                72,
                before=50,
                after=10,
                artifact_root=Path(tmpdir),
                waveform_path=Path(tmpdir) / "failure.fst",
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["window_start_commit"], 22)
            self.assertEqual(payload["window_end_commit"], 82)

    def test_locate_waveforms_prefers_latest_case_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            harness_root = Path(tmpdir) / "build" / "harness"
            older = harness_root / "test_demo_old"
            newer = harness_root / "test_demo_new"
            older.mkdir(parents=True)
            newer.mkdir(parents=True)
            (older / "old.fst").write_bytes(b"old")
            (newer / "new.fst").write_bytes(b"new")

            located = locate_waveforms("test_demo", harness_root=harness_root)
            self.assertEqual(located["fst"].name, "new.fst")


if __name__ == "__main__":
    unittest.main()
