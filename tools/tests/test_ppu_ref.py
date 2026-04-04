from __future__ import annotations

import unittest

from bench.ppu.evidence import EvidenceSourceKind, Exact, Hypothesis
from bench.ref.ppu_ref import (
    DotInput,
    ForceLcdPower,
    Lcdc,
    LcdRunState,
    MmioReg,
    MmioWrite,
    PpuMode,
    PpuPhase,
    PpuReferenceModel,
    PpuRegs,
    PpuState,
    PpuStatusState,
    PpuVisibleState,
    PpuRenderState,
    StatIrqState,
    StatSelect,
    TimedPpuEvent,
    VideoCoord,
    step_dot,
)
from spec.profiles import BehaviorConfig, BehaviorFeature, ModelProfile, ResetProfile


def make_state(
    *,
    regs: PpuRegs | None = None,
    ly: int = 0,
    run: LcdRunState = LcdRunState.Running,
    phase: PpuPhase = PpuPhase.OamScan,
    line_high: bool = False,
    dot_in_line: int = 0,
) -> PpuState:
    return PpuState(
        visible=PpuVisibleState(regs=regs or PpuRegs(lcdc=Lcdc(lcd_enable=True)), ly=ly),
        status=PpuStatusState(run=run, phase=phase, stat_irq=StatIrqState(line_high=line_high)),
        render=PpuRenderState(dot_in_line=dot_in_line, first_frame_blank=False),
    )


class PpuReferenceModelTest(unittest.TestCase):
    def test_skipboot_reset_uses_wave_a_dmg_defaults(self) -> None:
        model = PpuReferenceModel()
        state = model.reset(ModelProfile.DMG, ResetProfile.SkipBoot)
        self.assertEqual(state.visible.regs.bgp, 0xFC)
        self.assertEqual(state.visible.regs.obp0, 0xFF)
        self.assertEqual(state.visible.regs.obp1, 0xFF)
        self.assertEqual(state.visible.regs.scx, 0x00)
        self.assertTrue(state.visible.regs.lcdc.lcd_enable)
        self.assertEqual(state.status.run, LcdRunState.Running)
        self.assertEqual(state.status.phase, PpuPhase.OamScan)

    def test_reset_rejects_behavior_config_model_mismatch(self) -> None:
        model = PpuReferenceModel()
        with self.assertRaisesRegex(ValueError, "BehaviorConfig.model"):
            model.reset(
                ModelProfile.DMG,
                ResetProfile.SkipBoot,
                BehaviorConfig(model=ModelProfile.CGB),
            )

    def test_force_lcd_power_enable_enters_warmup_oam_scan(self) -> None:
        state = make_state(run=LcdRunState.Disabled, phase=PpuPhase.LcdOff)
        output = step_dot(
            state,
            DotInput(
                bus_events=(
                    TimedPpuEvent(seq=1, at=VideoCoord(), kind=ForceLcdPower(enabled=True)),
                )
            ),
        )

        self.assertEqual(output.next_state.status.run, LcdRunState.WarmupBlankFrame)
        self.assertEqual(output.next_state.status.phase, PpuPhase.OamScan)
        self.assertEqual(output.next_state.visible.ly, 0)
        self.assertEqual(output.semantic.mode_after, PpuMode.OamScan)
        self.assertIn(EvidenceSourceKind.PAN_DOCS, {tag.source_kind for tag in output.semantic.evidence})

    def test_mode_sequence_advances_through_visible_line_boundaries(self) -> None:
        regs = PpuRegs(lcdc=Lcdc(lcd_enable=True))
        oam_done = step_dot(make_state(regs=regs, phase=PpuPhase.OamScan, dot_in_line=79), DotInput())
        transfer_done = step_dot(make_state(regs=regs, phase=PpuPhase.Transfer, dot_in_line=251), DotInput())
        hblank_done = step_dot(make_state(regs=regs, phase=PpuPhase.HBlank, dot_in_line=455), DotInput())

        self.assertEqual(oam_done.next_state.status.phase, PpuPhase.Transfer)
        self.assertEqual(transfer_done.next_state.status.phase, PpuPhase.HBlank)
        self.assertEqual(hblank_done.next_state.status.phase, PpuPhase.OamScan)
        self.assertEqual(hblank_done.next_state.visible.ly, 1)

    def test_vblank_entry_raises_vblank_irq_and_exact_expectations(self) -> None:
        output = step_dot(
            make_state(ly=143, phase=PpuPhase.HBlank, dot_in_line=455),
            DotInput(),
        )
        self.assertTrue(output.irq_req.vblank_req)
        self.assertEqual(output.semantic.irq_edge.value, "VBlank")
        self.assertEqual(output.semantic.mode_after, PpuMode.VBlank)
        self.assertTrue(output.semantic.mode_expectation.matches(PpuMode.VBlank))
        self.assertIsInstance(output.semantic.mode_expectation, Exact)

    def test_lyc_match_raises_stat_irq_on_rising_edge(self) -> None:
        regs = PpuRegs(lcdc=Lcdc(lcd_enable=True), stat_sel=StatSelect(lyc_sel=True), lyc=5)
        output = step_dot(
            make_state(regs=regs, ly=5, phase=PpuPhase.HBlank, line_high=False, dot_in_line=10),
            DotInput(),
        )
        self.assertTrue(output.irq_req.stat_req)
        self.assertEqual(output.semantic.irq_edge.value, "Stat")
        self.assertTrue(output.semantic.stat_line_after)
        self.assertTrue(output.semantic.stat_line_expectation.matches(True))

    def test_stat_write_quirk_uses_hypothesis_expectation_when_feature_enabled(self) -> None:
        model = PpuReferenceModel()
        model.reset(
            ModelProfile.DMG,
            ResetProfile.SkipBoot,
            BehaviorConfig(model=ModelProfile.DMG, features=(BehaviorFeature.DmgStatWriteQuirk,)),
        )
        model.state = make_state(
            regs=PpuRegs(lcdc=Lcdc(lcd_enable=True)),
            ly=0,
            phase=PpuPhase.Transfer,
            line_high=False,
            dot_in_line=5,
        )
        output = model.step(
            DotInput(
                bus_events=(
                    TimedPpuEvent(
                        seq=1,
                        at=VideoCoord(),
                        kind=MmioWrite(target=MmioReg.Stat, value=0x00),
                    ),
                )
            )
        )
        self.assertTrue(output.irq_req.stat_req)
        self.assertIsInstance(output.semantic.irq_edge_expectation, Hypothesis)
        self.assertIn(EvidenceSourceKind.HYPOTHESIS, {tag.source_kind for tag in output.semantic.evidence})


if __name__ == "__main__":
    unittest.main()
