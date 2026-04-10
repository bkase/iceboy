# top = sim::oam_dma_mode2_test_top::oam_dma_mode2_test_top
from __future__ import annotations

import cocotb
from cocotb.triggers import ReadOnly, Timer


def decode_output(value: int) -> dict[str, int]:
    return {
        "line_obj_count": value & 0xF,
        "next_index": (value >> 4) & 0x3F,
        "next_found": (value >> 10) & 0xF,
        "slot0_oam_index": (value >> 14) & 0x3F,
        "slot0_x": (value >> 20) & 0xFF,
        "slot0_y": (value >> 28) & 0xFF,
        "slot0_rank": (value >> 36) & 0xF,
    }


async def sample(dut, *, ly: int, obj_y: int, obj_x: int, dma_active: bool) -> dict[str, int]:
    dut.ly_i.value = ly & 0xFF
    dut.obj_y_i.value = obj_y & 0xFF
    dut.obj_x_i.value = obj_x & 0xFF
    dut.dma_active_i.value = int(dma_active)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


@cocotb.test()
async def test_mode2_oam_scan_selects_visible_sprite_when_dma_is_idle(dut):
    snapshot = await sample(dut, ly=0x00, obj_y=0x10, obj_x=0x20, dma_active=False)
    assert snapshot["line_obj_count"] == 1
    assert snapshot["next_index"] == 1
    assert snapshot["next_found"] == 1
    assert snapshot["slot0_oam_index"] == 0
    assert snapshot["slot0_x"] == 0x20
    assert snapshot["slot0_y"] == 0x10
    assert snapshot["slot0_rank"] == 0


@cocotb.test()
async def test_mode2_oam_scan_hides_visible_sprite_when_dma_is_active(dut):
    snapshot = await sample(dut, ly=0x00, obj_y=0x10, obj_x=0x20, dma_active=True)
    assert snapshot["line_obj_count"] == 0
    assert snapshot["next_index"] == 1
    assert snapshot["next_found"] == 0
    assert snapshot["slot0_oam_index"] == 0
    assert snapshot["slot0_x"] == 0
    assert snapshot["slot0_y"] == 0
    assert snapshot["slot0_rank"] == 0
