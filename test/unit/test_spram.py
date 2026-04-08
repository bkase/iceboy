# top = mem::phys::spram_test_top::wram_spram_test_top
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "cpu_data": (value >> 52) & 0xFF,
        "aux_data": (value >> 44) & 0xFF,
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
    dut.aux_addr_i.value = 0
    dut.write_en_i.value = 0
    dut.write_addr_i.value = 0
    dut.write_data_i.value = 0
    await Timer(1, units="ns")


async def step(
    dut,
    *,
    t_index: int,
    cpu_addr: int = 0,
    aux_addr: int = 0,
    write_en: bool = False,
    write_addr: int = 0,
    write_data: int = 0,
) -> dict[str, int | bool]:
    dut.t_index_i.value = t_index & 0x3
    dut.cpu_addr_i.value = cpu_addr & 0x1FFF
    dut.aux_addr_i.value = aux_addr & 0x1FFF
    dut.write_en_i.value = int(write_en)
    dut.write_addr_i.value = write_addr & 0x1FFF
    dut.write_data_i.value = write_data & 0xFF
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")
    return decode_output(int(dut.output__.value))


@cocotb.test()
async def test_wram_dual_read_and_write_schedule(dut):
    await start_clock(dut)

    cpu_issue = await step(dut, t_index=0, cpu_addr=0x0020)
    assert cpu_issue["address"] == 0x0010
    assert cpu_issue["read_valid"] is True
    assert cpu_issue["read_aux"] is False
    assert cpu_issue["wren"] is False

    aux_issue = await step(dut, t_index=1, cpu_addr=0x0020, aux_addr=0x0031)
    assert aux_issue["address"] == 0x0018
    assert aux_issue["read_valid"] is True
    assert aux_issue["read_aux"] is True
    assert aux_issue["read_high"] is True

    write_issue = await step(
        dut,
        t_index=2,
        cpu_addr=0x0020,
        aux_addr=0x0031,
        write_en=True,
        write_addr=0x0041,
        write_data=0xAB,
    )
    assert write_issue["wren"] is True
    assert write_issue["address"] == 0x0020
    assert write_issue["maskwren"] == 0xC
    assert write_issue["datain"] == 0xAB00
    assert write_issue["poweroff"] is True
    assert write_issue["standby"] is False
    assert write_issue["sleep"] is False


@cocotb.test()
async def test_wram_write_then_readback_low_and_high_bytes(dut):
    await start_clock(dut)

    await step(dut, t_index=2, write_en=True, write_addr=0x0040, write_data=0x12)
    await step(dut, t_index=3)
    await step(dut, t_index=2, write_en=True, write_addr=0x0041, write_data=0x34)
    await step(dut, t_index=3)

    await step(dut, t_index=0, cpu_addr=0x0040)
    read_low = await step(dut, t_index=1, aux_addr=0x0041)
    read_high = await step(dut, t_index=2)

    assert read_low["cpu_data"] == 0x12, read_low
    assert read_high["aux_data"] == 0x34, read_high


@cocotb.test()
async def test_wram_outputs_stay_stable_after_mcycle_reads(dut):
    await start_clock(dut)

    await step(dut, t_index=2, write_en=True, write_addr=0x0002, write_data=0x5A)
    await step(dut, t_index=3)
    await step(dut, t_index=0, cpu_addr=0x0002)
    captured = await step(dut, t_index=1)
    held = await step(dut, t_index=3)

    assert captured["cpu_data"] == 0x5A, captured
    assert held["cpu_data"] == 0x5A, held
