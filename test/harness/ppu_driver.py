from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from test.harness.logging_std import TestLogger


DOTS_PER_LINE = 456
VISIBLE_LINES = 144
LINES_PER_FRAME = 154
FRAME_DOTS = DOTS_PER_LINE * LINES_PER_FRAME

PPU_MODE_LCD_OFF = 0
PPU_MODE_OAM = 1
PPU_MODE_TRANSFER = 2
PPU_MODE_HBLANK = 3
PPU_MODE_VBLANK = 4


def mode_name(mode_kind: int) -> str:
    return {
        PPU_MODE_LCD_OFF: "LcdOff",
        PPU_MODE_OAM: "OamScan",
        PPU_MODE_TRANSFER: "PixelTransfer",
        PPU_MODE_HBLANK: "HBlank",
        PPU_MODE_VBLANK: "VBlank",
    }.get(mode_kind, f"Unknown({mode_kind})")


@dataclass(frozen=True)
class PpuRegWrite:
    addr: int
    value: int


@dataclass(frozen=True)
class PpuStepObservation:
    commit_seq: int
    dot_in_line: int
    line_index: int
    phase_kind: int
    mode_kind: int
    semantic_valid: bool = False
    line_summary_valid: bool = False
    semantic: Any | None = None
    line_summary: Any | None = None
    scanout: Any | None = None


@runtime_checkable
class PpuDriverProtocol(Protocol):
    async def reset(self) -> None: ...

    async def step_dot(self, *, reg_write: PpuRegWrite | None = None) -> PpuStepObservation: ...


@runtime_checkable
class PpuRegisterReadProtocol(Protocol):
    async def read_reg(self, addr: int) -> int: ...


class PpuHarnessBase:
    def __init__(
        self,
        driver: PpuDriverProtocol,
        *,
        logger: TestLogger | None = None,
        suite_name: str = "test/ppu",
    ) -> None:
        self.driver = driver
        self.logger = logger
        self.suite_name = suite_name

    async def reset(self) -> None:
        if self.logger is not None:
            self.logger.step("reset()")
        await self.driver.reset()

    async def write_ppu_reg(self, addr: int, val: int) -> PpuStepObservation:
        if self.logger is not None:
            self.logger.step(f"write_ppu_reg(addr=0x{addr:04x}, val=0x{val:02x})")
        return await self.driver.step_dot(reg_write=PpuRegWrite(addr=addr & 0xFFFF, value=val & 0xFF))

    async def read_ppu_reg(self, addr: int) -> int:
        if not isinstance(self.driver, PpuRegisterReadProtocol):
            raise NotImplementedError("Underlying PPU driver does not implement read_reg(addr)")
        value = await self.driver.read_reg(addr & 0xFFFF)
        if self.logger is not None:
            self.logger.check(f"ppu_reg[0x{addr:04x}]", expected=f"0x{value:02x}", actual=f"0x{value:02x}")
        return value

    async def advance_dots(self, n: int) -> PpuStepObservation:
        if n < 0:
            raise ValueError("advance_dots(n) requires n >= 0")
        if self.logger is not None:
            self.logger.step(f"advance_dots({n})")
        last = PpuStepObservation(commit_seq=0, dot_in_line=0, line_index=0, phase_kind=0, mode_kind=PPU_MODE_LCD_OFF)
        for _ in range(n):
            last = await self.driver.step_dot()
        return last

    async def advance_to_line(self, ly: int, *, max_dots: int = FRAME_DOTS * 2) -> PpuStepObservation:
        if self.logger is not None:
            self.logger.step(f"advance_to_line({ly})")
        for _ in range(max_dots):
            obs = await self.driver.step_dot()
            if obs.line_index == ly:
                if self.logger is not None:
                    self.logger.check("ppu_line", expected=ly, actual=obs.line_index)
                return obs
        raise TimeoutError(f"LY {ly} not reached within {max_dots} dots")

    async def advance_to_mode(self, mode: int, *, max_dots: int = FRAME_DOTS * 2) -> PpuStepObservation:
        if self.logger is not None:
            self.logger.step(f"advance_to_mode({mode_name(mode)})")
        for _ in range(max_dots):
            obs = await self.driver.step_dot()
            if obs.mode_kind == mode:
                if self.logger is not None:
                    self.logger.check("ppu_mode", expected=mode, actual=obs.mode_kind)
                return obs
        raise TimeoutError(f"Mode {mode_name(mode)} not reached within {max_dots} dots")

    async def wait_vblank(self, *, max_dots: int = FRAME_DOTS * 2) -> PpuStepObservation:
        if self.logger is not None:
            self.logger.step("wait_vblank()")
        return await self.advance_to_mode(PPU_MODE_VBLANK, max_dots=max_dots)

    async def capture_line(self, ly: int, *, max_dots: int = FRAME_DOTS * 2) -> tuple[Any, ...]:
        if self.logger is not None:
            self.logger.step(f"capture_line({ly})")
        await self.advance_to_line(ly, max_dots=max_dots)
        captured: list[Any] = []
        for _ in range(DOTS_PER_LINE * 2):
            obs = await self.driver.step_dot()
            if obs.line_index != ly:
                return tuple(captured)
            if obs.scanout is not None:
                captured.append(obs.scanout)
        raise TimeoutError(f"Line {ly} did not complete within {DOTS_PER_LINE * 2} dots")

    async def capture_frame(self, *, max_dots: int = FRAME_DOTS * 3) -> tuple[Any, ...]:
        if self.logger is not None:
            self.logger.step("capture_frame()")
        captured: list[Any] = []
        started = False
        for _ in range(max_dots):
            obs = await self.driver.step_dot()
            if obs.scanout is not None:
                captured.append(obs.scanout)
            if obs.line_index != 0 or obs.dot_in_line != 0:
                started = True
            elif started:
                return tuple(captured)
        raise TimeoutError(f"Frame boundary not observed within {max_dots} dots")


def ppu_test_harness(driver: PpuDriverProtocol, *, logger: TestLogger | None = None) -> PpuHarnessBase:
    return PpuHarnessBase(driver, logger=logger, suite_name="test/ppu/unit")


def ppu_lockstep_harness(driver: PpuDriverProtocol, *, logger: TestLogger | None = None) -> PpuHarnessBase:
    return PpuHarnessBase(driver, logger=logger, suite_name="test/ppu/lockstep")
