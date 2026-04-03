# top = periph::interrupts_test_top::interrupts_test_top
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer


IE_ADDR = 0xFFFF
IF_ADDR = 0xFF0F


def decode_interrupts(output_value: int) -> dict[str, int]:
    return {
        "ie": (output_value >> 13) & 0xFF,
        "iflags": (output_value >> 5) & 0xFF,
        "pending": output_value & 0x1F,
    }


def log_snapshot(label: str, snapshot: dict[str, int]) -> None:
    cocotb.log.info(
        "%s IE=0x%02X IF=0x%02X pending=0x%02X",
        label,
        snapshot["ie"],
        snapshot["iflags"],
        snapshot["pending"],
    )


async def reset_dut(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.write_en_i.value = 0
    dut.write_addr_i.value = 0
    dut.write_data_i.value = 0
    dut.vblank_irq_i.value = 0
    dut.lcd_stat_irq_i.value = 0
    dut.timer_irq_i.value = 0
    dut.serial_irq_i.value = 0
    dut.joypad_irq_i.value = 0
    dut.irq_ack_valid_i.value = 0
    dut.irq_ack_bit_i.value = 0
    dut.rst_i.value = 1
    await ClockCycles(dut.clk_i, 3)
    dut.rst_i.value = 0
    await ReadOnly()
    await Timer(1, units="ps")


async def step(
    dut,
    *,
    write_addr: int | None = None,
    write_data: int = 0,
    vblank_irq: bool = False,
    lcd_stat_irq: bool = False,
    timer_irq: bool = False,
    serial_irq: bool = False,
    joypad_irq: bool = False,
    ack_bit: int | None = None,
) -> dict[str, int]:
    dut.write_en_i.value = int(write_addr is not None)
    dut.write_addr_i.value = (write_addr or 0) & 0xFFFF
    dut.write_data_i.value = write_data & 0xFF
    dut.vblank_irq_i.value = int(vblank_irq)
    dut.lcd_stat_irq_i.value = int(lcd_stat_irq)
    dut.timer_irq_i.value = int(timer_irq)
    dut.serial_irq_i.value = int(serial_irq)
    dut.joypad_irq_i.value = int(joypad_irq)
    dut.irq_ack_valid_i.value = int(ack_bit is not None)
    dut.irq_ack_bit_i.value = (ack_bit or 0) & 0x7
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    snapshot = decode_interrupts(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


@cocotb.test()
async def test_ie_and_if_readback_keep_upper_bits_set(dut):
    await reset_dut(dut)

    snapshot = await step(dut)
    assert snapshot == {"ie": 0xE0, "iflags": 0xE0, "pending": 0x00}, snapshot

    snapshot = await step(dut, write_addr=IE_ADDR, write_data=0x1F)
    assert snapshot["ie"] == 0xFF, snapshot
    assert snapshot["pending"] == 0x00, snapshot

    snapshot = await step(dut, write_addr=IF_ADDR, write_data=0x84)
    assert snapshot["iflags"] == 0xE4, snapshot
    assert snapshot["pending"] == 0x04, snapshot


@cocotb.test()
async def test_sources_latch_if_and_pending_is_masked_by_ie(dut):
    await reset_dut(dut)

    snapshot = await step(dut, vblank_irq=True, timer_irq=True)
    assert snapshot["iflags"] == 0xE5, snapshot
    assert snapshot["pending"] == 0x00, snapshot

    snapshot = await step(dut, write_addr=IE_ADDR, write_data=0x05)
    assert snapshot["ie"] == 0xE5, snapshot
    assert snapshot["pending"] == 0x05, snapshot

    snapshot = await step(dut)
    assert snapshot["iflags"] == 0xE5, snapshot
    assert snapshot["pending"] == 0x05, snapshot


@cocotb.test()
async def test_ack_clears_selected_flag_and_fresh_source_wins(dut):
    await reset_dut(dut)

    await step(dut, write_addr=IE_ADDR, write_data=0x14)
    snapshot = await step(dut, timer_irq=True, joypad_irq=True)
    assert snapshot["iflags"] == 0xF4, snapshot
    assert snapshot["pending"] == 0x14, snapshot

    snapshot = await step(dut, ack_bit=2)
    assert snapshot["iflags"] == 0xF0, snapshot
    assert snapshot["pending"] == 0x10, snapshot

    snapshot = await step(dut, timer_irq=True, ack_bit=2)
    assert snapshot["iflags"] == 0xF4, snapshot
    assert snapshot["pending"] == 0x14, snapshot


@cocotb.test()
async def test_pending_matches_ie_and_if_across_full_5bit_space(dut):
    await reset_dut(dut)

    for ie_bits in range(0x20):
        ie_visible = 0xE0 | ie_bits
        snapshot = await step(dut, write_addr=IE_ADDR, write_data=ie_bits)
        assert snapshot["ie"] == ie_visible, (ie_bits, snapshot)

        for if_bits in range(0x20):
            if_visible = 0xE0 | if_bits
            snapshot = await step(dut, write_addr=IF_ADDR, write_data=if_bits)
            if ie_bits in (0x00, 0x1F) and if_bits in (0x00, 0x15, 0x1F):
                log_snapshot(f"ie=0x{ie_bits:02X} if=0x{if_bits:02X}", snapshot)
            assert snapshot["iflags"] == if_visible, (ie_bits, if_bits, snapshot)
            assert snapshot["pending"] == (ie_bits & if_bits), (ie_bits, if_bits, snapshot)


@cocotb.test()
async def test_ack_clears_only_requested_bit_when_multiple_flags_pending(dut):
    await reset_dut(dut)

    await step(dut, write_addr=IE_ADDR, write_data=0x1F)
    snapshot = await step(dut, write_addr=IF_ADDR, write_data=0x1F)
    log_snapshot("all pending", snapshot)
    assert snapshot["pending"] == 0x1F, snapshot

    snapshot = await step(dut, ack_bit=3)
    log_snapshot("ack serial", snapshot)
    assert snapshot["iflags"] == 0xF7, snapshot
    assert snapshot["pending"] == 0x17, snapshot

    snapshot = await step(dut, ack_bit=0)
    log_snapshot("ack vblank", snapshot)
    assert snapshot["iflags"] == 0xF6, snapshot
    assert snapshot["pending"] == 0x16, snapshot


@cocotb.test()
async def test_if_write_and_ack_same_cycle_clear_requested_bit_before_sources(dut):
    await reset_dut(dut)

    await step(dut, write_addr=IE_ADDR, write_data=0x1F)
    snapshot = await step(dut, write_addr=IF_ADDR, write_data=0x1F, ack_bit=2)
    log_snapshot("if write + ack", snapshot)
    assert snapshot["iflags"] == 0xFB, snapshot
    assert snapshot["pending"] == 0x1B, snapshot

    snapshot = await step(dut, write_addr=IF_ADDR, write_data=0x00, ack_bit=4, joypad_irq=True)
    log_snapshot("if clear + ack + fresh joypad", snapshot)
    assert snapshot["iflags"] == 0xF0, snapshot
    assert snapshot["pending"] == 0x10, snapshot
