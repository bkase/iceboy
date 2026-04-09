# top = ppu::rtl::obj_transfer_live_test_top::obj_transfer_live_test_top
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer


FETCHER_BG = 0
FETCHER_OBJ = 2

MEM_REGION_VRAM = 0
MEM_REGION_OAM = 1

MEM_CLIENT_OBJ_FETCHER = 2

def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "fetcher_source": value & 0x3,
        "fetcher_step": (value >> 2) & 0x7,
        "mem_req_count": (value >> 5) & 0x7,
        "obj_fifo_count": (value >> 8) & 0x1F,
        "req_addr": (value >> 13) & 0xFFFF,
        "req_region": (value >> 29) & 0x1,
        "req_client": (value >> 30) & 0x7,
        "req_id": (value >> 33) & 0xF,
        "resp_valid": bool((value >> 37) & 0x1),
        "line_obj_count": (value >> 38) & 0xF,
        "ly": (value >> 42) & 0xFF,
        "dot_in_line": (value >> 50) & 0x1FF,
    }


async def reset_dut(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.dot_ce_i.value = 0
    dut.rst_i.value = 1
    await RisingEdge(dut.clk_i)
    await RisingEdge(dut.clk_i)
    dut.rst_i.value = 0
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    await Timer(1, units="ps")


async def step(
    dut,
) -> dict[str, int | bool]:
    dut.dot_ce_i.value = 1
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot

@cocotb.test()
async def test_transfer_drives_live_object_fetch_requests_and_fifo_fill(dut):
    await reset_dut(dut)

    first = await step(dut)
    assert first["line_obj_count"] == 1, first
    assert first["ly"] == 0, first

    saw_obj_fetcher = first["fetcher_source"] == FETCHER_OBJ
    saw_oam_req = (
        first["mem_req_count"] > 0
        and first["req_region"] == MEM_REGION_OAM
        and first["req_client"] == MEM_CLIENT_OBJ_FETCHER
    )
    saw_vram_req = (
        first["mem_req_count"] > 0
        and first["req_region"] == MEM_REGION_VRAM
        and first["req_client"] == MEM_CLIENT_OBJ_FETCHER
    )
    saw_obj_fifo = first["obj_fifo_count"] > 0

    last = first
    for _ in range(16):
        last = await step(dut)
        saw_obj_fetcher = saw_obj_fetcher or last["fetcher_source"] == FETCHER_OBJ
        saw_oam_req = saw_oam_req or (
            last["mem_req_count"] > 0
            and last["req_region"] == MEM_REGION_OAM
            and last["req_client"] == MEM_CLIENT_OBJ_FETCHER
        )
        saw_vram_req = saw_vram_req or (
            last["mem_req_count"] > 0
            and last["req_region"] == MEM_REGION_VRAM
            and last["req_client"] == MEM_CLIENT_OBJ_FETCHER
        )
        saw_obj_fifo = saw_obj_fifo or last["obj_fifo_count"] > 0
        if saw_obj_fetcher and saw_oam_req and saw_vram_req and saw_obj_fifo:
            break

    assert saw_obj_fetcher, last
    assert saw_oam_req, last
    assert saw_vram_req, last
    assert saw_obj_fifo, last
