# top = mem::phys::rom_baked_ebr_test_top::rom_baked_ebr_test_top
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "cpu_data": (value >> 9) & 0xFF,
        "dma_data": (value >> 1) & 0xFF,
        "rom_ready": bool(value & 0x1),
    }


def baked_pattern(addr: int) -> int:
    return ((addr * 37) + 0x11) & 0xFF


async def start_clock(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.cpu_addr_i.value = 0
    dut.dma_addr_i.value = 0
    dut.loader_write_en_i.value = 0
    dut.loader_write_addr_i.value = 0
    dut.loader_write_data_i.value = 0
    await Timer(1, units="ns")


async def step(
    dut,
    *,
    cpu_addr: int,
    dma_addr: int = 0,
    loader_write_en: bool = False,
    loader_write_addr: int = 0,
    loader_write_data: int = 0,
) -> dict[str, int | bool]:
    dut.cpu_addr_i.value = cpu_addr & 0x7FFF
    dut.dma_addr_i.value = dma_addr & 0x7FFF
    dut.loader_write_en_i.value = int(loader_write_en)
    dut.loader_write_addr_i.value = loader_write_addr & 0x7FFF
    dut.loader_write_data_i.value = loader_write_data & 0xFF
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")
    return decode_output(int(dut.output__.value))


@cocotb.test()
async def test_cpu_reads_baked_image_and_out_of_range_returns_ff(dut):
    await start_clock(dut)

    first = await step(dut, cpu_addr=0x0000)
    second = await step(dut, cpu_addr=0x0001)
    last_in_range = await step(dut, cpu_addr=0x03FF)
    out_of_range = await step(dut, cpu_addr=0x0400)

    assert first["cpu_data"] == baked_pattern(0x0000)
    assert second["cpu_data"] == baked_pattern(0x0001)
    assert last_in_range["cpu_data"] == baked_pattern(0x03FF)
    assert out_of_range["cpu_data"] == 0xFF
    assert first["dma_data"] == 0xFF
    assert out_of_range["dma_data"] == 0xFF
    assert first["rom_ready"] is True
    assert out_of_range["rom_ready"] is True


@cocotb.test()
async def test_dma_and_loader_paths_are_ignored_without_disturbing_cpu_reads(dut):
    await start_clock(dut)

    cpu_addr = 0x0020
    expected = baked_pattern(cpu_addr)

    with_dma = await step(
        dut,
        cpu_addr=cpu_addr,
        dma_addr=0x0015,
        loader_write_en=True,
        loader_write_addr=0x0003,
        loader_write_data=0xA5,
    )
    changed_side_inputs = await step(
        dut,
        cpu_addr=cpu_addr,
        dma_addr=0x03AA,
        loader_write_en=False,
        loader_write_addr=0x0111,
        loader_write_data=0x5A,
    )

    assert with_dma["cpu_data"] == expected
    assert changed_side_inputs["cpu_data"] == expected
    assert with_dma["dma_data"] == 0xFF
    assert changed_side_inputs["dma_data"] == 0xFF
    assert with_dma["rom_ready"] is True
    assert changed_side_inputs["rom_ready"] is True
