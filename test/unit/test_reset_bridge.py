# top = board::reset_bridge_test_top::reset_bridge_test_top
from __future__ import annotations

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer


RANDOM_SEQUENCE_COUNT = 1_000


def decode_status(value: int) -> dict[str, int | bool]:
    return {
        "rst": bool(value & 0x1),
        "sync_btn_n": bool((value >> 1) & 0x1),
        "debounced_btn_n": bool((value >> 2) & 0x1),
        "counter": (value >> 3) & 0xFFFF,
    }


def saturating_inc(counter: int) -> int:
    return min(counter + 1, 0xFFFF)


class ResetBridgeModel:
    def __init__(self, debounce_ticks: int, release_hold_ticks: int) -> None:
        self.debounce_ticks = debounce_ticks
        self.release_hold_ticks = release_hold_ticks
        self.sync0 = False
        self.sync1 = False
        self.debounced_btn_n = False
        self.counter = 0

    def stable_ticks_required(self, sync_btn_n: bool) -> int:
        if sync_btn_n:
            return min(self.debounce_ticks + self.release_hold_ticks, 0xFFFF)
        return self.debounce_ticks

    def step(self, btn_n: bool) -> dict[str, int | bool]:
        sampled_sync_btn_n = self.sync1
        required_ticks = self.stable_ticks_required(sampled_sync_btn_n)
        next_counter = saturating_inc(self.counter)
        transition_ready = required_ticks == 0 or next_counter >= required_ticks

        next_debounced_btn_n = self.debounced_btn_n
        if sampled_sync_btn_n != self.debounced_btn_n and transition_ready:
            next_debounced_btn_n = sampled_sync_btn_n

        if sampled_sync_btn_n == self.debounced_btn_n or transition_ready:
            next_counter_value = 0
        else:
            next_counter_value = next_counter

        old_sync0 = self.sync0
        self.sync0 = btn_n
        self.sync1 = old_sync0
        self.debounced_btn_n = next_debounced_btn_n
        self.counter = next_counter_value

        return {
            "rst": not self.debounced_btn_n,
            "sync_btn_n": self.sync1,
            "debounced_btn_n": self.debounced_btn_n,
            "counter": self.counter,
        }


