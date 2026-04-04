from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Iterable

from bench.ppu.evidence import (
    CompareSurface,
    EvidenceConfidence,
    EvidenceRuleStrength,
    EvidenceSourceKind,
    EvidenceTag,
    Exact,
    ExpectedSemantics,
    Hypothesis,
)
from spec.profiles import BehaviorConfig, BehaviorFeature, ModelProfile, ResetProfile, default_behavior_config


VISIBLE_DOTS_PER_LINE = 456
VISIBLE_LINES = 144
TOTAL_LINES = 154
OAM_LAST_DOT = 79
TRANSFER_LAST_DOT = 251
LINE_LAST_DOT = 455

DMG_SKIPBOOT_IO = {
    "lcdc": 0x91,
    "stat": 0x85,
    "scy": 0x00,
    "scx": 0x00,
    "lyc": 0x00,
    "bgp": 0xFC,
    "obp0": 0xFF,
    "obp1": 0xFF,
    "wy": 0x00,
    "wx": 0x00,
}

TIMING_EVIDENCE = EvidenceTag(
    source_kind=EvidenceSourceKind.PAN_DOCS,
    confidence=EvidenceConfidence.HIGH,
    rule_strength=EvidenceRuleStrength.ARCHITECTURAL,
    affected_surface=CompareSurface.DOT_COMMIT,
    note="Wave A timing follows 80-dot OAM, 172-dot transfer, and 456-dot scanline cadence.",
)
STAT_EVIDENCE = EvidenceTag(
    source_kind=EvidenceSourceKind.PAN_DOCS,
    confidence=EvidenceConfidence.HIGH,
    rule_strength=EvidenceRuleStrength.ARCHITECTURAL,
    affected_surface=CompareSurface.DOT_COMMIT,
    note="STAT line is the OR of enabled mode sources and LYC coincidence, with rising-edge IRQ behavior.",
)
POWER_EVIDENCE = EvidenceTag(
    source_kind=EvidenceSourceKind.PAN_DOCS,
    confidence=EvidenceConfidence.HIGH,
    rule_strength=EvidenceRuleStrength.ARCHITECTURAL,
    affected_surface=CompareSurface.DOT_COMMIT,
    note="LCD power events reset LY and move the PPU between Disabled and WarmupBlankFrame execution.",
)
QUIRK_EVIDENCE = EvidenceTag(
    source_kind=EvidenceSourceKind.HYPOTHESIS,
    confidence=EvidenceConfidence.LOW,
    rule_strength=EvidenceRuleStrength.INFERRED,
    affected_surface=CompareSurface.DOT_COMMIT,
    note="STAT write quirk handling remains hypothesis-tier until hardware-backed evidence replaces it.",
)


class PpuMode(str, Enum):
    HBlank = "HBlank"
    VBlank = "VBlank"
    OamScan = "OamScan"
    PixelTransfer = "PixelTransfer"
    LcdOff = "LcdOff"


class LcdRunState(str, Enum):
    Disabled = "Disabled"
    WarmupBlankFrame = "WarmupBlankFrame"
    Running = "Running"


class PpuPhase(str, Enum):
    LcdOff = "LcdOff"
    OamScan = "OamScan"
    Transfer = "Transfer"
    HBlank = "HBlank"
    VBlank = "VBlank"


class PpuIrqEdge(str, Enum):
    None_ = "None"
    VBlank = "VBlank"
    Stat = "Stat"
    Both = "Both"


class MmioReg(str, Enum):
    Lcdc = "Lcdc"
    Stat = "Stat"
    Scy = "Scy"
    Scx = "Scx"
    Lyc = "Lyc"
    Wy = "Wy"
    Wx = "Wx"
    Bgp = "Bgp"
    Obp0 = "Obp0"
    Obp1 = "Obp1"


@dataclass(frozen=True)
class VideoCoord:
    frame: int = 0
    line: int = 0
    dot: int = 0


@dataclass(frozen=True)
class Lcdc:
    lcd_enable: bool = False
    win_map_hi: bool = False
    win_enable: bool = False
    bgwin_data_hi: bool = False
    bg_map_hi: bool = False
    obj_size_8x16: bool = False
    obj_enable: bool = False
    bg_enable: bool = False


@dataclass(frozen=True)
class StatSelect:
    lyc_sel: bool = False
    mode2_sel: bool = False
    mode1_sel: bool = False
    mode0_sel: bool = False


