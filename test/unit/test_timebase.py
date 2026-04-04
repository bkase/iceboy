# top = board::clockgen::timebase
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge


BOARD_CLOCKS_PER_T_CYCLE = 1
T_CYCLES_PER_M_CYCLE = 4
SHORT_RUN_BOARD_CLOCKS = 100
LONG_RUN_BOARD_CLOCKS = 1024


def decode_timebase(output_value: int) -> dict[str, int | bool]:
    return {
        "t_ce": bool((output_value >> 85) & 0x1),
        "m_ce": bool((output_value >> 84) & 0x1),
        "sys_counter": (output_value >> 52) & 0xFFFF_FFFF,
        "t_index": (output_value >> 50) & 0x3,
        "m_index": (output_value >> 20) & 0x3FFF_FFFF,
        "dot_ce": bool((output_value >> 19) & 0x1),
        "line_start": bool((output_value >> 18) & 0x1),
        "frame_start": bool((output_value >> 17) & 0x1),
        "line_index": (output_value >> 9) & 0xFF,
        "dot_in_line": output_value & 0x1FF,
    }


async def reset_dut(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.rst_i.value = 1
    await ClockCycles(dut.clk_i, 3)
    dut.rst_i.value = 0
    await ReadOnly()


async def sample_cycle(dut) -> dict[str, int | bool]:
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    return decode_timebase(int(dut.output__.value))


async def sample_cycles(dut, board_clocks: int) -> list[dict[str, int | bool]]:
    return [await sample_cycle(dut) for _ in range(board_clocks)]


def expected_t_ce_count(board_clocks: int, board_clocks_per_t_cycle: int = BOARD_CLOCKS_PER_T_CYCLE) -> int:
    return board_clocks // board_clocks_per_t_cycle


def expected_m_ce_count(board_clocks: int) -> int:
    return expected_t_ce_count(board_clocks) // T_CYCLES_PER_M_CYCLE


@cocotb.test()
async def test_timebase_reset_behavior(dut):
    await reset_dut(dut)
    snapshot = decode_timebase(int(dut.output__.value))
    assert snapshot == {
        "t_ce": True,
        "m_ce": False,
        "sys_counter": 0,
        "t_index": 0,
        "m_index": 0,
        "dot_ce": True,
        "line_start": True,
        "frame_start": True,
        "line_index": 0,
        "dot_in_line": 0,
    }, snapshot


@cocotb.test()
async def test_timebase_enable_patterns_and_indices(dut):
    await reset_dut(dut)
    samples = await sample_cycles(dut, 16)

    t_ce_count = sum(1 for sample in samples if sample["t_ce"])
    m_ce_edges = [index for index, sample in enumerate(samples, start=1) if sample["m_ce"]]
    t_indices = [sample["t_index"] for sample in samples]
    m_indices = [sample["m_index"] for sample in samples]
    sys_counters = [sample["sys_counter"] for sample in samples]

    assert t_ce_count == 16, samples
    assert m_ce_edges == [3, 7, 11, 15], m_ce_edges
    assert t_indices == [1, 2, 3, 0] * 4, t_indices
    assert sys_counters == list(range(1, 17)), sys_counters
    assert m_indices == [0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4], m_indices
    assert all(sample["dot_ce"] for sample in samples), samples
    assert [sample["dot_in_line"] for sample in samples[:6]] == [1, 2, 3, 4, 5, 6]
    assert [sample["line_index"] for sample in samples[:6]] == [0, 0, 0, 0, 0, 0]
    assert sum(1 for sample in samples if sample["line_start"]) == 0
    assert sum(1 for sample in samples if sample["frame_start"]) == 0


@cocotb.test()
async def test_timebase_m_cycle_pattern(dut):
    await reset_dut(dut)
    samples = await sample_cycles(dut, SHORT_RUN_BOARD_CLOCKS)

    t_ce_count = sum(1 for sample in samples if sample["t_ce"])
    m_ce_count = sum(1 for sample in samples if sample["m_ce"])
    m_ce_t_indices = [sample["t_index"] for sample in samples if sample["m_ce"]]
    final_snapshot = samples[-1]

    dut._log.info(
        "[timebase] test_m_cycle_pattern: board_clocks=%d t_ce=%d expected_t_ce=%d "
        "m_ce=%d expected_m_ce=%d t_index_at_m_ce=%s sys_counter_final=%d",
        SHORT_RUN_BOARD_CLOCKS,
        t_ce_count,
        expected_t_ce_count(SHORT_RUN_BOARD_CLOCKS),
        m_ce_count,
        expected_m_ce_count(SHORT_RUN_BOARD_CLOCKS),
        m_ce_t_indices,
        final_snapshot["sys_counter"],
    )

    assert t_ce_count == expected_t_ce_count(SHORT_RUN_BOARD_CLOCKS)
    assert m_ce_count == expected_m_ce_count(SHORT_RUN_BOARD_CLOCKS)
    assert all(t_index == T_CYCLES_PER_M_CYCLE - 1 for t_index in m_ce_t_indices), m_ce_t_indices
    assert final_snapshot["sys_counter"] == SHORT_RUN_BOARD_CLOCKS
    assert final_snapshot["m_index"] == expected_m_ce_count(SHORT_RUN_BOARD_CLOCKS)
    assert final_snapshot["line_index"] == 0
    assert final_snapshot["dot_in_line"] == SHORT_RUN_BOARD_CLOCKS
    assert final_snapshot["dot_ce"] == final_snapshot["t_ce"]


@cocotb.test()
async def test_timebase_long_run_consistency(dut):
    await reset_dut(dut)
    samples = await sample_cycles(dut, LONG_RUN_BOARD_CLOCKS)

    t_ce_count = 0
    m_ce_count = 0
    last_sys_counter = 0
    last_m_index = 0
    consecutive_t_ce = 0
    consecutive_m_ce = 0
    previous_t_ce = False
    previous_m_ce = False

    for snapshot in samples:
        t_ce_count += int(snapshot["t_ce"])
        m_ce_count += int(snapshot["m_ce"])
        consecutive_t_ce += int(previous_t_ce and snapshot["t_ce"])
        consecutive_m_ce += int(previous_m_ce and snapshot["m_ce"])

        assert snapshot["sys_counter"] >= last_sys_counter
        assert snapshot["m_index"] >= last_m_index
        assert not snapshot["m_ce"] or snapshot["t_ce"]

        last_sys_counter = int(snapshot["sys_counter"])
        last_m_index = int(snapshot["m_index"])
        previous_t_ce = bool(snapshot["t_ce"])
        previous_m_ce = bool(snapshot["m_ce"])

    if BOARD_CLOCKS_PER_T_CYCLE == 1:
        assert consecutive_t_ce == LONG_RUN_BOARD_CLOCKS - 1
    else:
        assert consecutive_t_ce == 0
    assert consecutive_m_ce == 0
    assert t_ce_count == expected_t_ce_count(LONG_RUN_BOARD_CLOCKS)
    assert m_ce_count == expected_m_ce_count(LONG_RUN_BOARD_CLOCKS)
    assert t_ce_count == m_ce_count * T_CYCLES_PER_M_CYCLE
    assert last_sys_counter == LONG_RUN_BOARD_CLOCKS
    assert last_m_index == expected_m_ce_count(LONG_RUN_BOARD_CLOCKS)


@cocotb.test()
async def test_video_dot_counters_wrap_each_scanline(dut):
    await reset_dut(dut)
    samples = await sample_cycles(dut, 456)
    final_snapshot = samples[-1]

    dut._log.info(
        "[timebase] test_video_dot_counters_wrap_each_scanline: final dot=%d line=%d line_start=%s",
        final_snapshot["dot_in_line"],
        final_snapshot["line_index"],
        final_snapshot["line_start"],
    )

    assert final_snapshot["dot_in_line"] == 0
    assert final_snapshot["line_index"] == 1
    assert final_snapshot["line_start"]
    assert not final_snapshot["frame_start"]
    assert sum(1 for sample in samples if sample["line_start"]) == 1
    assert sum(1 for sample in samples if sample["frame_start"]) == 0


@cocotb.test()
async def test_video_dot_counters_wrap_each_frame(dut):
    await reset_dut(dut)
    frame_dots = 456 * 154
    samples = await sample_cycles(dut, frame_dots)
    final_snapshot = samples[-1]

    dut._log.info(
        "[timebase] test_video_dot_counters_wrap_each_frame: final dot=%d line=%d frame_start=%s",
        final_snapshot["dot_in_line"],
        final_snapshot["line_index"],
        final_snapshot["frame_start"],
    )

    assert final_snapshot["dot_in_line"] == 0
    assert final_snapshot["line_index"] == 0
    assert final_snapshot["line_start"]
    assert final_snapshot["frame_start"]
    assert sum(1 for sample in samples if sample["line_start"]) == 154
    assert sum(1 for sample in samples if sample["frame_start"]) == 1
