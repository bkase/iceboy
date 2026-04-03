# top = periph::timer_test_top::timer_test_top
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer


DIV_ADDR = 0xFF04
TIMA_ADDR = 0xFF05
TMA_ADDR = 0xFF06
TAC_ADDR = 0xFF07


def decode_timer(output_value: int) -> dict[str, int | bool]:
    return {
        "div": (output_value >> 24) & 0xFF,
        "tima": (output_value >> 16) & 0xFF,
        "tma": (output_value >> 8) & 0xFF,
        "tac": (output_value >> 5) & 0x7,
        "timer_irq": bool((output_value >> 4) & 0x1),
        "div_reset_request": bool((output_value >> 3) & 0x1),
        "overflow_delay": output_value & 0x7,
    }


def log_cycle(sys_counter: int, snapshot: dict[str, int | bool], *, note: str = "") -> None:
    suffix = f" {note}" if note else ""
    cocotb.log.info(
        "[CYCLE %d] DIV=0x%02X TIMA=0x%02X TMA=0x%02X TAC=0x%02X IRQ=%d delay=%d%s",
        sys_counter,
        int(snapshot["div"]),
        int(snapshot["tima"]),
        int(snapshot["tma"]),
        int(snapshot["tac"]),
        int(bool(snapshot["timer_irq"])),
        int(snapshot["overflow_delay"]),
        suffix,
    )


