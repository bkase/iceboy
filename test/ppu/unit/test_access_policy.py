# top = video::access_test_top::access_test_top
from __future__ import annotations

import sys
from pathlib import Path

import cocotb
from cocotb.triggers import ReadOnly, Timer


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
for entry in [ROOT, ROOT / "test" / "harness"]:
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from logging_std import TestLogger


RUN_DISABLED = 0
RUN_WARMUP = 1
RUN_RUNNING = 2

PHASE_LCD_OFF = 0
PHASE_OAM = 1
PHASE_TRANSFER = 2
PHASE_HBLANK = 3
PHASE_VBLANK = 4

REGION_VRAM = 0
REGION_OAM = 1

CLIENT_CPU = 0
CLIENT_BG = 1
CLIENT_OBJ = 2
CLIENT_OAM = 3
CLIENT_DMA = 4

REQ_READ = 0
REQ_WRITE = 1

RESULT_OK = 0
RESULT_DENIED = 1
RESULT_UNDEFINED = 2

REASON_NONE = 0
REASON_MODE2 = 1
REASON_MODE3 = 2
REASON_OAM_DMA = 3
REASON_OWNERSHIP = 4

SUITE_NAME = "test_access_policy.py"


def case_logger(case_name: str) -> TestLogger:
    suite = TestLogger(suite_name=SUITE_NAME, stream=sys.stdout, color=False)
    suite.suite()
    return suite.bind_case(case_name)


def decode_output(value: int) -> dict[str, int]:
    return {
        "data": value & 0xFF,
        "result": (value >> 8) & 0x3,
        "reason": (value >> 10) & 0x7,
        "tag_id": (value >> 13) & 0xF,
        "region": (value >> 17) & 0x1,
        "client": (value >> 18) & 0x7,
    }


async def sample(
    dut,
    *,
    run: int,
    phase: int,
    lcd_enable: bool,
    region: int,
    client: int,
    req_kind: int,
    tag_id: int = 0xA,
    oam_dma_active: bool = False,
    ownership_granted: bool = True,
    read_data: int = 0x5A,
    write_data: int = 0xC3,
) -> dict[str, int]:
    dut.run_i.value = run
    dut.phase_i.value = phase
    dut.lcd_enable_i.value = int(lcd_enable)
    dut.region_i.value = region
    dut.client_i.value = client
    dut.req_kind_i.value = req_kind
    dut.tag_id_i.value = tag_id
    dut.oam_dma_active_i.value = int(oam_dma_active)
    dut.ownership_granted_i.value = int(ownership_granted)
    dut.read_data_i.value = read_data
    dut.write_data_i.value = write_data
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


def require(logger: TestLogger, snapshot: dict[str, int], *, expected: dict[str, int]) -> None:
    for field, value in expected.items():
        assert logger.check(field, expected=value, actual=snapshot[field]), (
            f"{field} mismatch: expected={value} actual={snapshot[field]} snapshot={snapshot}"
        )


@cocotb.test()
async def test_mode2_access_matrix(dut):
    logger = case_logger("test_mode2_access_matrix")
    cases = [
        (
            "cpu_vram_read",
            dict(run=RUN_RUNNING, phase=PHASE_OAM, lcd_enable=True, region=REGION_VRAM, client=CLIENT_CPU, req_kind=REQ_READ, read_data=0x44),
            dict(result=RESULT_OK, reason=REASON_NONE, data=0x44, region=REGION_VRAM, client=CLIENT_CPU),
        ),
        (
            "cpu_oam_read",
            dict(run=RUN_RUNNING, phase=PHASE_OAM, lcd_enable=True, region=REGION_OAM, client=CLIENT_CPU, req_kind=REQ_READ),
            dict(result=RESULT_UNDEFINED, reason=REASON_MODE2, data=0x00, region=REGION_OAM, client=CLIENT_CPU),
        ),
        (
            "cpu_vram_write",
            dict(run=RUN_RUNNING, phase=PHASE_OAM, lcd_enable=True, region=REGION_VRAM, client=CLIENT_CPU, req_kind=REQ_WRITE, write_data=0x9A),
            dict(result=RESULT_OK, reason=REASON_NONE, data=0x9A, region=REGION_VRAM, client=CLIENT_CPU),
        ),
        (
            "cpu_oam_write",
            dict(run=RUN_RUNNING, phase=PHASE_OAM, lcd_enable=True, region=REGION_OAM, client=CLIENT_CPU, req_kind=REQ_WRITE, write_data=0x9A),
            dict(result=RESULT_DENIED, reason=REASON_NONE, data=0x00, region=REGION_OAM, client=CLIENT_CPU),
        ),
        (
            "oam_scanner_read",
            dict(run=RUN_RUNNING, phase=PHASE_OAM, lcd_enable=True, region=REGION_OAM, client=CLIENT_OAM, req_kind=REQ_READ, read_data=0x81),
            dict(result=RESULT_OK, reason=REASON_NONE, data=0x81, region=REGION_OAM, client=CLIENT_OAM),
        ),
    ]

    for label, kwargs, expected in cases:
        logger.step(
            f"[{label}] Set mode=OamScan region={kwargs['region']} client={kwargs['client']} req_kind={kwargs['req_kind']}"
        )
        snapshot = await sample(dut, **kwargs)
        require(logger, snapshot, expected=expected)


