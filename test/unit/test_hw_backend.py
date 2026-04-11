# top = video::hw_backend_test_top::hw_backend_test_top
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


REGION_VRAM = 0
REGION_OAM = 1

CLIENT_CPU = 0
CLIENT_BG = 1
CLIENT_OBJ = 2
CLIENT_OAM = 3
CLIENT_DMA = 4

RESULT_DENIED = 0
RESULT_OK = 1
RESULT_UNDEFINED = 2


def resolved_uint(value) -> int:
    return int(value.binstr.replace("x", "0").replace("z", "0"), 2)


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "cpu_vram_read_data": value & 0xFF,
        "cpu_oam_read_data": (value >> 8) & 0xFF,
        "resp_data": (value >> 16) & 0xFF,
        "resp_id": (value >> 24) & 0xF,
        "resp_region": (value >> 28) & 0x1,
        "resp_client": (value >> 29) & 0x7,
        "resp_result": (value >> 32) & 0x3,
        "resp_reason": (value >> 34) & 0x7,
        "resp_valid": bool((value >> 37) & 0x1),
    }


async def reset_dut(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.rst_i.value = 1
    dut.req_valid_i.value = 0
    dut.req_region_i.value = REGION_VRAM
    dut.req_client_i.value = CLIENT_CPU
    dut.req_id_i.value = 0
    dut.req_addr_i.value = 0
    dut.cpu_addr_i.value = 0
    dut.cpu_write_en_i.value = 0
    dut.cpu_write_data_i.value = 0
    dut.cpu_is_vram_i.value = 0
    dut.cpu_is_oam_i.value = 0
    dut.dma_active_i.value = 0
    dut.dma_oam_write_en_i.value = 0
    dut.dma_oam_write_addr_i.value = 0
    dut.dma_oam_write_data_i.value = 0
    dut.ppu_vram_active_i.value = 0
    dut.ppu_oam_active_i.value = 0
    await RisingEdge(dut.clk_i)
    await RisingEdge(dut.clk_i)
    dut.rst_i.value = 0
    await Timer(1, units="ns")


async def step(
    dut,
    *,
    req_valid: bool = False,
    req_region: int = REGION_VRAM,
    req_client: int = CLIENT_CPU,
    req_id: int = 0,
    req_addr: int = 0,
    cpu_addr: int = 0,
    cpu_write_en: bool = False,
    cpu_write_data: int = 0,
    cpu_is_vram: bool = False,
    cpu_is_oam: bool = False,
    dma_active: bool = False,
    dma_oam_write_en: bool = False,
    dma_oam_write_addr: int = 0,
    dma_oam_write_data: int = 0,
    ppu_vram_active: bool = False,
    ppu_oam_active: bool = False,
) -> dict[str, int | bool]:
    dut.req_valid_i.value = int(req_valid)
    dut.req_region_i.value = req_region
    dut.req_client_i.value = req_client
    dut.req_id_i.value = req_id & 0xF
    dut.req_addr_i.value = req_addr & 0xFFFF
    dut.cpu_addr_i.value = cpu_addr & 0xFFFF
    dut.cpu_write_en_i.value = int(cpu_write_en)
    dut.cpu_write_data_i.value = cpu_write_data & 0xFF
    dut.cpu_is_vram_i.value = int(cpu_is_vram)
    dut.cpu_is_oam_i.value = int(cpu_is_oam)
    dut.dma_active_i.value = int(dma_active)
    dut.dma_oam_write_en_i.value = int(dma_oam_write_en)
    dut.dma_oam_write_addr_i.value = dma_oam_write_addr & 0xFF
    dut.dma_oam_write_data_i.value = dma_oam_write_data & 0xFF
    dut.ppu_vram_active_i.value = int(ppu_vram_active)
    dut.ppu_oam_active_i.value = int(ppu_oam_active)
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")
    return decode_output(resolved_uint(dut.output__.value))


async def issue_ppu_read(dut, *, region: int, client: int, tag_id: int, addr: int) -> dict[str, int | bool]:
    return await step(
        dut,
        req_valid=True,
        req_region=region,
        req_client=client,
        req_id=tag_id,
        req_addr=addr,
    )


async def read_cpu_vram(dut, addr: int, *, ppu_vram_active: bool = False) -> int:
    await step(dut, cpu_addr=addr, cpu_is_vram=True, ppu_vram_active=ppu_vram_active)
    snapshot = await step(dut, cpu_addr=addr, cpu_is_vram=True, ppu_vram_active=ppu_vram_active)
    return int(snapshot["cpu_vram_read_data"])


async def read_cpu_oam(dut, addr: int, *, ppu_oam_active: bool = False, dma_active: bool = False) -> int:
    await step(dut, cpu_addr=addr, cpu_is_oam=True, ppu_oam_active=ppu_oam_active, dma_active=dma_active)
    snapshot = await step(dut, cpu_addr=addr, cpu_is_oam=True, ppu_oam_active=ppu_oam_active, dma_active=dma_active)
    return int(snapshot["cpu_oam_read_data"])


@cocotb.test()
async def test_ppu_slot0_reads_return_vram_and_oam_data_with_one_tick_latency(dut):
    await reset_dut(dut)

    await step(dut, cpu_addr=0x8005, cpu_write_en=True, cpu_write_data=0xA1, cpu_is_vram=True)
    await step(dut, cpu_addr=0xFE02, cpu_write_en=True, cpu_write_data=0x33, cpu_is_oam=True)

    vram_resp = await issue_ppu_read(dut, region=REGION_VRAM, client=CLIENT_BG, tag_id=0x4, addr=0x8005)
    oam_resp = await issue_ppu_read(dut, region=REGION_OAM, client=CLIENT_OAM, tag_id=0x6, addr=0xFE02)

    assert vram_resp["resp_valid"] is True
    assert vram_resp["resp_result"] == RESULT_OK
    assert vram_resp["resp_data"] == 0xA1
    assert vram_resp["resp_region"] == REGION_VRAM
    assert vram_resp["resp_client"] == CLIENT_BG
    assert vram_resp["resp_id"] == 0x4

    assert oam_resp["resp_valid"] is True
    assert oam_resp["resp_result"] == RESULT_OK
    assert oam_resp["resp_data"] == 0x33
    assert oam_resp["resp_region"] == REGION_OAM
    assert oam_resp["resp_client"] == CLIENT_OAM
    assert oam_resp["resp_id"] == 0x6


@cocotb.test()
async def test_cpu_reads_are_masked_when_ppu_or_dma_owns_the_backend(dut):
    await reset_dut(dut)

    await step(dut, cpu_addr=0x8012, cpu_write_en=True, cpu_write_data=0x5A, cpu_is_vram=True)
    await step(dut, cpu_addr=0xFE12, cpu_write_en=True, cpu_write_data=0x6C, cpu_is_oam=True)

    assert await read_cpu_vram(dut, 0x8012, ppu_vram_active=False) == 0x5A
    assert await read_cpu_vram(dut, 0x8012, ppu_vram_active=True) == 0xFF

    assert await read_cpu_oam(dut, 0xFE12, ppu_oam_active=False, dma_active=False) == 0x6C
    assert await read_cpu_oam(dut, 0xFE12, ppu_oam_active=True, dma_active=False) == 0xFF
    assert await read_cpu_oam(dut, 0xFE12, ppu_oam_active=False, dma_active=True) == 0xFF


@cocotb.test()
async def test_dma_oam_writes_fill_the_oam_array_and_override_cpu_writes(dut):
    await reset_dut(dut)

    await step(dut, cpu_addr=0xFE00, cpu_write_en=True, cpu_write_data=0x11, cpu_is_oam=True)

    for offset in range(160):
        await step(
            dut,
            dma_active=True,
            dma_oam_write_en=True,
            dma_oam_write_addr=offset,
            dma_oam_write_data=(offset * 3) & 0xFF,
            cpu_addr=0xFE00 + offset,
            cpu_write_en=True,
            cpu_write_data=0xEE,
            cpu_is_oam=True,
        )

    assert await read_cpu_oam(dut, 0xFE00) == 0x00
    assert await read_cpu_oam(dut, 0xFE20) == (0x20 * 3) & 0xFF
    assert await read_cpu_oam(dut, 0xFE9F) == (0x9F * 3) & 0xFF

    for offset in range(160):
        resp = await issue_ppu_read(dut, region=REGION_OAM, client=CLIENT_OAM, tag_id=offset & 0xF, addr=0xFE00 + offset)
        assert resp["resp_valid"] is True
        assert resp["resp_result"] == RESULT_OK
        assert resp["resp_data"] == (offset * 3) & 0xFF