async def step(dut, *, btn_n: bool) -> dict[str, int | bool]:
    dut.btn_n_i.value = int(btn_n)
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    snapshot = decode_status(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


async def initialize_dut(dut, *, debounce_ticks: int, release_hold_ticks: int, btn_n: bool = False) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.btn_n_i.value = int(btn_n)
    dut.debounce_ticks_i.value = debounce_ticks
    dut.release_hold_ticks_i.value = release_hold_ticks
    await Timer(1, units="ps")


async def boot_released(dut, *, debounce_ticks: int, release_hold_ticks: int) -> ResetBridgeModel:
    model = ResetBridgeModel(debounce_ticks, release_hold_ticks)
    await initialize_dut(dut, debounce_ticks=debounce_ticks, release_hold_ticks=release_hold_ticks, btn_n=False)

    for bootstrap_step in range(2):
        observed = await step(dut, btn_n=False)
        expected = model.step(False)
        assert_snapshot_matches(observed, expected, step_index=bootstrap_step)

    for release_step in range(32):
        observed = await step(dut, btn_n=True)
        expected = model.step(True)
        assert_snapshot_matches(observed, expected, step_index=2 + release_step)
        if observed["rst"] is False:
            return model
    raise AssertionError("reset bridge never released from its startup asserted state")


def assert_snapshot_matches(
    observed: dict[str, int | bool],
    expected: dict[str, int | bool],
    *,
    step_index: int,
) -> None:
    assert observed == expected, f"mismatch at step {step_index}: observed={observed} expected={expected}"


@cocotb.test()
async def test_clean_press_and_release_honor_debounce_and_release_hold(dut):
    debounce_ticks = 3
    release_hold_ticks = 2
    model = await boot_released(dut, debounce_ticks=debounce_ticks, release_hold_ticks=release_hold_ticks)

    press_snapshots = []
    for step_index in range(5):
        observed = await step(dut, btn_n=False)
        expected = model.step(False)
        assert_snapshot_matches(observed, expected, step_index=step_index)
        press_snapshots.append(observed)
    assert all(snapshot["rst"] is False for snapshot in press_snapshots[:-1])
    assert press_snapshots[-1]["rst"] is True

    release_snapshots = []
    for step_index in range(7):
        observed = await step(dut, btn_n=True)
        expected = model.step(True)
        assert_snapshot_matches(observed, expected, step_index=5 + step_index)
        release_snapshots.append(observed)
    assert all(snapshot["rst"] is True for snapshot in release_snapshots[:-1])
    assert release_snapshots[-1]["rst"] is False


@cocotb.test()
async def test_short_press_shorter_than_dwell_does_not_assert_reset(dut):
    debounce_ticks = 4
    release_hold_ticks = 1
    model = await boot_released(dut, debounce_ticks=debounce_ticks, release_hold_ticks=release_hold_ticks)

    short_press = []
    for step_index in range(3):
        observed = await step(dut, btn_n=False)
        expected = model.step(False)
        assert_snapshot_matches(observed, expected, step_index=step_index)
        short_press.append(observed)
    assert all(snapshot["rst"] is False for snapshot in short_press)

    release = []
    for step_index in range(4):
        observed = await step(dut, btn_n=True)
        expected = model.step(True)
        assert_snapshot_matches(observed, expected, step_index=3 + step_index)
        release.append(observed)
    assert all(snapshot["rst"] is False for snapshot in release)


@cocotb.test()
async def test_boundary_dwell_and_one_cycle_pulses_are_filtered(dut):
    debounce_ticks = 3
    model = await boot_released(dut, debounce_ticks=debounce_ticks, release_hold_ticks=0)

    step_index = 0
    for _ in range(8):
        observed_low = await step(dut, btn_n=False)
        expected_low = model.step(False)
        assert_snapshot_matches(observed_low, expected_low, step_index=step_index)
        step_index += 1
        assert observed_low["rst"] is False

        observed_high = await step(dut, btn_n=True)
        expected_high = model.step(True)
        assert_snapshot_matches(observed_high, expected_high, step_index=step_index)
        step_index += 1
        assert observed_high["rst"] is False

    pre_boundary = []
    for _ in range(4):
        observed = await step(dut, btn_n=False)
        expected = model.step(False)
        assert_snapshot_matches(observed, expected, step_index=step_index)
        step_index += 1
        pre_boundary.append(observed)
    assert all(snapshot["rst"] is False for snapshot in pre_boundary)
    boundary = await step(dut, btn_n=False)
    expected_boundary = model.step(False)
    assert_snapshot_matches(boundary, expected_boundary, step_index=step_index)
    assert boundary["rst"] is True


@cocotb.test()
async def test_random_bounce_sequences_match_reference_model(dut):
    debounce_ticks = 4
    release_hold_ticks = 3
    rng = random.Random(0x161E)
    model = await boot_released(dut, debounce_ticks=debounce_ticks, release_hold_ticks=release_hold_ticks)

    step_index = 0
    for _ in range(RANDOM_SEQUENCE_COUNT):
        bounce_length = rng.randint(1, 8)
        for _ in range(bounce_length):
            btn_n = bool(rng.getrandbits(1))
            observed = await step(dut, btn_n=btn_n)
            expected = model.step(btn_n)
            assert_snapshot_matches(observed, expected, step_index=step_index)
            step_index += 1

        settled_btn_n = bool(rng.getrandbits(1))
        settled_cycles = rng.randint(1, 6)
        for _ in range(settled_cycles):
            observed = await step(dut, btn_n=settled_btn_n)
            expected = model.step(settled_btn_n)
            assert_snapshot_matches(observed, expected, step_index=step_index)
            step_index += 1