@dataclass(frozen=True)
class PpuRegs:
    lcdc: Lcdc = field(default_factory=Lcdc)
    stat_sel: StatSelect = field(default_factory=StatSelect)
    scy: int = 0
    scx: int = 0
    lyc: int = 0
    wy: int = 0
    wx: int = 0
    bgp: int = 0
    obp0: int = 0
    obp1: int = 0


@dataclass(frozen=True)
class PpuVisibleState:
    regs: PpuRegs = field(default_factory=PpuRegs)
    ly: int = 0


@dataclass(frozen=True)
class StatIrqState:
    line_high: bool = False


@dataclass(frozen=True)
class PpuStatusState:
    run: LcdRunState = LcdRunState.Disabled
    phase: PpuPhase = PpuPhase.LcdOff
    stat_irq: StatIrqState = field(default_factory=StatIrqState)


@dataclass(frozen=True)
class PpuSamplingState:
    scx_low3_line: int = 0
    wy_triggered_this_frame: bool = False
    window_enable_at_mode2_start: bool = False


@dataclass(frozen=True)
class PpuRenderState:
    dot_in_line: int = 0
    first_frame_blank: bool = False


@dataclass(frozen=True)
class PpuState:
    visible: PpuVisibleState = field(default_factory=PpuVisibleState)
    status: PpuStatusState = field(default_factory=PpuStatusState)
    sampled: PpuSamplingState = field(default_factory=PpuSamplingState)
    render: PpuRenderState = field(default_factory=PpuRenderState)


@dataclass(frozen=True)
class PpuIrqReq:
    vblank_req: bool = False
    stat_req: bool = False


@dataclass(frozen=True)
class PpuMmioResp:
    read_valid: bool = False
    read_data: int = 0xFF


@dataclass(frozen=True)
class PpuMemReqs:
    count: int = 0
    slots: tuple[object, ...] = ()


@dataclass(frozen=True)
class MmioWrite:
    target: MmioReg
    value: int


@dataclass(frozen=True)
class TimedPpuEvent:
    seq: int
    at: VideoCoord
    kind: object


@dataclass(frozen=True)
class DmaStart:
    source_high: int


@dataclass(frozen=True)
class ForceLcdPower:
    enabled: bool


@dataclass(frozen=True)
class OamDmaState:
    active: bool = False
    source_high: int = 0


@dataclass(frozen=True)
class DotInput:
    bus_events: tuple[TimedPpuEvent, ...] = ()
    mem_resp: object | None = None
    dma_state: OamDmaState = field(default_factory=OamDmaState)


@dataclass(frozen=True)
class PpuSemanticCommit:
    ly_after: int
    mode_after: PpuMode
    stat_line_after: bool
    irq_edge: PpuIrqEdge
    scanout: object | None
    ly_expectation: ExpectedSemantics[int]
    mode_expectation: ExpectedSemantics[PpuMode]
    stat_line_expectation: ExpectedSemantics[bool]
    irq_edge_expectation: ExpectedSemantics[PpuIrqEdge]
    evidence: tuple[EvidenceTag, ...]


@dataclass(frozen=True)
class DotOutput:
    next_state: PpuState
    mem_reqs: PpuMemReqs = field(default_factory=PpuMemReqs)
    mmio_resp: PpuMmioResp = field(default_factory=PpuMmioResp)
    irq_req: PpuIrqReq = field(default_factory=PpuIrqReq)
    scanout: object | None = None
    semantic: PpuSemanticCommit | None = None
    line_summary: object | None = None


def initial_ppu_state() -> PpuState:
    return PpuState()


def visible_mode(status: PpuStatusState) -> PpuMode:
    if status.run is LcdRunState.Disabled:
        return PpuMode.LcdOff
    return {
        PpuPhase.LcdOff: PpuMode.LcdOff,
        PpuPhase.OamScan: PpuMode.OamScan,
        PpuPhase.Transfer: PpuMode.PixelTransfer,
        PpuPhase.HBlank: PpuMode.HBlank,
        PpuPhase.VBlank: PpuMode.VBlank,
    }[status.phase]


def lcd_enabled(status: PpuStatusState, regs: PpuRegs) -> bool:
    return status.run is not LcdRunState.Disabled and regs.lcdc.lcd_enable


def _decode_lcdc(value: int) -> Lcdc:
    return Lcdc(
        lcd_enable=bool((value >> 7) & 1),
        win_map_hi=bool((value >> 6) & 1),
        win_enable=bool((value >> 5) & 1),
        bgwin_data_hi=bool((value >> 4) & 1),
        bg_map_hi=bool((value >> 3) & 1),
        obj_size_8x16=bool((value >> 2) & 1),
        obj_enable=bool((value >> 1) & 1),
        bg_enable=bool(value & 1),
    )


