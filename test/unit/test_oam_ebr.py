# top = mem::phys::ebr_test_top::oam_ebr_test_top
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def resolved_uint(value) -> int:
    return int(value.binstr.replace("x", "0").replace("z", "0"), 2)


async def start_clock(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.read_addr_i.value = 0
    dut.cpu_write_en_i.value = 0
    dut.cpu_write_addr_i.value = 0
    dut.cpu_write_data_i.value = 0
    dut.dma_write_en_i.value = 0
    dut.dma_write_addr_i.value = 0
    dut.dma_write_data_i.value = 0
    await Timer(1, units="ns")


async def step(
    dut,
    *,
    read_addr: int = 0,
    cpu_write_en: bool = False,
    cpu_write_addr: int = 0,
    cpu_write_data: int = 0,
    dma_write_en: bool = False,
    dma_write_addr: int = 0,
    dma_write_data: int = 0,
) -> int:
    dut.read_addr_i.value = read_addr & 0xFF
    dut.cpu_write_en_i.value = int(cpu_write_en)
    dut.cpu_write_addr_i.value = cpu_write_addr & 0xFF
    dut.cpu_write_data_i.value = cpu_write_data & 0xFF
    dut.dma_write_en_i.value = int(dma_write_en)
    dut.dma_write_addr_i.value = dma_write_addr & 0xFF
    dut.dma_write_data_i.value = dma_write_data & 0xFF
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")
    return resolved_uint(dut.output__.value) & 0xFF


@cocotb.test()
async def test_oam_cpu_and_dma_writes_round_trip_with_one_cycle_read_latency(dut):
    await start_clock(dut)

    await step(dut, cpu_write_en=True, cpu_write_addr=0x00, cpu_write_data=0x77)
    await step(dut, dma_write_en=True, dma_write_addr=0x10, dma_write_data=0xAB)
    first = await step(dut, read_addr=0x00)
    second = await step(dut, read_addr=0x10)

    assert first == 0x77
    assert second == 0xAB


@cocotb.test()
async def test_oam_dma_wins_on_conflict_and_bulk_dma_transfer_reads_back(dut):
    await start_clock(dut)

    await step(
        dut,
        cpu_write_en=True,
        cpu_write_addr=0x20,
        cpu_write_data=0x11,
        dma_write_en=True,
        dma_write_addr=0x20,
        dma_write_data=0x22,
    )
    conflict = await step(dut, read_addr=0x20)
    assert conflict == 0x22

    for offset in range(160):
        await step(dut, dma_write_en=True, dma_write_addr=offset, dma_write_data=(offset * 3) & 0xFF)

    first = await step(dut, read_addr=0x00)
    last = await step(dut, read_addr=0x9F)

    assert first == 0x00
    assert last == (0x9F * 3) & 0xFF
