from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

import warnings

from pyboy import PyBoy
import yaml

from bench.ref.ppu_ref import (
    DotInput as PpuDotInput,
    MmioReg as PpuMmioReg,
    MmioWrite as PpuMmioWrite,
    PpuMode,
    PpuReferenceModel,
    TimedPpuEvent as PpuTimedEvent,
    VideoCoord as PpuVideoCoord,
    apply_mmio_write as ppu_apply_mmio_write,
    lcd_enabled as ppu_lcd_enabled,
    lyc_match as ppu_lyc_match,
    step_dot as ppu_step_dot,
    visible_mode as ppu_visible_mode,
)
from bench.pyboy.hooks import HookManifest, build_hook_manifest
from bench.pyboy.oracle import PyBoyOracle
from bench.pyboy.symbols import SymbolTable
try:
    from dut_driver import SimStimulus
except ModuleNotFoundError:
    from test.harness.dut_driver import SimStimulus
try:
    from event_script_support import stimulus_from_events
except ModuleNotFoundError:
    from test.harness.event_script_support import stimulus_from_events
try:
    from fixtures import event_script
except ModuleNotFoundError:
    from test.harness.fixtures import event_script
from spec.profiles import ModelProfile, ResetProfile, SimulationProfiles

ROOT = Path(__file__).resolve().parents[2]
ROM_MANIFEST_PATH = ROOT / "bench" / "manifests" / "rom_inventory.yaml"

ABI_SIGNATURE_BASE = 0xC000
ABI_LOG_BASE = 0xC020
ABI_SIGNATURE_SIZE = 0x20
ABI_LOG_SIZE = 0x06
ABI_RESULT_RUNNING = 0x00
ABI_RESULT_PASS = 0x01
ABI_RESULT_FAIL = 0xFF

BUS_REQ_IDLE = 0
BUS_REQ_READ = 1
BUS_REQ_WRITE = 2
PYBOY_BATCH_TICKS = 40
TIMER_IF_BIT = 0x04
SERIAL_IF_BIT = 0x08
JOYPAD_IF_BIT = 0x10
JOYP_ADDR = 0xFF00
SB_ADDR = 0xFF01
SC_ADDR = 0xFF02
DIV_ADDR = 0xFF04
TIMA_ADDR = 0xFF05
TMA_ADDR = 0xFF06
TAC_ADDR = 0xFF07
DMA_ADDR = 0xFF46
IF_ADDR = 0xFF0F
IE_ADDR = 0xFFFF
LCDC_ADDR = 0xFF40
STAT_ADDR = 0xFF41
SCY_ADDR = 0xFF42
SCX_ADDR = 0xFF43
LY_ADDR = 0xFF44
LYC_ADDR = 0xFF45
BGP_ADDR = 0xFF47
OBP0_ADDR = 0xFF48
OBP1_ADDR = 0xFF49
WY_ADDR = 0xFF4A
WX_ADDR = 0xFF4B
VRAM_BASE = 0x8000
VRAM_SIZE = 0x2000
OAM_BASE = 0xFE00
OAM_SIZE = 0xA0
CARTRIDGE_TYPE_ADDR = 0x0147
CARTRIDGE_RAM_SIZE_ADDR = 0x0149
MBC1_CART_TYPES = frozenset({0x01, 0x02, 0x03})
MBC3_CART_TYPES = frozenset({0x0F, 0x10, 0x11, 0x12, 0x13})
MBC1_RAM_BANK_SIZE = 0x2000
MBC3_RTC_SELECTS = frozenset({0x08, 0x09, 0x0A, 0x0B, 0x0C})
VBLANK_IF_BIT = 0x01
STAT_IF_BIT = 0x02
MOONEYE_PASS_BYTES = (3, 5, 8, 13, 21, 34)
MOONEYE_FAIL_BYTES = (0x42, 0x42, 0x42, 0x42, 0x42, 0x42)


def _cartridge_ram_size_bytes(size_code: int) -> int:
    return {
        0x00: 0,
        0x02: 0x2000,
        0x03: 0x8000,
        0x04: 0x20000,
        0x05: 0x10000,
    }.get(size_code & 0xFF, 0)


def _ack_mask(valid: bool, ack_bit: int) -> int:
    if not valid:
        return 0
    if 0 <= ack_bit < 5:
        return 1 << ack_bit
    return 0


def _tac_enabled(tac: int) -> bool:
    return (tac & 0x4) == 0x4


def _timer_bit(sys_counter: int, tac: int) -> bool:
    shift = {0: 9, 1: 3, 2: 5, 3: 7}[tac & 0x3]
    return bool((sys_counter >> shift) & 0x1)


@dataclass(frozen=True)
class RomManifestEntry:
    rom_id: str
    rom_path: Path
    sym_path: Path
    profiles: SimulationProfiles
    timeout_commits: int
    checkpoint_symbols: tuple[str, ...]
    manifest_entry: dict[str, object]


@dataclass(frozen=True)
class AbiSnapshot:
    signature: bytes
    log: bytes

    @property
    def result(self) -> int:
        return self.signature[1]


@dataclass(frozen=True)
class DutTerminalState:
    abi: AbiSnapshot
    cycles: int


@dataclass(frozen=True)
class SerialTerminalState:
    capture: tuple[int, ...]
    cycles: int


@dataclass(frozen=True)
class MooneyeTerminalState:
    signature: tuple[int, ...]
    cycles: int
    screen_lines: tuple[str, ...] = ()
    assert_block: dict[str, object] | None = None
    last_pc: int = 0
    failure_triplet: tuple[int, int, int] | None = None
    oracle_history: tuple[tuple[int, int, int, int], ...] = ()


