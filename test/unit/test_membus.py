# top = bus::membus_test_top::membus_test_top
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


REGION_ROM = 0
REGION_VRAM = 1
REGION_CART_RAM = 2
REGION_WRAM = 3
REGION_ECHO = 4
REGION_OAM = 5
REGION_NOT_USABLE = 6
REGION_IO = 7
REGION_HRAM = 8
REGION_IE = 9

OWNER_CPU = 0
OWNER_IDLE = 3

REQ_IDLE = 0
REQ_READ = 1
REQ_WRITE = 2


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "data": (value >> 7) & 0xFF,
        "region": (value >> 3) & 0xF,
        "owner": (value >> 1) & 0x3,
        "blocked": bool(value & 0x1),
    }


async def prepare_dut(dut) -> None:
    dut.rst.value = 0
    dut.m_ce_i.value = 0
    dut.req_kind_i.value = REQ_IDLE
    dut.addr_i.value = 0
    dut.data_i.value = 0
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")


async def sample(dut, *, req_kind: int, addr: int, data: int = 0, m_ce: bool = True) -> dict[str, int | bool]:
    dut.m_ce_i.value = int(m_ce)
    dut.req_kind_i.value = req_kind & 0x3
    dut.addr_i.value = addr & 0xFFFF
    dut.data_i.value = data & 0xFF
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    return decode_output(int(dut.output__.value))


async def write_then_read(dut, *, addr: int, value: int, m_ce: bool = True) -> tuple[dict[str, int | bool], dict[str, int | bool]]:
    dut.m_ce_i.value = int(m_ce)
    dut.req_kind_i.value = REQ_WRITE
    dut.addr_i.value = addr & 0xFFFF
    dut.data_i.value = value & 0xFF
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    write_snapshot = decode_output(int(dut.output__.value))

    dut.req_kind_i.value = REQ_READ
    await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    read_snapshot = decode_output(int(dut.output__.value))
    return write_snapshot, read_snapshot


@cocotb.test()
async def test_idle_returns_ff_and_idle_bus_obs(dut):
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    snapshot = await sample(dut, req_kind=REQ_IDLE, addr=0x0000, m_ce=True)

    assert snapshot == {
        "data": 0xFF,
        "region": REGION_HRAM,
        "owner": OWNER_IDLE,
        "blocked": False,
    }


@cocotb.test()
async def test_address_decode_boundaries_cover_every_wave_a_region(dut):
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    cases = [
        (0x0000, REGION_ROM),
        (0x7FFF, REGION_ROM),
        (0x8000, REGION_VRAM),
        (0x9FFF, REGION_VRAM),
        (0xA000, REGION_CART_RAM),
        (0xBFFF, REGION_CART_RAM),
        (0xC000, REGION_WRAM),
        (0xDFFF, REGION_WRAM),
        (0xE000, REGION_ECHO),
        (0xFDFF, REGION_ECHO),
        (0xFE00, REGION_OAM),
        (0xFE9F, REGION_OAM),
        (0xFEA0, REGION_NOT_USABLE),
        (0xFEFF, REGION_NOT_USABLE),
        (0xFF00, REGION_IO),
        (0xFF7F, REGION_IO),
        (0xFF80, REGION_HRAM),
        (0xFFFE, REGION_HRAM),
        (0xFFFF, REGION_IE),
    ]

    for addr, region in cases:
        snapshot = await sample(dut, req_kind=REQ_READ, addr=addr)
        assert snapshot["region"] == region, (hex(addr), snapshot)
        assert snapshot["owner"] == OWNER_CPU, (hex(addr), snapshot)
        assert snapshot["blocked"] is False, (hex(addr), snapshot)


@cocotb.test()
async def test_rom_reads_zero_image_and_ignores_writes(dut):
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    snapshot = await sample(dut, req_kind=REQ_READ, addr=0x0150)
    assert snapshot["data"] == 0x00
    assert snapshot["region"] == REGION_ROM

    _, after_write = await write_then_read(dut, addr=0x0150, value=0xA5)
    assert after_write["data"] == 0x00
    assert after_write["region"] == REGION_ROM


@cocotb.test()
async def test_wram_round_trips_and_m_ce_gates_writes(dut):
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    _, first = await write_then_read(dut, addr=0xC123, value=0x5A)
    assert first["data"] == 0x5A
    assert first["region"] == REGION_WRAM

    _, blocked = await write_then_read(dut, addr=0xC123, value=0x99, m_ce=False)
    assert blocked["data"] == 0xFF
    assert blocked["region"] == REGION_HRAM
    assert blocked["owner"] == OWNER_IDLE

    final = await sample(dut, req_kind=REQ_READ, addr=0xC123)
    assert final["data"] == 0x5A
    assert final["region"] == REGION_WRAM


@cocotb.test()
async def test_hram_round_trips(dut):
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    _, snapshot = await write_then_read(dut, addr=0xFF80, value=0xC3)
    assert snapshot["data"] == 0xC3
    assert snapshot["region"] == REGION_HRAM

    _, upper = await write_then_read(dut, addr=0xFFFE, value=0x11)
    assert upper["data"] == 0x11
    assert upper["region"] == REGION_HRAM


@cocotb.test()
async def test_io_and_unimplemented_regions_read_ff_and_ignore_writes(dut):
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    for addr, region in [
        (0xFF04, REGION_IO),
        (0x8000, REGION_VRAM),
        (0xA000, REGION_CART_RAM),
        (0xE000, REGION_ECHO),
        (0xFE00, REGION_OAM),
        (0xFEA0, REGION_NOT_USABLE),
        (0xFFFF, REGION_IE),
    ]:
        before = await sample(dut, req_kind=REQ_READ, addr=addr)
        assert before["data"] == 0xFF
        assert before["region"] == region

        _, after = await write_then_read(dut, addr=addr, value=0x77)
        assert after["data"] == 0xFF
        assert after["region"] == region
