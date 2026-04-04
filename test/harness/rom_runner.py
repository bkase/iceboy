from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import warnings

from pyboy import PyBoy
import yaml

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
from spec.profiles import SimulationProfiles

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
IF_ADDR = 0xFF0F
IE_ADDR = 0xFFFF
CARTRIDGE_TYPE_ADDR = 0x0147
CARTRIDGE_RAM_SIZE_ADDR = 0x0149
MBC1_CART_TYPES = frozenset({0x01, 0x02, 0x03})
MBC3_CART_TYPES = frozenset({0x0F, 0x10, 0x11, 0x12, 0x13})
MBC1_RAM_BANK_SIZE = 0x2000
MBC3_RTC_SELECTS = frozenset({0x08, 0x09, 0x0A, 0x0B, 0x0C})


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


class ExternalMemoryBus:
    def __init__(self, rom_bytes: bytes) -> None:
        self.rom = bytes(rom_bytes)
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
        if addr < 0x8000:
            return self._cart_rom_read(addr)
        if 0xA000 <= addr <= 0xBFFF:
            return self._cart_ram_read(addr)
        if 0xC000 <= addr <= 0xDFFF:
            return self.wram[addr - 0xC000]
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
        if addr == IF_ADDR:
            return self.if_reg & 0x1F
        if 0xFF80 <= addr <= 0xFFFE:
            return self.hram[addr - 0xFF80]
        if addr == IE_ADDR:
            return self.ie_reg & 0x1F
        return 0xFF

    def write(self, addr: int, value: int) -> None:
        addr &= 0xFFFF
        value &= 0xFF
        if (self.is_mbc1 or self.is_mbc3) and (addr < 0x8000 or 0xA000 <= addr <= 0xBFFF):
            self._cart_write(addr, value)
        elif 0xC000 <= addr <= 0xDFFF:
            self.wram[addr - 0xC000] = value
        elif addr == JOYP_ADDR:
            self.joyp_select = (value >> 4) & 0x3
        elif addr == SB_ADDR:
            self.serial_sb = value & 0xFF
        elif addr == SC_ADDR:
            self.serial_sc = value & 0x83
            if (self.serial_sc & 0x81) == 0x81:
                self.serial_cycles_left = 8
                self.serial_capture.append(self.serial_sb & 0xFF)
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
        return (TIMER_IF_BIT if next_timer_irq else 0) | (SERIAL_IF_BIT if next_serial_irq else 0)

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
        self.sys_counter = 0 if write_div else (self.sys_counter + 4) & 0xFFFF_FFFF

        cpu_written_ie = (write_data & 0x1F) if write_ie else self.ie_reg
        cpu_written_if = (write_data & 0x1F) if write_if else self.if_reg
        self.ie_reg = cpu_written_ie & 0x1F
        self.if_reg = ((cpu_written_if & ~_ack_mask(irq_ack_valid, irq_ack_bit)) | if_set_bits) & 0x1F

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