def _decode_stat_select(value: int) -> StatSelect:
    return StatSelect(
        lyc_sel=bool((value >> 6) & 1),
        mode2_sel=bool((value >> 5) & 1),
        mode1_sel=bool((value >> 4) & 1),
        mode0_sel=bool((value >> 3) & 1),
    )


def apply_mmio_write(regs: PpuRegs, event: MmioWrite) -> PpuRegs:
    value = event.value & 0xFF
    if event.target is MmioReg.Lcdc:
        return replace(regs, lcdc=_decode_lcdc(value))
    if event.target is MmioReg.Stat:
        return replace(regs, stat_sel=_decode_stat_select(value))
    if event.target is MmioReg.Scy:
        return replace(regs, scy=value)
    if event.target is MmioReg.Scx:
        return replace(regs, scx=value)
    if event.target is MmioReg.Lyc:
        return replace(regs, lyc=value)
    if event.target is MmioReg.Wy:
        return replace(regs, wy=value)
    if event.target is MmioReg.Wx:
        return replace(regs, wx=value)
    if event.target is MmioReg.Bgp:
        return replace(regs, bgp=value)
    if event.target is MmioReg.Obp0:
        return replace(regs, obp0=value)
    if event.target is MmioReg.Obp1:
        return replace(regs, obp1=value)
    return regs


def _next_line(ly: int) -> int:
    return 0 if ly == TOTAL_LINES - 1 else ly + 1


def _sample_visible_line(regs: PpuRegs, sampled: PpuSamplingState, *, reset_frame: bool) -> PpuSamplingState:
    return PpuSamplingState(
        scx_low3_line=regs.scx & 0x7,
        wy_triggered_this_frame=False if reset_frame else sampled.wy_triggered_this_frame,
        window_enable_at_mode2_start=regs.lcdc.win_enable,
    )


def _mode_source_enabled(regs: PpuRegs, mode: PpuMode) -> bool:
    if mode is PpuMode.HBlank:
        return regs.stat_sel.mode0_sel
    if mode is PpuMode.VBlank:
        return regs.stat_sel.mode1_sel
    if mode is PpuMode.OamScan:
        return regs.stat_sel.mode2_sel
    return False


def lyc_match(regs: PpuRegs, ly: int) -> bool:
    return ly == regs.lyc


def stat_line(regs: PpuRegs, status: PpuStatusState, ly: int) -> bool:
    if not lcd_enabled(status, regs):
        return False
    mode = visible_mode(status)
    return _mode_source_enabled(regs, mode) or (regs.stat_sel.lyc_sel and lyc_match(regs, ly))


def _step_edge(vblank_req: bool, stat_req: bool) -> PpuIrqEdge:
    if vblank_req and stat_req:
        return PpuIrqEdge.Both
    if vblank_req:
        return PpuIrqEdge.VBlank
    if stat_req:
        return PpuIrqEdge.Stat
    return PpuIrqEdge.None_


def _advance_timing(state: PpuState, regs: PpuRegs) -> tuple[LcdRunState, PpuPhase, int, PpuSamplingState, int]:
    status = state.status
    ly = state.visible.ly
    sampled = state.sampled
    dot = state.render.dot_in_line

    if status.run is LcdRunState.Disabled:
        return (LcdRunState.Disabled, PpuPhase.LcdOff, 0, PpuSamplingState(), 0)

    next_run = status.run
    next_phase = status.phase
    next_ly = ly
    next_sampled = sampled

    if status.phase is PpuPhase.LcdOff:
        next_phase = PpuPhase.OamScan
        next_sampled = _sample_visible_line(regs, sampled, reset_frame=False)
    elif status.phase is PpuPhase.OamScan:
        if dot == OAM_LAST_DOT:
            next_phase = PpuPhase.Transfer
    elif status.phase is PpuPhase.Transfer:
        if dot == TRANSFER_LAST_DOT:
            next_phase = PpuPhase.HBlank
    elif status.phase is PpuPhase.HBlank:
        if dot == LINE_LAST_DOT:
            next_ly = _next_line(ly)
            if ly == VISIBLE_LINES - 1:
                next_phase = PpuPhase.VBlank
            else:
                next_phase = PpuPhase.OamScan
                next_sampled = _sample_visible_line(regs, sampled, reset_frame=False)
    elif status.phase is PpuPhase.VBlank and dot == LINE_LAST_DOT:
        next_ly = _next_line(ly)
        if ly == TOTAL_LINES - 1:
            next_ly = 0
            next_phase = PpuPhase.OamScan
            next_sampled = _sample_visible_line(regs, sampled, reset_frame=True)
            if status.run is LcdRunState.WarmupBlankFrame:
                next_run = LcdRunState.Running
        else:
            next_phase = PpuPhase.VBlank

    next_dot = 0 if dot == LINE_LAST_DOT else dot + 1
    return (next_run, next_phase, next_ly, next_sampled, next_dot)


