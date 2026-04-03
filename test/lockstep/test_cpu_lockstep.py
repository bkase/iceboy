# top = sim::cpu_test_top::cpu_test_top
from dataclasses import dataclass
import sys
import warnings
from pathlib import Path

import cocotb
from cocotb.triggers import Timer


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from bench.pyboy.comparator import compare_commit
from bench.pyboy.trace_formatter import format_compare_result
from bench.pyboy.oracle import PyBoyOracle
from dut_driver import SimStimulus
from fixtures import cpu_dut
from rom_runner import BUS_REQ_READ, BUS_REQ_WRITE, ExternalMemoryBus, build_manifest, load_manifest_entry, load_symbol_table
from spec.compare_scopes import CompareField
from spec.profiles import ResetProfile


warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")

COMPARE_FIELDS = (CompareField.ProgramCounter, CompareField.BusResponse)


@dataclass(frozen=True)
class DutCheckpointObservation:
    seq: int
    commit_seq: int
    pc: int
    bus_req_kind: int
    bus_read_data: int
    irq_pending: int
    cpu_arch_time_enable: bool
    freeze_arch_time: bool
    cpu_hold_only: bool


async def step_to_checkpoint(driver, memory: ExternalMemoryBus, checkpoint_addr: int, *, max_mcycles: int = 20000):
    await Timer(1, units="ns")
    for _ in range(max_mcycles):
        pre = driver.observe()
        bus_read_data = memory.read(pre.bus_req_addr) if pre.bus_req_kind == BUS_REQ_READ else 0
        write_en = pre.bus_req_kind == BUS_REQ_WRITE
        write_addr = pre.bus_req_addr if write_en else 0
        write_data = pre.bus_req_data if write_en else 0
        if_set_bits = memory.next_if_set_bits(write_en=write_en, write_addr=write_addr, write_data=write_data)
        pending_write = (pre.bus_req_addr, pre.bus_req_data) if pre.bus_req_kind == BUS_REQ_WRITE else None
        hit_checkpoint = pre.bus_req_kind == BUS_REQ_READ and pre.bus_req_addr == checkpoint_addr
        await driver.step_mcycle(
            stimulus=SimStimulus(if_set_bits=if_set_bits),
            bus_read_data=bus_read_data,
            irq_pending=0,
        )
        if pending_write is not None and write_addr not in (0xFF04, 0xFF05, 0xFF06, 0xFF07, 0xFF0F, 0xFFFF):
            memory.write(pending_write[0], pending_write[1])
        memory.advance_cycle(
            write_en=write_en,
            write_addr=write_addr,
            write_data=write_data,
            if_set_bits=if_set_bits,
            irq_ack_valid=bool(pre.irq_ack_valid),
            irq_ack_bit=pre.irq_ack_bit,
        )
        await Timer(1, units="ns")
        if hit_checkpoint:
            return DutCheckpointObservation(
                seq=pre.seq,
                commit_seq=pre.commit_seq,
                pc=checkpoint_addr,
                bus_req_kind=pre.bus_req_kind,
                bus_read_data=bus_read_data,
                irq_pending=pre.irq_pending,
                cpu_arch_time_enable=pre.cpu_arch_time_enable,
                freeze_arch_time=pre.freeze_arch_time,
                cpu_hold_only=pre.cpu_hold_only,
            )
    raise TimeoutError(f"DUT did not reach checkpoint 0x{checkpoint_addr:04X} within {max_mcycles} M-cycles")


async def assert_lockstep_subset(driver, rom_id: str) -> None:
    entry = load_manifest_entry(rom_id)
    manifest = build_manifest(entry)
    symbol_table = load_symbol_table(entry)
    memory = ExternalMemoryBus(entry.rom_path.read_bytes())

    with PyBoyOracle(entry.rom_path, sym_path=entry.sym_path, commit_points=manifest.commit_points()) as oracle:
        oracle.reset(entry.profiles.model, entry.profiles.reset)
        oracle_state = oracle.step_commit()
        labels = tuple(label for label in (oracle_state.label or "").split("|") if label in entry.checkpoint_symbols)
        assert labels, f"{rom_id} expected checkpoint label, got {oracle_state.label}"
        checkpoint_addr = symbol_table.lookup(labels[0]).addr
        dut_trace = await step_to_checkpoint(driver, memory, checkpoint_addr)
        comparison = compare_commit(dut_trace, oracle_state, COMPARE_FIELDS)
        assert comparison.matched, format_compare_result(
            comparison,
            dut_trace=dut_trace,
            oracle_state=oracle_state,
        )


@cocotb.test()
async def test_cpu_lockstep_matches_ei_delay_checkpoints(dut):
    driver = cpu_dut(dut)
    await driver.reset(ResetProfile.SkipBoot)
    await assert_lockstep_subset(driver, "EI_DELAY")


@cocotb.test()
async def test_cpu_lockstep_matches_timer_irq_halt_checkpoints(dut):
    driver = cpu_dut(dut)
    await driver.reset(ResetProfile.SkipBoot)
    await assert_lockstep_subset(driver, "TIMER_IRQ_HALT")
