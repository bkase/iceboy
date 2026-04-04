from __future__ import annotations

import unittest

from bench.ppu.evidence import (
    CompareSurface,
    DontCare,
    EvidenceConfidence,
    EvidenceRuleStrength,
    EvidenceSourceKind,
    EvidenceTag,
    Exact,
    Hypothesis,
    MaskedBits,
    OneOf,
)


class PpuEvidenceTest(unittest.TestCase):
    def test_enum_values_match_manifest_vocabulary(self) -> None:
        self.assertEqual(EvidenceSourceKind.PAN_DOCS.value, "PanDocs")
        self.assertEqual(EvidenceSourceKind.MOONEYE_TEST.value, "MooneyeTest")
        self.assertEqual(EvidenceSourceKind.MEALYBUG_TEST.value, "MealybugTest")
        self.assertEqual(EvidenceConfidence.EXACT.value, "Exact")
        self.assertEqual(EvidenceRuleStrength.ARCHITECTURAL.value, "Architectural")
        self.assertEqual(CompareSurface.REFERENCE_IMAGE.value, "ReferenceImage")

    def test_evidence_tag_rejects_blank_notes(self) -> None:
        with self.assertRaises(ValueError):
            EvidenceTag(
                source_kind=EvidenceSourceKind.PAN_DOCS,
                confidence=EvidenceConfidence.HIGH,
                rule_strength=EvidenceRuleStrength.ARCHITECTURAL,
                affected_surface=CompareSurface.DOT_COMMIT,
                note="  ",
            )

    def test_evidence_tag_captures_rule_metadata(self) -> None:
        tag = EvidenceTag(
            source_kind=EvidenceSourceKind.MEALYBUG_TEST,
            confidence=EvidenceConfidence.MEDIUM,
            rule_strength=EvidenceRuleStrength.EMPIRICAL,
            affected_surface=CompareSurface.SCANLINE_SUMMARY,
            note="Mode-3 length varies by sprite overlap",
        )

        self.assertEqual(tag.source_kind, EvidenceSourceKind.MEALYBUG_TEST)
        self.assertEqual(tag.confidence, EvidenceConfidence.MEDIUM)
        self.assertEqual(tag.rule_strength, EvidenceRuleStrength.EMPIRICAL)
        self.assertEqual(tag.affected_surface, CompareSurface.SCANLINE_SUMMARY)
        self.assertEqual(tag.note, "Mode-3 length varies by sprite overlap")

    def test_expected_semantics_matchers_cover_supported_modes(self) -> None:
        self.assertTrue(Exact(0x91).matches(0x91))
        self.assertFalse(Exact(0x91).matches(0x90))

        self.assertTrue(OneOf((0, 1, 2)).matches(2))
        self.assertFalse(OneOf((0, 1, 2)).matches(3))

        self.assertTrue(MaskedBits(value=0b1010, mask=0b1110).matches(0b1011))
        self.assertFalse(MaskedBits(value=0b1010, mask=0b1110).matches(0b0110))

        self.assertTrue(DontCare[int]().matches(123))

        self.assertTrue(Hypothesis("fifo-stall").matches("fifo-stall"))
        self.assertFalse(Hypothesis("fifo-stall").matches("sprite-drop"))

    def test_one_of_requires_at_least_one_option(self) -> None:
        with self.assertRaises(ValueError):
            OneOf(())

    def test_masked_bits_rejects_negative_parameters(self) -> None:
        with self.assertRaises(ValueError):
            MaskedBits(value=-1, mask=0xFF)
        with self.assertRaises(ValueError):
            MaskedBits(value=0x12, mask=-1)


if __name__ == "__main__":
    unittest.main()