@cocotb.test()
async def test_mode3_access_matrix(dut):
    logger = case_logger("test_mode3_access_matrix")
    cases = [
        (
            "cpu_vram_read",
            dict(run=RUN_RUNNING, phase=PHASE_TRANSFER, lcd_enable=True, region=REGION_VRAM, client=CLIENT_CPU, req_kind=REQ_READ),
            dict(result=RESULT_UNDEFINED, reason=REASON_MODE3, data=0x00),
        ),
        (
            "cpu_oam_read",
            dict(run=RUN_RUNNING, phase=PHASE_TRANSFER, lcd_enable=True, region=REGION_OAM, client=CLIENT_CPU, req_kind=REQ_READ),
            dict(result=RESULT_UNDEFINED, reason=REASON_MODE3, data=0x00),
        ),
        (
            "cpu_vram_write",
            dict(run=RUN_RUNNING, phase=PHASE_TRANSFER, lcd_enable=True, region=REGION_VRAM, client=CLIENT_CPU, req_kind=REQ_WRITE, write_data=0x55),
            dict(result=RESULT_DENIED, reason=REASON_NONE, data=0x00),
        ),
        (
            "cpu_oam_write",
            dict(run=RUN_RUNNING, phase=PHASE_TRANSFER, lcd_enable=True, region=REGION_OAM, client=CLIENT_CPU, req_kind=REQ_WRITE, write_data=0x55),
            dict(result=RESULT_DENIED, reason=REASON_NONE, data=0x00),
        ),
        (
            "bg_fetcher_vram_read",
            dict(run=RUN_RUNNING, phase=PHASE_TRANSFER, lcd_enable=True, region=REGION_VRAM, client=CLIENT_BG, req_kind=REQ_READ, read_data=0x33),
            dict(result=RESULT_OK, reason=REASON_NONE, data=0x33),
        ),
        (
            "obj_fetcher_oam_read",
            dict(run=RUN_RUNNING, phase=PHASE_TRANSFER, lcd_enable=True, region=REGION_OAM, client=CLIENT_OBJ, req_kind=REQ_READ, read_data=0x77),
            dict(result=RESULT_OK, reason=REASON_NONE, data=0x77),
        ),
    ]

    for label, kwargs, expected in cases:
        logger.step(
            f"[{label}] Set mode=PixelTransfer region={kwargs['region']} client={kwargs['client']} req_kind={kwargs['req_kind']}"
        )
        snapshot = await sample(dut, **kwargs)
        require(logger, snapshot, expected=expected)


@cocotb.test()
async def test_modes_0_and_1_restore_cpu_access(dut):
    logger = case_logger("test_modes_0_and_1_restore_cpu_access")
    for phase_name, phase in [("HBlank", PHASE_HBLANK), ("VBlank", PHASE_VBLANK)]:
        for region in [REGION_VRAM, REGION_OAM]:
            logger.step(f"Set mode={phase_name} region={region} client=Cpu")
            read_snapshot = await sample(
                dut,
                run=RUN_RUNNING,
                phase=phase,
                lcd_enable=True,
                region=region,
                client=CLIENT_CPU,
                req_kind=REQ_READ,
                read_data=0x66 + region,
            )
            write_snapshot = await sample(
                dut,
                run=RUN_RUNNING,
                phase=phase,
                lcd_enable=True,
                region=region,
                client=CLIENT_CPU,
                req_kind=REQ_WRITE,
                write_data=0xA0 + region,
            )
            require(logger, read_snapshot, expected=dict(result=RESULT_OK, reason=REASON_NONE, data=0x66 + region))
            require(logger, write_snapshot, expected=dict(result=RESULT_OK, reason=REASON_NONE, data=0xA0 + region))


