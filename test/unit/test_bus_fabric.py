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


async def write_then_read(dut, *, addr: int, value: int) -> tuple[dict[str, int | bool], dict[str, int | bool]]:
    dut.m_ce_i.value = 1
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
async def test_address_decode_boundary_pairs(dut):
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    cases = [
        (0x7FFF, REGION_ROM, 0x8000, REGION_VRAM),
        (0x9FFF, REGION_VRAM, 0xA000, REGION_CART_RAM),
        (0xBFFF, REGION_CART_RAM, 0xC000, REGION_WRAM),
        (0xDFFF, REGION_WRAM, 0xE000, REGION_ECHO),
        (0xFDFF, REGION_ECHO, 0xFE00, REGION_OAM),
        (0xFE9F, REGION_OAM, 0xFEA0, REGION_NOT_USABLE),
        (0xFEFF, REGION_NOT_USABLE, 0xFF00, REGION_IO),
        (0xFF7F, REGION_IO, 0xFF80, REGION_HRAM),
        (0xFFFE, REGION_HRAM, 0xFFFF, REGION_IE),
    ]

    for left_addr, left_region, right_addr, right_region in cases:
        left = await sample(dut, req_kind=REQ_READ, addr=left_addr)
        right = await sample(dut, req_kind=REQ_READ, addr=right_addr)
        assert left["region"] == left_region, (hex(left_addr), left)
        assert right["region"] == right_region, (hex(right_addr), right)
        assert left["owner"] == OWNER_CPU, (hex(left_addr), left)
        assert right["owner"] == OWNER_CPU, (hex(right_addr), right)
        assert left["blocked"] is False, (hex(left_addr), left)
        assert right["blocked"] is False, (hex(right_addr), right)


@cocotb.test()
async def test_rom_window_endpoints_are_stable_and_read_only(dut):
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    first = await sample(dut, req_kind=REQ_READ, addr=0x0000)
    last = await sample(dut, req_kind=REQ_READ, addr=0x7FFF)
    assert first["data"] == 0x00
    assert last["data"] == 0x00
    assert first["region"] == REGION_ROM
    assert last["region"] == REGION_ROM

    _, after_first = await write_then_read(dut, addr=0x0000, value=0xAA)
    _, after_last = await write_then_read(dut, addr=0x7FFF, value=0x55)
    assert after_first["data"] == 0x00
    assert after_last["data"] == 0x00


@cocotb.test()
async def test_wram_roundtrip_covers_endpoints_and_same_step_readback(dut):
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    for addr, value in [(0xC000, 0xAA), (0xDFFF, 0x55)]:
        write_snapshot, read_snapshot = await write_then_read(dut, addr=addr, value=value)
        assert write_snapshot["region"] == REGION_WRAM
        assert read_snapshot["data"] == value
        assert read_snapshot["region"] == REGION_WRAM
        assert read_snapshot["owner"] == OWNER_CPU
        assert read_snapshot["blocked"] is False


@cocotb.test()
async def test_hram_roundtrip_covers_endpoints(dut):
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    for addr, value in [(0xFF80, 0x3C), (0xFFFE, 0xC3)]:
        write_snapshot, read_snapshot = await write_then_read(dut, addr=addr, value=value)
        assert write_snapshot["region"] == REGION_HRAM
        assert read_snapshot["data"] == value
        assert read_snapshot["region"] == REGION_HRAM


@cocotb.test()
async def test_io_stub_and_unmapped_regions_return_ff_without_blocking(dut):
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    for addr, region in [
        (0xFF00, REGION_IO),
        (0x8000, REGION_VRAM),
        (0xA000, REGION_CART_RAM),
        (0xE000, REGION_ECHO),
        (0xFE00, REGION_OAM),
        (0xFEA0, REGION_NOT_USABLE),
        (0xFFFF, REGION_IE),
    ]:
        snapshot = await sample(dut, req_kind=REQ_READ, addr=addr)
        assert snapshot["data"] == 0xFF
        assert snapshot["region"] == region
        assert snapshot["owner"] == OWNER_CPU
        assert snapshot["blocked"] is False


@cocotb.test()
async def test_idle_returns_ff_without_cpu_ownership(dut):
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    snapshot = await sample(dut, req_kind=REQ_IDLE, addr=0xC000)
    assert snapshot == {
        "data": 0xFF,
        "region": REGION_HRAM,
        "owner": OWNER_IDLE,
        "blocked": False,
    }
