# top = periph::button_bank_test_top::button_bank_test_top
from __future__ import annotations

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer


RANDOM_SEQUENCE_COUNT = 1_000


def unpack_bits(value: int, width: int) -> list[bool]:
    return [bool((value >> index) & 0x1) for index in range(width)]


def decode_output(value: int) -> dict[str, list[bool]]:
    return {
        "raw_sync4": unpack_bits((value >> 20) & 0xF, 4),
        "debounced4": unpack_bits((value >> 16) & 0xF, 4),
        "rising4": unpack_bits((value >> 12) & 0xF, 4),
        "falling4": unpack_bits((value >> 8) & 0xF, 4),
        "raw_sync2": unpack_bits((value >> 6) & 0x3, 2),
        "debounced2": unpack_bits((value >> 4) & 0x3, 2),
        "rising2": unpack_bits((value >> 2) & 0x3, 2),
        "falling2": unpack_bits(value & 0x3, 2),
    }


class ButtonBankModel:
    def __init__(self, width: int, debounce_bits: int) -> None:
        self.width = width
        self.threshold_mask = 1 << (debounce_bits - 1)
        self.counter_max = (1 << debounce_bits) - 1
        self.sync0 = [False] * width
        self.sync1 = [False] * width
        self.counters = [0] * width
        self.debounced = [False] * width

    def step(self, buttons: int) -> dict[str, list[bool]]:
        sampled_sync = list(self.sync1)
        next_sync0 = [bool((buttons >> index) & 0x1) for index in range(self.width)]
        next_sync1 = list(self.sync0)
        next_counters = []
        next_debounced = []
        for index in range(self.width):
            if sampled_sync[index]:
                next_counter = min(self.counters[index] + 1, self.counter_max)
            else:
                next_counter = max(self.counters[index] - 1, 0)
            next_counters.append(next_counter)
            next_debounced.append(bool(next_counter & self.threshold_mask))

        rising = [next_debounced[i] and not self.debounced[i] for i in range(self.width)]
        falling = [not next_debounced[i] and self.debounced[i] for i in range(self.width)]

        self.sync0 = next_sync0
        self.sync1 = next_sync1
        self.counters = next_counters
        self.debounced = next_debounced

        return {
            "raw_sync": list(next_sync1),
            "debounced": list(next_debounced),
            "rising": rising,
            "falling": falling,
        }


async def initialize_dut(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.buttons4_i.value = 0
    dut.buttons2_i.value = 0
    await ClockCycles(dut.clk_i, 3)
    await ReadOnly()
    await Timer(1, units="ps")


async def step(dut, *, buttons4: int, buttons2: int) -> dict[str, list[bool]]:
    dut.buttons4_i.value = buttons4 & 0xF
    dut.buttons2_i.value = buttons2 & 0x3
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


def assert_snapshot_matches(
    observed: dict[str, list[bool]],
    expected4: dict[str, list[bool]],
    expected2: dict[str, list[bool]],
    *,
    step_index: int,
) -> None:
    expected = {
        "raw_sync4": expected4["raw_sync"],
        "debounced4": expected4["debounced"],
        "rising4": expected4["rising"],
        "falling4": expected4["falling"],
        "raw_sync2": expected2["raw_sync"],
        "debounced2": expected2["debounced"],
        "rising2": expected2["rising"],
        "falling2": expected2["falling"],
    }
    assert observed == expected, f"mismatch at step {step_index}: observed={observed} expected={expected}"


async def boot_models(dut, model4: ButtonBankModel, model2: ButtonBankModel) -> None:
    await initialize_dut(dut)
    for step_index in range(3):
        observed = await step(dut, buttons4=0, buttons2=0)
        expected4 = model4.step(0)
        expected2 = model2.step(0)
        assert_snapshot_matches(observed, expected4, expected2, step_index=step_index)


@cocotb.test()
async def test_clean_press_release_and_edges_match_reference_model(dut):
    model4 = ButtonBankModel(width=4, debounce_bits=3)
    model2 = ButtonBankModel(width=2, debounce_bits=2)
    await boot_models(dut, model4, model2)

    sequence = (
        [(0b0000, 0b00)] * 2
        + [(0b0101, 0b01)] * 5
        + [(0b0101, 0b01)] * 2
        + [(0b0000, 0b00)] * 5
    )

    for step_index, (buttons4, buttons2) in enumerate(sequence, start=3):
        observed = await step(dut, buttons4=buttons4, buttons2=buttons2)
        expected4 = model4.step(buttons4)
        expected2 = model2.step(buttons2)
        assert_snapshot_matches(observed, expected4, expected2, step_index=step_index)

    for step_index in range(3 + len(sequence), 3 + len(sequence) + 5):
        observed = await step(dut, buttons4=0, buttons2=0)
        expected4 = model4.step(0)
        expected2 = model2.step(0)
        assert_snapshot_matches(observed, expected4, expected2, step_index=step_index)

    assert observed["debounced4"] == [False, False, False, False]
    assert observed["debounced2"] == [False, False]


@cocotb.test()
async def test_short_bounces_do_not_cross_the_midpoint_threshold(dut):
    model4 = ButtonBankModel(width=4, debounce_bits=3)
    model2 = ButtonBankModel(width=2, debounce_bits=2)
    await boot_models(dut, model4, model2)

    sequence = [(0b0001, 0b01), (0b0000, 0b00)] * 16
    for step_index, (buttons4, buttons2) in enumerate(sequence, start=3):
        observed = await step(dut, buttons4=buttons4, buttons2=buttons2)
        expected4 = model4.step(buttons4)
        expected2 = model2.step(buttons2)
        assert_snapshot_matches(observed, expected4, expected2, step_index=step_index)
        assert observed["debounced4"][0] is False
        assert observed["debounced2"][0] is False


@cocotb.test()
async def test_random_sequences_match_reference_model_and_inputs_are_independent(dut):
    model4 = ButtonBankModel(width=4, debounce_bits=3)
    model2 = ButtonBankModel(width=2, debounce_bits=2)
    await boot_models(dut, model4, model2)
    rng = random.Random(0x0B38)

    for step_index in range(3, 3 + RANDOM_SEQUENCE_COUNT):
        buttons4 = rng.randrange(16)
        buttons2 = rng.randrange(4)
        observed = await step(dut, buttons4=buttons4, buttons2=buttons2)
        expected4 = model4.step(buttons4)
        expected2 = model2.step(buttons2)
        assert_snapshot_matches(observed, expected4, expected2, step_index=step_index)
