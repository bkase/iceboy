from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import warnings

from pyboy import PyBoy
import yaml

from bench.pyboy.hooks import HookManifest, build_hook_manifest
from bench.pyboy.symbols import SymbolTable

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

    def read(self, addr: int) -> int:
        addr &= 0xFFFF
        if addr < 0x8000:
            return self.rom[addr] if addr < len(self.rom) else 0xFF
        if 0xC000 <= addr <= 0xDFFF:
            return self.wram[addr - 0xC000]
        if 0xFF80 <= addr <= 0xFFFE:
            return self.hram[addr - 0xFF80]
        return 0xFF

    def write(self, addr: int, value: int) -> None:
        addr &= 0xFFFF
        value &= 0xFF
        if 0xC000 <= addr <= 0xDFFF:
            self.wram[addr - 0xC000] = value
        elif 0xFF80 <= addr <= 0xFFFE:
            self.hram[addr - 0xFF80] = value

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
        pending_write = None
        if int(getattr(trace, "bus_req_kind", BUS_REQ_IDLE)) == BUS_REQ_WRITE:
            pending_write = (
                int(getattr(trace, "bus_req_addr", 0)),
                int(getattr(trace, "bus_req_data", 0)),
            )

        await driver.step_mcycle(bus_read_data=bus_read_data, irq_pending=0)
        if pending_write is not None:
            memory.write(pending_write[0], pending_write[1])
        await Timer(1, units="ns")
        abi = memory.abi_snapshot()
        if abi.result != ABI_RESULT_RUNNING:
            return DutTerminalState(abi=abi, cycles=cycle)
    raise TimeoutError(f"DUT did not finish within {max_mcycles} M-cycles")


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
