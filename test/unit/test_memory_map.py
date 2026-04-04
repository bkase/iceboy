# top = bus::membus_test_top::membus_test_top
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer


REGION_WRAM = 3
REGION_ECHO = 4
REGION_OAM = 5
REGION_NOT_USABLE = 6
REGION_IO = 7
REGION_HRAM = 8

OWNER_CPU = 0
OWNER_OAM_DMA = 1
OWNER_PPU = 2

REQ_READ = 1
REQ_WRITE = 2

PROFILE_DMG_CONSERVATIVE = 0
PROFILE_DMG_REVISION_SPECIFIC = 1


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
    dut.req_kind_i_i.value = 0
    dut.addr_i_i.value = 0
    dut.data_i_i.value = 0
    dut.memory_behavior_profile_i_i.value = PROFILE_DMG_CONSERVATIVE
    dut.oam_dma_active_i_i.value = 0
    dut.ppu_vram_active_i_i.value = 0
    dut.ppu_oam_active_i_i.value = 0
    await ClockCycles(dut.clk_i, 2)
    dut.rst_i.value = 0
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")


async def cycle(
    dut,
    *,
    req_kind: int,
    addr: int,
    data: int = 0,
    memory_behavior_profile: int = PROFILE_DMG_CONSERVATIVE,
    oam_dma_active: bool = False,
    ppu_vram_active: bool = False,
    ppu_oam_active: bool = False,
) -> dict[str, int | bool]:
    dut.m_ce_i_i.value = 1
    dut.req_kind_i_i.value = req_kind & 0x3
    dut.addr_i_i.value = addr & 0xFFFF
    dut.data_i_i.value = data & 0xFF
    dut.memory_behavior_profile_i_i.value = memory_behavior_profile & 0x3
    dut.oam_dma_active_i_i.value = int(oam_dma_active)
    dut.ppu_vram_active_i_i.value = int(ppu_vram_active)
    dut.ppu_oam_active_i_i.value = int(ppu_oam_active)
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")
    return decode_output(int(dut.output__.value))


async def write_then_read(
    dut,
    *,
    addr: int,
    value: int,
    memory_behavior_profile: int = PROFILE_DMG_CONSERVATIVE,
    oam_dma_active: bool = False,
    ppu_vram_active: bool = False,
    ppu_oam_active: bool = False,
) -> tuple[dict[str, int | bool], dict[str, int | bool]]:
    write_snapshot = await cycle(
        dut,
        req_kind=REQ_WRITE,
        addr=addr,
        data=value,
        memory_behavior_profile=memory_behavior_profile,
        oam_dma_active=oam_dma_active,
        ppu_vram_active=ppu_vram_active,
        ppu_oam_active=ppu_oam_active,
    )
    read_snapshot = await cycle(
        dut,
        req_kind=REQ_READ,
        addr=addr,
        memory_behavior_profile=memory_behavior_profile,
        oam_dma_active=oam_dma_active,
        ppu_vram_active=ppu_vram_active,
        ppu_oam_active=ppu_oam_active,
    )
    return write_snapshot, read_snapshot


