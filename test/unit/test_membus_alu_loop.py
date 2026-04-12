# top = bus::membus_alu_loop_test_top::membus_alu_loop_test_top
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer


REGION_ROM = 0
REGION_WRAM = 3

OWNER_CPU = 0
OWNER_IDLE = 3

REQ_IDLE = 0
REQ_READ = 1
REQ_WRITE = 2

PROFILE_DMG_CONSERVATIVE = 0


def resolved_uint(value) -> int:
    return int(value.binstr.replace("x", "0").replace("z", "0"), 2)


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "data": (value >> 7) & 0xFF,
        "region": (value >> 3) & 0xF,
        "owner": (value >> 1) & 0x3,
        "blocked": bool(value & 0x1),
    }


async def prepare_dut(dut) -> None:
    dut.rst_i.value = 1
    dut.m_ce_i_i.value = 0
    dut.t_index_i_i.value = 0
    dut.req_kind_i_i.value = REQ_IDLE
    dut.addr_i_i.value = 0
    dut.data_i_i.value = 0
    dut.buttons_i_i.value = 0
    dut.memory_behavior_profile_i_i.value = PROFILE_DMG_CONSERVATIVE
    dut.oam_dma_active_i_i.value = 0
    dut.ppu_vram_active_i_i.value = 0
    dut.ppu_oam_active_i_i.value = 0
    await ClockCycles(dut.clk_i, 2)
    dut.rst_i.value = 0
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")


async def sample(
    dut,
    *,
    req_kind: int,
    addr: int,
    data: int = 0,
    m_ce: bool = True,
) -> dict[str, int | bool]:
    phase_req_kind = (req_kind & 0x3) if m_ce else REQ_IDLE
    phase_addr = addr & 0xFFFF if m_ce else 0
    phase_data = data & 0xFF if m_ce else 0
    for t_index in range(4):
        dut.m_ce_i_i.value = int(m_ce and t_index == 3)
        dut.t_index_i_i.value = t_index
        dut.req_kind_i_i.value = phase_req_kind
        dut.addr_i_i.value = phase_addr
        dut.data_i_i.value = phase_data
        await RisingEdge(dut.clk_i)
        await Timer(1, units="ns")
    return decode_output(resolved_uint(dut.output__.value))


async def write_then_read(dut, *, addr: int, value: int, m_ce: bool = True) -> tuple[dict[str, int | bool], dict[str, int | bool]]:
    write_snapshot = await sample(dut, req_kind=REQ_WRITE, addr=addr, data=value, m_ce=m_ce)
    read_snapshot = await sample(dut, req_kind=REQ_READ, addr=addr, m_ce=m_ce)
    return write_snapshot, read_snapshot


@cocotb.test()
async def test_rom_reads_baked_alu_loop_bytes_and_ignores_writes(dut):
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    await prepare_dut(dut)

    entry = await sample(dut, req_kind=REQ_READ, addr=0x0150)
    assert entry["data"] == 0xF3
    assert entry["region"] == REGION_ROM
    assert entry["owner"] == OWNER_CPU

    title = await sample(dut, req_kind=REQ_READ, addr=0x0134)
    assert title["data"] == ord("I")
    assert title["region"] == REGION_ROM

    _, after_write = await write_then_read(dut, addr=0x0150, value=0xA5)
    assert after_write["data"] == 0xF3
    assert after_write["region"] == REGION_ROM


@cocotb.test()
async def test_non_rom_paths_still_behave_like_cpu_only_membus(dut):
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    await prepare_dut(dut)

    _, first = await write_then_read(dut, addr=0xC123, value=0x5A)
    assert first["data"] == 0x5A
    assert first["region"] == REGION_WRAM

    _, blocked = await write_then_read(dut, addr=0xC123, value=0x99, m_ce=False)
    assert blocked["data"] == 0xFF
    assert blocked["owner"] == OWNER_IDLE

    final = await sample(dut, req_kind=REQ_READ, addr=0xC123)
    assert final["data"] == 0x5A
    assert final["region"] == REGION_WRAM
