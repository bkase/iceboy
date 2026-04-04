# top = sim::cpu_test_top::cpu_test_top
from __future__ import annotations

import sys
from pathlib import Path

import cocotb
from cocotb.triggers import Timer


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from dut_driver import SimStimulus
from fixtures import cpu_dut
from power_metrics import append_metrics_artifact, read_power_metrics
from rom_runner import BUS_REQ_READ, BUS_REQ_WRITE, ExternalMemoryBus
from roms.build_micro_rom import build_rom
from spec.profiles import ResetProfile


SUITE_LABEL = "test_duty_cycle_metrics.py"
ROM_BASE = 0x0150
HALT_HALTED = 1
PHASE_HALTED = 1


def build_case_rom() -> bytes:
    return build_rom("PWRDUTY", bytes([0x06, 0x02, 0x80, 0x76, 0x00, 0x18, 0xFE]))


@cocotb.test()
async def test_cpu_top_reports_expected_logical_duty_cycles(dut):
    driver = cpu_dut(dut)
    await driver.reset(ResetProfile.SkipBoot)
    await Timer(1, units="ns")
    memory = ExternalMemoryBus(build_case_rom())
    metrics_start = None
    halted_quiescent_cycles = 0

    for _ in range(64):
        pre = driver.observe()
        if metrics_start is None and pre.bus_req_kind == BUS_REQ_READ and pre.bus_req_addr == ROM_BASE:
            metrics_start = await read_power_metrics(dut)

        bus_read_data = memory.read(pre.bus_req_addr) if pre.bus_req_kind == BUS_REQ_READ else 0
        pending_write = (pre.bus_req_addr, pre.bus_req_data) if pre.bus_req_kind == BUS_REQ_WRITE else None
        await driver.step_mcycle(stimulus=SimStimulus.idle(), bus_read_data=bus_read_data, irq_pending=0)
        if pending_write is not None:
            memory.write(pending_write[0], pending_write[1])
        await Timer(1, units="ps")

        if metrics_start is None:
            continue

        if pre.phase_kind == PHASE_HALTED and pre.halt_state == HALT_HALTED:
            halted_quiescent_cycles += 1
            if halted_quiescent_cycles >= 3:
                break

    assert metrics_start is not None, "never reached program entry"
    metrics = (await read_power_metrics(dut)).subtract(metrics_start)
    append_metrics_artifact(SUITE_LABEL, "test_cpu_top_reports_expected_logical_duty_cycles", metrics)

    for line in metrics.summary_lines():
        cocotb.log.info(line)

    assert metrics.total_cycles == 9
    assert metrics.bus_active_cycles == 4
    assert metrics.alu_active_cycles == 1
    assert metrics.halted_cycles == 3
    assert metrics.halt_quiescent_cycles == 3
    assert metrics.reg_a_we_cycles == 1
    assert metrics.reg_f_we_cycles == 1
    assert metrics.reg_b_we_cycles == 1
    assert metrics.reg_c_we_cycles == 0
    assert metrics.reg_d_we_cycles == 0
    assert metrics.reg_e_we_cycles == 0
    assert metrics.reg_h_we_cycles == 0
    assert metrics.reg_l_we_cycles == 0
    assert metrics.reg_sp_we_cycles == 0
    assert metrics.reg_pc_we_cycles == 4
    assert metrics.anomaly_lines() == []