def _extract_mmio_writes(events: Iterable[TimedPpuEvent]) -> tuple[tuple[MmioWrite, ...], bool, bool]:
    writes: list[MmioWrite] = []
    power_enable = False
    power_disable = False
    for event in events:
        kind = event.kind
        if isinstance(kind, MmioWrite):
            writes.append(kind)
        elif isinstance(kind, ForceLcdPower):
            if kind.enabled:
                power_enable = True
            else:
                power_disable = True
    return (tuple(writes), power_enable, power_disable)


def _skipboot_ppu_regs() -> PpuRegs:
    return PpuRegs(
        lcdc=_decode_lcdc(DMG_SKIPBOOT_IO["lcdc"]),
        stat_sel=_decode_stat_select(DMG_SKIPBOOT_IO["stat"]),
        scy=DMG_SKIPBOOT_IO["scy"],
        scx=DMG_SKIPBOOT_IO["scx"],
        lyc=DMG_SKIPBOOT_IO["lyc"],
        wy=DMG_SKIPBOOT_IO["wy"],
        wx=DMG_SKIPBOOT_IO["wx"],
        bgp=DMG_SKIPBOOT_IO["bgp"],
        obp0=DMG_SKIPBOOT_IO["obp0"],
        obp1=DMG_SKIPBOOT_IO["obp1"],
    )


def _coerce_behavior_config(
    model_profile: ModelProfile,
    behavior_config: BehaviorConfig | None,
) -> BehaviorConfig:
    config = default_behavior_config(model_profile) if behavior_config is None else behavior_config
    if config.model is not model_profile:
        raise ValueError("BehaviorConfig.model must match the selected model profile")
    return config


def _base_reset_state(reset_profile: ResetProfile) -> PpuState:
    if reset_profile is ResetProfile.SkipBoot:
        regs = _skipboot_ppu_regs()
        sampled = _sample_visible_line(regs, PpuSamplingState(), reset_frame=True)
        return PpuState(
            visible=PpuVisibleState(regs=regs, ly=0),
            status=PpuStatusState(run=LcdRunState.Running, phase=PpuPhase.OamScan, stat_irq=StatIrqState()),
            sampled=sampled,
            render=PpuRenderState(dot_in_line=0, first_frame_blank=False),
        )
    return initial_ppu_state()


