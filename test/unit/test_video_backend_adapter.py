# top = video::backend_adapter_test_top::backend_adapter_test_top
from __future__ import annotations

import cocotb
from cocotb.triggers import ReadOnly, Timer


REGION_VRAM = 0
REGION_OAM = 1

CLIENT_CPU = 0
CLIENT_BG = 1
CLIENT_OBJ = 2
CLIENT_OAM = 3
CLIENT_DMA = 4

REQ_READ = 0
REQ_WRITE = 1


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "vram_write_data": value & 0xFF,
        "vram_addr": (value >> 8) & 0x1FFF,
        "vram_read": bool((value >> 21) & 0x1),
        "vram_write": bool((value >> 22) & 0x1),
        "oam_write_data": (value >> 23) & 0xFF,
        "oam_addr": (value >> 31) & 0xFF,
        "oam_read": bool((value >> 39) & 0x1),
        "oam_write": bool((value >> 40) & 0x1),
        "next_pending_valid": bool((value >> 41) & 0x1),
        "next_pending_id": (value >> 42) & 0xF,
        "next_pending_region": (value >> 46) & 0x1,
        "next_pending_epoch": (value >> 47) & 0xF,
        "resp_data": (value >> 51) & 0xFF,
        "resp_valid": bool((value >> 59) & 0x1),
        "resp_id": (value >> 60) & 0xF,
        "resp_region": (value >> 64) & 0x1,
        "resp_client": (value >> 65) & 0x7,
    }


async def sample(
    dut,
    *,
    pending_valid: bool = False,
    pending_region: int = REGION_VRAM,
    pending_client: int = CLIENT_CPU,
    pending_id: int = 0,
    pending_epoch: int = 0,
    req_valid: bool = False,
    req_region: int = REGION_VRAM,
    req_client: int = CLIENT_CPU,
    req_kind: int = REQ_READ,
    req_id: int = 0,
    req_addr: int = 0,
    req_epoch: int = 0,
    write_data: int = 0,
    vram_read_data: int = 0,
    oam_read_data: int = 0,
) -> dict[str, int | bool]:
    dut.pending_valid_i.value = int(pending_valid)
    dut.pending_region_i.value = pending_region
    dut.pending_client_i.value = pending_client
    dut.pending_id_i.value = pending_id
    dut.pending_epoch_i.value = pending_epoch
    dut.req_valid_i.value = int(req_valid)
    dut.req_region_i.value = req_region
    dut.req_client_i.value = req_client
    dut.req_kind_i.value = req_kind
    dut.req_id_i.value = req_id
    dut.req_addr_i.value = req_addr
    dut.req_epoch_i.value = req_epoch
    dut.write_data_i.value = write_data
    dut.vram_read_data_i.value = vram_read_data
    dut.oam_read_data_i.value = oam_read_data
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


@cocotb.test()
async def test_idle_request_keeps_ports_low_and_emits_no_response(dut):
    snapshot = await sample(dut)
    assert snapshot["vram_read"] is False
    assert snapshot["vram_write"] is False
    assert snapshot["oam_read"] is False
    assert snapshot["oam_write"] is False
    assert snapshot["next_pending_valid"] is False
    assert snapshot["resp_valid"] is False


@cocotb.test()
async def test_vram_read_routes_address_and_tracks_pending_tag(dut):
    snapshot = await sample(
        dut,
        req_valid=True,
        req_region=REGION_VRAM,
        req_client=CLIENT_BG,
        req_kind=REQ_READ,
        req_id=0xA,
        req_addr=0x8123,
        req_epoch=0x5,
    )
    assert snapshot["vram_read"] is True
    assert snapshot["vram_addr"] == 0x123
    assert snapshot["oam_read"] is False
    assert snapshot["next_pending_valid"] is True
    assert snapshot["next_pending_region"] == REGION_VRAM
    assert snapshot["next_pending_id"] == 0xA
    assert snapshot["next_pending_epoch"] == 0x5
    assert snapshot["resp_valid"] is False


@cocotb.test()
async def test_oam_read_completes_with_tagged_response_one_cycle_later(dut):
    snapshot = await sample(
        dut,
        pending_valid=True,
        pending_region=REGION_OAM,
        pending_client=CLIENT_OBJ,
        pending_id=0x4,
        pending_epoch=0x7,
        req_valid=False,
        oam_read_data=0x66,
    )
    assert snapshot["resp_valid"] is True
    assert snapshot["resp_data"] == 0x66
    assert snapshot["resp_region"] == REGION_OAM
    assert snapshot["resp_client"] == CLIENT_OBJ
    assert snapshot["resp_id"] == 0x4
    assert snapshot["next_pending_valid"] is False


@cocotb.test()
async def test_write_routes_to_target_array_without_leaving_pending_read(dut):
    vram = await sample(
        dut,
        req_valid=True,
        req_region=REGION_VRAM,
        req_kind=REQ_WRITE,
        req_addr=0x9ABC,
        write_data=0x55,
    )
    oam = await sample(
        dut,
        req_valid=True,
        req_region=REGION_OAM,
        req_kind=REQ_WRITE,
        req_addr=0xFE87,
        write_data=0x33,
    )
    assert vram["vram_write"] is True
    assert vram["vram_addr"] == 0x1ABC
    assert vram["vram_write_data"] == 0x55
    assert vram["next_pending_valid"] is False
    assert oam["oam_write"] is True
    assert oam["oam_addr"] == 0x87
    assert oam["oam_write_data"] == 0x33
    assert oam["next_pending_valid"] is False


@cocotb.test()
async def test_adapter_can_complete_previous_read_while_issuing_next_one(dut):
    snapshot = await sample(
        dut,
        pending_valid=True,
        pending_region=REGION_VRAM,
        pending_client=CLIENT_BG,
        pending_id=0x1,
        pending_epoch=0x2,
        req_valid=True,
        req_region=REGION_OAM,
        req_client=CLIENT_DMA,
        req_kind=REQ_READ,
        req_id=0xC,
        req_addr=0xFE20,
        req_epoch=0x9,
        vram_read_data=0xA5,
    )
    assert snapshot["resp_valid"] is True
    assert snapshot["resp_data"] == 0xA5
    assert snapshot["resp_region"] == REGION_VRAM
    assert snapshot["resp_id"] == 0x1
    assert snapshot["oam_read"] is True
    assert snapshot["oam_addr"] == 0x20
    assert snapshot["next_pending_valid"] is True
    assert snapshot["next_pending_region"] == REGION_OAM
    assert snapshot["next_pending_id"] == 0xC
    assert snapshot["next_pending_epoch"] == 0x9
