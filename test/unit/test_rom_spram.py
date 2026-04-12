# top = mem::phys::spram_test_top::rom_image_spram_test_top
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "cpu_data": (value >> 53) & 0xFF,
        "dma_data": (value >> 45) & 0xFF,
        "rom_ready": bool((value >> 44) & 0x1),
        "address": (value >> 30) & 0x3FFF,
        "maskwren": (value >> 26) & 0xF,
        "read_high": bool((value >> 25) & 0x1),
        "read_aux": bool((value >> 24) & 0x1),
        "read_valid": bool((value >> 23) & 0x1),
        "wren": bool((value >> 22) & 0x1),
        "chipselect": bool((value >> 21) & 0x1),
        "standby": bool((value >> 20) & 0x1),
        "sleep": bool((value >> 19) & 0x1),
        "poweroff": bool((value >> 18) & 0x1),
        "datain": value & 0xFFFF,
    }


async def start_clock(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.t_index_i.value = 0
    dut.cpu_addr_i.value = 0
    dut.dma_addr_i.value = 0
    await Timer(1, units="ns")


async def step(dut, *, t_index: int, cpu_addr: int = 0, dma_addr: int = 0) -> dict[str, int | bool]:
    dut.t_index_i.value = t_index & 0x3
    dut.cpu_addr_i.value = cpu_addr & 0x7FFF
    dut.dma_addr_i.value = dma_addr & 0x7FFF
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")
    return decode_output(int(dut.output__.value))


@cocotb.test()
async def test_rom_schedule_keeps_write_disabled_and_tracks_byte_selects(dut):
    await start_clock(dut)

    cpu_issue = await step(dut, t_index=0, cpu_addr=0x0123)
    assert cpu_issue["address"] == 0x0091
    assert cpu_issue["read_valid"] is True
    assert cpu_issue["read_aux"] is False
    assert cpu_issue["read_high"] is True
    assert cpu_issue["wren"] is False
    assert cpu_issue["maskwren"] == 0x0
    assert cpu_issue["datain"] == 0x0000
    assert cpu_issue["chipselect"] is True
    assert cpu_issue["rom_ready"] is True

    dma_issue = await step(dut, t_index=1, dma_addr=0x0200)
    assert dma_issue["address"] == 0x0100
    assert dma_issue["read_valid"] is True
    assert dma_issue["read_aux"] is True
    assert dma_issue["read_high"] is False
    assert dma_issue["wren"] is False
    assert dma_issue["rom_ready"] is True

    idle = await step(dut, t_index=2)
    assert idle["read_valid"] is False
    assert idle["wren"] is False
    assert idle["chipselect"] is False
    assert idle["poweroff"] is True
    assert idle["standby"] is False
    assert idle["sleep"] is False


@cocotb.test()
async def test_rom_model_starts_deterministic_and_holds_outputs(dut):
    await start_clock(dut)

    await step(dut, t_index=0, cpu_addr=0x0000)
    captured = await step(dut, t_index=1, dma_addr=0x0001)
    held = await step(dut, t_index=3)

    assert captured["cpu_data"] == 0x00
    assert captured["dma_data"] == 0x00
    assert captured["rom_ready"] is True
    assert held["cpu_data"] == 0x00
    assert held["dma_data"] == 0x00
    assert held["rom_ready"] is True