@cocotb.test()
async def test_lcd_off_overrides_phase_blocking(dut):
    logger = case_logger("test_lcd_off_overrides_phase_blocking")
    for phase_name, phase in [
        ("LcdOff", PHASE_LCD_OFF),
        ("OamScan", PHASE_OAM),
        ("PixelTransfer", PHASE_TRANSFER),
        ("HBlank", PHASE_HBLANK),
        ("VBlank", PHASE_VBLANK),
    ]:
        logger.step(f"Set lcd_enable=0 phase={phase_name} for both CPU and PPU clients")
        cpu_snapshot = await sample(
            dut,
            run=RUN_DISABLED,
            phase=phase,
            lcd_enable=False,
            region=REGION_OAM,
            client=CLIENT_CPU,
            req_kind=REQ_READ,
            read_data=0x7C,
        )
        ppu_snapshot = await sample(
            dut,
            run=RUN_DISABLED,
            phase=phase,
            lcd_enable=False,
            region=REGION_VRAM,
            client=CLIENT_BG,
            req_kind=REQ_READ,
            read_data=0x52,
        )
        require(logger, cpu_snapshot, expected=dict(result=RESULT_OK, reason=REASON_NONE, data=0x7C))
        require(logger, ppu_snapshot, expected=dict(result=RESULT_OK, reason=REASON_NONE, data=0x52))


@cocotb.test()
async def test_oam_dma_priority_and_ownership_cases(dut):
    logger = case_logger("test_oam_dma_priority_and_ownership_cases")

    logger.step("Set dma_active=1 for CPU VRAM read and CPU OAM read")
    cpu_vram = await sample(
        dut,
        run=RUN_RUNNING,
        phase=PHASE_TRANSFER,
        lcd_enable=True,
        region=REGION_VRAM,
        client=CLIENT_CPU,
        req_kind=REQ_READ,
        oam_dma_active=True,
    )
    cpu_oam = await sample(
        dut,
        run=RUN_RUNNING,
        phase=PHASE_OAM,
        lcd_enable=True,
        region=REGION_OAM,
        client=CLIENT_CPU,
        req_kind=REQ_READ,
        oam_dma_active=True,
    )
    require(logger, cpu_vram, expected=dict(result=RESULT_UNDEFINED, reason=REASON_OAM_DMA, data=0x00))
    require(logger, cpu_oam, expected=dict(result=RESULT_UNDEFINED, reason=REASON_OAM_DMA, data=0x00))

    logger.step("Set dma_active=1 for CPU writes and verify blocked write stays denied")
    cpu_write = await sample(
        dut,
        run=RUN_RUNNING,
        phase=PHASE_TRANSFER,
        lcd_enable=True,
        region=REGION_OAM,
        client=CLIENT_CPU,
        req_kind=REQ_WRITE,
        write_data=0x99,
        oam_dma_active=True,
    )
    require(logger, cpu_write, expected=dict(result=RESULT_DENIED, reason=REASON_NONE, data=0x00))

    logger.step("Set ownership_granted=0 for a non-CPU client and verify ownership denial")
    ownership_blocked = await sample(
        dut,
        run=RUN_RUNNING,
        phase=PHASE_TRANSFER,
        lcd_enable=True,
        region=REGION_VRAM,
        client=CLIENT_BG,
        req_kind=REQ_READ,
        ownership_granted=False,
    )
    require(logger, ownership_blocked, expected=dict(result=RESULT_UNDEFINED, reason=REASON_OWNERSHIP, data=0x00))

    logger.step("Set dma_active=1 with granted PPU ownership and verify PPU clients stay allowed")
    ppu_during_dma = await sample(
        dut,
        run=RUN_RUNNING,
        phase=PHASE_TRANSFER,
        lcd_enable=True,
        region=REGION_OAM,
        client=CLIENT_DMA,
        req_kind=REQ_READ,
        oam_dma_active=True,
        ownership_granted=True,
        read_data=0x24,
    )
    require(logger, ppu_during_dma, expected=dict(result=RESULT_OK, reason=REASON_NONE, data=0x24))
