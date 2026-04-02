# top = sim::cpu_test_top::cpu_test_top
import sys
import tempfile
import warnings
from pathlib import Path

import cocotb


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from bench.pyboy.lockstep_driver import run_lockstep
from bench.pyboy.oracle import CommitPoint, PyBoyOracle
from fixtures import cpu_dut
from roms.build_micro_rom import build_alu_loop
from spec.compare_scopes import OracleMode
from spec.profiles import ModelProfile, ResetProfile


warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")

HOOK_ADDRS = (0x0150, 0x0152, 0x0154, 0x0155, 0x0156)


class EmptyScript:
    def events_for_commit(self, commit_index: int) -> tuple[object, ...]:
        return ()


@cocotb.test(expect_fail=True)
async def test_cpu_lockstep_placeholder_xfail(dut):
    """Keep the live lockstep path stable while the HDL surface is still incomplete."""
    driver = cpu_dut(dut)
    await driver.reset(ResetProfile.SkipBoot)

    with tempfile.TemporaryDirectory() as tmpdir:
        rom_path = Path(tmpdir) / "alu_loop.gb"
        rom_path.write_bytes(build_alu_loop())
        commit_points = tuple(CommitPoint(bank=0, addr=addr, label=f"hook_{addr:04X}") for addr in HOOK_ADDRS)

        with PyBoyOracle(rom_path, commit_points=commit_points) as oracle:
            oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)
            result = await run_lockstep(
                oracle,
                driver,
                EmptyScript(),
                OracleMode.InstrCommit,
                commit_limit=1,
            )
            assert result.matched, f"semantic value mismatch: {result.mismatch_report}"
