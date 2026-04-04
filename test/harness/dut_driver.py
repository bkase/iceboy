from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spec.profiles import CPU_BRING_UP_PROFILES, MemoryBehaviorProfile, ModelProfile, ResetProfile, SimulationProfiles


JOYPAD_BITS = ("up", "down", "left", "right", "a", "b", "start", "select")


def _enum_bit(value: object, zero: object, one: object) -> int:
    if value == zero:
        return 0
    if value == one:
        return 1
    raise ValueError(f"Unsupported profile variant: {value}")


def encode_profiles(profiles: SimulationProfiles) -> int:
    return (
        (_enum_bit(profiles.model, ModelProfile.DMG, ModelProfile.CGB) << 2)
        | (_enum_bit(profiles.reset, ResetProfile.SkipBoot, ResetProfile.RawPowerOn) << 1)
        | _enum_bit(
            profiles.memory_behavior,
            MemoryBehaviorProfile.DmgConservative,
            MemoryBehaviorProfile.DmgRevisionSpecific,
        )
    )


@dataclass(frozen=True)
class JoypadState:
    up: bool = False
    down: bool = False
    left: bool = False
    right: bool = False
    a: bool = False
    b: bool = False
    start: bool = False
    select: bool = False

    def encode(self) -> int:
        value = 0
        for bit_index, name in enumerate(reversed(JOYPAD_BITS)):
            value |= int(bool(getattr(self, name))) << bit_index
        return value


@dataclass(frozen=True)
class SimStimulus:
    joyp_buttons: JoypadState | None = None
    if_set_bits: int = 0
    if_clear_bits: int = 0
    ie_override: int | None = None
    dma_start: int | None = None
    serial_inject: int | None = None
    freeze_arch_time: bool = False
    cpu_hold_only: bool = False

    @classmethod
    def idle(cls) -> "SimStimulus":
        return cls()

    def encode(self) -> int:
        value = 0
        if self.joyp_buttons is not None:
            value |= ((1 << 8) | self.joyp_buttons.encode()) << 36
        value |= (self.if_set_bits & 0x1F) << 31
        value |= (self.if_clear_bits & 0x1F) << 26
        if self.ie_override is not None:
            value |= ((1 << 5) | (self.ie_override & 0x1F)) << 20
        if self.dma_start is not None:
            value |= ((1 << 8) | (self.dma_start & 0xFF)) << 11
        if self.serial_inject is not None:
            value |= ((1 << 8) | (self.serial_inject & 0xFF)) << 2
        value |= int(self.freeze_arch_time) << 1
        value |= int(self.cpu_hold_only)
        return value


@dataclass(frozen=True)
class CpuCommitTrace:
    seq: int
    bus_read_data: int
    irq_pending: int
    cpu_arch_time_enable: bool
    freeze_arch_time: bool
    cpu_hold_only: bool
    ime_state: int = 0
    halt_state: int = 0
    phase_kind: int = 0
    commit_seq: int = 0
    pc: int = 0
    bus_req_kind: int = 0
    bus_req_addr: int = 0
    bus_req_data: int = 0
    bus_region: int = 0
    bus_owner: int = 0
    bus_blocked: bool = False
    irq_ack_valid: bool = False
    irq_ack_bit: int = 0

    @classmethod
    def from_output(cls, output_value: int, *, seq: int) -> "CpuCommitTrace":
        return cls(
            seq=seq,
            ime_state=(output_value >> 139) & 0x3,
            halt_state=(output_value >> 137) & 0x3,
            phase_kind=(output_value >> 133) & 0xF,
            irq_ack_valid=bool((output_value >> 132) & 0x1),
            irq_ack_bit=(output_value >> 129) & 0x7,
            commit_seq=(output_value >> 65) & 0xFFFF_FFFF_FFFF_FFFF,
            pc=(output_value >> 49) & 0xFFFF,
            bus_req_kind=(output_value >> 47) & 0x3,
            bus_req_addr=(output_value >> 31) & 0xFFFF,
            bus_req_data=(output_value >> 23) & 0xFF,
            bus_region=(output_value >> 19) & 0xF,
            bus_owner=(output_value >> 17) & 0x3,
            bus_blocked=bool((output_value >> 16) & 0x1),
            bus_read_data=(output_value >> 8) & 0xFF,
            irq_pending=(output_value >> 3) & 0x1F,
            cpu_arch_time_enable=bool((output_value >> 2) & 0x1),
            freeze_arch_time=bool((output_value >> 1) & 0x1),
            cpu_hold_only=bool(output_value & 0x1),
        )


