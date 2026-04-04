# top = periph::oam_dma_test_top::oam_dma_test_top
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "active": bool((value >> 16) & 0x1),
        "source_high": (value >> 8) & 0xFF,
        "index": value & 0xFF,
    }


async def prepare_dut(dut) -> None:
    dut.rst_i.value = 1
    dut.m_ce_i.value = 0
    dut.start_i.value = 0
    dut.source_high_i.value = 0
    await ClockCycles(dut.clk_i, 3)
    dut.rst_i.value = 0
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")


async def step(
    dut,
    *,
    m_ce: bool = True,
    start: bool = False,
    source_high: int = 0,
) -> dict[str, int | bool]:
    dut.m_ce_i.value = int(m_ce)
    dut.start_i.value = int(start)
    dut.source_high_i.value = source_high & 0xFF
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")
    return decode_output(int(dut.output__.value))


@cocotb.test()
async def test_dma_start_latches_source_page_and_begins_at_index_zero(dut):
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    await prepare_dut(dut)

    idle = await step(dut, m_ce=False)
    assert idle == {"active": False, "source_high": 0x00, "index": 0x00}

    started = await step(dut, m_ce=True, start=True, source_high=0xC1)
    assert started == {"active": True, "source_high": 0xC1, "index": 0x00}


@cocotb.test()
async def test_dma_advances_one_byte_per_enabled_mcycle_for_160_cycles(dut):
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    await prepare_dut(dut)

    snapshot = await step(dut, m_ce=True, start=True, source_high=0x80)
    assert snapshot["active"] is True
    assert snapshot["index"] == 0x00

    for expected_index in range(1, 0xA0):
        snapshot = await step(dut, m_ce=True)
        assert snapshot["active"] is True, (expected_index, snapshot)
        assert snapshot["index"] == expected_index, (expected_index, snapshot)

    snapshot = await step(dut, m_ce=True)
    assert snapshot["active"] is False, snapshot
    assert snapshot["index"] == 0x00, snapshot


@cocotb.test()
async def test_dma_holds_progress_when_m_ce_is_low_and_can_restart(dut):
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    await prepare_dut(dut)

    snapshot = await step(dut, m_ce=True, start=True, source_high=0x12)
    assert snapshot["active"] is True
    assert snapshot["source_high"] == 0x12
    assert snapshot["index"] == 0x00

    snapshot = await step(dut, m_ce=False)
    assert snapshot["active"] is True
    assert snapshot["index"] == 0x00

    snapshot = await step(dut, m_ce=True)
    assert snapshot["active"] is True
    assert snapshot["index"] == 0x01

    snapshot = await step(dut, m_ce=True, start=True, source_high=0x34)
    assert snapshot["active"] is True
    assert snapshot["source_high"] == 0x34
    assert snapshot["index"] == 0x00