@cocotb.test()
async def test_echo_ram_mirrors_wram_and_respects_boundary(dut):
    clock = Clock(dut.clk_i, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    dut._log.info("[CASE] echo mirror via WRAM->Echo profile=DmgConservative addr=0xC000 mirror=0xE000")
    _, echo_read = await write_then_read(dut, addr=0xC000, value=0x42)
    mirrored = await cycle(dut, req_kind=REQ_READ, addr=0xE000)
    dut._log.info(
        "[CHECK] addr=0xE000 expected=0x42 actual=0x%02X profile=DmgConservative",
        mirrored["data"],
    )
    assert echo_read["region"] == REGION_WRAM
    assert mirrored["data"] == 0x42
    assert mirrored["region"] == REGION_ECHO

    dut._log.info("[CASE] echo mirror via Echo->WRAM profile=DmgConservative addr=0xFDFF mirror=0xDDFF")
    _, wram_read = await write_then_read(dut, addr=0xFDFF, value=0x99)
    mirrored_back = await cycle(dut, req_kind=REQ_READ, addr=0xDDFF)
    dut._log.info(
        "[CHECK] addr=0xDDFF expected=0x99 actual=0x%02X profile=DmgConservative",
        mirrored_back["data"],
    )
    assert wram_read["region"] == REGION_ECHO
    assert mirrored_back["data"] == 0x99
    assert mirrored_back["region"] == REGION_WRAM

    boundary = await cycle(dut, req_kind=REQ_READ, addr=0xFE00)
    assert boundary["region"] == REGION_OAM


@cocotb.test()
async def test_unusable_region_reads_ff_under_memory_profiles(dut):
    clock = Clock(dut.clk_i, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    for profile, label in [
        (PROFILE_DMG_CONSERVATIVE, "DmgConservative"),
        (PROFILE_DMG_REVISION_SPECIFIC, "DmgRevisionSpecific"),
    ]:
        dut._log.info("[CASE] unusable region read profile=%s addr=0xFEA0", label)
        before = await cycle(
            dut,
            req_kind=REQ_READ,
            addr=0xFEA0,
            memory_behavior_profile=profile,
        )
        dut._log.info(
            "[CHECK] addr=0xFEA0 expected=0xFF actual=0x%02X profile=%s",
            before["data"],
            label,
        )
        assert before["data"] == 0xFF
        assert before["region"] == REGION_NOT_USABLE

        _, after = await write_then_read(
            dut,
            addr=0xFEA0,
            value=0x5E,
            memory_behavior_profile=profile,
        )
        assert after["data"] == 0xFF
        assert after["region"] == REGION_NOT_USABLE


@cocotb.test()
async def test_ppu_pixel_transfer_blocks_vram_accesses(dut):
    clock = Clock(dut.clk_i, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    dut._log.info("[CASE] blocked VRAM read profile=DmgConservative addr=0x8000")
    blocked = await cycle(
        dut,
        req_kind=REQ_READ,
        addr=0x8000,
        ppu_vram_active=True,
    )
    dut._log.info(
        "[CHECK] addr=0x8000 expected=0xFF actual=0x%02X profile=DmgConservative",
        blocked["data"],
    )
    assert blocked["data"] == 0xFF
    assert blocked["owner"] == OWNER_PPU
    assert blocked["blocked"] is True

    _, after_write = await write_then_read(
        dut,
        addr=0x8000,
        value=0x66,
        ppu_vram_active=True,
    )
    assert after_write["data"] == 0xFF
    assert after_write["blocked"] is True


@cocotb.test()
async def test_ppu_oam_search_blocks_oam_reads_and_writes(dut):
    clock = Clock(dut.clk_i, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    _, seeded = await write_then_read(dut, addr=0xFE20, value=0x4C)
    assert seeded["data"] == 0x4C
    assert seeded["region"] == REGION_OAM

    dut._log.info("[CASE] blocked OAM read profile=DmgConservative addr=0xFE20")
    blocked = await cycle(
        dut,
        req_kind=REQ_READ,
        addr=0xFE20,
        ppu_oam_active=True,
    )
    dut._log.info(
        "[CHECK] addr=0xFE20 expected=0xFF actual=0x%02X profile=DmgConservative",
        blocked["data"],
    )
    assert blocked["data"] == 0xFF
    assert blocked["owner"] == OWNER_PPU
    assert blocked["blocked"] is True

    _, blocked_write = await write_then_read(
        dut,
        addr=0xFE20,
        value=0x99,
        ppu_oam_active=True,
    )
    assert blocked_write["data"] == 0xFF
    assert blocked_write["blocked"] is True

    after = await cycle(dut, req_kind=REQ_READ, addr=0xFE20)
    assert after["data"] == 0x4C
    assert after["region"] == REGION_OAM


@cocotb.test()
async def test_oam_dma_restricts_cpu_access_to_io_and_hram(dut):
    clock = Clock(dut.clk_i, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    _, seeded_wram = await write_then_read(dut, addr=0xC123, value=0x5A)
    _, seeded_hram = await write_then_read(dut, addr=0xFF80, value=0xA1)
    assert seeded_wram["data"] == 0x5A
    assert seeded_hram["data"] == 0xA1

    dut._log.info("[CASE] dma restriction profile=DmgConservative blocked_addr=0xC123 allowed_addr=0xFF80")
    blocked = await cycle(
        dut,
        req_kind=REQ_READ,
        addr=0xC123,
        oam_dma_active=True,
    )
    dut._log.info(
        "[CHECK] addr=0xC123 expected=0xFF actual=0x%02X profile=DmgConservative",
        blocked["data"],
    )
    assert blocked["data"] == 0xFF
    assert blocked["region"] == REGION_WRAM
    assert blocked["owner"] == OWNER_OAM_DMA
    assert blocked["blocked"] is True

    hram = await cycle(
        dut,
        req_kind=REQ_READ,
        addr=0xFF80,
        oam_dma_active=True,
    )
    assert hram["data"] == 0xA1
    assert hram["region"] == REGION_HRAM
    assert hram["owner"] == OWNER_CPU
    assert hram["blocked"] is False

    io_reg = await cycle(
        dut,
        req_kind=REQ_READ,
        addr=0xFF04,
        oam_dma_active=True,
    )
    assert io_reg["data"] == 0xFF
    assert io_reg["region"] == REGION_IO
    assert io_reg["owner"] == OWNER_CPU
    assert io_reg["blocked"] is False
