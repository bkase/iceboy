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
        "t_ce": bool((output_value >> 65) & 0x1),
        "m_ce": bool((output_value >> 64) & 0x1),
        "sys_counter": (output_value >> 32) & 0xFFFF_FFFF,
        "t_index": (output_value >> 30) & 0x3,
        "m_index": output_value & 0x3FFF_FFFF,
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
