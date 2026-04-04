from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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

    def test_oracle_wrapper_targets_direct_smoke_tool(self) -> None:
        completed = self.run_script("oracle.sh", "--dry-run")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("[tool] pyboy: 2.7.0", completed.stdout)
        self.assertIn("tools/oracle_smoke.py", completed.stdout)

    def test_oracle_smoke_main_round_trips_snapshot(self) -> None:
        oracle_smoke_main()

    def test_precommit_uses_curated_exact_swim_paths(self) -> None:
        text = (TOOLS / "run_precommit_checks.sh").read_text(encoding="utf-8")
        self.assertIn('"test/unit/test_main.py"', text)
        self.assertIn('"test/unit/test_halt_bug.py"', text)
        self.assertIn('"test/unit/test_membus.py"', text)
        self.assertIn('"test/unit/test_memory_map.py"', text)
        self.assertIn('"test/unit/test_event_bridge.py"', text)
        self.assertIn('"test/unit/test_frame_sink.py"', text)
        self.assertIn('"test/unit/test_ppu_irq.py"', text)
        self.assertIn('"test/unit/test_ppu_timing.py"', text)
        self.assertIn('"test/ppu/unit/test_access_policy.py"', text)
        self.assertIn('"test/unit/test_video_backend_adapter.py"', text)
        self.assertIn('"test/unit/test_oam_dma.py"', text)
        self.assertIn('"test/unit/test_serial.py"', text)
        self.assertIn('"test/lockstep/test_ei_halt_corners.py"', text)
        self.assertIn('"test/harness/test_arch_time_invariants.py"', text)
        self.assertIn('"test/power/test_duty_cycle_metrics.py"', text)
        self.assertIn('"test/power/test_halt_quiescence.py"', text)
        self.assertIn('"test/harness/test_reset_profile.py"', text)
        self.assertIn('"test/rom/test_ei_delay.py"', text)
        self.assertIn('"test/rom/test_dma_oam_copy.py"', text)
        self.assertIn('"test/rom/test_alu16_sp.py"', text)
        self.assertIn('"test/rom/test_joy_diverge_persist.py"', text)
        self.assertIn('"test/rom/test_mbc1_ram.py"', text)
        self.assertIn('"test/rom/test_mbc1_switch.py"', text)
        self.assertIn('"test/rom/test_mbc3_ram.py"', text)
        self.assertIn('"test/rom/test_mbc3_switch.py"', text)
        self.assertIn('"test/rom/test_timer_div_basic.py"', text)
        self.assertIn('"test/rom/test_timer_irq_halt.py"', text)
        self.assertIn('"$SWIM" test "$test_file"', text)
        self.assertNotIn('label="$(basename "${test_file%.py}")"', text)

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
        self.assertIn('ICEBOY_PRECOMMIT_INCLUDE_FORMAL', text)
        self.assertIn('ICEBOY_PRECOMMIT_EXTENDED', text)
        self.assertIn('Running fast Python spec tests...', text)

    def test_formal_tier_registers_ppu_control_jobs(self) -> None:
        text = (TOOLS / "run_tests.py").read_text(encoding="utf-8")
        self.assertIn('SuiteDefinition("formal", "ppu_irq.sby", "shell", "tools/run_formal_ppu_irq.sh")', text)
        self.assertIn('SuiteDefinition("formal", "ppu_timing.sby", "shell", "tools/run_formal_ppu_timing.sh")', text)
        self.assertTrue((TOOLS / "run_formal_ppu_irq.sh").exists())
        self.assertTrue((TOOLS / "run_formal_ppu_timing.sh").exists())
        self.assertTrue((ROOT / "formal" / "ppu" / "safety" / "ppu_irq.sby").exists())
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


if __name__ == "__main__":
    unittest.main()
