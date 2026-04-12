# top = mem::phys::ebr_test_top::hram_ebr_test_top
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def resolved_uint(value) -> int:
    return int(value.binstr.replace("x", "0").replace("z", "0"), 2)


def decode_output(value: int) -> dict[str, int]:
    return {
        "cpu_data": (value >> 8) & 0xFF,
        "dma_data": value & 0xFF,
    }


async def start_clock(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.cpu_addr_i.value = 0
    dut.dma_addr_i.value = 0
    dut.write_en_i.value = 0
    dut.write_addr_i.value = 0
    dut.write_data_i.value = 0
    await Timer(1, units="ns")


async def step(
    dut,
    *,
    cpu_addr: int = 0,
    dma_addr: int = 0,
    write_en: bool = False,
    write_addr: int = 0,
    write_data: int = 0,
) -> dict[str, int]:
    dut.cpu_addr_i.value = cpu_addr & 0x7F
    dut.dma_addr_i.value = dma_addr & 0x7F
    dut.write_en_i.value = int(write_en)
    dut.write_addr_i.value = write_addr & 0x7F
    dut.write_data_i.value = write_data & 0xFF
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")
    return decode_output(resolved_uint(dut.output__.value))


@cocotb.test()
async def test_hram_write_then_dual_read_has_one_cycle_latency(dut):
    await start_clock(dut)

    await step(dut, write_en=True, write_addr=0, write_data=0xC3)
    first = await step(dut, cpu_addr=0, dma_addr=0)

    assert first == {"cpu_data": 0xC3, "dma_data": 0xC3}


@cocotb.test()
async def test_hram_boundary_and_neighbor_reads_stay_isolated(dut):
    await start_clock(dut)

    await step(dut, write_en=True, write_addr=5, write_data=0x44)
    await step(dut, write_en=True, write_addr=126, write_data=0x11)
    neighbors = await step(dut, cpu_addr=4, dma_addr=6)
    boundary = await step(dut, cpu_addr=126, dma_addr=5)

    assert neighbors == {"cpu_data": 0x00, "dma_data": 0x00}
    assert boundary == {"cpu_data": 0x11, "dma_data": 0x44}


@cocotb.test()
async def test_hram_stack_like_adjacent_bytes_survive_back_to_back_reads(dut):
    await start_clock(dut)

    await step(dut, write_en=True, write_addr=0x7D, write_data=0x01)
    await step(dut, write_en=True, write_addr=0x7C, write_data=0x58)

    high = await step(dut, cpu_addr=0x7D, dma_addr=0x7C)
    low = await step(dut, cpu_addr=0x7C, dma_addr=0x7D)

    assert high == {"cpu_data": 0x01, "dma_data": 0x58}
    assert low == {"cpu_data": 0x58, "dma_data": 0x01}
