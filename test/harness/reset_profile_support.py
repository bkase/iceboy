from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from spec.profiles import CPU_BRING_UP_PROFILES, ModelProfile, ResetProfile, SimulationProfiles


@dataclass(frozen=True)
class ExpectedResetState:
    a: int
    f: int
    b: int
    c: int
    d: int
    e: int
    h: int
    l: int
    sp: int
    pc: int
    ie: int
    if_: int
    ime_enabled: bool
    tima: int
    tma: int
    tac: int
    joyp: int
    lcdc: int
    stat: int
    scy: int
    scx: int
    ly: int
    lyc: int
    bgp: int
    obp0: int
    obp1: int
    wy: int
    wx: int


DMG_SKIPBOOT_EXPECTED_STATE = ExpectedResetState(
    a=0x01,
    f=0xB0,
    b=0x00,
    c=0x13,
    d=0x00,
    e=0xD8,
    h=0x01,
    l=0x4D,
    sp=0xFFFE,
    pc=0x0100,
    ie=0x00,
    if_=0xE1,
    ime_enabled=False,
    tima=0x00,
    tma=0x00,
    tac=0x00,
    joyp=0xCF,
    lcdc=0x91,
    stat=0x85,
    scy=0x00,
    scx=0x00,
    ly=0x00,
    lyc=0x00,
    bgp=0xFC,
    obp0=0xFF,
    obp1=0xFF,
    wy=0x00,
    wx=0x00,
)


def expected_reset_state_for(profiles: SimulationProfiles = CPU_BRING_UP_PROFILES) -> ExpectedResetState:
    if profiles.model is ModelProfile.DMG and profiles.reset is ResetProfile.SkipBoot:
        return DMG_SKIPBOOT_EXPECTED_STATE
    raise NotImplementedError(f"Reset-state scaffold only defines DMG + SkipBoot, got {profiles!r}")


def capture_dut_reset_state(driver: Any) -> ExpectedResetState:
    raise NotImplementedError(
        "cpu_test_top does not yet expose architectural reset state; wire register, interrupt, "
        "and key IO visibility into the sim surface before enabling this compare."
    )
