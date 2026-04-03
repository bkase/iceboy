from __future__ import annotations

from pathlib import Path
import unittest

from spec.sm83_opcodes import ALL_OPCODES, PrefixClass
from tools.sm83_decode_reference import projection_for_opcode, render_decode_snapshot


ROOT = Path(__file__).resolve().parents[2]
DECODE_SNAPSHOT_PATH = ROOT / "tools" / "fixtures" / "decode_snapshot.jsonl"


ILLEGAL_SM83_UNPREFIXED = {
    0xD3,
    0xDB,
    0xDD,
    0xE3,
    0xE4,
    0xEB,
    0xEC,
    0xED,
    0xF4,
    0xFC,
    0xFD,
}


class DecodeCompletenessScaffoldTest(unittest.TestCase):
    def test_metadata_covers_all_decode_slots(self) -> None:
        self.assertEqual(len(ALL_OPCODES), 0x200)
        illegal = {
            entry.opcode
            for entry in ALL_OPCODES
            if entry.prefix is PrefixClass.NONE and entry.is_illegal
        }
        self.assertEqual(illegal, ILLEGAL_SM83_UNPREFIXED)

    def test_decoder_completeness_matches_canonical_opcode_metadata(self) -> None:
        for entry in ALL_OPCODES:
            with self.subTest(prefix=entry.prefix.value, opcode=f"0x{entry.opcode:02X}"):
                decoded = projection_for_opcode(entry.prefix, entry.opcode)
                self.assertIsNotNone(decoded)
                if entry.prefix is PrefixClass.NONE and entry.opcode in ILLEGAL_SM83_UNPREFIXED:
                    self.assertEqual(decoded["invalid"], 1)
                else:
                    self.assertEqual(decoded["invalid"], 0)

    def test_decode_snapshot_matches_known_good_projection(self) -> None:
        expected = DECODE_SNAPSHOT_PATH.read_text(encoding="utf-8").strip()
        self.assertEqual(render_decode_snapshot(), expected)


if __name__ == "__main__":
    unittest.main()
