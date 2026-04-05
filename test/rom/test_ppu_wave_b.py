# top = sim::cpu_test_top::cpu_test_top
import sys
import warnings
from pathlib import Path

import cocotb


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from fixtures import cpu_dut
from rom_runner import assert_rom_matches_pyboy_signature
from spec.profiles import ResetProfile


warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")

PPU_WAVE_B_ROMS = (
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
)
PPU_WAVE_B_MAX_MCYCLES = 60000


async def _run_ppu_wave_b_rom(dut, rom_id: str) -> None:
    driver = cpu_dut(dut)
    await driver.reset(ResetProfile.SkipBoot)
    await assert_rom_matches_pyboy_signature(
        driver,
        rom_id=rom_id,
        max_mcycles=PPU_WAVE_B_MAX_MCYCLES,
    )


@cocotb.test()
async def test_bg_static_rom_matches_pyboy_signature(dut):
    await _run_ppu_wave_b_rom(dut, "BG_STATIC")


@cocotb.test()
async def test_bg_scroll_wrap_rom_matches_pyboy_signature(dut):
    await _run_ppu_wave_b_rom(dut, "BG_SCROLL_WRAP")


@cocotb.test()
async def test_bg_signed_addr_rom_matches_pyboy_signature(dut):
    await _run_ppu_wave_b_rom(dut, "BG_SIGNED_ADDR")


@cocotb.test()
async def test_window_basic_rom_matches_pyboy_signature(dut):
    await _run_ppu_wave_b_rom(dut, "WINDOW_BASIC")


@cocotb.test()
async def test_window_line_counter_rom_matches_pyboy_signature(dut):
    await _run_ppu_wave_b_rom(dut, "WINDOW_LINE_COUNTER")


@cocotb.test()
async def test_window_wx_wy_edge_rom_matches_pyboy_signature(dut):
    await _run_ppu_wave_b_rom(dut, "WINDOW_WX_WY_EDGE")


@cocotb.test()
async def test_window_wx0_stutter_rom_matches_pyboy_signature(dut):
    await _run_ppu_wave_b_rom(dut, "WINDOW_WX0_STUTTER")


@cocotb.test()
async def test_window_wx166_nextline_rom_matches_pyboy_signature(dut):
    await _run_ppu_wave_b_rom(dut, "WINDOW_WX166_NEXTLINE")


@cocotb.test()
async def test_window_wx_retrigger_glitch_rom_matches_pyboy_signature(dut):
    await _run_ppu_wave_b_rom(dut, "WINDOW_WX_RETRIGGER_GLITCH")


@cocotb.test()
async def test_window_winen_toggle_rearm_rom_matches_pyboy_signature(dut):
    await _run_ppu_wave_b_rom(dut, "WINDOW_WINEN_TOGGLE_REARM")
