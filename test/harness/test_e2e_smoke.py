# top = sim::cpu_test_top::cpu_test_top
import sys
import tempfile
import warnings
from pathlib import Path

import cocotb
from cocotb.triggers import ReadOnly


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from assertions import assert_registers_match
from bench.pyboy.oracle import CommitPoint, PyBoyOracle, RegisterState
from dut_driver import SimStimulus
from fixtures import cpu_dut
from rom_runner import ExternalMemoryBus
from roms.build_micro_rom import build_rom
from spec.profiles import ModelProfile, ResetProfile


warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")


def decode_dut_registers(arch_state_value: int) -> RegisterState:
    regs = (arch_state_value >> 4) & ((1 << 96) - 1)
    return RegisterState(
        a=(regs >> 88) & 0xFF,
        f=(regs >> 80) & 0xFF,
        b=(regs >> 72) & 0xFF,
        c=(regs >> 64) & 0xFF,
        d=(regs >> 56) & 0xFF,
        e=(regs >> 48) & 0xFF,
        hl=(regs >> 32) & 0xFFFF,
        sp=(regs >> 16) & 0xFFFF,
        pc=regs & 0xFFFF,
    )


@cocotb.test()
async def test_first_instruction_executes_correctly_against_pyboy_oracle(dut):
    rom_bytes = build_rom("E2E_SMOKE", bytes([0x18, 0xFE]))
    sym_text = "00:0101 __commit_after_first\n"
    driver = cpu_dut(dut)
    await driver.reset(ResetProfile.SkipBoot)

    memory = ExternalMemoryBus(rom_bytes)
    trace = await driver.step_mcycle(
        stimulus=SimStimulus.idle(),
        bus_read_data=memory.read(0x0100),
        irq_pending=0,
    )
    await ReadOnly()
    actual = decode_dut_registers(int(dut.cpu_core_0.arch_state.value))

    with tempfile.TemporaryDirectory() as tmpdir:
        rom_path = Path(tmpdir) / "e2e_smoke.gb"
        sym_path = rom_path.with_suffix(".sym")
        rom_path.write_bytes(rom_bytes)
        sym_path.write_text(sym_text, encoding="utf-8")
        with PyBoyOracle(
            rom_path,
            sym_path=sym_path,
            commit_points=(CommitPoint(bank=0, addr=0x0101, label="__commit_after_first"),),
        ) as oracle:
            oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)
            expected = oracle.step_commit().registers_after

    assert trace.pc == expected.pc, trace
    assert_registers_match(expected, actual, "e2e_smoke.first_instruction")
