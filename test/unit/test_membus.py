# top = bus::membus_test_top::membus_test_top
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer


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
OWNER_OAM_DMA = 1
OWNER_PPU = 2
OWNER_IDLE = 3

REQ_IDLE = 0
REQ_READ = 1
REQ_WRITE = 2

PROFILE_DMG_CONSERVATIVE = 0
PROFILE_DMG_REVISION_SPECIFIC = 1


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
    buttons: int = 0,
    m_ce: bool = True,
    memory_behavior_profile: int = PROFILE_DMG_CONSERVATIVE,
    oam_dma_active: bool = False,
    ppu_vram_active: bool = False,
    ppu_oam_active: bool = False,
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
        dut.buttons_i_i.value = buttons & 0xFF
        dut.memory_behavior_profile_i_i.value = memory_behavior_profile & 0x3
        dut.oam_dma_active_i_i.value = int(oam_dma_active)
        dut.ppu_vram_active_i_i.value = int(ppu_vram_active)
        dut.ppu_oam_active_i_i.value = int(ppu_oam_active)
        await RisingEdge(dut.clk_i)
        await Timer(1, units="ns")
    return decode_output(resolved_uint(dut.output__.value))


async def write_then_read(
    dut,
    *,
    addr: int,
    value: int,
    buttons: int = 0,
    m_ce: bool = True,
    memory_behavior_profile: int = PROFILE_DMG_CONSERVATIVE,
    oam_dma_active: bool = False,
    ppu_vram_active: bool = False,
    ppu_oam_active: bool = False,
) -> tuple[dict[str, int | bool], dict[str, int | bool]]:
    write_snapshot = await sample(
        dut,
        req_kind=REQ_WRITE,
        addr=addr,
        data=value,
        buttons=buttons,
        m_ce=m_ce,
        memory_behavior_profile=memory_behavior_profile,
        oam_dma_active=oam_dma_active,
        ppu_vram_active=ppu_vram_active,
        ppu_oam_active=ppu_oam_active,
    )
    read_snapshot = await sample(
        dut,
        req_kind=REQ_READ,
        addr=addr,
        buttons=buttons,
        m_ce=m_ce,
        memory_behavior_profile=memory_behavior_profile,
        oam_dma_active=oam_dma_active,
        ppu_vram_active=ppu_vram_active,
        ppu_oam_active=ppu_oam_active,
    )
    return write_snapshot, read_snapshot


