# top = video::access_test_top::access_test_top
from __future__ import annotations

import cocotb
from cocotb.triggers import ReadOnly, Timer


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


@cocotb.test()
async def test_cpu_oam_read_is_undefined_in_mode2(dut):
    snapshot = await sample(
        dut,
        run=RUN_RUNNING,
        phase=PHASE_OAM,
        lcd_enable=True,
        region=REGION_OAM,
        client=CLIENT_CPU,
        req_kind=REQ_READ,
        tag_id=0x3,
    )
    assert snapshot["result"] == RESULT_UNDEFINED
    assert snapshot["reason"] == REASON_MODE2
    assert snapshot["tag_id"] == 0x3
    assert snapshot["region"] == REGION_OAM
    assert snapshot["client"] == CLIENT_CPU


@cocotb.test()
async def test_cpu_vram_and_oam_reads_are_undefined_in_mode3(dut):
    vram = await sample(
        dut,
        run=RUN_RUNNING,
        phase=PHASE_TRANSFER,
        lcd_enable=True,
        region=REGION_VRAM,
        client=CLIENT_CPU,
        req_kind=REQ_READ,
    )
    oam = await sample(
        dut,
        run=RUN_RUNNING,
        phase=PHASE_TRANSFER,
        lcd_enable=True,
        region=REGION_OAM,
        client=CLIENT_CPU,
        req_kind=REQ_READ,
    )
    assert vram["result"] == RESULT_UNDEFINED
    assert vram["reason"] == REASON_MODE3
    assert oam["result"] == RESULT_UNDEFINED
    assert oam["reason"] == REASON_MODE3


@cocotb.test()
async def test_lcd_off_restores_cpu_video_reads(dut):
    snapshot = await sample(
        dut,
        run=RUN_DISABLED,
        phase=PHASE_LCD_OFF,
        lcd_enable=False,
        region=REGION_OAM,
        client=CLIENT_CPU,
        req_kind=REQ_READ,
        read_data=0x77,
    )
    assert snapshot["result"] == RESULT_OK
    assert snapshot["reason"] == REASON_NONE
    assert snapshot["data"] == 0x77


@cocotb.test()
async def test_oam_dma_blocks_cpu_video_access_even_when_lcd_is_off(dut):
    snapshot = await sample(
        dut,
        run=RUN_DISABLED,
        phase=PHASE_LCD_OFF,
        lcd_enable=False,
        region=REGION_VRAM,
        client=CLIENT_CPU,
        req_kind=REQ_READ,
        oam_dma_active=True,
    )
    assert snapshot["result"] == RESULT_UNDEFINED
    assert snapshot["reason"] == REASON_OAM_DMA


@cocotb.test()
async def test_blocked_writes_return_denied(dut):
    snapshot = await sample(
        dut,
        run=RUN_RUNNING,
        phase=PHASE_TRANSFER,
        lcd_enable=True,
        region=REGION_OAM,
        client=CLIENT_CPU,
        req_kind=REQ_WRITE,
        write_data=0x99,
    )
    assert snapshot["result"] == RESULT_DENIED
    assert snapshot["reason"] == REASON_NONE
    assert snapshot["data"] == 0


@cocotb.test()
async def test_non_cpu_clients_require_granted_ownership(dut):
    blocked = await sample(
        dut,
        run=RUN_RUNNING,
        phase=PHASE_TRANSFER,
        lcd_enable=True,
        region=REGION_VRAM,
        client=CLIENT_BG,
        req_kind=REQ_READ,
        ownership_granted=False,
    )
    granted = await sample(
        dut,
        run=RUN_RUNNING,
        phase=PHASE_TRANSFER,
        lcd_enable=True,
        region=REGION_VRAM,
        client=CLIENT_BG,
        req_kind=REQ_READ,
        ownership_granted=True,
        read_data=0x42,
    )
    assert blocked["result"] == RESULT_UNDEFINED
    assert blocked["reason"] == REASON_OWNERSHIP
    assert granted["result"] == RESULT_OK
    assert granted["data"] == 0x42