class ExternalMemoryBus:
    def __init__(
        self,
        rom_bytes: bytes,
        *,
        enforce_dma_cpu_restrictions: bool = False,
        use_integrated_ppu: bool = False,
    ) -> None:
        self.rom = bytes(rom_bytes)
        self.enforce_dma_cpu_restrictions = enforce_dma_cpu_restrictions
        self.use_integrated_ppu = use_integrated_ppu
        self.cartridge_type = self.rom[CARTRIDGE_TYPE_ADDR] if len(self.rom) > CARTRIDGE_TYPE_ADDR else 0x00
        self.is_mbc1 = self.cartridge_type in MBC1_CART_TYPES
        self.is_mbc3 = self.cartridge_type in MBC3_CART_TYPES
        self.rom_bank_count = max(1, (len(self.rom) + 0x3FFF) // 0x4000)
        ram_size_code = self.rom[CARTRIDGE_RAM_SIZE_ADDR] if len(self.rom) > CARTRIDGE_RAM_SIZE_ADDR else 0x00
        self.cart_ram = bytearray(_cartridge_ram_size_bytes(ram_size_code))
        self.mbc1_ram_enabled = False
        self.mbc1_rom_bank_low5 = 1
        self.mbc1_bank_high2 = 0
        self.mbc1_mode = 0
        self.mbc3_ram_rtc_enabled = False
        self.mbc3_rom_bank = 1
        self.mbc3_ram_rtc_select = 0
        self.mbc3_rtc_regs = {selector: 0 for selector in MBC3_RTC_SELECTS}
        self.mbc3_latched_rtc_regs = dict(self.mbc3_rtc_regs)
        self.mbc3_latch_last = 0
        self.wram = bytearray(0x2000)
        self.vram = bytearray(VRAM_SIZE)
        self.oam = bytearray(OAM_SIZE)
        self.hram = bytearray(0x7F)
        self.ie_reg = 0
        self.if_reg = 0
        self.joyp_select = 0x3
        self.joyp_buttons = 0
        self.sys_counter = 0
        self.tima = 0
        self.tma = 0
        self.tac = 0
        self.serial_sb = 0
        self.serial_sc = 0
        self.serial_cycles_left = 0
        self.serial_inject_value = 0xFF
        self.serial_capture: list[int] = []
        self.sampled_timer_enabled = False
        self.sampled_timer_bit = False
        self.overflow_delay = 0
        self.dma_active = False
        self.dma_source_high = 0
        self.dma_next_index = 0
        self.ppu = PpuReferenceModel()
        self.ppu.reset(ModelProfile.DMG, ResetProfile.SkipBoot)
        self.ppu_event_seq = 0
        self.integrated_ppu_mode = PpuMode.OamScan
        self.integrated_ppu_ly = 0
        self.integrated_ppu_stat = 0x82
        self.integrated_ppu_if_bits = 0
        self._integrated_ppu_vblank_window_high = False
        self._integrated_ppu_stat_window_high = False

    @staticmethod
    def _decode_integrated_ppu_mode(mode_code: int) -> PpuMode:
        return {
            0: PpuMode.LcdOff,
            1: PpuMode.OamScan,
            2: PpuMode.PixelTransfer,
            3: PpuMode.HBlank,
            4: PpuMode.VBlank,
        }.get(int(mode_code), PpuMode.LcdOff)

    def sync_integrated_ppu(self, observation: Any) -> None:
        if not self.use_integrated_ppu:
            return
        self.integrated_ppu_mode = self._decode_integrated_ppu_mode(getattr(observation, "ppu_mode", 0))
        self.integrated_ppu_ly = int(getattr(observation, "ppu_ly", 0)) & 0xFF
        self.integrated_ppu_stat = int(getattr(observation, "ppu_stat", 0x80)) & 0xFF
        vblank_window_high = bool(getattr(observation, "ppu_vblank_req_window", False)) or bool(
            getattr(observation, "ppu_vblank_req", False)
        )
        stat_window_high = bool(getattr(observation, "ppu_stat_req_window", False)) or bool(
            getattr(observation, "ppu_stat_req", False)
        )
        self.integrated_ppu_if_bits = 0
        if vblank_window_high and not self._integrated_ppu_vblank_window_high:
            self.integrated_ppu_if_bits |= VBLANK_IF_BIT
        if stat_window_high and not self._integrated_ppu_stat_window_high:
            self.integrated_ppu_if_bits |= STAT_IF_BIT
        self._integrated_ppu_vblank_window_high = vblank_window_high
        self._integrated_ppu_stat_window_high = stat_window_high

    def _ppu_apply_shadow_write(self, addr: int, value: int) -> None:
        event = self._ppu_mmio_write_event(addr, value)
        if event is None:
            return
        regs = ppu_apply_mmio_write(self.ppu.state.visible.regs, event.kind)
        self.ppu.state = self.ppu.state.__class__(
            visible=self.ppu.state.visible.__class__(regs=regs, ly=self.ppu.state.visible.ly),
            status=self.ppu.state.status,
            sampled=self.ppu.state.sampled,
            render=self.ppu.state.render,
        )

    def _ppu_current_coord(self) -> PpuVideoCoord:
        state = self.ppu.state
        return PpuVideoCoord(frame=0, line=state.visible.ly, dot=state.render.dot_in_line)

    def _ppu_mode(self) -> PpuMode:
        if self.use_integrated_ppu:
            return self.integrated_ppu_mode
        return ppu_visible_mode(self.ppu.state.status)

    def _ppu_lcd_enabled(self) -> bool:
        if self.use_integrated_ppu:
            return bool(self.ppu.state.visible.regs.lcdc.lcd_enable)
        return ppu_lcd_enabled(self.ppu.state.status, self.ppu.state.visible.regs)

    def _ppu_vram_accessible(self) -> bool:
        return (not self._ppu_lcd_enabled()) or self._ppu_mode() is not PpuMode.PixelTransfer

    def _ppu_oam_accessible(self) -> bool:
        return (not self._ppu_lcd_enabled()) or self._ppu_mode() not in (PpuMode.OamScan, PpuMode.PixelTransfer)

    def _ppu_stat_readback(self) -> int:
        if self.use_integrated_ppu:
            return self.integrated_ppu_stat
        regs = self.ppu.state.visible.regs
        ly = self.ppu.state.visible.ly
        if self._ppu_lcd_enabled():
            mode_bits = {
                PpuMode.HBlank: 0,
                PpuMode.VBlank: 1,
                PpuMode.OamScan: 2,
                PpuMode.PixelTransfer: 3,
                PpuMode.LcdOff: 0,
            }[self._ppu_mode()]
            lyc_flag = 1 if ppu_lyc_match(regs, ly) else 0
        else:
            mode_bits = 0
            lyc_flag = 0
        return (
            0x80
            | (int(regs.stat_sel.lyc_sel) << 6)
            | (int(regs.stat_sel.mode2_sel) << 5)
            | (int(regs.stat_sel.mode1_sel) << 4)
            | (int(regs.stat_sel.mode0_sel) << 3)
            | (lyc_flag << 2)
            | mode_bits
        ) & 0xFF

    def _ppu_mmio_read(self, addr: int) -> int:
        regs = self.ppu.state.visible.regs
        if addr == LCDC_ADDR:
            return (
                (int(regs.lcdc.lcd_enable) << 7)
                | (int(regs.lcdc.win_map_hi) << 6)
                | (int(regs.lcdc.win_enable) << 5)
                | (int(regs.lcdc.bgwin_data_hi) << 4)
                | (int(regs.lcdc.bg_map_hi) << 3)
                | (int(regs.lcdc.obj_size_8x16) << 2)
                | (int(regs.lcdc.obj_enable) << 1)
                | int(regs.lcdc.bg_enable)
            ) & 0xFF
        if addr == STAT_ADDR:
            return self._ppu_stat_readback()
        if addr == SCY_ADDR:
            return regs.scy & 0xFF
        if addr == SCX_ADDR:
            return regs.scx & 0xFF
        if addr == LY_ADDR:
            if self.use_integrated_ppu:
                return self.integrated_ppu_ly
            return self.ppu.state.visible.ly & 0xFF
        if addr == LYC_ADDR:
            return regs.lyc & 0xFF
        if addr == BGP_ADDR:
            return regs.bgp & 0xFF
        if addr == OBP0_ADDR:
            return regs.obp0 & 0xFF
        if addr == OBP1_ADDR:
            return regs.obp1 & 0xFF
        if addr == WY_ADDR:
            return regs.wy & 0xFF
        if addr == WX_ADDR:
            return regs.wx & 0xFF
        return 0xFF

    def integrated_ppu_mmio_read_from_observation(self, observation: Any, addr: int) -> int:
        if not self.use_integrated_ppu:
            return self._ppu_mmio_read(addr)
        if addr == STAT_ADDR:
            return int(getattr(observation, "ppu_stat", 0x80)) & 0xFF
        if addr == LY_ADDR:
            return int(getattr(observation, "ppu_ly", 0)) & 0xFF
        return self._ppu_mmio_read(addr)

    def integrated_ppu_cpu_read_from_observation(self, observation: Any, addr: int) -> int:
        if not self.use_integrated_ppu:
            return self.read(addr)
        addr &= 0xFFFF
        if not self._integrated_ppu_cpu_access_allows_from_observation(observation, addr):
            return 0xFF
        return self._raw_read(addr)

    def _integrated_ppu_cpu_access_allows_from_observation(self, observation: Any, addr: int) -> bool:
        addr &= 0xFFFF
        if self._dma_blocks_cpu_addr(addr):
            return False
        mode = self._decode_integrated_ppu_mode(getattr(observation, "ppu_mode", 0))
        lcd_is_enabled = bool(self.ppu.state.visible.regs.lcdc.lcd_enable)
        if lcd_is_enabled:
            if VRAM_BASE <= addr < VRAM_BASE + VRAM_SIZE and mode is PpuMode.PixelTransfer:
                return False
            if OAM_BASE <= addr < OAM_BASE + OAM_SIZE and mode in (PpuMode.OamScan, PpuMode.PixelTransfer):
                return False
        return True

    def integrated_ppu_cpu_write_from_observation(self, observation: Any, addr: int, value: int) -> None:
        if not self.use_integrated_ppu:
            self.write(addr, value)
            return
        addr &= 0xFFFF
        value &= 0xFF
        if VRAM_BASE <= addr < VRAM_BASE + VRAM_SIZE:
            if self._integrated_ppu_cpu_access_allows_from_observation(observation, addr):
                self.vram[addr - VRAM_BASE] = value
            return
        if OAM_BASE <= addr < OAM_BASE + OAM_SIZE:
            if self._integrated_ppu_cpu_access_allows_from_observation(observation, addr):
                self.oam[addr - OAM_BASE] = value
            return
        self.write(addr, value)

    def write_video_direct(self, addr: int, value: int) -> None:
        addr &= 0xFFFF
        value &= 0xFF
        if VRAM_BASE <= addr < VRAM_BASE + VRAM_SIZE:
            self.vram[addr - VRAM_BASE] = value
        elif OAM_BASE <= addr < OAM_BASE + OAM_SIZE:
            self.oam[addr - OAM_BASE] = value

    def _ppu_mmio_write_event(self, addr: int, value: int) -> PpuTimedEvent | None:
        target = {
            LCDC_ADDR: PpuMmioReg.Lcdc,
            STAT_ADDR: PpuMmioReg.Stat,
            SCY_ADDR: PpuMmioReg.Scy,
            SCX_ADDR: PpuMmioReg.Scx,
            LYC_ADDR: PpuMmioReg.Lyc,
            BGP_ADDR: PpuMmioReg.Bgp,
            OBP0_ADDR: PpuMmioReg.Obp0,
            OBP1_ADDR: PpuMmioReg.Obp1,
            WY_ADDR: PpuMmioReg.Wy,
            WX_ADDR: PpuMmioReg.Wx,
        }.get(addr)
        if target is None:
            return None
        return PpuTimedEvent(
            seq=self.ppu_event_seq,
            at=self._ppu_current_coord(),
            kind=PpuMmioWrite(target=target, value=value & 0xFF),
        )

    def _ppu_step_mcycle(self, *, write_en: bool, write_addr: int, write_data: int, preview: bool) -> int:
        if self.use_integrated_ppu:
            return 0
        state = self.ppu.state
        event = self._ppu_mmio_write_event(write_addr, write_data) if write_en else None
        irq_bits = 0
        for dot_index in range(4):
            output = ppu_step_dot(
                state,
                PpuDotInput(bus_events=((event,) if event is not None and dot_index == 0 else ())),
            )
            if output.irq_req.vblank_req:
                irq_bits |= VBLANK_IF_BIT
            if output.irq_req.stat_req:
                irq_bits |= STAT_IF_BIT
            state = output.next_state
        if not preview:
            self.ppu.state = state
            if event is not None:
                self.ppu_event_seq += 1
        return irq_bits

    def _dma_blocks_cpu_addr(self, addr: int) -> bool:
        if not self.enforce_dma_cpu_restrictions:
            return False
        if not self.dma_active:
            return False
        if addr < 0x8000:
            return False
        if 0xFF00 <= addr <= 0xFF7F:
            return False
        if 0xFF80 <= addr <= 0xFFFE:
            return False
        return True

    def _raw_read(self, addr: int) -> int:
        addr &= 0xFFFF
        if addr < 0x8000:
            return self._cart_rom_read(addr)
        if VRAM_BASE <= addr < VRAM_BASE + VRAM_SIZE:
            return self.vram[addr - VRAM_BASE]
        if 0xA000 <= addr <= 0xBFFF:
            return self._cart_ram_read(addr)
        if 0xC000 <= addr <= 0xDFFF:
            return self.wram[addr - 0xC000]
        if OAM_BASE <= addr < OAM_BASE + OAM_SIZE:
            return self.oam[addr - OAM_BASE]
        if addr == JOYP_ADDR:
            return self._joyp_visible()
        if addr == SB_ADDR:
            return self.serial_sb & 0xFF
        if addr == SC_ADDR:
            return self.serial_sc & 0xFF
        if addr == DIV_ADDR:
            return (self.sys_counter >> 8) & 0xFF
        if addr == TIMA_ADDR:
            return self.tima
        if addr == TMA_ADDR:
            return self.tma
        if addr == TAC_ADDR:
            return self.tac & 0x7
        if addr == DMA_ADDR:
            return self.dma_source_high & 0xFF
        if LCDC_ADDR <= addr <= WX_ADDR and addr != DMA_ADDR:
            return self._ppu_mmio_read(addr)
        if addr == IF_ADDR:
            return self.if_reg & 0x1F
        if 0xFF80 <= addr <= 0xFFFE:
            return self.hram[addr - 0xFF80]
        if addr == IE_ADDR:
            return self.ie_reg & 0x1F
        return 0xFF

    def _dma_copy_byte(self, index: int) -> None:
        source_addr = ((self.dma_source_high & 0xFF) << 8) | (index & 0xFF)
        self.oam[index & 0xFF] = self._raw_read(source_addr)

    def _start_dma(self, source_high: int) -> None:
        self.dma_active = True
        self.dma_source_high = source_high & 0xFF
        self.dma_next_index = 0
        self._dma_copy_byte(self.dma_next_index)
        self.dma_next_index += 1

    def _advance_dma(self) -> None:
        if not self.dma_active:
            return
        if self.dma_next_index >= OAM_SIZE:
            self.dma_active = False
            self.dma_next_index = 0
            return
        self._dma_copy_byte(self.dma_next_index)
        self.dma_next_index += 1
        if self.dma_next_index >= OAM_SIZE:
            self.dma_active = False
            self.dma_next_index = 0

    def _rom_bank_value(self) -> int:
        bank = self.mbc1_rom_bank_low5 & 0x1F
        return bank if bank != 0 else 1

    def _rom_bank_index(self, bank: int) -> int:
        return bank % self.rom_bank_count if self.rom_bank_count > 0 else 0

    def _mbc1_lower_rom_bank(self) -> int:
        if not self.is_mbc1:
            return 0
        if self.mbc1_mode == 0:
            return 0
        return self._rom_bank_index((self.mbc1_bank_high2 & 0x03) << 5)

    def _mbc1_upper_rom_bank(self) -> int:
        if not self.is_mbc1:
            return self._rom_bank_index(1)
        raw_bank = ((self.mbc1_bank_high2 & 0x03) << 5) | self._rom_bank_value()
        return self._rom_bank_index(raw_bank)

    def _mbc1_ram_bank(self) -> int:
        if not self.is_mbc1 or len(self.cart_ram) == 0:
            return 0
        bank_count = max(1, len(self.cart_ram) // MBC1_RAM_BANK_SIZE)
        raw_bank = (self.mbc1_bank_high2 & 0x03) if self.mbc1_mode == 1 else 0
        return raw_bank % bank_count

    def _cart_rom_read(self, addr: int) -> int:
        if not self.is_mbc1 and not self.is_mbc3:
            return self.rom[addr] if addr < len(self.rom) else 0xFF

        if self.is_mbc3:
            if addr < 0x4000:
                rom_addr = addr
            else:
                bank = self._rom_bank_index(self.mbc3_rom_bank & 0x7F)
                rom_addr = (bank * 0x4000) + (addr - 0x4000)
            return self.rom[rom_addr] if rom_addr < len(self.rom) else 0xFF

        if addr < 0x4000:
            bank = self._mbc1_lower_rom_bank()
            rom_addr = (bank * 0x4000) + addr
            return self.rom[rom_addr] if rom_addr < len(self.rom) else 0xFF

        bank = self._mbc1_upper_rom_bank()
        rom_addr = (bank * 0x4000) + (addr - 0x4000)
        return self.rom[rom_addr] if rom_addr < len(self.rom) else 0xFF

    def _cart_ram_read(self, addr: int) -> int:
        if self.is_mbc3:
            if not self.mbc3_ram_rtc_enabled:
                return 0xFF
            if self.mbc3_ram_rtc_select in MBC3_RTC_SELECTS:
                return self.mbc3_latched_rtc_regs[self.mbc3_ram_rtc_select] & 0xFF
            if len(self.cart_ram) == 0:
                return 0xFF
            bank_count = max(1, len(self.cart_ram) // MBC1_RAM_BANK_SIZE)
            ram_bank = (self.mbc3_ram_rtc_select & 0x03) % bank_count
            ram_addr = (ram_bank * MBC1_RAM_BANK_SIZE) + (addr - 0xA000)
            return self.cart_ram[ram_addr] if ram_addr < len(self.cart_ram) else 0xFF

        if len(self.cart_ram) == 0 or not self.mbc1_ram_enabled:
            return 0xFF
        ram_addr = (self._mbc1_ram_bank() * MBC1_RAM_BANK_SIZE) + (addr - 0xA000)
        return self.cart_ram[ram_addr] if ram_addr < len(self.cart_ram) else 0xFF

    def _cart_write(self, addr: int, value: int) -> None:
        if self.is_mbc3:
            if 0x0000 <= addr <= 0x1FFF:
                self.mbc3_ram_rtc_enabled = (value & 0x0F) == 0x0A
            elif 0x2000 <= addr <= 0x3FFF:
                bank = value & 0x7F
                self.mbc3_rom_bank = bank if bank != 0 else 1
            elif 0x4000 <= addr <= 0x5FFF:
                self.mbc3_ram_rtc_select = value & 0x0F
            elif 0x6000 <= addr <= 0x7FFF:
                next_latch = value & 0x01
                if self.mbc3_latch_last == 0 and next_latch == 1:
                    self.mbc3_latched_rtc_regs = dict(self.mbc3_rtc_regs)
                self.mbc3_latch_last = next_latch
            elif 0xA000 <= addr <= 0xBFFF and self.mbc3_ram_rtc_enabled:
                if self.mbc3_ram_rtc_select in MBC3_RTC_SELECTS:
                    self.mbc3_rtc_regs[self.mbc3_ram_rtc_select] = value & 0xFF
                elif len(self.cart_ram) > 0:
                    bank_count = max(1, len(self.cart_ram) // MBC1_RAM_BANK_SIZE)
                    ram_bank = (self.mbc3_ram_rtc_select & 0x03) % bank_count
                    ram_addr = (ram_bank * MBC1_RAM_BANK_SIZE) + (addr - 0xA000)
                    if ram_addr < len(self.cart_ram):
                        self.cart_ram[ram_addr] = value
            return

        if not self.is_mbc1:
            return
        if 0x0000 <= addr <= 0x1FFF:
            self.mbc1_ram_enabled = (value & 0x0F) == 0x0A
        elif 0x2000 <= addr <= 0x3FFF:
            self.mbc1_rom_bank_low5 = value & 0x1F
        elif 0x4000 <= addr <= 0x5FFF:
            self.mbc1_bank_high2 = value & 0x03
        elif 0x6000 <= addr <= 0x7FFF:
            self.mbc1_mode = value & 0x01
        elif 0xA000 <= addr <= 0xBFFF and len(self.cart_ram) > 0 and self.mbc1_ram_enabled:
            ram_addr = (self._mbc1_ram_bank() * MBC1_RAM_BANK_SIZE) + (addr - 0xA000)
            if ram_addr < len(self.cart_ram):
                self.cart_ram[ram_addr] = value

    def _joyp_low_nibble(self) -> int:
        low_nibble = 0x0F
        if (self.joyp_select & 0x1) == 0:
            if self.joyp_buttons & (1 << 4):
                low_nibble &= ~0x01
            if self.joyp_buttons & (1 << 5):
                low_nibble &= ~0x02
            if self.joyp_buttons & (1 << 7):
                low_nibble &= ~0x04
            if self.joyp_buttons & (1 << 6):
                low_nibble &= ~0x08
        if (self.joyp_select & 0x2) == 0:
            if self.joyp_buttons & (1 << 3):
                low_nibble &= ~0x01
            if self.joyp_buttons & (1 << 2):
                low_nibble &= ~0x02
            if self.joyp_buttons & (1 << 0):
                low_nibble &= ~0x04
            if self.joyp_buttons & (1 << 1):
                low_nibble &= ~0x08
        return low_nibble

    def _joyp_visible(self) -> int:
        return 0xC0 | ((self.joyp_select & 0x3) << 4) | self._joyp_low_nibble()

    def apply_stimulus(self, stimulus: SimStimulus) -> int:
        if stimulus.serial_inject is not None:
            self.serial_inject_value = stimulus.serial_inject & 0xFF
        if stimulus.joyp_buttons is None:
            return 0
        next_buttons = 0
        for bit, name in enumerate(reversed(("up", "down", "left", "right", "a", "b", "start", "select"))):
            next_buttons |= int(bool(getattr(stimulus.joyp_buttons, name))) << bit
        fresh_press = next_buttons & ~self.joyp_buttons
        self.joyp_buttons = next_buttons & 0xFF
        return JOYPAD_IF_BIT if fresh_press else 0

    def read(self, addr: int) -> int:
        addr &= 0xFFFF
        if self._dma_blocks_cpu_addr(addr):
            return 0xFF
        if VRAM_BASE <= addr < VRAM_BASE + VRAM_SIZE and not self._ppu_vram_accessible():
            return 0xFF
        if OAM_BASE <= addr < OAM_BASE + OAM_SIZE and not self._ppu_oam_accessible():
            return 0xFF
        return self._raw_read(addr)

    def write(self, addr: int, value: int) -> None:
        addr &= 0xFFFF
        value &= 0xFF
        if self._dma_blocks_cpu_addr(addr):
            return
        if (self.is_mbc1 or self.is_mbc3) and (addr < 0x8000 or 0xA000 <= addr <= 0xBFFF):
            self._cart_write(addr, value)
        elif VRAM_BASE <= addr < VRAM_BASE + VRAM_SIZE:
            if self._ppu_vram_accessible():
                self.vram[addr - VRAM_BASE] = value
        elif 0xC000 <= addr <= 0xDFFF:
            self.wram[addr - 0xC000] = value
        elif OAM_BASE <= addr < OAM_BASE + OAM_SIZE:
            if self._ppu_oam_accessible():
                self.oam[addr - OAM_BASE] = value
        elif addr == JOYP_ADDR:
            self.joyp_select = (value >> 4) & 0x3
        elif addr == SB_ADDR:
            self.serial_sb = value & 0xFF
        elif addr == SC_ADDR:
            self.serial_sc = value & 0x83
            if (self.serial_sc & 0x81) == 0x81:
                self.serial_cycles_left = 8
                self.serial_capture.append(self.serial_sb & 0xFF)
        elif addr == DMA_ADDR:
            self._start_dma(value)
        elif LCDC_ADDR <= addr <= WX_ADDR and addr != DMA_ADDR:
            return
        elif 0xFF80 <= addr <= 0xFFFE:
            self.hram[addr - 0xFF80] = value

    def next_if_set_bits(self, *, write_en: bool, write_addr: int, write_data: int) -> int:
        effective_sys_counter = 0 if write_en and write_addr == DIV_ADDR else self.sys_counter
        write_tima = write_en and write_addr == TIMA_ADDR
        write_tma = write_en and write_addr == TMA_ADDR
        write_tac = write_en and write_addr == TAC_ADDR

        next_tma = write_data if write_tma else self.tma
        next_tac = (write_data & 0x7) if write_tac else self.tac
        next_sampled_timer_enabled = _tac_enabled(next_tac)
        next_sampled_timer_bit = _timer_bit(effective_sys_counter, next_tac)
        timer_tick = (
            self.sampled_timer_enabled
            and next_sampled_timer_enabled
            and self.sampled_timer_bit
            and not next_sampled_timer_bit
        )

        if write_tima:
            next_timer_irq = False
        elif self.overflow_delay == 1:
            next_timer_irq = True
        else:
            next_timer_irq = False
            if self.overflow_delay == 0 and timer_tick and self.tima == 0xFF:
                next_timer_irq = False

        next_serial_irq = self.serial_cycles_left == 1 and (self.serial_sc & 0x81) == 0x81
        ppu_if_bits = self._ppu_step_mcycle(
            write_en=write_en,
            write_addr=write_addr,
            write_data=write_data,
            preview=True,
        )
        return (TIMER_IF_BIT if next_timer_irq else 0) | (SERIAL_IF_BIT if next_serial_irq else 0) | ppu_if_bits

    def advance_cycle(
        self,
        *,
        write_en: bool,
        write_addr: int,
        write_data: int,
        if_set_bits: int,
        irq_ack_valid: bool,
        irq_ack_bit: int,
    ) -> None:
        write_div = write_en and write_addr == DIV_ADDR
        write_tima = write_en and write_addr == TIMA_ADDR
        write_tma = write_en and write_addr == TMA_ADDR
        write_tac = write_en and write_addr == TAC_ADDR
        write_if = write_en and write_addr == IF_ADDR
        write_ie = write_en and write_addr == IE_ADDR

        effective_sys_counter = 0 if write_div else self.sys_counter
        next_tma = write_data if write_tma else self.tma
        next_tac = (write_data & 0x7) if write_tac else self.tac
        next_sampled_timer_enabled = _tac_enabled(next_tac)
        next_sampled_timer_bit = _timer_bit(effective_sys_counter, next_tac)
        timer_tick = (
            self.sampled_timer_enabled
            and next_sampled_timer_enabled
            and self.sampled_timer_bit
            and not next_sampled_timer_bit
        )

        if write_tima:
            next_tima = write_data & 0xFF
            next_overflow_delay = 0
        elif self.overflow_delay == 1:
            next_tima = next_tma
            next_overflow_delay = 0
        elif self.overflow_delay > 1:
            next_tima = self.tima
            next_overflow_delay = self.overflow_delay - 1
        elif timer_tick:
            if self.tima == 0xFF:
                next_tima = 0
                next_overflow_delay = 4
            else:
                next_tima = (self.tima + 1) & 0xFF
                next_overflow_delay = 0
        else:
            next_tima = self.tima
            next_overflow_delay = 0

        self.tima = next_tima & 0xFF
        self.tma = next_tma & 0xFF
        self.tac = next_tac & 0x7
        if self.serial_cycles_left > 0 and (self.serial_sc & 0x81) == 0x81:
            self.serial_cycles_left -= 1
            if self.serial_cycles_left == 0:
                self.serial_sb = self.serial_inject_value & 0xFF
                self.serial_sc &= 0x7F
        self.sampled_timer_enabled = next_sampled_timer_enabled
        self.sampled_timer_bit = next_sampled_timer_bit
        self.overflow_delay = next_overflow_delay
        self.sys_counter = 4 if write_div else (self.sys_counter + 4) & 0xFFFF_FFFF
        if self.use_integrated_ppu:
            if write_en and LCDC_ADDR <= write_addr <= WX_ADDR and write_addr != DMA_ADDR:
                self._ppu_apply_shadow_write(write_addr, write_data)
            ppu_if_bits = self.integrated_ppu_if_bits
        else:
            ppu_if_bits = self._ppu_step_mcycle(
                write_en=write_en,
                write_addr=write_addr,
                write_data=write_data,
                preview=False,
            )
        self._advance_dma()

        ack_mask = _ack_mask(irq_ack_valid, irq_ack_bit)
        cpu_written_ie = (write_data & 0x1F) if write_ie else self.ie_reg
        cpu_written_if = (write_data & 0x1F) if write_if else self.if_reg
        self.ie_reg = cpu_written_ie & 0x1F
        if self.use_integrated_ppu:
            ppu_if_bits &= ~ack_mask
        self.if_reg = ((cpu_written_if & ~ack_mask) | if_set_bits | ppu_if_bits) & 0x1F

    def abi_snapshot(self) -> AbiSnapshot:
        base = ABI_SIGNATURE_BASE - 0xC000
        log_base = ABI_LOG_BASE - 0xC000
        return AbiSnapshot(
            signature=bytes(self.wram[base : base + ABI_SIGNATURE_SIZE]),
            log=bytes(self.wram[log_base : log_base + ABI_LOG_SIZE]),
        )


def load_manifest_entry(rom_id: str) -> RomManifestEntry:
    payload = yaml.safe_load(ROM_MANIFEST_PATH.read_text(encoding="utf-8"))
    roms = payload.get("roms", []) if isinstance(payload, dict) else []
    for entry in roms:
        if isinstance(entry, dict) and str(entry.get("id")) == rom_id:
            rom_path = ROOT / str(entry["path"])
            return RomManifestEntry(
                rom_id=rom_id,
                rom_path=rom_path,
                sym_path=rom_path.with_suffix(".sym"),
                profiles=SimulationProfiles.from_mapping(entry),
                timeout_commits=int(entry["timeout_commits"]),
                checkpoint_symbols=tuple(str(label) for label in entry.get("checkpoint_symbols", [])),
                manifest_entry=dict(entry),
            )
    raise KeyError(f"Unknown ROM id: {rom_id}")


def build_manifest(entry: RomManifestEntry) -> HookManifest:
    return build_hook_manifest(entry.sym_path, checkpoint_symbols=entry.checkpoint_symbols)


def load_symbol_table(entry: RomManifestEntry) -> SymbolTable:
    return SymbolTable.load(entry.sym_path)


def _merge_stimulus(base: SimStimulus, *, if_set_bits: int) -> SimStimulus:
    return SimStimulus(
        joyp_buttons=base.joyp_buttons,
        if_set_bits=(base.if_set_bits | if_set_bits) & 0x1F,
        if_clear_bits=base.if_clear_bits,
        ie_override=base.ie_override,
        dma_start=base.dma_start,
        serial_inject=base.serial_inject,
        freeze_arch_time=base.freeze_arch_time,
        cpu_hold_only=base.cpu_hold_only,
    )


@dataclass
class _ScriptedJoypadOracleState:
    buttons: int = 0
    if_bits: int = 0
    event_index: int = 0

    def advance(self, event_schedule: Any) -> None:
        stimulus = stimulus_from_events(event_schedule.events_for_commit(self.event_index))
        self.event_index += 1
        if stimulus.joyp_buttons is None:
            self.if_bits = 0
            return
        next_buttons = 0
        for bit, name in enumerate(reversed(("up", "down", "left", "right", "a", "b", "start", "select"))):
            next_buttons |= int(bool(getattr(stimulus.joyp_buttons, name))) << bit
        fresh_press = next_buttons & ~self.buttons
        self.buttons = next_buttons & 0xFF
        self.if_bits = JOYPAD_IF_BIT if fresh_press else 0

    def joyp_read(self, *, directions_selected: bool) -> int:
        low_nibble = 0x0F
        if directions_selected:
            if self.buttons & (1 << 4):
                low_nibble &= ~0x01
            if self.buttons & (1 << 5):
                low_nibble &= ~0x02
            if self.buttons & (1 << 7):
                low_nibble &= ~0x04
            if self.buttons & (1 << 6):
                low_nibble &= ~0x08
            return 0xE0 | low_nibble
        if self.buttons & (1 << 3):
            low_nibble &= ~0x01
        if self.buttons & (1 << 2):
            low_nibble &= ~0x02
        if self.buttons & (1 << 0):
            low_nibble &= ~0x04
        if self.buttons & (1 << 1):
            low_nibble &= ~0x08
        return 0xD0 | low_nibble


def _labels_from_commit(commit: Any) -> tuple[str, ...]:
    label = getattr(commit, "label", None)
    if label is None:
        return ()
    return tuple(part for part in str(label).split("|") if part)


def _read_oracle_abi_snapshot(oracle: PyBoyOracle) -> AbiSnapshot:
    signature = bytes(oracle.read_mem(ABI_SIGNATURE_BASE + offset) for offset in range(ABI_SIGNATURE_SIZE))
    log = bytes(oracle.read_mem(ABI_LOG_BASE + offset) for offset in range(ABI_LOG_SIZE))
    return AbiSnapshot(signature=signature, log=log)


def _read_pyboy_abi_snapshot(pyboy: PyBoy) -> AbiSnapshot:
    signature = bytes(int(pyboy.memory[ABI_SIGNATURE_BASE + offset]) for offset in range(ABI_SIGNATURE_SIZE))
    log = bytes(int(pyboy.memory[ABI_LOG_BASE + offset]) for offset in range(ABI_LOG_SIZE))
    return AbiSnapshot(signature=signature, log=log)


def _install_scripted_joypad_hooks(oracle: PyBoyOracle, entry: RomManifestEntry, event_schedule: Any) -> None:
    symbols = load_symbol_table(entry)
    checkpoint_addr = symbols.lookup("__checkpoint_poll").addr
    dir_read_addr = symbols.lookup("__joyp_dir_after_read").addr
    button_read_addr = symbols.lookup("__joyp_button_after_read").addr
    if_read_addr = symbols.lookup("__joyp_if_after_read").addr
    state = _ScriptedJoypadOracleState()

    def checkpoint_callback(_resolved: Any) -> None:
        state.advance(event_schedule)

    def dir_callback(_resolved: Any) -> None:
        pyboy = oracle._pyboy
        if pyboy is None:
            raise RuntimeError("PyBoy oracle unexpectedly closed during joypad callback")
        pyboy.register_file.A = state.joyp_read(directions_selected=True)

    def button_callback(_resolved: Any) -> None:
        pyboy = oracle._pyboy
        if pyboy is None:
            raise RuntimeError("PyBoy oracle unexpectedly closed during joypad callback")
        pyboy.register_file.A = state.joyp_read(directions_selected=False)

    def if_callback(_resolved: Any) -> None:
        pyboy = oracle._pyboy
        if pyboy is None:
            raise RuntimeError("PyBoy oracle unexpectedly closed during joypad callback")
        pyboy.register_file.A = state.if_bits

    for addr, callback in (
        (checkpoint_addr, checkpoint_callback),
        (dir_read_addr, dir_callback),
        (button_read_addr, button_callback),
        (if_read_addr, if_callback),
    ):
        oracle.register_runtime_hook(bank=0, addr=addr, callback=callback)


def _trace_bus_read_data(trace: Any, memory: ExternalMemoryBus) -> int:
    if int(getattr(trace, "bus_req_kind", BUS_REQ_IDLE)) != BUS_REQ_READ:
        return 0
    return memory.read(int(getattr(trace, "bus_req_addr", 0)))


def _apply_bus_write(trace: Any, memory: ExternalMemoryBus) -> None:
    if int(getattr(trace, "bus_req_kind", BUS_REQ_IDLE)) != BUS_REQ_WRITE:
        return
    memory.write(
        int(getattr(trace, "bus_req_addr", 0)),
        int(getattr(trace, "bus_req_data", 0)),
    )


async def _soc_step_to_commit(driver: Any, memory: ExternalMemoryBus) -> tuple[Any, int, int, int, Any | None, bool | None]:
    from cocotb.triggers import ClockCycles

    observe = getattr(driver, "observe_rom", driver.observe)
    step_mcycle = getattr(driver, "step_mcycle_rom", driver.step_mcycle)
    video_debug = os.environ.get("ICEBOY_SOC_ROM_VIDEO_DEBUG", "").strip().lower() not in {"", "0", "false", "no", "off"}
    prefinal_observation = None
    mid_observation = None
    obs_t0 = observe()
    memory.sync_integrated_ppu(obs_t0)

    def video_access_observation(kind: int, addr: int) -> Any:
        mode_t0 = int(getattr(obs_t0, "ppu_mode", 0))
        ly_t0 = int(getattr(obs_t0, "ppu_ly", 0))
        if ly_t0 == 0 or mid_observation is None:
            return obs_t0
        if kind == BUS_REQ_READ:
            if OAM_BASE <= addr < OAM_BASE + OAM_SIZE and mode_t0 == 0:
                return mid_observation
            if VRAM_BASE <= addr < VRAM_BASE + VRAM_SIZE and mode_t0 == 1:
                return mid_observation
        if kind == BUS_REQ_WRITE:
            if OAM_BASE <= addr < OAM_BASE + OAM_SIZE and mode_t0 == 1:
                return mid_observation
        return obs_t0

    def video_write_allowed(addr: int) -> bool | None:
        if not memory.use_integrated_ppu:
            return None
        if not (VRAM_BASE <= addr < VRAM_BASE + VRAM_SIZE or OAM_BASE <= addr < OAM_BASE + OAM_SIZE):
            return None
        mode_t0 = int(getattr(obs_t0, "ppu_mode", 0))
        ly_t0 = int(getattr(obs_t0, "ppu_ly", 0))
        mode_mid = int(getattr(mid_observation, "ppu_mode", mode_t0))
        if VRAM_BASE <= addr < VRAM_BASE + VRAM_SIZE:
            return mode_t0 != 2
        if ly_t0 == 0:
            return mode_t0 in {0, 3}
        if mode_t0 in {0, 3}:
            return True
        if mode_t0 == 1:
            return mode_mid == 2
        return False

    def pending_inputs(observation: Any) -> tuple[int, int, int, int, int, int, Any | None, bool | None]:
        if all(
            hasattr(observation, name)
            for name in ("preview_bus_req_kind", "preview_bus_req_addr", "preview_bus_req_data")
        ):
            preview_kind = int(getattr(observation, "preview_bus_req_kind", BUS_REQ_IDLE))
            preview_addr = int(getattr(observation, "preview_bus_req_addr", 0))
            preview_data = int(getattr(observation, "preview_bus_req_data", 0))
        else:
            preview_kind, preview_addr, preview_data = soc_preview_bus_req(driver)
        video_sample = None
        write_allowed = None
        live_if_bits = (memory.if_reg | memory.integrated_ppu_if_bits) & 0x1F
        if preview_kind == BUS_REQ_READ:
            if preview_addr == IF_ADDR:
                bus_read_data = live_if_bits
            elif (
                memory.use_integrated_ppu
                and LCDC_ADDR <= preview_addr <= WX_ADDR
                and preview_addr != DMA_ADDR
            ):
                bus_read_data = memory.integrated_ppu_mmio_read_from_observation(obs_t0, preview_addr)
            elif memory.use_integrated_ppu and (
                VRAM_BASE <= preview_addr < VRAM_BASE + VRAM_SIZE
                or OAM_BASE <= preview_addr < OAM_BASE + OAM_SIZE
            ):
                video_sample = video_access_observation(preview_kind, preview_addr)
                bus_read_data = memory.integrated_ppu_cpu_read_from_observation(
                    video_sample,
                    preview_addr,
                )
            else:
                bus_read_data = memory.read(preview_addr)
        else:
            bus_read_data = 0
            if memory.use_integrated_ppu and (
                VRAM_BASE <= preview_addr < VRAM_BASE + VRAM_SIZE
                or OAM_BASE <= preview_addr < OAM_BASE + OAM_SIZE
            ):
                video_sample = video_access_observation(preview_kind, preview_addr)
                write_allowed = video_write_allowed(preview_addr)
        return (
            preview_kind,
            preview_addr,
            preview_data,
            bus_read_data & 0xFF,
            memory.if_reg & 0x1F,
            memory.ie_reg & 0x1F,
            video_sample,
            write_allowed,
        )

    skip_to_prefinal = 3 if bool(getattr(obs_t0, "m_ce", False)) else max(0, 2 - int(getattr(obs_t0, "t_index", 0)))
    preview_kind, preview_addr, preview_data, bus_read_data, if_reg, ie_reg, video_sample, write_allowed = pending_inputs(obs_t0)
    if skip_to_prefinal > 0:
        driver.inject_stimulus(SimStimulus.idle())
        driver.set_bus_inputs(bus_read_data=bus_read_data, irq_pending=0, if_reg=if_reg, ie_reg=ie_reg)
        await ClockCycles(driver.dut.clk_i, 1)
        mid_observation = observe()
        if skip_to_prefinal > 1:
            await ClockCycles(driver.dut.clk_i, skip_to_prefinal - 1)
            prefinal_observation = observe()
        else:
            prefinal_observation = mid_observation
        preview_kind, preview_addr, preview_data, bus_read_data, if_reg, ie_reg, video_sample, write_allowed = pending_inputs(prefinal_observation)
    if (
        video_debug
        and preview_kind in {BUS_REQ_READ, BUS_REQ_WRITE}
        and (
            VRAM_BASE <= preview_addr < VRAM_BASE + VRAM_SIZE
            or OAM_BASE <= preview_addr < OAM_BASE + OAM_SIZE
        )
    ):
        print(
            "soc-rom-video",
            {
                "kind": "write" if preview_kind == BUS_REQ_WRITE else "read",
                "addr": hex(preview_addr),
                "data": hex(preview_data),
                "bus_read_data": hex(bus_read_data),
                "start_mode": int(getattr(obs_t0, "ppu_mode", 0)),
                "start_ly": int(getattr(obs_t0, "ppu_ly", 0)),
                "start_stat": hex(int(getattr(obs_t0, "ppu_stat", 0))),
                "mid_mode": int(getattr(mid_observation, "ppu_mode", getattr(obs_t0, "ppu_mode", 0))),
                "mid_ly": int(getattr(mid_observation, "ppu_ly", getattr(obs_t0, "ppu_ly", 0))),
                "mid_stat": hex(int(getattr(mid_observation, "ppu_stat", getattr(obs_t0, "ppu_stat", 0)))),
                "prefinal_mode": int(getattr(prefinal_observation, "ppu_mode", getattr(obs_t0, "ppu_mode", 0))),
                "prefinal_ly": int(getattr(prefinal_observation, "ppu_ly", getattr(obs_t0, "ppu_ly", 0))),
                "prefinal_stat": hex(int(getattr(prefinal_observation, "ppu_stat", getattr(obs_t0, "ppu_stat", 0)))),
            },
            flush=True,
        )
    post = await step_mcycle(
        stimulus=SimStimulus.idle(),
        bus_read_data=bus_read_data,
        irq_pending=0,
        if_reg=if_reg,
        ie_reg=ie_reg,
    )
    memory.sync_integrated_ppu(post)
    return post, preview_kind, preview_addr, preview_data, video_sample, write_allowed


async def run_dut_to_abi_result(
    driver: Any,
    *,
    rom_bytes: bytes,
    max_mcycles: int,
    checkpoint_addr: int | None = None,
    event_schedule: Any | None = None,
) -> DutTerminalState:
    from cocotb.triggers import Timer

    memory = ExternalMemoryBus(rom_bytes)
    event_index = 0
    await Timer(1, units="ns")
    for cycle in range(1, max_mcycles + 1):
        trace = driver.observe()
        bus_read_data = _trace_bus_read_data(trace, memory)
        write_en = int(getattr(trace, "bus_req_kind", BUS_REQ_IDLE)) == BUS_REQ_WRITE
        write_addr = int(getattr(trace, "bus_req_addr", 0)) if write_en else 0
        write_data = int(getattr(trace, "bus_req_data", 0)) if write_en else 0
        if_set_bits = memory.next_if_set_bits(write_en=write_en, write_addr=write_addr, write_data=write_data)
        checkpoint_hit = (
            checkpoint_addr is not None
            and int(getattr(trace, "bus_req_kind", BUS_REQ_IDLE)) == BUS_REQ_READ
            and int(getattr(trace, "bus_req_addr", 0)) == checkpoint_addr
        )
        scripted_stimulus = (
            stimulus_from_events(event_schedule.events_for_commit(event_index))
            if checkpoint_hit and event_schedule is not None
            else SimStimulus.idle()
        )
        joypad_if_set_bits = memory.apply_stimulus(scripted_stimulus)

        await driver.step_mcycle(
            stimulus=_merge_stimulus(scripted_stimulus, if_set_bits=if_set_bits | joypad_if_set_bits),
            bus_read_data=bus_read_data,
            irq_pending=0,
        )
        if checkpoint_hit and event_schedule is not None:
            event_index += 1
        if write_en and not (DIV_ADDR <= write_addr <= TAC_ADDR) and write_addr not in (IF_ADDR, IE_ADDR):
            memory.write(write_addr, write_data)
        memory.advance_cycle(
            write_en=write_en,
            write_addr=write_addr,
            write_data=write_data,
            if_set_bits=if_set_bits | joypad_if_set_bits,
            irq_ack_valid=bool(getattr(trace, "irq_ack_valid", False)),
            irq_ack_bit=int(getattr(trace, "irq_ack_bit", 0)),
        )
        await Timer(1, units="ns")
        abi = memory.abi_snapshot()
        if abi.result != ABI_RESULT_RUNNING:
            return DutTerminalState(abi=abi, cycles=cycle)
    raise TimeoutError(f"DUT did not finish within {max_mcycles} M-cycles")


async def run_dut_to_serial_capture(
    driver: Any,
    *,
    rom_bytes: bytes,
    max_mcycles: int,
    min_capture_bytes: int = len(MOONEYE_PASS_BYTES),
) -> SerialTerminalState:
    from cocotb.triggers import Timer

    memory = ExternalMemoryBus(rom_bytes)
    await Timer(1, units="ns")
    for cycle in range(1, max_mcycles + 1):
        trace = driver.observe()
        bus_read_data = _trace_bus_read_data(trace, memory)
        write_en = int(getattr(trace, "bus_req_kind", BUS_REQ_IDLE)) == BUS_REQ_WRITE
        write_addr = int(getattr(trace, "bus_req_addr", 0)) if write_en else 0
        write_data = int(getattr(trace, "bus_req_data", 0)) if write_en else 0
        if_set_bits = memory.next_if_set_bits(write_en=write_en, write_addr=write_addr, write_data=write_data)

        await driver.step_mcycle(
            stimulus=_merge_stimulus(SimStimulus.idle(), if_set_bits=if_set_bits),
            bus_read_data=bus_read_data,
            irq_pending=0,
        )
        if write_en and not (DIV_ADDR <= write_addr <= TAC_ADDR) and write_addr not in (IF_ADDR, IE_ADDR):
            memory.write(write_addr, write_data)
        memory.advance_cycle(
            write_en=write_en,
            write_addr=write_addr,
            write_data=write_data,
            if_set_bits=if_set_bits,
            irq_ack_valid=bool(getattr(trace, "irq_ack_valid", False)),
            irq_ack_bit=int(getattr(trace, "irq_ack_bit", 0)),
        )
        await Timer(1, units="ns")
        if len(memory.serial_capture) >= min_capture_bytes:
            return SerialTerminalState(capture=tuple(memory.serial_capture), cycles=cycle)
    raise TimeoutError(f"DUT did not reach {min_capture_bytes} serial bytes within {max_mcycles} M-cycles")


async def run_soc_dut_to_serial_capture(
    driver: Any,
    *,
    rom_bytes: bytes,
    max_mcycles: int,
    min_capture_bytes: int = len(MOONEYE_PASS_BYTES),
) -> SerialTerminalState:
    memory = ExternalMemoryBus(rom_bytes, use_integrated_ppu=True)
    debug = os.environ.get("ICEBOY_SOC_ROM_DEBUG", "").strip().lower() not in {"", "0", "false", "no", "off"}
    last_post = None
    cycle = 0
    while cycle < max_mcycles:
        post, preview_kind, preview_addr, preview_data, video_sample, video_write_allowed = await _soc_step_to_commit(driver, memory)
        last_post = post
        cycle += 1
        write_en = int(getattr(post, "bus_req_kind", BUS_REQ_IDLE)) == BUS_REQ_WRITE
        write_addr = int(getattr(post, "bus_req_addr", 0)) if write_en else 0
        write_data = int(getattr(post, "bus_req_data", 0)) if write_en else 0
        if write_en and not (DIV_ADDR <= write_addr <= TAC_ADDR) and write_addr not in (IF_ADDR, IE_ADDR):
            if video_write_allowed is not None:
                if video_write_allowed:
                    memory.write_video_direct(write_addr, write_data)
            else:
                memory.write(write_addr, write_data)
        memory.advance_cycle(
            write_en=write_en,
            write_addr=write_addr,
            write_data=write_data,
            if_set_bits=0,
            irq_ack_valid=bool(getattr(post, "irq_ack_valid", False)),
            irq_ack_bit=int(getattr(post, "irq_ack_bit", 0)),
        )
        if debug and (cycle <= 32 or cycle % 5000 == 0):
            print(
                "soc-rom-debug",
                {
                    "cycle": cycle,
                    "pc": hex(int(getattr(post, "pc", 0))),
                    "preview_kind": preview_kind,
                    "preview_addr": hex(preview_addr),
                    "preview_data": hex(preview_data),
                    "write_en": write_en,
                    "write_addr": hex(write_addr),
                    "write_data": hex(write_data),
                    "bus_req_kind": int(getattr(post, "bus_req_kind", 0)),
                    "bus_req_addr": hex(int(getattr(post, "bus_req_addr", 0))),
                    "irq_pending": hex(memory.ie_reg & memory.if_reg),
                    "if_reg": hex(memory.if_reg),
                    "ie_reg": hex(memory.ie_reg),
                    "ppu_mode": int(getattr(post, "ppu_mode", 0)),
                    "ppu_ly": int(getattr(post, "ppu_ly", 0)),
                    "trace_vblank_window": bool(getattr(post, "ppu_vblank_req_window", False)),
                    "trace_stat_window": bool(getattr(post, "ppu_stat_req_window", False)),
                    "ppu_vblank_req": bool(getattr(post, "ppu_vblank_req", False)),
                    "ppu_stat_req": bool(getattr(post, "ppu_stat_req", False)),
                    "serial_len": len(memory.serial_capture),
                    "serial_sc": hex(memory.serial_sc),
                },
                flush=True,
            )
        if len(memory.serial_capture) >= min_capture_bytes:
            return SerialTerminalState(capture=tuple(memory.serial_capture), cycles=cycle)
    raise TimeoutError(
        f"SoC DUT did not reach {min_capture_bytes} serial bytes within {max_mcycles} M-cycles; "
        f"last_pc=0x{int(getattr(last_post, 'pc', 0)):04X} "
        f"last_if=0x{memory.if_reg:02X} last_ie=0x{memory.ie_reg:02X} "
        f"serial_len={len(memory.serial_capture)}"
    )


def mooneye_register_signature(observation: Any) -> tuple[int, ...]:
    return tuple(
        int(getattr(observation, name, 0)) & 0xFF
        for name in ("cpu_b", "cpu_c", "cpu_d", "cpu_e", "cpu_h", "cpu_l")
    )


def mooneye_arch_state_signature(arch_state_value: int) -> tuple[int, ...]:
    regs = (int(arch_state_value) >> 4) & ((1 << 96) - 1)
    return (
        (regs >> 72) & 0xFF,
        (regs >> 64) & 0xFF,
        (regs >> 56) & 0xFF,
        (regs >> 48) & 0xFF,
        (regs >> 40) & 0xFF,
        (regs >> 32) & 0xFF,
    )


def decode_arch_state_registers(arch_state_value: int) -> dict[str, int]:
    regs = (int(arch_state_value) >> 4) & ((1 << 96) - 1)
    return {
        "a": (regs >> 88) & 0xFF,
        "f": (regs >> 80) & 0xFF,
        "b": (regs >> 72) & 0xFF,
        "c": (regs >> 64) & 0xFF,
        "d": (regs >> 56) & 0xFF,
        "e": (regs >> 48) & 0xFF,
        "h": (regs >> 40) & 0xFF,
        "l": (regs >> 32) & 0xFF,
        "sp": (regs >> 16) & 0xFFFF,
        "pc": regs & 0xFFFF,
    }


def soc_preview_bus_req(driver: Any) -> tuple[int, int, int]:
    dut = getattr(driver, "dut", None)
    cpu_core = getattr(dut, "cpu_core_0", None)
    output_handle = getattr(cpu_core, "output__", None)
    output_value = getattr(output_handle, "value", None)
    if output_value is None:
        return (BUS_REQ_IDLE, 0, 0)
    if hasattr(output_value, "binstr"):
        tail_bits = output_value.binstr[-26:]
        encoded = int(
            "".join("0" if bit in {"x", "X", "z", "Z", "u", "U", "w", "W"} else bit for bit in tail_bits),
            2,
        )
    else:
        encoded = int(output_value) & ((1 << 26) - 1)
    return (
        (encoded >> 24) & 0x3,
        (encoded >> 8) & 0xFFFF,
        encoded & 0xFF,
    )


def soc_mooneye_register_signature(driver: Any, observation: Any) -> tuple[int, ...]:
    if all(hasattr(observation, name) for name in ("cpu_b", "cpu_c", "cpu_d", "cpu_e", "cpu_h", "cpu_l")):
        return mooneye_register_signature(observation)
    dut = getattr(driver, "dut", None)
    cpu_core = getattr(dut, "cpu_core_0", None)
    arch_state = getattr(cpu_core, "arch_state", None)
    if arch_state is not None:
        return mooneye_arch_state_signature(int(arch_state.value))
    return mooneye_register_signature(observation)


def classify_mooneye_register_signature(signature: list[int] | tuple[int, ...]) -> str:
    prefix = tuple(int(value) & 0xFF for value in signature[: len(MOONEYE_PASS_BYTES)])
    if prefix == MOONEYE_PASS_BYTES:
        return "pass"
    if prefix == MOONEYE_FAIL_BYTES:
        return "fail"
    return "unknown"


def find_mooneye_assert_block(memory: ExternalMemoryBus) -> dict[str, object] | None:
    expected_flags = 0x3C
    expected_asserts = bytes([0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00])
    hram = bytes(memory.hram)
    for base in range(0, len(hram) - 17):
        flags = hram[base + 8]
        asserts = hram[base + 9 : base + 17]
        if flags == expected_flags and asserts == expected_asserts:
            saved = hram[base : base + 8]
            return {
                "base": 0xFF80 + base,
                "flags": flags,
                "saved": saved,
                "asserts": asserts,
            }
    return None


def classify_mooneye_assert_block(block: dict[str, object] | None) -> str:
    if block is None:
        return "unknown"
    saved = bytes(block["saved"])
    expected = bytes(block["asserts"])
    flags = int(block["flags"]) & 0xFF
    bit_to_reg_dump_index = {
        0: 1,  # A
        1: 0,  # F
        2: 3,  # B
        3: 2,  # C
        4: 5,  # D
        5: 4,  # E
        6: 7,  # H
        7: 6,  # L
    }
    for bit, index in bit_to_reg_dump_index.items():
        if (flags & (1 << bit)) != 0 and saved[index] != expected[index]:
            return "fail"
    return "pass"


def decode_vram_text(memory: ExternalMemoryBus, *, rows: int = 4, cols: int = 20) -> tuple[str, ...]:
    tilemap = memory.vram[0x1800 : 0x1800 + (rows * 32)]
    lines: list[str] = []
    for row in range(rows):
        start = row * 32
        raw = tilemap[start : start + cols]
        chars = []
        for value in raw:
            if 32 <= value <= 126:
                chars.append(chr(value))
            elif value == 0:
                chars.append(" ")
            else:
                chars.append(".")
        lines.append("".join(chars).rstrip())
    return tuple(lines)


def classify_mooneye_screen_text(memory: ExternalMemoryBus) -> str:
    screen = "\n".join(decode_vram_text(memory))
    if "Test OK" in screen:
        return "pass"
    if "Fail:" in screen or "Test failed" in screen:
        return "fail"
    return "unknown"


def _screen_lines_for_failure(memory: ExternalMemoryBus) -> tuple[str, ...]:
    return decode_vram_text(memory, rows=10, cols=32)


def _failure_triplet(memory: ExternalMemoryBus) -> tuple[int, int, int]:
    return (
        memory.read(0xFF98),
        memory.read(0xFF99),
        memory.read(0xFF9A),
    )


def _screen_signal(lines: tuple[str, ...]) -> int:
    return sum(len(line.rstrip()) for line in lines)


def _sample_bytes(memory: ExternalMemoryBus, base: int, count: int) -> tuple[int, ...]:
    return tuple(memory.read((base + offset) & 0xFFFF) for offset in range(count))


async def _capture_soc_failure_screen(
    driver: Any,
    memory: ExternalMemoryBus,
    *,
    max_extra_mcycles: int = 4096,
) -> tuple[tuple[str, ...], dict[str, object] | None, int]:
    best_lines = _screen_lines_for_failure(memory)
    best_score = _screen_signal(best_lines)
    best_assert_block = find_mooneye_assert_block(memory)
    last_pc = 0
    stable_lines = 0
    previous_lines = best_lines

    for _ in range(max_extra_mcycles):
        post, _, _, _, video_sample, video_write_allowed = await _soc_step_to_commit(driver, memory)
        last_pc = int(getattr(post, "pc", 0))
        write_en = int(getattr(post, "bus_req_kind", BUS_REQ_IDLE)) == BUS_REQ_WRITE
        write_addr = int(getattr(post, "bus_req_addr", 0)) if write_en else 0
        write_data = int(getattr(post, "bus_req_data", 0)) if write_en else 0
        if write_en and not (DIV_ADDR <= write_addr <= TAC_ADDR) and write_addr not in (IF_ADDR, IE_ADDR):
            if video_write_allowed is not None:
                if video_write_allowed:
                    memory.write_video_direct(write_addr, write_data)
            else:
                memory.write(write_addr, write_data)
        memory.advance_cycle(
            write_en=write_en,
            write_addr=write_addr,
            write_data=write_data,
            if_set_bits=0,
            irq_ack_valid=bool(getattr(post, "irq_ack_valid", False)),
            irq_ack_bit=int(getattr(post, "irq_ack_bit", 0)),
        )

        lines = _screen_lines_for_failure(memory)
        score = _screen_signal(lines)
        assert_block = find_mooneye_assert_block(memory)
        if score >= best_score:
            best_lines = lines
            best_score = score
            best_assert_block = assert_block

        if lines == previous_lines:
            stable_lines += 1
        else:
            previous_lines = lines
            stable_lines = 0

        screen_text = "\n".join(lines)
        if "Expected:" in screen_text and "Actual:" in screen_text:
            return lines, assert_block, last_pc
        if stable_lines >= 256 and "Test failed:" in screen_text:
            return best_lines, best_assert_block, last_pc

    return best_lines, best_assert_block, last_pc


async def run_soc_dut_to_mooneye_signature(
    driver: Any,
    *,
    rom_bytes: bytes,
    max_mcycles: int,
) -> MooneyeTerminalState:
    memory = ExternalMemoryBus(rom_bytes, use_integrated_ppu=True)
    debug = os.environ.get("ICEBOY_SOC_ROM_DEBUG", "").strip().lower() not in {"", "0", "false", "no", "off"}
    last_post = None
    last_signature: tuple[int, ...] | None = None
    stable_signature_cycles = 0
    cycle = 0
    oracle_history: list[tuple[int, int, int, int]] = []
    while cycle < max_mcycles:
        post, preview_kind, preview_addr, preview_data, video_sample, video_write_allowed = await _soc_step_to_commit(driver, memory)
        last_post = post
        cycle += 1
        write_en = int(getattr(post, "bus_req_kind", BUS_REQ_IDLE)) == BUS_REQ_WRITE
        write_addr = int(getattr(post, "bus_req_addr", 0)) if write_en else 0
        write_data = int(getattr(post, "bus_req_data", 0)) if write_en else 0
        if write_en and not (DIV_ADDR <= write_addr <= TAC_ADDR) and write_addr not in (IF_ADDR, IE_ADDR):
            if video_write_allowed is not None:
                if video_write_allowed:
                    memory.write_video_direct(write_addr, write_data)
            else:
                memory.write(write_addr, write_data)
        memory.advance_cycle(
            write_en=write_en,
            write_addr=write_addr,
            write_data=write_data,
            if_set_bits=0,
            irq_ack_valid=bool(getattr(post, "irq_ack_valid", False)),
            irq_ack_bit=int(getattr(post, "irq_ack_bit", 0)),
        )
        pc_now = int(getattr(post, "pc", 0))
        oracle_a = getattr(post, "cpu_a", None)
        if oracle_a is None:
            cpu_core = getattr(getattr(driver, "dut", None), "cpu_core_0", None)
            trace_arch_state = getattr(cpu_core, "arch_state", None)
            if trace_arch_state is not None:
                regs = decode_arch_state_registers(int(trace_arch_state.value))
                oracle_a = int(regs["a"]) & 0xFF
        if oracle_a is not None and (not oracle_history or oracle_history[-1][0] != pc_now):
            oracle_history.append(
                (
                    pc_now,
                    int(oracle_a) & 0xFF,
                    memory.read(pc_now),
                    memory.read((pc_now + 1) & 0xFFFF),
                )
            )
            if len(oracle_history) > 16:
                oracle_history.pop(0)
        assert_block = find_mooneye_assert_block(memory)
        assert_block_outcome = classify_mooneye_assert_block(assert_block)
        if assert_block_outcome == "pass":
            return MooneyeTerminalState(
                signature=MOONEYE_PASS_BYTES,
                cycles=cycle,
                assert_block=assert_block,
                last_pc=int(getattr(post, "pc", 0)),
                oracle_history=tuple(oracle_history),
            )
        if assert_block_outcome == "fail":
            screen_lines, assert_block, last_pc = await _capture_soc_failure_screen(driver, memory)
            if debug:
                print("soc-rom-debug-screen", {"lines": screen_lines}, flush=True)
            return MooneyeTerminalState(
                signature=MOONEYE_FAIL_BYTES,
                cycles=cycle,
                screen_lines=screen_lines,
                assert_block=assert_block,
                last_pc=last_pc,
                failure_triplet=_failure_triplet(memory),
                oracle_history=tuple(oracle_history),
            )
        if not debug and cycle % 256 == 0:
            screen_outcome = classify_mooneye_screen_text(memory)
            if screen_outcome == "pass":
                return MooneyeTerminalState(
                    signature=MOONEYE_PASS_BYTES,
                    cycles=cycle,
                    assert_block=assert_block,
                    last_pc=int(getattr(post, "pc", 0)),
                    oracle_history=tuple(oracle_history),
                )
            if screen_outcome == "fail":
                screen_lines, assert_block, last_pc = await _capture_soc_failure_screen(driver, memory)
                if debug:
                    print("soc-rom-debug-screen", {"lines": screen_lines}, flush=True)
                return MooneyeTerminalState(
                    signature=MOONEYE_FAIL_BYTES,
                    cycles=cycle,
                    screen_lines=screen_lines,
                    assert_block=assert_block,
                    last_pc=last_pc,
                    failure_triplet=_failure_triplet(memory),
                    oracle_history=tuple(oracle_history),
                )
        signature = soc_mooneye_register_signature(driver, post)
        outcome = classify_mooneye_register_signature(signature)
        if signature == last_signature:
            stable_signature_cycles += 1
        else:
            stable_signature_cycles = 1
            last_signature = signature
        debug_pc = pc_now in {
            0x0339,
            0x47F7,
            0x47F8,
            0x4807,
            0x4830,
            0x4860,
            0x4872,
            0x489C,
            0x48CC,
            0x48E9,
            0x49DC,
            0x4B8E,
            0x4BDF,
            0x4BE3,
            0x4BE5,
        }
        preview_bus_addr = preview_addr if preview_kind in {BUS_REQ_READ, BUS_REQ_WRITE} else -1
        post_bus_addr = int(getattr(post, "bus_req_addr", 0)) if int(getattr(post, "bus_req_kind", BUS_REQ_IDLE)) != BUS_REQ_IDLE else -1
        debug_bus = preview_bus_addr in {LCDC_ADDR, STAT_ADDR, LYC_ADDR, IF_ADDR, IE_ADDR} or post_bus_addr in {
            LCDC_ADDR,
            STAT_ADDR,
            LYC_ADDR,
            IF_ADDR,
            IE_ADDR,
        }
        if debug and (cycle <= 32 or cycle % 5000 == 0 or debug_pc or debug_bus):
            pre_trace = driver.observe()
            cpu_core = getattr(getattr(driver, "dut", None), "cpu_core_0", None)
            trace_arch_state = getattr(cpu_core, "arch_state", None)
            trace_regs = (
                decode_arch_state_registers(int(trace_arch_state.value))
                if trace_arch_state is not None
                else None
            )
            print(
                "soc-rom-debug",
                {
                    "cycle": cycle,
                    "trace_pc": hex(int(getattr(pre_trace, "pc", 0))),
                    "pc": hex(int(getattr(post, "pc", 0))),
                    "preview_kind": preview_kind,
                    "preview_addr": hex(preview_addr),
                    "preview_data": hex(preview_data),
                    "post_bus_req_kind": int(getattr(post, "bus_req_kind", 0)),
                    "post_bus_req_addr": hex(int(getattr(post, "bus_req_addr", 0))),
                    "post_bus_req_data": hex(int(getattr(post, "bus_req_data", 0))),
                    "write_en": write_en,
                    "write_addr": hex(write_addr),
                    "write_data": hex(write_data),
                    "irq_pending": hex(memory.ie_reg & memory.if_reg),
                    "if_reg": hex(memory.if_reg),
                    "ie_reg": hex(memory.ie_reg),
                    "trace_a": None if trace_regs is None else hex(trace_regs["a"]),
                    "post_a": "n/a",
                    "b": hex(int(getattr(post, "cpu_b", 0))),
                    "c": hex(int(getattr(post, "cpu_c", 0))),
                    "d": hex(int(getattr(post, "cpu_d", 0))),
                    "e": hex(int(getattr(post, "cpu_e", 0))),
                    "h": hex(int(getattr(post, "cpu_h", 0))),
                    "l": hex(int(getattr(post, "cpu_l", 0))),
                    "ime": int(getattr(post, "cpu_ime_state", 0)),
                    "halt": int(getattr(post, "cpu_halt_state", 0)),
                    "phase": int(getattr(post, "cpu_phase_kind", 0)),
                    "ppu_mode": int(getattr(post, "ppu_mode", 0)),
                    "ppu_ly": int(getattr(post, "ppu_ly", 0)),
                    "ppu_stat": hex(int(getattr(post, "ppu_stat", 0))),
                    "trace_vblank_window": bool(getattr(post, "ppu_vblank_req_window", False)),
                    "trace_stat_window": bool(getattr(post, "ppu_stat_req_window", False)),
                    "signature": [hex(value) for value in signature],
                    "signature_outcome": outcome,
                },
                flush=True,
            )
        if outcome in {"pass", "fail"} and stable_signature_cycles >= 2:
            screen_lines = ()
            last_pc_for_state = pc_now
            if outcome == "fail":
                screen_lines, assert_block, last_pc_for_state = await _capture_soc_failure_screen(driver, memory)
            if debug and outcome == "fail":
                print("soc-rom-debug-screen", {"lines": screen_lines}, flush=True)
            return MooneyeTerminalState(
                signature=signature,
                cycles=cycle,
                screen_lines=screen_lines,
                assert_block=assert_block,
                last_pc=last_pc_for_state,
                failure_triplet=_failure_triplet(memory) if outcome == "fail" else None,
                oracle_history=tuple(oracle_history),
            )
    if debug:
        print("soc-rom-debug-screen", {"lines": decode_vram_text(memory, rows=6, cols=32)}, flush=True)
        print(
            "soc-rom-debug-timeout",
            {
                "test_results": [hex(value) for value in _sample_bytes(memory, 0xC12C, 19)],
                "oam0": hex(memory.read(OAM_BASE)),
                "vram0": hex(memory.read(VRAM_BASE)),
            },
            flush=True,
        )
    raise TimeoutError(
        f"SoC DUT did not reach a stable mooneye signature within {max_mcycles} M-cycles; "
        f"last_pc=0x{int(getattr(last_post, 'pc', 0)):04X} "
        f"last_if=0x{memory.if_reg:02X} last_ie=0x{memory.ie_reg:02X} "
        f"last_sig={[f'0x{value:02X}' for value in (last_signature or ())]} "
        f"assert_block={find_mooneye_assert_block(memory)}"
    )


def classify_mooneye_serial_capture(capture: list[int] | tuple[int, ...]) -> str:
    prefix = tuple(int(value) & 0xFF for value in capture[: len(MOONEYE_PASS_BYTES)])
    if prefix == MOONEYE_PASS_BYTES:
        return "pass"
    if prefix == MOONEYE_FAIL_BYTES:
        return "fail"
    return "unknown"


async def assert_mooneye_ppu_rom_passes(driver: Any, *, rom_path: str | Path, max_mcycles: int = 250000) -> SerialTerminalState:
    state = await run_dut_to_serial_capture(
        driver,
        rom_bytes=Path(rom_path).read_bytes(),
        max_mcycles=max_mcycles,
        min_capture_bytes=len(MOONEYE_PASS_BYTES),
    )
    outcome = classify_mooneye_serial_capture(state.capture)
    if outcome != "pass":
        raise AssertionError(
            f"Mooneye ROM {Path(rom_path).name} produced serial outcome {outcome}: "
            f"{[f'0x{byte:02X}' for byte in state.capture[: len(MOONEYE_PASS_BYTES)]]}"
        )
    return state


async def assert_mooneye_ppu_soc_rom_passes(
    driver: Any,
    *,
    rom_path: str | Path,
    max_mcycles: int = 250000,
) -> MooneyeTerminalState:
    state = await run_soc_dut_to_mooneye_signature(
        driver,
        rom_bytes=Path(rom_path).read_bytes(),
        max_mcycles=max_mcycles,
    )
    outcome = classify_mooneye_register_signature(state.signature)
    if outcome != "pass":
        detail_parts = [f"cycles={state.cycles}", f"last_pc=0x{state.last_pc:04X}"]
        if state.screen_lines:
            detail_parts.append(f"screen={list(state.screen_lines)}")
        if state.assert_block is not None:
            detail_parts.append(f"assert_block={state.assert_block}")
        if state.failure_triplet is not None:
            cycle_byte, expected_byte, actual_byte = state.failure_triplet
            detail_parts.append(
                f"failure_triplet=(cycle=0x{cycle_byte:02X}, expected=0x{expected_byte:02X}, actual=0x{actual_byte:02X})"
            )
        if state.oracle_history:
            oracle_text = [
                f"pc=0x{pc:04X}/a=0x{a:02X}/op=0x{opcode:02X}/imm=0x{operand:02X}"
                for pc, a, opcode, operand in state.oracle_history[-6:]
            ]
            detail_parts.append(f"oracle={oracle_text}")
        raise AssertionError(
            f"Mooneye SoC ROM {Path(rom_path).name} produced register outcome {outcome}: "
            f"{[f'0x{byte:02X}' for byte in state.signature[: len(MOONEYE_PASS_BYTES)]]}; "
            + " ".join(detail_parts)
        )
    return state


async def assert_rom_matches_pyboy_signature(
    driver: Any,
    *,
    rom_id: str,
    max_mcycles: int = 20000,
) -> DutTerminalState:
    entry = load_manifest_entry(rom_id)
    manifest = build_manifest(entry)
    event_schedule = event_script(None, entry.manifest_entry)
    checkpoint_addr = None
    if event_schedule.events:
        if len(entry.checkpoint_symbols) != 1:
            raise ValueError(f"{rom_id} requires exactly one checkpoint symbol for event-script replay")
        checkpoint_addr = load_symbol_table(entry).lookup(entry.checkpoint_symbols[0]).addr
    expected_labels, expected_abi = run_oracle_to_terminal(entry, manifest, event_schedule=event_schedule)
    dut_max_mcycles = max_mcycles if event_schedule.events else min(entry.timeout_commits, max_mcycles)
    actual = await run_dut_to_abi_result(
        driver,
        rom_bytes=entry.rom_path.read_bytes(),
        max_mcycles=dut_max_mcycles,
        checkpoint_addr=checkpoint_addr,
        event_schedule=event_schedule,
    )

    if "__pass" not in expected_labels[-1]:
        raise AssertionError(f"PyBoy oracle did not pass for {rom_id}: {expected_labels}")
    if actual.abi.result != ABI_RESULT_PASS:
        raise AssertionError(
            f"{rom_id} DUT ended with ABI result 0x{actual.abi.result:02X} "
            f"after {actual.cycles} cycles; expected terminal labels {expected_labels}"
        )
    if actual.abi.signature != expected_abi.signature:
        raise AssertionError(
            f"{rom_id} signature mismatch\n"
            f"expected={expected_abi.signature.hex()}\n"
            f"actual={actual.abi.signature.hex()}"
        )
    if actual.abi.log != expected_abi.log:
        raise AssertionError(
            f"{rom_id} log mismatch\nexpected={expected_abi.log.hex()}\nactual={actual.abi.log.hex()}"
        )
    return actual


def run_oracle_to_terminal(
    entry: RomManifestEntry,
    manifest: HookManifest,
    *,
    event_schedule: Any | None = None,
) -> tuple[tuple[str, ...], AbiSnapshot]:
    if event_schedule is not None and event_schedule.events:
        if len(entry.checkpoint_symbols) != 1:
            raise ValueError(f"{entry.rom_id} requires exactly one checkpoint symbol for event-script replay")
        checkpoint_label = entry.checkpoint_symbols[0]
        with PyBoyOracle(
            entry.rom_path,
            sym_path=entry.sym_path,
            commit_points=manifest.commit_points(),
        ) as oracle:
            if entry.rom_id == "JOY_DIVERGE_PERSIST":
                _install_scripted_joypad_hooks(oracle, entry, event_schedule)
            oracle.reset(entry.profiles.model, entry.profiles.reset)
            event_index = 0
            while event_index < entry.timeout_commits:
                for event in event_schedule.events_for_commit(event_index):
                    if entry.rom_id != "JOY_DIVERGE_PERSIST":
                        oracle.write_event(event)
                commit = oracle.step_commit()
                labels = _labels_from_commit(commit)
                abi = _read_oracle_abi_snapshot(oracle)
                if abi.result == ABI_RESULT_PASS:
                    return (("__pass",)), abi
                if abi.result == ABI_RESULT_FAIL:
                    return (("__fail",)), abi
                if checkpoint_label in labels:
                    event_index += 1
            pyboy = oracle._pyboy
            if pyboy is None:
                raise RuntimeError("PyBoy oracle unexpectedly closed during scripted ROM run")
            for _ in range(PYBOY_BATCH_TICKS):
                pyboy.tick(1, False, False)
                abi = _read_oracle_abi_snapshot(oracle)
                if abi.result == ABI_RESULT_PASS:
                    return (("__pass",)), abi
                if abi.result == ABI_RESULT_FAIL:
                    return (("__fail",)), abi
        raise TimeoutError(f"Oracle did not reach a terminal hook for {entry.rom_id}")

    warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")
    with PyBoy(
        str(entry.rom_path),
        window="null",
        sound_emulated=False,
        no_input=True,
        log_level="ERROR",
        symbols=str(entry.sym_path),
    ) as pyboy:
        pyboy.set_emulation_speed(0)
        ticks = 0
        while ticks < entry.timeout_commits:
            batch = min(PYBOY_BATCH_TICKS, entry.timeout_commits - ticks)
            pyboy.tick(batch, False, False)
            ticks += batch
            abi = _read_pyboy_abi_snapshot(pyboy)
            if abi.result == ABI_RESULT_PASS:
                return (("__pass",)), abi
            if abi.result == ABI_RESULT_FAIL:
                return (("__fail",)), abi

    raise TimeoutError(f"Oracle did not reach a terminal hook for {entry.rom_id}")
