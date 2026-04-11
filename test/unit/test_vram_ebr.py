# top = mem::phys::ebr_test_top::vram_ebr_test_top
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def resolved_uint(value) -> int:
    return int(value.binstr.replace("x", "0").replace("z", "0"), 2)


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "read_data": (value >> 2) & 0xFF,
        "ppu_read_active": bool((value >> 1) & 0x1),
        "dma_read_active": bool(value & 0x1),
    }


async def start_clock(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.cpu_addr_i.value = 0
    dut.ppu_addr_i.value = 0
    dut.dma_addr_i.value = 0
    dut.ppu_read_active_i.value = 0
    dut.dma_read_active_i.value = 0
    dut.write_en_i.value = 0
    dut.write_addr_i.value = 0
    dut.write_data_i.value = 0
    await Timer(1, units="ns")


async def step(
    dut,
    *,
    cpu_addr: int = 0,
    ppu_addr: int = 0,
    dma_addr: int = 0,
    ppu_read_active: bool = False,
    dma_read_active: bool = False,
    write_en: bool = False,
    write_addr: int = 0,
    write_data: int = 0,
) -> dict[str, int | bool]:
    dut.cpu_addr_i.value = cpu_addr & 0x1FFF
    dut.ppu_addr_i.value = ppu_addr & 0x1FFF
    dut.dma_addr_i.value = dma_addr & 0x1FFF
    dut.ppu_read_active_i.value = int(ppu_read_active)
    dut.dma_read_active_i.value = int(dma_read_active)
    dut.write_en_i.value = int(write_en)
    dut.write_addr_i.value = write_addr & 0x1FFF
    dut.write_data_i.value = write_data & 0xFF
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")
    return decode_output(resolved_uint(dut.output__.value))


@cocotb.test()
async def test_vram_ebr_cpu_write_then_ppu_read_has_one_cycle_latency(dut):
    await start_clock(dut)

    await step(dut, write_en=True, write_addr=0x0012, write_data=0xC3)
    first = await step(dut, ppu_addr=0x0012, ppu_read_active=True)

    assert first["read_data"] == 0xC3
    assert first["ppu_read_active"] is True


@cocotb.test()
async def test_vram_ebr_cpu_and_ppu_reads_select_the_requested_owner(dut):
    await start_clock(dut)

    await step(dut, write_en=True, write_addr=0x0020, write_data=0x44)
    await step(dut, write_en=True, write_addr=0x0133, write_data=0x99)

    cpu_read = await step(dut, cpu_addr=0x0020)
    ppu_read = await step(dut, ppu_addr=0x0133, ppu_read_active=True)

    assert cpu_read["read_data"] == 0x44
    assert ppu_read["read_data"] == 0x99


@cocotb.test()
async def test_vram_ebr_dma_reads_return_ff_without_disturbing_ppu_contents(dut):
    await start_clock(dut)

    await step(dut, write_en=True, write_addr=0x0042, write_data=0x7A)

    dma_read = await step(dut, dma_addr=0x0042, dma_read_active=True)
    ppu_read = await step(dut, ppu_addr=0x0042, ppu_read_active=True)

    assert dma_read["read_data"] == 0xFF
    assert dma_read["dma_read_active"] is True
    assert ppu_read["read_data"] == 0x7A