def _step_dot_with_config(state: PpuState, input: DotInput, behavior_config: BehaviorConfig) -> DotOutput:
    regs = state.visible.regs
    status = state.status
    sampled = state.sampled
    render = state.render

    writes, power_enable, power_disable = _extract_mmio_writes(input.bus_events)
    stat_write_seen = any(write.target is MmioReg.Stat for write in writes)

    evidence: list[EvidenceTag] = [TIMING_EVIDENCE]

    for write in writes:
        regs = apply_mmio_write(regs, write)

    if power_enable:
        regs = replace(regs, lcdc=replace(regs.lcdc, lcd_enable=True))

    if power_disable or (status.run is not LcdRunState.Disabled and not regs.lcdc.lcd_enable):
        regs = replace(regs, lcdc=replace(regs.lcdc, lcd_enable=False))
        next_state = PpuState(
            visible=PpuVisibleState(regs=regs, ly=0),
            status=PpuStatusState(run=LcdRunState.Disabled, phase=PpuPhase.LcdOff, stat_irq=StatIrqState()),
            sampled=PpuSamplingState(),
            render=PpuRenderState(dot_in_line=0, first_frame_blank=False),
        )
        evidence.append(POWER_EVIDENCE)
    else:
        transient_status = status
        if power_enable or (status.run is LcdRunState.Disabled and regs.lcdc.lcd_enable):
            transient_status = PpuStatusState(
                run=LcdRunState.WarmupBlankFrame,
                phase=PpuPhase.LcdOff,
                stat_irq=StatIrqState(),
            )
            evidence.append(POWER_EVIDENCE)

        transient_state = PpuState(
            visible=PpuVisibleState(regs=regs, ly=state.visible.ly),
            status=transient_status,
            sampled=sampled,
            render=render,
        )
        next_run, next_phase, next_ly, next_sampled, next_dot = _advance_timing(transient_state, regs)
        next_status = PpuStatusState(
            run=next_run,
            phase=next_phase,
            stat_irq=StatIrqState(line_high=False),
        )
        new_line = stat_line(regs, next_status, next_ly)
        quirk_enabled = BehaviorFeature.DmgStatWriteQuirk in behavior_config.features
        stat_req = (not transient_status.stat_irq.line_high and new_line) or (quirk_enabled and stat_write_seen)
        vblank_req = visible_mode(transient_status) is not PpuMode.VBlank and visible_mode(next_status) is PpuMode.VBlank
        next_status = replace(next_status, stat_irq=StatIrqState(line_high=new_line))
        next_state = PpuState(
            visible=PpuVisibleState(regs=regs, ly=next_ly),
            status=next_status,
            sampled=next_sampled,
            render=PpuRenderState(dot_in_line=next_dot, first_frame_blank=render.first_frame_blank),
        )
        if stat_req or vblank_req or regs.stat_sel.lyc_sel:
            evidence.append(STAT_EVIDENCE)
        if quirk_enabled and stat_write_seen:
            evidence.append(QUIRK_EVIDENCE)

    vblank_req = False
    stat_req = False
    if next_state.status.run is not LcdRunState.Disabled:
        prev_mode = visible_mode(status)
        next_mode = visible_mode(next_state.status)
        vblank_req = prev_mode is not PpuMode.VBlank and next_mode is PpuMode.VBlank
        new_line = stat_line(next_state.visible.regs, next_state.status, next_state.visible.ly)
        prev_line = status.stat_irq.line_high
        quirk_enabled = BehaviorFeature.DmgStatWriteQuirk in behavior_config.features
        stat_req = (not prev_line and new_line) or (quirk_enabled and stat_write_seen)
    irq_edge = _step_edge(vblank_req, stat_req)
    quirk_used = BehaviorFeature.DmgStatWriteQuirk in behavior_config.features and stat_write_seen
    semantic = PpuSemanticCommit(
        ly_after=next_state.visible.ly,
        mode_after=visible_mode(next_state.status),
        stat_line_after=stat_line(next_state.visible.regs, next_state.status, next_state.visible.ly),
        irq_edge=irq_edge,
        scanout=None,
        ly_expectation=Exact(next_state.visible.ly),
        mode_expectation=Exact(visible_mode(next_state.status)),
        stat_line_expectation=Exact(stat_line(next_state.visible.regs, next_state.status, next_state.visible.ly)),
        irq_edge_expectation=Hypothesis(irq_edge) if quirk_used else Exact(irq_edge),
        evidence=tuple(evidence),
    )
    return DotOutput(
        next_state=next_state,
        irq_req=PpuIrqReq(vblank_req=vblank_req, stat_req=stat_req),
        semantic=semantic,
    )


def step_dot(state: PpuState, input: DotInput) -> DotOutput:
    return _step_dot_with_config(state, input, default_behavior_config(ModelProfile.DMG))


@dataclass
class PpuReferenceModel:
    model_profile: ModelProfile = ModelProfile.DMG
    reset_profile: ResetProfile = ResetProfile.SkipBoot
    behavior_config: BehaviorConfig = field(default_factory=lambda: default_behavior_config(ModelProfile.DMG))
    state: PpuState = field(default_factory=initial_ppu_state)

    def reset(
        self,
        model_profile: ModelProfile | str,
        reset_profile: ResetProfile | str,
        behavior_config: BehaviorConfig | None = None,
    ) -> PpuState:
        self.model_profile = ModelProfile(model_profile)
        self.reset_profile = ResetProfile(reset_profile)
        self.behavior_config = _coerce_behavior_config(self.model_profile, behavior_config)
        self.state = _base_reset_state(self.reset_profile)
        return self.state

    def step(self, input: DotInput) -> DotOutput:
        output = _step_dot_with_config(self.state, input, self.behavior_config)
        self.state = output.next_state
        return output


__all__ = [
    "BehaviorConfig",
    "DotInput",
    "DotOutput",
    "ForceLcdPower",
    "Lcdc",
    "LcdRunState",
    "MmioReg",
    "MmioWrite",
    "OamDmaState",
    "PpuIrqEdge",
    "PpuMode",
    "PpuPhase",
    "PpuReferenceModel",
    "PpuRegs",
    "PpuSemanticCommit",
    "PpuState",
    "PpuStatusState",
    "ResetProfile",
    "StatIrqState",
    "StatSelect",
    "TimedPpuEvent",
    "VideoCoord",
    "initial_ppu_state",
    "lyc_match",
    "lcd_enabled",
    "stat_line",
    "step_dot",
    "visible_mode",
]