@dataclass(frozen=True)
class SoCLockstepObservation:
    ppu_scanout_valid: bool = False
    ppu_scanout_kind: int = 0
    ppu_scanout_x: int = 0
    ppu_scanout_y: int = 0
    ppu_scanout_shade: int = 0
    ppu_scanout_source: int = 0
    ppu_blank_reason: int = 0
    ppu_semantic_valid: bool = False
    ppu_semantic_ly: int = 0
    ppu_semantic_mode: int = 0
    ppu_semantic_stat_line: bool = False
    ppu_semantic_irq_edge: int = 0
    ppu_mode: int = 0
    ppu_ly: int = 0
    ppu_stat: int = 0
    ppu_dot_in_line: int = 0
    ppu_vblank_req: bool = False
    ppu_stat_req: bool = False
    model_profile: int = 0
    reset_profile: int = 0
    memory_behavior_profile: int = 0
    cpu_arch_time_enable: bool = False
    peripheral_arch_time_enable: bool = False
    irq_pending: int = 0
    bus_read_data: int = 0
    commit_seq: int = 0
    pc: int = 0
    bus_req_kind: int = 0
    bus_req_addr: int = 0
    bus_req_data: int = 0
    sys_counter: int = 0
    t_index: int = 0
    m_index: int = 0
    m_ce: bool = False
    bus_region: int = 0
    bus_owner: int = 0
    bus_blocked: bool = False

    @classmethod
    def from_output(cls, output_value: int) -> "SoCLockstepObservation":
        return cls(
            ppu_scanout_valid=bool((output_value >> 268) & 0x1),
            ppu_scanout_kind=(output_value >> 266) & 0x3,
            ppu_scanout_x=(output_value >> 258) & 0xFF,
            ppu_scanout_y=(output_value >> 250) & 0xFF,
            ppu_scanout_shade=(output_value >> 248) & 0x3,
            ppu_scanout_source=(output_value >> 246) & 0x3,
            ppu_blank_reason=(output_value >> 244) & 0x3,
            ppu_semantic_valid=bool((output_value >> 243) & 0x1),
            ppu_semantic_ly=(output_value >> 235) & 0xFF,
            ppu_semantic_mode=(output_value >> 232) & 0x7,
            ppu_semantic_stat_line=bool((output_value >> 231) & 0x1),
            ppu_semantic_irq_edge=(output_value >> 229) & 0x3,
            ppu_mode=(output_value >> 226) & 0x7,
            ppu_ly=(output_value >> 218) & 0xFF,
            ppu_stat=(output_value >> 210) & 0xFF,
            ppu_dot_in_line=(output_value >> 201) & 0x1FF,
            ppu_vblank_req=bool((output_value >> 200) & 0x1),
            ppu_stat_req=bool((output_value >> 199) & 0x1),
            commit_seq=(output_value >> 135) & 0xFFFF_FFFF_FFFF_FFFF,
            pc=(output_value >> 119) & 0xFFFF,
            bus_req_kind=(output_value >> 117) & 0x3,
            bus_req_addr=(output_value >> 101) & 0xFFFF,
            bus_req_data=(output_value >> 93) & 0xFF,
            sys_counter=(output_value >> 61) & 0xFFFF_FFFF,
            t_index=(output_value >> 59) & 0x3,
            m_index=(output_value >> 29) & 0x3FFF_FFFF,
            m_ce=bool((output_value >> 28) & 0x1),
            bus_region=(output_value >> 24) & 0xF,
            bus_owner=(output_value >> 22) & 0x3,
            bus_blocked=bool((output_value >> 21) & 0x1),
            model_profile=(output_value >> 19) & 0x3,
            reset_profile=(output_value >> 17) & 0x3,
            memory_behavior_profile=(output_value >> 15) & 0x3,
            cpu_arch_time_enable=bool((output_value >> 14) & 0x1),
            peripheral_arch_time_enable=bool((output_value >> 13) & 0x1),
            irq_pending=(output_value >> 8) & 0x1F,
            bus_read_data=output_value & 0xFF,
        )


