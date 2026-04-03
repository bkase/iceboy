from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import warnings

from pyboy import PyBoy
import yaml

from bench.pyboy.hooks import HookManifest, build_hook_manifest
from bench.pyboy.symbols import SymbolTable
try:
    from dut_driver import SimStimulus
except ModuleNotFoundError:
    from test.harness.dut_driver import SimStimulus

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
DIV_ADDR = 0xFF04
TIMA_ADDR = 0xFF05
TMA_ADDR = 0xFF06
TAC_ADDR = 0xFF07
IF_ADDR = 0xFF0F
IE_ADDR = 0xFFFF


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
    timeout_commits: int
    checkpoint_symbols: tuple[str, ...]


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
        self.wram = bytearray(0x2000)
        self.hram = bytearray(0x7F)
        self.ie_reg = 0
        self.if_reg = 0
        self.sys_counter = 0
        self.tima = 0
        self.tma = 0
        self.tac = 0
        self.sampled_timer_enabled = False
        self.sampled_timer_bit = False
        self.overflow_delay = 0

    def read(self, addr: int) -> int:
        addr &= 0xFFFF
        if addr < 0x8000:
            return self.rom[addr] if addr < len(self.rom) else 0xFF
        if 0xC000 <= addr <= 0xDFFF:
            return self.wram[addr - 0xC000]
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
        if 0xC000 <= addr <= 0xDFFF:
            self.wram[addr - 0xC000] = value
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

        return TIMER_IF_BIT if next_timer_irq else 0

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
                timeout_commits=int(entry["timeout_commits"]),
                checkpoint_symbols=tuple(str(label) for label in entry.get("checkpoint_symbols", [])),
            )
    raise KeyError(f"Unknown ROM id: {rom_id}")


def build_manifest(entry: RomManifestEntry) -> HookManifest:
    return build_hook_manifest(entry.sym_path, checkpoint_symbols=entry.checkpoint_symbols)


def load_symbol_table(entry: RomManifestEntry) -> SymbolTable:
    return SymbolTable.load(entry.sym_path)


def _read_pyboy_abi_snapshot(pyboy: PyBoy) -> AbiSnapshot:
    signature = bytes(int(pyboy.memory[ABI_SIGNATURE_BASE + offset]) for offset in range(ABI_SIGNATURE_SIZE))
    log = bytes(int(pyboy.memory[ABI_LOG_BASE + offset]) for offset in range(ABI_LOG_SIZE))
    return AbiSnapshot(signature=signature, log=log)


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
) -> DutTerminalState:
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
            stimulus=SimStimulus(if_set_bits=if_set_bits),
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
    expected_labels, expected_abi = run_oracle_to_terminal(entry, build_manifest(entry))
    actual = await run_dut_to_abi_result(
        driver,
        rom_bytes=entry.rom_path.read_bytes(),
        max_mcycles=min(entry.timeout_commits, max_mcycles),
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
) -> tuple[tuple[str, ...], AbiSnapshot]:
    del manifest
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
