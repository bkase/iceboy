from __future__ import annotations

import importlib.util
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

from oracle_smoke import main as oracle_smoke_main


def make_fake_tool(directory: Path, name: str, version: str) -> Path:
    path = directory / name
    path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "case \"$1\" in\n"
        "  --version|-V)\n"
        f"    echo \"{version}\"\n"
        "    ;;\n"
        "  run)\n"
        "    shift\n"
        "    if [[ \"$1\" == \"--with-requirements\" ]]; then shift 2; fi\n"
        "    if [[ \"$1\" == \"python\" && \"$2\" == \"-c\" ]]; then\n"
        "      shift 2\n"
        "      if [[ \"$1\" == *\"version('pyboy')\"* ]]; then\n"
        "        echo \"2.7.0\"\n"
        "        exit 0\n"
        "      fi\n"
        "    fi\n"
        "    echo \"fake uv run\"\n"
        "    ;;\n"
        "  *)\n"
        f"    echo \"{version}\"\n"
        "    ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def load_module_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LocalEntrypointsTest(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        bindir = Path(self.tempdir.name)
        self.env = os.environ.copy()
        self.env.update(
            {
                "ICEBOY_UV_BIN": str(make_fake_tool(bindir, "uv", "uv 0.0-test")),
                "ICEBOY_SWIM_BIN": str(make_fake_tool(bindir, "swim", "swim v0.17.0-test")),
                "ICEBOY_IVERILOG_BIN": str(make_fake_tool(bindir, "iverilog", "Icarus Verilog version 13.0")),
                "ICEBOY_VERILATOR_BIN": str(make_fake_tool(bindir, "verilator", "Verilator 5.046")),
                "ICEBOY_YOSYS_BIN": str(make_fake_tool(bindir, "yosys", "Yosys 0.63+188")),
                "ICEBOY_NEXTPNR_BIN": str(make_fake_tool(bindir, "nextpnr-ice40", "nextpnr-0.10-15-g77ccf518")),
                "ICEBOY_SBY_BIN": str(make_fake_tool(bindir, "sby", "SBY 0.63-11-g6424d15")),
                "ICEBOY_EQY_BIN": str(make_fake_tool(bindir, "eqy", "EQY 0.1-test")),
            }
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_script(self, name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(TOOLS / name), *args],
            cwd=ROOT,
            env=self.env,
            capture_output=True,
            text=True,
        )

    def test_smoke_dry_run_uses_canonical_runner(self) -> None:
        completed = self.run_script("smoke.sh", "--dry-run")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("[tool] uv: uv 0.0-test", completed.stdout)
        self.assertIn("[tool] swim: swim v0.17.0-test", completed.stdout)
        self.assertIn("[tool] iverilog: Icarus Verilog version 13.0", completed.stdout)
        self.assertIn("tools/run_tests.py", completed.stdout)
        self.assertIn("--tier smoke", completed.stdout)

    def test_regress_nightly_dry_run_selects_nightly_preset(self) -> None:
        completed = self.run_script("regress.sh", "--dry-run", "--nightly", "--sim", "verilator")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("[tool] verilator: Verilator 5.046", completed.stdout)
        self.assertIn("--tier nightly", completed.stdout)
        self.assertNotIn("--tier full", completed.stdout)

    def test_wrappers_reject_direct_tier_override(self) -> None:
        completed = self.run_script("formal.sh", "--dry-run", "--tier", "full")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("do not pass --tier directly", completed.stderr)

    def test_wrappers_reject_quick_override(self) -> None:
        completed = self.run_script("smoke.sh", "--dry-run", "--quick")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("do not pass --quick", completed.stderr)

    def test_power_dry_run_uses_power_tier(self) -> None:
        completed = self.run_script("power.sh", "--dry-run")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("[tool] yosys: Yosys 0.63+188", completed.stdout)
        self.assertIn("[tool] nextpnr-ice40: nextpnr-0.10-15-g77ccf518", completed.stdout)
        self.assertIn("--tier power", completed.stdout)

    def test_verify_hw_build_dry_run_uses_debug_free_contract(self) -> None:
        completed = self.run_script("verify_hw_build.sh", "--dry-run", "--skip-build", "--enforce-budget")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("[tool] swim: swim v0.17.0-test", completed.stdout)
        self.assertIn("[tool] yosys: Yosys 0.63+188", completed.stdout)
        self.assertIn("skip swim build", completed.stdout)
        self.assertIn("src/board/icebreaker_top.spade", completed.stdout)
        self.assertIn("build/hw_verify/hardware.json", completed.stdout)
        self.assertIn("build/hw_verify/yosys-stat.txt", completed.stdout)
        self.assertIn("LUT4/DFF/SPRAM/EBR", completed.stdout)
        self.assertIn("CommitTrace", completed.stdout)
        self.assertIn("BusObs", completed.stdout)

    def test_hardware_baseline_dry_run_emits_synth_and_pnr_steps(self) -> None:
        completed = self.run_script("run_hardware_baseline.sh", "--dry-run")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("[tool] uv: uv 0.0-test", completed.stdout)
        self.assertIn("[tool] swim: swim v0.17.0-test", completed.stdout)
        self.assertIn("[tool] yosys: Yosys 0.63+188", completed.stdout)
        self.assertIn("[tool] nextpnr-ice40: nextpnr-0.10-15-g77ccf518", completed.stdout)
        self.assertIn("DRY RUN: /", completed.stdout)
        self.assertIn("read_verilog -sv", completed.stdout)
        self.assertIn("synth_ice40 -top icebreaker_top", completed.stdout)
        self.assertIn("--freq 12", completed.stdout)
        self.assertIn("icebreaker.pcf", completed.stdout)
        self.assertIn("docs/hardware/icebreaker_up5k_baseline.json", completed.stdout)
        self.assertTrue((ROOT / "tools" / "run_hardware_baseline.sh").exists())

    def test_oracle_wrapper_targets_direct_smoke_tool(self) -> None:
        completed = self.run_script("oracle.sh", "--dry-run")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("[tool] pyboy: 2.7.0", completed.stdout)
        self.assertIn("tools/oracle_smoke.py", completed.stdout)

    def test_ppu_wave_a_mooneye_verilator_wrapper_dry_run_uses_sanitized_verilog_path(self) -> None:
        completed = self.run_script("run_ppu_wave_a_mooneye_verilator.sh", "--dry-run", "--skip-build")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("[tool] uv: uv 0.0-test", completed.stdout)
        self.assertIn("[tool] swim: swim v0.17.0-test", completed.stdout)
        self.assertIn("[tool] verilator: Verilator 5.046", completed.stdout)
        self.assertIn("tools/prepare_verilator_sv.py", completed.stdout)
        self.assertIn("build/spade.verilator.sv", completed.stdout)
        self.assertIn("soc_rom_top_verilator_wrapper.sv", completed.stdout)
        self.assertIn("skip swim build", completed.stdout)

    def test_cpu_instrs_blargg_verilator_wrapper_dry_run_uses_cpu_wrapper(self) -> None:
        completed = self.run_script("run_cpu_instrs_blargg_verilator.sh", "--dry-run", "--skip-build")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("[tool] uv: uv 0.0-test", completed.stdout)
        self.assertIn("[tool] swim: swim v0.17.0-test", completed.stdout)
        self.assertIn("[tool] verilator: Verilator 5.046", completed.stdout)
        self.assertIn("tools/prepare_verilator_sv.py", completed.stdout)
        self.assertIn("build/spade.verilator.sv", completed.stdout)
        self.assertIn("cpu_test_top_verilator_wrapper.sv", completed.stdout)
        self.assertIn("skip swim build", completed.stdout)

    def test_ppu_wave_b_mealybug_verilator_wrapper_dry_run_uses_sanitized_verilog_path(self) -> None:
        completed = self.run_script("run_ppu_wave_b_mealybug_verilator.sh", "--dry-run", "--skip-build")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("[tool] uv: uv 0.0-test", completed.stdout)
        self.assertIn("[tool] swim: swim v0.17.0-test", completed.stdout)
        self.assertIn("[tool] verilator: Verilator 5.046", completed.stdout)
        self.assertIn("tools/prepare_verilator_sv.py", completed.stdout)
        self.assertIn("build/spade.verilator.sv", completed.stdout)
        self.assertIn("soc_rom_top_verilator_wrapper.sv", completed.stdout)
        self.assertIn("skip swim build", completed.stdout)

    def test_dmg_acid2_verilator_wrapper_dry_run_uses_sanitized_verilog_path(self) -> None:
        completed = self.run_script("run_dmg_acid2_verilator.sh", "--dry-run", "--skip-build")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("[tool] uv: uv 0.0-test", completed.stdout)
        self.assertIn("[tool] swim: swim v0.17.0-test", completed.stdout)
        self.assertIn("[tool] verilator: Verilator 5.046", completed.stdout)
        self.assertIn("tools/prepare_verilator_sv.py", completed.stdout)
        self.assertIn("build/spade.verilator.sv", completed.stdout)
        self.assertIn("soc_rom_top_verilator_wrapper.sv", completed.stdout)
        self.assertIn("tools/verilator/dmg_acid2_main.cpp", completed.stdout)
        self.assertIn("tools/compare_shaded_frame.py", completed.stdout)
        self.assertIn("--max-mcycles=1800000", completed.stdout)
        self.assertIn("--completed-frames=84", completed.stdout)
        self.assertIn("skip swim build", completed.stdout)

    def test_ppu_wave_c_verilator_wrapper_dry_run_uses_native_soc_rom_runner(self) -> None:
        completed = self.run_script("run_ppu_wave_c_verilator.sh", "--dry-run", "--skip-build")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("[tool] uv: uv 0.0-test", completed.stdout)
        self.assertIn("[tool] swim: swim v0.17.0-test", completed.stdout)
        self.assertIn("[tool] verilator: Verilator 5.046", completed.stdout)
        self.assertIn("[tool] python3:", completed.stdout)
        self.assertIn("tools/prepare_verilator_sv.py", completed.stdout)
        self.assertIn("build/spade.verilator.sv", completed.stdout)
        self.assertIn("soc_rom_top_verilator_wrapper.sv", completed.stdout)
        self.assertIn("tools/verilator/dmg_acid2_main.cpp", completed.stdout)
        self.assertIn("tools/write_checkpoint_shaded_frame.py", completed.stdout)
        self.assertIn("tools/resolve_checkpoint_pc.py", completed.stdout)
        self.assertIn("tools/compare_shaded_frame.py", completed.stdout)
        self.assertIn("rom ids: OBJ_10_PER_LINE OBJ_X_HIDDEN_STILL_COUNTS", completed.stdout)
        self.assertIn("--checkpoint-pc=0x", completed.stdout)
        self.assertIn("--checkpoint-completed-frames=2", completed.stdout)
        self.assertIn("skip swim build", completed.stdout)

    def test_ppu_checker_ball_verilator_wrapper_dry_run_uses_multiframe_native_runner(self) -> None:
        completed = self.run_script("run_ppu_checker_ball_verilator.sh", "--dry-run", "--skip-build")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("[tool] uv: uv 0.0-test", completed.stdout)
        self.assertIn("[tool] swim: swim v0.17.0-test", completed.stdout)
        self.assertIn("[tool] verilator: Verilator 5.046", completed.stdout)
        self.assertIn("rom ids: CHECKER_BALL CHECKER_BALL_CANCEL", completed.stdout)
        self.assertIn("rom id: CHECKER_BALL", completed.stdout)
        self.assertIn("rom id: CHECKER_BALL_CANCEL", completed.stdout)
        self.assertIn("expected settles: 1 2 3", completed.stdout)
        self.assertIn("expected settles: 1", completed.stdout)
        self.assertIn("checkpoint completed frames: 3 4 5", completed.stdout)
        self.assertIn("checkpoint completed frames: 2", completed.stdout)
        self.assertIn("--settle-rendered-frames=1", completed.stdout)
        self.assertIn("--checkpoint-completed-frames=5", completed.stdout)
        self.assertIn("--max-mcycles=160000", completed.stdout)
        self.assertIn("skip swim build", completed.stdout)

    def test_ppu_checker_ball_verilator_wrapper_can_include_overlap_reducer(self) -> None:
        env = dict(self.env)
        env["ICEBOY_PPU_CHECKER_BALL_INCLUDE_RED"] = "1"
        completed = subprocess.run(
            [str(TOOLS / "run_ppu_checker_ball_verilator.sh"), "--dry-run", "--skip-build"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("rom ids: CHECKER_BALL CHECKER_BALL_CANCEL CHECKER_BALL_CANCEL_OVERLAP", completed.stdout)
        self.assertIn("rom id: CHECKER_BALL_CANCEL_OVERLAP", completed.stdout)
        self.assertIn("checkpoint completed frames: 2", completed.stdout)

    def test_spram_synth_smoke_dry_run_targets_named_test_top(self) -> None:
        completed = self.run_script("run_spram_synth_smoke.sh", "--dry-run", "--skip-build")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("[tool] swim: swim v0.17.0-test", completed.stdout)
        self.assertIn("[tool] yosys: Yosys 0.63+188", completed.stdout)
        self.assertIn("wram_spram_synth_smoke_top", completed.stdout)
        self.assertIn("tools/verilog/wram_spram_synth_smoke_top.v", completed.stdout)
        self.assertIn("build/spram_synth_smoke/wram_spram_test_top.json", completed.stdout)
        self.assertIn("build/spram_synth_smoke/yosys-stat.txt", completed.stdout)

    def test_ebr_synth_smoke_dry_run_targets_named_test_top(self) -> None:
        completed = self.run_script("run_ebr_synth_smoke.sh", "--dry-run", "--skip-build")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("[tool] swim: swim v0.17.0-test", completed.stdout)
        self.assertIn("[tool] yosys: Yosys 0.63+188", completed.stdout)
        self.assertIn("ebr_synth_smoke_top", completed.stdout)
        self.assertIn("tools/verilog/ebr_synth_smoke_top.v", completed.stdout)
        self.assertIn("build/ebr_synth_smoke/ebr_synth_test_top.json", completed.stdout)
        self.assertIn("build/ebr_synth_smoke/yosys-stat.txt", completed.stdout)

    def test_activity_capture_windows_dry_run_targets_manifest_runner(self) -> None:
        completed = self.run_script("run_activity_capture_windows.sh", "--dry-run")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("[tool] uv: uv 0.0-test", completed.stdout)
        self.assertIn("[tool] swim: swim v0.17.0-test", completed.stdout)
        self.assertIn("tools/activity_capture.py", completed.stdout)
        self.assertIn("bench/manifests/activity_windows.yaml", completed.stdout)

    def test_encoding_optimization_evaluation_assets_exist(self) -> None:
        text = (TOOLS / "run_tests.py").read_text(encoding="utf-8")
        self.assertIn('"test_encoding_optimization_evaluation.py"', text)
        self.assertIn('"tools.tests.test_encoding_optimization_evaluation"', text)
        self.assertTrue((TOOLS / "encoding_optimization_evaluation.py").exists())
        self.assertTrue((ROOT / "docs" / "hardware" / "icebreaker_up5k_baseline.json").exists())
        self.assertTrue((ROOT / "bench" / "manifests" / "activity_windows_baseline.json").exists())

    def test_pipeline_insertion_evaluation_assets_exist(self) -> None:
        text = (TOOLS / "run_tests.py").read_text(encoding="utf-8")
        self.assertIn('"test_pipeline_insertion_evaluation.py"', text)
        self.assertIn('"tools.tests.test_pipeline_insertion_evaluation"', text)
        self.assertTrue((TOOLS / "pipeline_insertion_evaluation.py").exists())
        self.assertTrue((ROOT / "docs" / "hardware" / "icebreaker_up5k_baseline.json").exists())

    def test_ppu_backend_diff_assets_exist(self) -> None:
        text = (TOOLS / "run_tests.py").read_text(encoding="utf-8")
        self.assertIn('"test_ppu_backend_diff.py"', text)
        self.assertIn('"tools.tests.test_ppu_backend_diff"', text)
        self.assertIn('"test_backend_diff_smoke.py"', text)
        self.assertIn('"test.ppu.backend_diff.test_backend_diff_smoke"', text)
        self.assertTrue((TOOLS / "ppu_backend_diff.py").exists())
        self.assertTrue((TOOLS / "run_ppu_backend_diff.sh").exists())
        self.assertTrue((ROOT / "bench" / "manifests" / "ppu_backend_diff_scenarios.yaml").exists())
        self.assertTrue((ROOT / "test" / "ppu" / "backend_diff" / "test_backend_diff_smoke.py").exists())

    def test_ppu_wave_c_reference_assets_exist(self) -> None:
        text = (TOOLS / "run_tests.py").read_text(encoding="utf-8")
        self.assertIn('"test_ppu_wave_c_reference.py"', text)
        self.assertIn('"tools.tests.test_ppu_wave_c_reference"', text)
        self.assertTrue((ROOT / "tools" / "tests" / "test_ppu_wave_c_reference.py").exists())
        self.assertTrue((ROOT / "bench" / "roms" / "OBJ_BASIC.asm").exists())
        self.assertTrue((ROOT / "bench" / "roms" / "OBJ_PRIORITY.asm").exists())
        self.assertTrue((ROOT / "bench" / "roms" / "OBJ_8X16.asm").exists())
        self.assertTrue((ROOT / "bench" / "roms" / "OBJ_FLIP.asm").exists())
        self.assertTrue((ROOT / "bench" / "roms" / "OBJ_BG_MASK.asm").exists())
        self.assertTrue((ROOT / "bench" / "roms" / "OBJ_10_PER_LINE.asm").exists())
        self.assertTrue((ROOT / "bench" / "roms" / "OBJ_X_HIDDEN_STILL_COUNTS.asm").exists())
        self.assertTrue((ROOT / "bench" / "roms" / "OBJ_FETCH_CANCEL_LCDC1.asm").exists())
        self.assertTrue((ROOT / "bench" / "roms" / "CHECKER_BALL.asm").exists())
        self.assertTrue((ROOT / "bench" / "roms" / "CHECKER_BALL_CANCEL.asm").exists())
        self.assertTrue((ROOT / "bench" / "roms" / "CHECKER_BALL_CANCEL_OVERLAP.asm").exists())

    def test_ppu_wave_c_live_suite_assets_exist(self) -> None:
        run_tests_text = (TOOLS / "run_tests.py").read_text(encoding="utf-8")
        hook_text = (TOOLS / "run_precommit_checks.sh").read_text(encoding="utf-8")
        self.assertIn('"test_ppu_wave_c.py"', run_tests_text)
        self.assertIn('"tools/run_ppu_wave_c_verilator.sh"', run_tests_text)
        self.assertIn('"tools/run_ppu_wave_c_verilator.sh"', hook_text)
        self.assertTrue((TOOLS / "run_ppu_wave_c_verilator.sh").exists())
        self.assertTrue((TOOLS / "write_checkpoint_shaded_frame.py").exists())

    def test_ppu_checker_ball_live_suite_assets_exist(self) -> None:
        run_tests_text = (TOOLS / "run_tests.py").read_text(encoding="utf-8")
        hook_text = (TOOLS / "run_precommit_checks.sh").read_text(encoding="utf-8")
        self.assertIn('"test_ppu_checker_ball.py"', run_tests_text)
        self.assertIn('"tools/run_ppu_checker_ball_verilator.sh"', run_tests_text)
        self.assertIn('"tools/run_ppu_checker_ball_verilator.sh"', hook_text)
        self.assertTrue((TOOLS / "run_ppu_checker_ball_verilator.sh").exists())
        self.assertTrue((ROOT / "bench" / "roms" / "CHECKER_BALL.asm").exists())
        self.assertTrue((ROOT / "bench" / "roms" / "CHECKER_BALL_CANCEL.asm").exists())
        self.assertTrue((ROOT / "bench" / "roms" / "CHECKER_BALL_CANCEL_OVERLAP.asm").exists())

    def test_obj_observe_assets_exist(self) -> None:
        run_tests_text = (TOOLS / "run_tests.py").read_text(encoding="utf-8")
        hook_text = (TOOLS / "run_precommit_checks.sh").read_text(encoding="utf-8")
        self.assertIn('"test_obj_observe.py"', run_tests_text)
        self.assertIn('"test/ppu/unit/test_obj_observe.py"', run_tests_text)
        self.assertIn('"test/ppu/unit/test_obj_observe.py"', hook_text)
        self.assertTrue((ROOT / "src" / "ppu" / "rtl" / "obj_observe_test_top.spade").exists())
        self.assertTrue((ROOT / "test" / "ppu" / "unit" / "test_obj_observe.py").exists())

    def test_bg_transfer_live_assets_exist(self) -> None:
        run_tests_text = (TOOLS / "run_tests.py").read_text(encoding="utf-8")
        hook_text = (TOOLS / "run_precommit_checks.sh").read_text(encoding="utf-8")
        self.assertIn('"test_bg_transfer_live.py"', run_tests_text)
        self.assertIn('"test/ppu/unit/test_bg_transfer_live.py"', run_tests_text)
        self.assertIn('"test/ppu/unit/test_bg_transfer_live.py"', hook_text)
        self.assertTrue((ROOT / "test" / "ppu" / "unit" / "test_bg_transfer_live.py").exists())

    def test_obj_transfer_live_assets_exist(self) -> None:
        run_tests_text = (TOOLS / "run_tests.py").read_text(encoding="utf-8")
        hook_text = (TOOLS / "run_precommit_checks.sh").read_text(encoding="utf-8")
        self.assertIn('"test_obj_transfer_live.py"', run_tests_text)
        self.assertIn('"test/ppu/unit/test_obj_transfer_live.py"', run_tests_text)
        self.assertIn('"test/ppu/unit/test_obj_transfer_live.py"', hook_text)
        self.assertTrue((ROOT / "src" / "ppu" / "rtl" / "obj_transfer_live_test_top.spade").exists())
        self.assertTrue((ROOT / "test" / "ppu" / "unit" / "test_obj_transfer_live.py").exists())

    def test_line_summary_assets_exist(self) -> None:
        run_tests_text = (TOOLS / "run_tests.py").read_text(encoding="utf-8")
        hook_text = (TOOLS / "run_precommit_checks.sh").read_text(encoding="utf-8")
        self.assertIn('"test_line_summary.py"', run_tests_text)
        self.assertIn('"test/ppu/unit/test_line_summary.py"', run_tests_text)
        self.assertIn('"test/ppu/unit/test_line_summary.py"', hook_text)
        self.assertTrue((ROOT / "src" / "sim" / "line_summary_test_top.spade").exists())
        self.assertTrue((ROOT / "test" / "ppu" / "unit" / "test_line_summary.py").exists())

    def test_scanout_blank_assets_exist(self) -> None:
        run_tests_text = (TOOLS / "run_tests.py").read_text(encoding="utf-8")
        hook_text = (TOOLS / "run_precommit_checks.sh").read_text(encoding="utf-8")
        self.assertIn('"test_scanout_blank.py"', run_tests_text)
        self.assertIn('"test/ppu/unit/test_scanout_blank.py"', run_tests_text)
        self.assertIn('"test/ppu/unit/test_scanout_blank.py"', hook_text)
        self.assertTrue((ROOT / "src" / "ppu" / "rtl" / "scanout_test_top.spade").exists())
        self.assertTrue((ROOT / "test" / "ppu" / "unit" / "test_scanout_blank.py").exists())

    def test_sim_encode_module_centralizes_shared_sim_helpers(self) -> None:
        util_text = (ROOT / "src" / "util.spade").read_text(encoding="utf-8")
        encode_text = (ROOT / "src" / "sim" / "encode.spade").read_text(encoding="utf-8")
        self.assertIn("pub fn cpu_bus_req", util_text)
        self.assertIn("pub fn encode_bus_region", encode_text)
        self.assertIn("pub fn encode_scanout_kind", encode_text)
        self.assertIn("pub fn count_inc", encode_text)

        forbidden = (
            r"fn cpu_bus_req\(",
            r"fn encode_bus_region\(",
            r"fn encode_bus_owner\(",
            r"fn encode_ime\(",
            r"fn encode_halt\(",
            r"fn encode_phase\(",
            r"fn encode_scanout_kind\(",
            r"fn encode_pixel_source\(",
            r"fn encode_blank_reason\(",
            r"fn scanout_x\(",
            r"fn scanout_y\(",
            r"fn scanout_shade\(",
            r"fn scanout_source\(",
            r"fn scanout_blank_reason\(",
            r"fn ppu_vram_active\(",
            r"fn ppu_oam_active\(",
            r"fn count_inc\(",
            r"fn mask_has\(",
            r"fn phase_is_halted\(",
            r"fn halt_is_halted\(",
        )
        for relative in (
            Path("src/board/icebreaker_top.spade"),
            Path("src/sim/cpu_test_top.spade"),
            Path("src/sim/soc_lockstep_top.spade"),
            Path("src/sim/soc_rom_top.spade"),
            Path("src/sim/ppu_power_top.spade"),
        ):
            text = (ROOT / relative).read_text(encoding="utf-8")
            for pattern in forbidden:
                self.assertIsNone(
                    re.search(pattern, text),
                    f"{relative} still defines shared sim helper matching {pattern}",
                )

    def test_ppu_support_centralizes_test_helper_constructors(self) -> None:
        support_text = (ROOT / "src" / "sim" / "ppu_support.spade").read_text(encoding="utf-8")
        self.assertIn("pub fn encode_lcd_run", support_text)
        self.assertIn("pub fn decode_lcd_run", support_text)
        self.assertIn("pub fn build_test_lcdc", support_text)
        self.assertIn("pub fn pack_u2_row", support_text)

        forbidden = (
            r"fn encode_phase\(",
            r"fn encode_run\(",
            r"fn decode_run\(",
            r"fn build_lcdc\(",
            r"fn pack_row\(",
        )
        for relative in (
            Path("src/ppu/rtl/core_test_top.spade"),
            Path("src/ppu/rtl/timing_test_top.spade"),
            Path("src/ppu/rtl/irq_test_top.spade"),
            Path("src/ppu/rtl/fetcher_test_top.spade"),
            Path("src/ppu/rtl/tile_test_top.spade"),
            Path("src/ppu/rtl/fifo_test_top.spade"),
            Path("src/ppu/rtl/mixer_test_top.spade"),
            Path("src/ppu/rtl/oam_scan_test_top.spade"),
            Path("src/ppu/rtl/obj_priority_test_top.spade"),
        ):
            text = (ROOT / relative).read_text(encoding="utf-8")
            for pattern in forbidden:
                self.assertIsNone(
                    re.search(pattern, text),
                    f"{relative} still defines PPU helper matching {pattern}",
                )
        power_text = (ROOT / "src" / "sim" / "ppu_power_top.spade").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"fn encode_mode\(", power_text))

    def test_gate_milestone_e_dry_run_targets_power_artifacts(self) -> None:
        completed = self.run_script("gate_milestone_e.sh", "--dry-run")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("MILESTONE E GATE", completed.stdout)
        self.assertIn("test/power/test_halt_quiescence.py", completed.stdout)
        self.assertIn("test/power/test_duty_cycle_metrics.py", completed.stdout)
        self.assertIn("tools/run_activity_capture_windows.sh", completed.stdout)
        self.assertIn("docs/hardware/icebreaker_up5k_baseline.json", completed.stdout)
        self.assertIn("tools/verify_hw_build.sh", completed.stdout)

    def test_oracle_smoke_main_round_trips_snapshot(self) -> None:
        oracle_smoke_main()

    def test_precommit_uses_curated_exact_swim_paths(self) -> None:
        text = (TOOLS / "run_precommit_checks.sh").read_text(encoding="utf-8")
        self.assertIn('"test/unit/test_main.py"', text)
        self.assertIn('"test/unit/test_halt_bug.py"', text)
        self.assertIn('"test/unit/test_bus_fabric.py"', text)
        self.assertIn('"test/unit/test_membus.py"', text)
        self.assertIn('"test/unit/test_memory_map.py"', text)
        self.assertIn('"test/unit/test_hram_ebr.py"', text)
        self.assertIn('"test/unit/test_rom_spram.py"', text)
        self.assertIn('"test/unit/test_regs.py"', text)
        self.assertIn('"test/unit/test_oam_ebr.py"', text)
        self.assertIn('"test/unit/test_spram.py"', text)
        self.assertIn('"test/unit/test_semantics_alu.py"', text)
        self.assertIn('"test/unit/test_semantics_flow.py"', text)
        self.assertIn('"test/unit/test_semantics_loads.py"', text)
        self.assertIn('"test/unit/test_semantics_wordalu.py"', text)
        self.assertIn('"test/unit/test_write_enable.py"', text)
        self.assertIn('"test/unit/test_event_bridge.py"', text)
        self.assertIn('"test/unit/test_frame_sink.py"', text)
        self.assertIn('"test/unit/test_ppu_timing.py"', text)
        self.assertIn('"test/ppu/unit/test_ppu_modes.py"', text)
        self.assertIn('"test/ppu/unit/test_stat_irq.py"', text)
        self.assertIn('"test/ppu/unit/test_ppu_invariants.py"', text)
        self.assertIn('"test/ppu/unit/test_tile.py"', text)
        self.assertIn('"test/ppu/unit/test_access_policy.py"', text)
        self.assertIn('"test/ppu/unit/test_bg_fetcher.py"', text)
        self.assertIn('"test/ppu/unit/test_bg_transfer_live.py"', text)
        self.assertIn('"test/ppu/unit/test_bg_fifo.py"', text)
        self.assertIn('"test/ppu/unit/test_line_summary.py"', text)
        self.assertIn('"test/ppu/unit/test_oam_dma_mode2.py"', text)
        self.assertIn('"test/ppu/unit/test_scanout_blank.py"', text)
        self.assertIn('"test/ppu/unit/test_obj_transfer_live.py"', text)
        self.assertIn('"test/ppu/unit/test_ppu_core_smoke.py"', text)
        self.assertIn('"test/ppu/unit/test_mixer.py"', text)
        self.assertIn('"test/ppu/unit/test_obj_observe.py"', text)
        self.assertIn('"test/ppu/unit/test_obj_priority.py"', text)
        self.assertIn('"test/ppu/unit/test_obj_fetch.py"', text)
        self.assertIn('"test/ppu/unit/test_oam_dma_mode2.py"', text)
        self.assertIn('"test/ppu/unit/test_oam_scan.py"', text)
        self.assertIn('"test/ppu/unit/test_window.py"', text)
        self.assertIn('"test/power/test_ppu_power_quiescence.py"', text)
        self.assertIn('"test/unit/test_video_backend_adapter.py"', text)
        self.assertIn('"test/unit/test_oam_dma.py"', text)
        self.assertIn('"test/unit/test_joypad.py"', text)
        self.assertIn('"test/unit/test_joypad_interrupts.py"', text)
        self.assertIn('"test/unit/test_serial.py"', text)
        self.assertIn('"test/lockstep/test_ei_halt_corners.py"', text)
        self.assertIn('"test/harness/test_arch_time_invariants.py"', text)
        self.assertIn('"test/harness/test_soc_lockstep_top.py"', text)
        self.assertIn('"test/harness/test_soc_rom_top.py"', text)
        self.assertIn('"test/power/test_duty_cycle_metrics.py"', text)
        self.assertIn('"test/power/test_halt_quiescence.py"', text)
        self.assertIn('"test/harness/test_reset_profile.py"', text)
        self.assertIn('"test/rom/test_ei_delay.py"', text)
        self.assertIn('"test/rom/test_dma_oam_copy.py"', text)
        self.assertIn('"test/rom/test_oam_dma_isolation.py"', text)
        self.assertIn('"test/rom/test_alu16_sp.py"', text)
        self.assertIn('"test/rom/test_joy_diverge_persist.py"', text)
        self.assertIn('"test/rom/test_mbc1_ram.py"', text)
        self.assertIn('"test/rom/test_mbc1_switch.py"', text)
        self.assertIn('"test/rom/test_mbc3_ram.py"', text)
        self.assertIn('"test/rom/test_mbc3_switch.py"', text)
        self.assertIn('"tools/run_cpu_instrs_blargg_verilator.sh"', text)
        self.assertIn('"test/rom/test_ppu_wave_a.py"', text)
        self.assertIn('"test/rom/test_ppu_wave_b.py"', text)
        self.assertIn('"tools/run_ppu_wave_c_verilator.sh"', text)
        self.assertIn('"tools/run_ppu_wave_a_mooneye_verilator.sh"', text)
        self.assertIn('"test/rom/test_timer_div_basic.py"', text)
        self.assertIn('"test/rom/test_timer_irq_halt.py"', text)
        self.assertIn('ICEBOY_PRECOMMIT_ENFORCE_BUDGET', text)
        self.assertIn('tools/verify_hw_build.sh --skip-build --enforce-budget', text)
        self.assertIn('"$SWIM" test "$test_file"', text)
        self.assertIn('run_checked "$test_file" --skip-build', text)
        self.assertNotIn('label="$(basename "${test_file%.py}")"', text)

    def test_default_precommit_moves_long_rom_runs_to_extended_lane(self) -> None:
        text = (TOOLS / "run_precommit_checks.sh").read_text(encoding="utf-8")
        default_match = re.search(
            r"PRECOMMIT_SWIM_TESTS_DEFAULT=\((?P<body>.*?)\)\n\nPRECOMMIT_SWIM_TESTS_EXTENDED=\(",
            text,
            re.DOTALL,
        )
        extended_match = re.search(
            r"PRECOMMIT_SWIM_TESTS_EXTENDED=\((?P<body>.*?)\)\n\nif \[\[ ! -x",
            text,
            re.DOTALL,
        )
        self.assertIsNotNone(default_match)
        self.assertIsNotNone(extended_match)
        default_body = default_match.group("body")
        extended_body = extended_match.group("body")

        self.assertNotIn('"tools/run_cpu_instrs_blargg_verilator.sh"', default_body)
        self.assertNotIn('"test/rom/test_loads_basic.py"', default_body)
        self.assertNotIn('"test/ppu/unit/test_ppu_core_smoke.py"', default_body)
        self.assertNotIn('"test/ppu/unit/test_mixer.py"', default_body)
        self.assertNotIn('"test/ppu/unit/test_obj_observe.py"', default_body)
        self.assertNotIn('"test/ppu/unit/test_obj_priority.py"', default_body)
        self.assertNotIn('"test/ppu/unit/test_obj_fetch.py"', default_body)
        self.assertIn('"test/ppu/unit/test_oam_dma_mode2.py"', default_body)
        self.assertIn('"test/ppu/unit/test_oam_scan.py"', default_body)
        self.assertNotIn('"test/ppu/unit/test_window.py"', default_body)
        self.assertNotIn('"test/ppu/unit/test_tile.py"', default_body)
        self.assertNotIn('"test/power/test_ppu_power_quiescence.py"', default_body)
        self.assertIn('"tools/run_cpu_instrs_blargg_verilator.sh"', extended_body)
        self.assertIn('"test/rom/test_loads_basic.py"', extended_body)
        self.assertIn('"test/ppu/unit/test_ppu_core_smoke.py"', extended_body)
        self.assertIn('"test/ppu/unit/test_mixer.py"', extended_body)
        self.assertIn('"test/ppu/unit/test_obj_observe.py"', extended_body)
        self.assertIn('"test/ppu/unit/test_obj_priority.py"', extended_body)
        self.assertIn('"test/ppu/unit/test_obj_fetch.py"', extended_body)
        self.assertNotIn('"test/ppu/unit/test_oam_dma_mode2.py"', extended_body)
        self.assertNotIn('"test/ppu/unit/test_oam_scan.py"', extended_body)
        self.assertIn('"test/ppu/unit/test_window.py"', extended_body)
        self.assertIn('"test/ppu/unit/test_tile.py"', extended_body)
        self.assertIn('"test/power/test_ppu_power_quiescence.py"', extended_body)

    def test_shared_util_module_centralizes_bool_bit_and_io_write_helpers(self) -> None:
        util_text = (ROOT / "src" / "util.spade").read_text(encoding="utf-8")
        self.assertIn("pub fn bit(value: bool)", util_text)
        self.assertIn("pub fn io_write(write_en: bool, write_addr: uint<16>, target: uint<16>)", util_text)

        for relative in [
            "src/periph/timer.spade",
            "src/periph/interrupts.spade",
            "src/periph/serial.spade",
            "src/periph/joypad.spade",
            "src/mem/phys/spram_test_top.spade",
            "src/cpu/decode_test_top.spade",
        ]:
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("fn io_write(", text)
            self.assertNotIn("fn bool_code(", text)
            self.assertNotIn("fn bit(", text)

        bool_to_bit_pattern = re.compile(r"if .*\\{ 1u1 \\} else \\{ 0u1 \\}")
        for path in (ROOT / "src").rglob("*.spade"):
            if path.name == "util.spade":
                continue
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(
                bool_to_bit_pattern.search(text),
                f"found inline 1-bit bool packing in {path.relative_to(ROOT)}",
            )

    def test_periph_and_video_test_helpers_are_centralized(self) -> None:
        joypad_text = (ROOT / "src" / "periph" / "joypad.spade").read_text(encoding="utf-8")
        self.assertIn("pub fn decode_buttons(buttons_i: uint<8>)", joypad_text)

        video_text = (ROOT / "src" / "video" / "test_helpers.spade").read_text(encoding="utf-8")
        self.assertIn("pub fn decode_region(region_i: bool)", video_text)
        self.assertIn("pub fn decode_client(client_i: uint<3>)", video_text)
        self.assertIn("pub fn decode_kind(req_kind_i: bool, write_data_i: uint<8>)", video_text)
        self.assertIn("pub fn region_bit(region: MemRegion)", video_text)

        frame_sink_text = (ROOT / "src" / "video" / "frame_sink.spade").read_text(encoding="utf-8")
        self.assertIn("pub fn source_bits(source: PixelSource)", frame_sink_text)

        for relative in [
            "src/periph/joypad_test_top.spade",
            "src/periph/joypad_interrupts_test_top.spade",
            "src/bus/membus_test_top.spade",
        ]:
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("fn decode_buttons(", text)

        for relative in [
            "src/video/access_test_top.spade",
            "src/video/backend_adapter_test_top.spade",
        ]:
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("fn decode_region(", text)
            self.assertNotIn("fn decode_client(", text)
            self.assertNotIn("fn decode_kind(", text)
            self.assertNotIn("fn region_bit(", text)

        frame_sink_test_text = (ROOT / "src" / "video" / "frame_sink_test_top.spade").read_text(encoding="utf-8")
        self.assertNotIn("fn encode_source(", frame_sink_test_text)
        self.assertNotIn("fn decode_run(", (ROOT / "src" / "video" / "access_test_top.spade").read_text(encoding="utf-8"))

        bridge_text = (ROOT / "src" / "bus" / "ppu_bridge_core_test_top.spade").read_text(encoding="utf-8")
        self.assertNotIn("fn encode_phase(", bridge_text)
        self.assertNotIn("fn encode_mode(", bridge_text)
        self.assertNotIn("fn encode_run(", bridge_text)

    def test_cpu_lockstep_targeted_subset_is_not_marked_expect_fail(self) -> None:
        text = (ROOT / "test" / "lockstep" / "test_cpu_lockstep.py").read_text(encoding="utf-8")
        self.assertIn("test_cpu_lockstep_matches_ei_delay_checkpoints", text)
        self.assertIn("test_cpu_lockstep_matches_timer_irq_halt_checkpoints", text)
        self.assertNotIn("expect_fail=True", text)

    def test_precommit_skips_redundant_heavy_python_modules_and_formal_by_default(self) -> None:
        text = (TOOLS / "run_precommit_checks.sh").read_text(encoding="utf-8")
        self.assertIn('tools.tests.test_spade_cocotb_pipeline', text)
        self.assertIn('tools.tests.test_verilator_backend', text)
        self.assertIn('tools.tests.test_alu_generated_vectors', text)
        self.assertIn('ICEBOY_PRECOMMIT_INCLUDE_SYNTH', text)
        self.assertIn('tools/verify_hw_build.sh --skip-build', text)
        self.assertIn('ICEBOY_PRECOMMIT_INCLUDE_FORMAL', text)
        self.assertIn('ICEBOY_PRECOMMIT_EXTENDED', text)
        self.assertIn('Running fast Python spec tests...', text)
        self.assertIn('build/precommit.lock', text)
        self.assertIn('Another pre-commit hook is already running', text)
        self.assertIn('git rev-parse --local-env-vars', text)

    def test_formal_tier_registers_ppu_control_jobs(self) -> None:
        text = (TOOLS / "run_tests.py").read_text(encoding="utf-8")
        self.assertIn('SuiteDefinition("formal", "ppu_irq.sby", "shell", "tools/run_formal_ppu_irq.sh")', text)
        self.assertIn('SuiteDefinition("formal", "ppu_lcd_off_quiescence.sby", "shell", "tools/run_formal_ppu_lcd_off.sh")', text)
        self.assertIn('SuiteDefinition("formal", "ppu_timing.sby", "shell", "tools/run_formal_ppu_timing.sh")', text)
        self.assertTrue((TOOLS / "run_formal_ppu_irq.sh").exists())
        self.assertTrue((TOOLS / "run_formal_ppu_lcd_off.sh").exists())
        self.assertTrue((TOOLS / "run_formal_ppu_timing.sh").exists())
        self.assertTrue((ROOT / "formal" / "ppu" / "safety" / "ppu_irq.sby").exists())
        self.assertTrue((ROOT / "formal" / "ppu" / "safety" / "ppu_lcd_off_quiescence.sby").exists())
        self.assertTrue((ROOT / "formal" / "ppu" / "safety" / "ppu_timing.sby").exists())

    def test_equivalence_wrapper_dry_run_renders_cpu_refactor_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            gold = tmpdir_path / "before.v"
            gate = tmpdir_path / "after.v"
            gold.write_text("module cpu_core; endmodule\n", encoding="utf-8")
            gate.write_text("module cpu_core; endmodule\n", encoding="utf-8")

            completed = self.run_script(
                "check_equivalence.sh",
                "--dry-run",
                "--top",
                "cpu_core",
                str(gold),
                str(gate),
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("[tool] eqy: EQY 0.1-test", completed.stdout)
        self.assertIn("[tool] yosys: Yosys 0.63+188", completed.stdout)
        self.assertIn("formal/cpu_refactor.eqy", completed.stdout)
        self.assertIn("cpu_refactor.generated.eqy", completed.stdout)
        self.assertIn("top=cpu_core", completed.stdout)
        self.assertTrue((ROOT / "formal" / "cpu_refactor.eqy").exists())

    def test_ppu_equivalence_wrapper_dry_run_renders_ppu_refactor_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            gold = tmpdir_path / "before.v"
            gate = tmpdir_path / "after.v"
            gold.write_text("module ppu_core; endmodule\n", encoding="utf-8")
            gate.write_text("module ppu_core; endmodule\n", encoding="utf-8")

            completed = self.run_script(
                "check_ppu_equivalence.sh",
                "--dry-run",
                "--top",
                "ppu_core",
                str(gold),
                str(gate),
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("[tool] eqy: EQY 0.1-test", completed.stdout)
        self.assertIn("[tool] yosys: Yosys 0.63+188", completed.stdout)
        self.assertIn("formal/ppu/equivalence/ppu_refactor.eqy", completed.stdout)
        self.assertIn("ppu_refactor.generated.eqy", completed.stdout)
        self.assertIn("top=ppu_core", completed.stdout)
        self.assertTrue((ROOT / "tools" / "check_ppu_equivalence.sh").exists())
        self.assertTrue((ROOT / "formal" / "ppu" / "equivalence" / "ppu_refactor.eqy").exists())

    def test_wave_a_mooneye_write_timing_budget_allows_env_override(self) -> None:
        module = load_module_from_path(
            "test_ppu_wave_a_mooneye_module",
            ROOT / "test" / "rom" / "test_ppu_wave_a_mooneye.py",
        )
        self.assertEqual(module._max_mcycles_for_rom("lcdon_write_timing-GS.gb"), 1_500_000)
        with patch.dict(
            os.environ,
            {"ICEBOY_MOONEYE_MAX_MCYCLES_LCDON_WRITE_TIMING_GS_GB": "1750000"},
            clear=False,
        ):
            self.assertEqual(module._max_mcycles_for_rom("lcdon_write_timing-GS.gb"), 1_750_000)

    def test_wave_b_mealybug_budget_allows_env_override(self) -> None:
        module = load_module_from_path(
            "test_ppu_wave_b_mealybug_module",
            ROOT / "test" / "rom" / "test_ppu_wave_b_mealybug.py",
        )
        self.assertEqual(module._max_mcycles_for_rom("m3_window_timing.gb"), 400_000)
        with patch.dict(
            os.environ,
            {"ICEBOY_MEALYBUG_MAX_MCYCLES_M3_WINDOW_TIMING_GB": "500000"},
            clear=False,
        ):
            self.assertEqual(module._max_mcycles_for_rom("m3_window_timing.gb"), 500_000)


if __name__ == "__main__":
    unittest.main()