class CpuTestDriver:
    def __init__(
        self,
        dut: Any,
        *,
        logger: Any | None = None,
        clock_period_ns: int = 10,
    ) -> None:
        self.dut = dut
        self.logger = logger
        self.clock_period_ns = clock_period_ns
        self._clock_started = False
        self._seq = 0

    async def ensure_clock(self) -> None:
        if self._clock_started:
            return
        import cocotb
        from cocotb.clock import Clock

        cocotb.start_soon(Clock(self.dut.clk_i, self.clock_period_ns, units="ns").start())
        self._clock_started = True

    async def reset(self, reset_profile: ResetProfile, cycles: int | None = None) -> None:
        from cocotb.triggers import ClockCycles, RisingEdge

        await self.ensure_clock()
        self._seq = 0
        held_cycles = cycles if cycles is not None else (2 if reset_profile is ResetProfile.SkipBoot else 8)
        self.inject_stimulus(SimStimulus(freeze_arch_time=True, cpu_hold_only=True))
        self.set_bus_inputs(bus_read_data=0, irq_pending=0)
        self.dut.rst_i.value = 1
        await ClockCycles(self.dut.clk_i, held_cycles)
        self.dut.rst_i.value = 0
        await RisingEdge(self.dut.clk_i)

    def inject_stimulus(self, stimulus: SimStimulus) -> None:
        self.dut.stimulus_i.value = stimulus.encode()

    def set_bus_inputs(self, *, bus_read_data: int, irq_pending: int) -> None:
        self.dut.bus_read_data_i.value = bus_read_data & 0xFF
        self.dut.irq_pending_i.value = irq_pending & 0x1F

    def read_signal(self, name: str) -> int:
        return int(getattr(self.dut, name).value)

    def observe(self) -> CpuCommitTrace:
        return CpuCommitTrace.from_output(int(self.dut.output__.value), seq=self._seq)

    async def step_mcycle(
        self,
        *,
        stimulus: SimStimulus | None = None,
        bus_read_data: int | None = None,
        irq_pending: int | None = None,
    ) -> CpuCommitTrace:
        from cocotb.triggers import RisingEdge

        self.inject_stimulus(stimulus or SimStimulus.idle())
        if bus_read_data is not None or irq_pending is not None:
            self.set_bus_inputs(
                bus_read_data=0 if bus_read_data is None else bus_read_data,
                irq_pending=0 if irq_pending is None else irq_pending,
            )
        await RisingEdge(self.dut.clk_i)
        self._seq += 1
        return self.observe()

    async def step_instruction(self, *, max_mcycles: int = 1) -> CpuCommitTrace:
        trace = self.observe()
        for _ in range(max_mcycles):
            trace = await self.step_mcycle()
        return trace


class SoCLockstepDriver:
    def __init__(self, dut: Any, *, logger: Any | None = None, clock_period_ns: int = 10) -> None:
        self.dut = dut
        self.logger = logger
        self.clock_period_ns = clock_period_ns
        self._clock_started = False

    async def ensure_clock(self) -> None:
        if self._clock_started:
            return
        import cocotb
        from cocotb.clock import Clock

        cocotb.start_soon(Clock(self.dut.clk_i, self.clock_period_ns, units="ns").start())
        self._clock_started = True

    async def reset(
        self,
        profiles: SimulationProfiles = CPU_BRING_UP_PROFILES,
        *,
        stimulus: SimStimulus | None = None,
        cycles: int = 2,
    ) -> None:
        from cocotb.triggers import ClockCycles, RisingEdge

        await self.ensure_clock()
        self.set_profiles(profiles)
        self.inject_stimulus(stimulus or SimStimulus(freeze_arch_time=True, cpu_hold_only=True))
        self.set_bus_inputs(bus_read_data=0, irq_pending=0)
        self.dut.rst_i.value = 1
        await ClockCycles(self.dut.clk_i, cycles)
        self.dut.rst_i.value = 0
        await RisingEdge(self.dut.clk_i)

    def set_profiles(self, profiles: SimulationProfiles = CPU_BRING_UP_PROFILES) -> None:
        self.dut.profiles_i.value = encode_profiles(profiles)

    def inject_stimulus(self, stimulus: SimStimulus) -> None:
        self.dut.stimulus_i.value = stimulus.encode()

    def set_bus_inputs(self, *, bus_read_data: int, irq_pending: int) -> None:
        self.dut.bus_read_data_i.value = bus_read_data & 0xFF
        self.dut.irq_pending_i.value = irq_pending & 0x1F

    def observe(self) -> SoCLockstepObservation:
        return SoCLockstepObservation.from_output(int(self.dut.output__.value))

    async def step_mcycle(
        self,
        *,
        stimulus: SimStimulus | None = None,
        bus_read_data: int | None = None,
        irq_pending: int | None = None,
    ) -> SoCLockstepObservation:
        from cocotb.triggers import RisingEdge

        self.inject_stimulus(stimulus or SimStimulus.idle())
        if bus_read_data is not None or irq_pending is not None:
            self.set_bus_inputs(
                bus_read_data=0 if bus_read_data is None else bus_read_data,
                irq_pending=0 if irq_pending is None else irq_pending,
            )
        await RisingEdge(self.dut.clk_i)
        return self.observe()