@cocotb.test()
async def test_idle_returns_ff_and_idle_bus_obs(dut):
    clock = Clock(dut.clk_i, 10, units="ns")
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
    clock = Clock(dut.clk_i, 10, units="ns")
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
    clock = Clock(dut.clk_i, 10, units="ns")
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
    clock = Clock(dut.clk_i, 10, units="ns")
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
    clock = Clock(dut.clk_i, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    _, snapshot = await write_then_read(dut, addr=0xFF80, value=0xC3)
    assert snapshot["data"] == 0xC3
    assert snapshot["region"] == REGION_HRAM

    _, upper = await write_then_read(dut, addr=0xFFFE, value=0x11)
    assert upper["data"] == 0x11
    assert upper["region"] == REGION_HRAM


@cocotb.test()
async def test_echo_ram_mirrors_wram_in_both_directions(dut):
    clock = Clock(dut.clk_i, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    _, through_echo = await write_then_read(dut, addr=0xC123, value=0x5A)
    assert through_echo["data"] == 0x5A
    assert through_echo["region"] == REGION_WRAM

    echo_read = await sample(dut, req_kind=REQ_READ, addr=0xE123)
    assert echo_read["data"] == 0x5A
    assert echo_read["region"] == REGION_ECHO

    _, through_wram = await write_then_read(dut, addr=0xE123, value=0xA7)
    assert through_wram["data"] == 0xA7
    assert through_wram["region"] == REGION_ECHO

    wram_read = await sample(dut, req_kind=REQ_READ, addr=0xC123)
    assert wram_read["data"] == 0xA7
    assert wram_read["region"] == REGION_WRAM


@cocotb.test()
async def test_io_and_unimplemented_regions_read_ff_and_ignore_writes(dut):
    clock = Clock(dut.clk_i, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    for addr, region in [
        (0xFF04, REGION_IO),
        (0x8000, REGION_VRAM),
        (0xA000, REGION_CART_RAM),
        (0xFEA0, REGION_NOT_USABLE),
        (0xFFFF, REGION_IE),
    ]:
        before = await sample(dut, req_kind=REQ_READ, addr=addr)
        assert before["data"] == 0xFF
        assert before["region"] == region

        _, after = await write_then_read(dut, addr=addr, value=0x77)
        assert after["data"] == 0xFF
        assert after["region"] == region

    before_oam = await sample(dut, req_kind=REQ_READ, addr=0xFE00)
    assert before_oam["data"] == 0x00
    assert before_oam["region"] == REGION_OAM

    _, after_oam = await write_then_read(dut, addr=0xFE00, value=0x77)
    assert after_oam["data"] == 0x77
    assert after_oam["region"] == REGION_OAM


@cocotb.test()
async def test_joypad_register_reads_selected_buttons_and_ignores_low_nibble_writes(dut):
    clock = Clock(dut.clk_i, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    default = await sample(dut, req_kind=REQ_READ, addr=0xFF00)
    assert default["data"] == 0xCF
    assert default["region"] == REGION_IO

    _, action = await write_then_read(dut, addr=0xFF00, value=0x10, buttons=0x10)
    assert action["data"] == 0xDE
    assert action["region"] == REGION_IO

    _, dpad = await write_then_read(dut, addr=0xFF00, value=0x20, buttons=0x04)
    assert dpad["data"] == 0xEB
    assert dpad["region"] == REGION_IO

    _, low_nibble_ignored = await write_then_read(dut, addr=0xFF00, value=0x2F, buttons=0x20)
    assert low_nibble_ignored["data"] == 0xEF
    assert low_nibble_ignored["region"] == REGION_IO


@cocotb.test()
async def test_oam_dma_blocks_non_io_hram_accesses_and_preserves_existing_contents(dut):
    clock = Clock(dut.clk_i, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    _, seeded = await write_then_read(dut, addr=0xC123, value=0x5A)
    assert seeded["data"] == 0x5A

    blocked = await sample(dut, req_kind=REQ_READ, addr=0xC123, oam_dma_active=True)
    assert blocked["data"] == 0xFF
    assert blocked["region"] == REGION_WRAM
    assert blocked["owner"] == OWNER_OAM_DMA
    assert blocked["blocked"] is True

    ie_blocked = await sample(dut, req_kind=REQ_READ, addr=0xFFFF, oam_dma_active=True)
    assert ie_blocked["data"] == 0xFF
    assert ie_blocked["region"] == REGION_IE
    assert ie_blocked["owner"] == OWNER_OAM_DMA
    assert ie_blocked["blocked"] is True

    _, after_write = await write_then_read(dut, addr=0xC123, value=0x99, oam_dma_active=True)
    assert after_write["data"] == 0xFF
    assert after_write["owner"] == OWNER_OAM_DMA
    assert after_write["blocked"] is True

    final = await sample(dut, req_kind=REQ_READ, addr=0xC123)
    assert final["data"] == 0x5A
    assert final["blocked"] is False


@cocotb.test()
async def test_oam_dma_keeps_only_hram_accessible(dut):
    clock = Clock(dut.clk_i, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    _, readback = await write_then_read(dut, addr=0xFF80, value=0xC3, oam_dma_active=True)
    assert readback["data"] == 0xC3
    assert readback["region"] == REGION_HRAM
    assert readback["owner"] == OWNER_CPU
    assert readback["blocked"] is False

    io_snapshot = await sample(dut, req_kind=REQ_READ, addr=0xFF04, oam_dma_active=True)
    assert io_snapshot["data"] == 0xFF
    assert io_snapshot["region"] == REGION_IO
    assert io_snapshot["owner"] == OWNER_OAM_DMA
    assert io_snapshot["blocked"] is True

    _, io_after_write = await write_then_read(dut, addr=0xFF04, value=0x12, oam_dma_active=True)
    assert io_after_write["data"] == 0xFF
    assert io_after_write["region"] == REGION_IO
    assert io_after_write["owner"] == OWNER_OAM_DMA
    assert io_after_write["blocked"] is True

    for addr, region in [
        (0x0150, REGION_ROM),
        (0x8000, REGION_VRAM),
        (0xA000, REGION_CART_RAM),
        (0xC123, REGION_WRAM),
        (0xE123, REGION_ECHO),
        (0xFE00, REGION_OAM),
        (0xFEA0, REGION_NOT_USABLE),
        (0xFF00, REGION_IO),
        (0xFFFF, REGION_IE),
    ]:
        snapshot = await sample(dut, req_kind=REQ_READ, addr=addr, oam_dma_active=True)
        assert snapshot["region"] == region, (hex(addr), snapshot)
        assert snapshot["owner"] == OWNER_OAM_DMA, (hex(addr), snapshot)
        assert snapshot["blocked"] is True, (hex(addr), snapshot)


@cocotb.test()
async def test_ff46_write_starts_internal_dma_copy_for_160_mcycles(dut):
    clock = Clock(dut.clk_i, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    for addr, value in [
        (0xC100, 0x12),
        (0xC101, 0x34),
        (0xC19F, 0xAB),
    ]:
        _, seeded = await write_then_read(dut, addr=addr, value=value)
        assert seeded["data"] == value
        assert seeded["region"] == REGION_WRAM

    start = await sample(dut, req_kind=REQ_WRITE, addr=0xFF46, data=0xC1)
    assert start["region"] == REGION_IO
    # The sample is taken after the transfer-start edge, so ownership already reflects
    # the latched DMA-active phase even though this FF46 write is what triggered it.
    assert start["owner"] == OWNER_OAM_DMA
    assert start["blocked"] is True

    for cycle in range(159):
        blocked = await sample(dut, req_kind=REQ_READ, addr=0xC100)
        assert blocked["data"] == 0xFF, (cycle, blocked)
        assert blocked["region"] == REGION_WRAM, (cycle, blocked)
        assert blocked["owner"] == OWNER_OAM_DMA, (cycle, blocked)
        assert blocked["blocked"] is True, (cycle, blocked)

    released = await sample(dut, req_kind=REQ_READ, addr=0xC100)
    assert released["data"] == 0x12
    assert released["region"] == REGION_WRAM
    assert released["owner"] == OWNER_CPU
    assert released["blocked"] is False

    first = await sample(dut, req_kind=REQ_READ, addr=0xFE00)
    assert first["data"] == 0x12
    assert first["region"] == REGION_OAM
    assert first["owner"] == OWNER_CPU
    assert first["blocked"] is False

    second = await sample(dut, req_kind=REQ_READ, addr=0xFE01)
    assert second["data"] == 0x34
    assert second["region"] == REGION_OAM

    last = await sample(dut, req_kind=REQ_READ, addr=0xFE9F)
    assert last["data"] == 0xAB
    assert last["region"] == REGION_OAM


@cocotb.test()
async def test_ppu_pixel_transfer_blocks_vram_but_not_wram(dut):
    clock = Clock(dut.clk_i, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    vram = await sample(dut, req_kind=REQ_READ, addr=0x8000, ppu_vram_active=True)
    assert vram["data"] == 0xFF
    assert vram["region"] == REGION_VRAM
    assert vram["owner"] == OWNER_PPU
    assert vram["blocked"] is True

    wram = await sample(dut, req_kind=REQ_READ, addr=0xC100, ppu_vram_active=True)
    assert wram["region"] == REGION_WRAM
    assert wram["owner"] == OWNER_CPU
    assert wram["blocked"] is False


@cocotb.test()
async def test_ppu_oam_search_blocks_oam_and_ignores_writes(dut):
    clock = Clock(dut.clk_i, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    blocked = await sample(dut, req_kind=REQ_READ, addr=0xFE00, ppu_oam_active=True)
    assert blocked["data"] == 0xFF
    assert blocked["region"] == REGION_OAM
    assert blocked["owner"] == OWNER_PPU
    assert blocked["blocked"] is True

    _, after_write = await write_then_read(dut, addr=0xFE00, value=0x77, ppu_oam_active=True)
    assert after_write["data"] == 0xFF
    assert after_write["owner"] == OWNER_PPU
    assert after_write["blocked"] is True


@cocotb.test()
async def test_oam_dma_takes_precedence_over_ppu_ownership(dut):
    clock = Clock(dut.clk_i, 10, units="ns")
    cocotb.start_soon(clock.start())
    await prepare_dut(dut)

    vram = await sample(dut, req_kind=REQ_READ, addr=0x8000, oam_dma_active=True, ppu_vram_active=True)
    assert vram["owner"] == OWNER_OAM_DMA
    assert vram["blocked"] is True

    oam = await sample(dut, req_kind=REQ_READ, addr=0xFE00, oam_dma_active=True, ppu_oam_active=True)
    assert oam["owner"] == OWNER_OAM_DMA
    assert oam["blocked"] is True
