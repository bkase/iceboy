# top = mem::phys::rom_spram_rw_test_top::rom_spram_rw_test_top
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "cpu_data": (value >> 9) & 0xFF,
        "dma_data": (value >> 1) & 0xFF,
        "rom_ready": bool(value & 0x1),
    }


async def start_clock(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.t_index_i.value = 3
    dut.cpu_addr_i.value = 0
    dut.dma_addr_i.value = 0
    dut.loader_write_en_i.value = 0
    dut.loader_write_addr_i.value = 0
    dut.loader_write_data_i.value = 0
    await Timer(1, units="ns")


async def step(
    dut,
    *,
    t_index: int,
    cpu_addr: int = 0,
    dma_addr: int = 0,
    loader_write_en: bool = False,
    loader_write_addr: int = 0,
    loader_write_data: int = 0,
) -> dict[str, int | bool]:
    dut.t_index_i.value = t_index & 0x3
    dut.cpu_addr_i.value = cpu_addr & 0x7FFF
    dut.dma_addr_i.value = dma_addr & 0x7FFF
    dut.loader_write_en_i.value = int(loader_write_en)
    dut.loader_write_addr_i.value = loader_write_addr & 0x7FFF
    dut.loader_write_data_i.value = loader_write_data & 0xFF
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")
    return decode_output(int(dut.output__.value))


async def write_byte(dut, addr: int, data: int) -> None:
    await step(
        dut,
        t_index=2,
        loader_write_en=True,
        loader_write_addr=addr,
        loader_write_data=data,
    )
    await step(dut, t_index=3)


async def read_cpu_byte(dut, addr: int) -> int:
    await step(dut, t_index=0, cpu_addr=addr)
    captured = await step(dut, t_index=3)
    return int(captured["cpu_data"])


async def read_dma_byte(dut, addr: int) -> int:
    await step(dut, t_index=1, dma_addr=addr)
    captured = await step(dut, t_index=3)
    return int(captured["dma_data"])


@cocotb.test()
async def test_loader_writes_can_be_read_back_through_cpu_port(dut):
    await start_clock(dut)

    for addr in range(256):
        await write_byte(dut, addr, (addr * 29 + 0x17) & 0xFF)

    for addr in range(256):
        observed = await read_cpu_byte(dut, addr)
        expected = (addr * 29 + 0x17) & 0xFF
        assert observed == expected, (addr, observed, expected)


@cocotb.test()
async def test_loader_write_coexists_with_cpu_and_dma_reads_in_separate_slots(dut):
    await start_clock(dut)

    await write_byte(dut, 0x0010, 0xA1)
    await write_byte(dut, 0x0021, 0xB2)
    await write_byte(dut, 0x0032, 0x00)

    cpu_issue = await step(dut, t_index=0, cpu_addr=0x0010)
    dma_capture_and_write = await step(
        dut,
        t_index=1,
        dma_addr=0x0021,
    )
    write_cycle = await step(
        dut,
        t_index=2,
        loader_write_en=True,
        loader_write_addr=0x0032,
        loader_write_data=0xC3,
    )
    held = await step(dut, t_index=3)

    assert cpu_issue["rom_ready"] is True
    assert dma_capture_and_write["cpu_data"] == 0xA1
    assert write_cycle["dma_data"] == 0xB2
    assert write_cycle["rom_ready"] is False
    assert held["rom_ready"] is True
    assert await read_cpu_byte(dut, 0x0032) == 0xC3


@cocotb.test()
async def test_rom_ready_tracks_loader_activity(dut):
    await start_clock(dut)

    idle = await step(dut, t_index=3)
    write_active = await step(
        dut,
        t_index=2,
        loader_write_en=True,
        loader_write_addr=0x0044,
        loader_write_data=0x5E,
    )
    after_write = await step(dut, t_index=3)

    assert idle["rom_ready"] is True
    assert write_active["rom_ready"] is False
    assert after_write["rom_ready"] is True


@cocotb.test()
async def test_loader_can_write_high_and_low_bytes_of_same_word(dut):
    await start_clock(dut)

    await write_byte(dut, 0x0120, 0x44)
    await write_byte(dut, 0x0121, 0x99)

    assert await read_cpu_byte(dut, 0x0120) == 0x44
    assert await read_cpu_byte(dut, 0x0121) == 0x99