async def reset_dut(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.sys_counter_i.value = 0
    dut.write_en_i.value = 0
    dut.write_addr_i.value = 0
    dut.write_data_i.value = 0
    dut.rst_i.value = 1
    await ClockCycles(dut.clk_i, 3)
    dut.rst_i.value = 0
    await ReadOnly()
    await Timer(1, units="ps")


async def step(
    dut,
    *,
    sys_counter: int,
    write_addr: int | None = None,
    write_data: int = 0,
) -> dict[str, int | bool]:
    dut.sys_counter_i.value = sys_counter & 0xFFFF_FFFF
    dut.write_en_i.value = int(write_addr is not None)
    dut.write_addr_i.value = (write_addr or 0) & 0xFFFF
    dut.write_data_i.value = write_data & 0xFF
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    snapshot = decode_timer(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


async def configure_fast_timer(dut, *, tma: int = 0x00, tima: int = 0x00) -> None:
    await step(dut, sys_counter=0, write_addr=TMA_ADDR, write_data=tma)
    await step(dut, sys_counter=0, write_addr=TIMA_ADDR, write_data=tima)
    await step(dut, sys_counter=0, write_addr=TAC_ADDR, write_data=0x05)


async def advance_to(dut, *, start: int, end: int) -> dict[str, int | bool]:
    snapshot: dict[str, int | bool] = decode_timer(int(dut.output__.value))
    for sys_counter in range(start, end + 1):
        snapshot = await step(dut, sys_counter=sys_counter)
    return snapshot


@cocotb.test()
async def test_div_reflects_upper_sys_counter_byte_and_div_write_requests_reset(dut):
    await reset_dut(dut)

    snapshot = await step(dut, sys_counter=0x00FF)
    assert snapshot["div"] == 0x00
    assert snapshot["div_reset_request"] is False

    snapshot = await step(dut, sys_counter=0x0100)
    assert snapshot["div"] == 0x01

    snapshot = await step(dut, sys_counter=0x01FF, write_addr=DIV_ADDR, write_data=0xAB)
    assert snapshot["div"] == 0x00
    assert snapshot["div_reset_request"] is True

    snapshot = await step(dut, sys_counter=0x0000)
    assert snapshot["div"] == 0x00
    assert snapshot["div_reset_request"] is False


@cocotb.test()
async def test_tima_counts_on_selected_falling_edges_for_each_tac_rate(dut):
    cases = (
        (0x04, 1024),
        (0x05, 16),
        (0x06, 64),
        (0x07, 256),
    )

    for tac_value, period in cases:
        await reset_dut(dut)
        await step(dut, sys_counter=0, write_addr=TAC_ADDR, write_data=tac_value)

        for sys_counter in range(1, period):
            snapshot = await step(dut, sys_counter=sys_counter)
            assert snapshot["tima"] == 0x00, (tac_value, sys_counter, snapshot)
            assert snapshot["timer_irq"] is False

        snapshot = await step(dut, sys_counter=period)
        assert snapshot["tima"] == 0x01, (tac_value, period, snapshot)
        assert snapshot["timer_irq"] is False


@cocotb.test()
async def test_div_reset_can_trigger_tima_increment_when_selected_bit_was_high(dut):
    await reset_dut(dut)
    await configure_fast_timer(dut)

    await step(dut, sys_counter=8)
    snapshot = await step(dut, sys_counter=9, write_addr=DIV_ADDR, write_data=0x00)

    assert snapshot["div_reset_request"] is True
    assert snapshot["tima"] == 0x01, snapshot
    assert snapshot["overflow_delay"] == 0


@cocotb.test()
async def test_tima_overflow_reloads_after_one_m_cycle_and_uses_latest_tma(dut):
    await reset_dut(dut)
    await configure_fast_timer(dut, tma=0x3C, tima=0xFF)

    snapshot = await advance_to(dut, start=1, end=16)
    assert snapshot["tima"] == 0x00, snapshot
    assert snapshot["timer_irq"] is False
    assert snapshot["overflow_delay"] == 4

    for sys_counter, expected_delay in ((17, 3), (18, 2)):
        snapshot = await step(dut, sys_counter=sys_counter)
        assert snapshot["tima"] == 0x00, (sys_counter, snapshot)
        assert snapshot["overflow_delay"] == expected_delay
        assert snapshot["timer_irq"] is False

    snapshot = await step(dut, sys_counter=19, write_addr=TMA_ADDR, write_data=0x55)
    assert snapshot["tma"] == 0x55
    assert snapshot["overflow_delay"] == 1
    assert snapshot["timer_irq"] is False

    snapshot = await step(dut, sys_counter=20)
    assert snapshot["tima"] == 0x55, snapshot
    assert snapshot["timer_irq"] is True
    assert snapshot["overflow_delay"] == 0


@cocotb.test()
async def test_writing_tima_during_overflow_delay_cancels_reload_and_interrupt(dut):
    await reset_dut(dut)
    await configure_fast_timer(dut, tma=0x77, tima=0xFF)

    snapshot = await advance_to(dut, start=1, end=16)
    assert snapshot["overflow_delay"] == 4

    snapshot = await step(dut, sys_counter=17)
    assert snapshot["overflow_delay"] == 3

    snapshot = await step(dut, sys_counter=18, write_addr=TIMA_ADDR, write_data=0x44)
    assert snapshot["tima"] == 0x44
    assert snapshot["overflow_delay"] == 0
    assert snapshot["timer_irq"] is False

    snapshot = await step(dut, sys_counter=19)
    assert snapshot["tima"] == 0x44
    assert snapshot["timer_irq"] is False
    assert snapshot["overflow_delay"] == 0

    snapshot = await step(dut, sys_counter=20)
    assert snapshot["tima"] == 0x44
    assert snapshot["timer_irq"] is False
    assert snapshot["overflow_delay"] == 0


@cocotb.test()
async def test_tac_enable_disable_edges_do_not_spuriously_increment_tima(dut):
    await reset_dut(dut)
    await step(dut, sys_counter=0, write_addr=TIMA_ADDR, write_data=0x10)
    await step(dut, sys_counter=0, write_addr=TAC_ADDR, write_data=0x00)

    snapshot = await step(dut, sys_counter=8)
    log_cycle(8, snapshot, note="timer disabled, selected fast bit would be high")
    assert snapshot["tima"] == 0x10, snapshot

    snapshot = await step(dut, sys_counter=9, write_addr=TAC_ADDR, write_data=0x05)
    log_cycle(9, snapshot, note="enable fast timer while selected bit is high")
    assert snapshot["tima"] == 0x10, snapshot
    assert snapshot["tac"] == 0x05, snapshot

    snapshot = await step(dut, sys_counter=10, write_addr=TAC_ADDR, write_data=0x00)
    log_cycle(10, snapshot, note="disable timer while previously sampled bit was high")
    assert snapshot["tima"] == 0x10, snapshot
    assert snapshot["tac"] == 0x00, snapshot

    snapshot = await step(dut, sys_counter=11)
    log_cycle(11, snapshot, note="remain stopped after disable edge")
    assert snapshot["tima"] == 0x10, snapshot
    assert snapshot["timer_irq"] is False


@cocotb.test()
async def test_tac_clock_select_change_can_trigger_falling_edge_increment(dut):
    await reset_dut(dut)
    await configure_fast_timer(dut, tima=0x20)

    snapshot = await step(dut, sys_counter=8)
    log_cycle(8, snapshot, note="fast-rate selected bit sampled high")
    assert snapshot["tima"] == 0x20, snapshot

    snapshot = await step(dut, sys_counter=9, write_addr=TAC_ADDR, write_data=0x07)
    log_cycle(9, snapshot, note="switch to /256 source, selected bit falls 1->0")
    assert snapshot["tac"] == 0x07, snapshot
    assert snapshot["tima"] == 0x21, snapshot
    assert snapshot["timer_irq"] is False


@cocotb.test()
async def test_tma_write_on_final_delay_cycle_sets_reload_value(dut):
    await reset_dut(dut)
    await configure_fast_timer(dut, tma=0x33, tima=0xFF)

    snapshot = await advance_to(dut, start=1, end=16)
    log_cycle(16, snapshot, note="overflow scheduled")
    assert snapshot["overflow_delay"] == 4

    for sys_counter, expected_delay in ((17, 3), (18, 2), (19, 1)):
        snapshot = await step(dut, sys_counter=sys_counter)
        log_cycle(sys_counter, snapshot)
        assert snapshot["overflow_delay"] == expected_delay, (sys_counter, snapshot)

    snapshot = await step(dut, sys_counter=20, write_addr=TMA_ADDR, write_data=0x99)
    log_cycle(20, snapshot, note="write TMA on final reload cycle")
    assert snapshot["tma"] == 0x99, snapshot
    assert snapshot["tima"] == 0x99, snapshot
    assert snapshot["timer_irq"] is True
    assert snapshot["overflow_delay"] == 0


@cocotb.test()
async def test_div_and_tima_stay_aligned_with_shared_timebase(dut):
    await reset_dut(dut)
    await configure_fast_timer(dut)

    snapshot = decode_timer(int(dut.output__.value))
    for sys_counter in range(1, 513):
        snapshot = await step(dut, sys_counter=sys_counter)
        expected_div = (sys_counter >> 8) & 0xFF
        expected_tima = (sys_counter // 16) & 0xFF
        if sys_counter in (15, 16, 255, 256, 511, 512):
            log_cycle(sys_counter, snapshot, note="shared-timebase boundary")
        assert snapshot["div"] == expected_div, (sys_counter, expected_div, snapshot)
        assert snapshot["tima"] == expected_tima, (sys_counter, expected_tima, snapshot)
