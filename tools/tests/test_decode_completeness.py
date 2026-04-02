from __future__ import annotations

import unittest

from spec.sm83_opcodes import ALL_OPCODES, PrefixClass


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


def _decode_opcode(prefix: PrefixClass, opcode: int) -> object:
    raise NotImplementedError(
        "Decoder surface is not implemented yet; see bd-30s for the green completeness bead."
    )


class DecodeCompletenessScaffoldTest(unittest.TestCase):
    def test_metadata_covers_all_decode_slots(self) -> None:
        self.assertEqual(len(ALL_OPCODES), 0x200)
        illegal = {
            entry.opcode
            for entry in ALL_OPCODES
            if entry.prefix is PrefixClass.NONE and entry.is_illegal
        }
        self.assertEqual(illegal, ILLEGAL_SM83_UNPREFIXED)

    @unittest.expectedFailure
    def test_decoder_completeness_matches_canonical_opcode_metadata(self) -> None:
        for entry in ALL_OPCODES:
            with self.subTest(prefix=entry.prefix.value, opcode=f"0x{entry.opcode:02X}"):
                decoded = _decode_opcode(entry.prefix, entry.opcode)
                self.assertIsNotNone(decoded)
                if entry.prefix is PrefixClass.NONE and entry.opcode in ILLEGAL_SM83_UNPREFIXED:
                    self.assertTrue(getattr(decoded, "is_illegal", False))
                else:
                    self.assertFalse(getattr(decoded, "is_illegal", False))


if __name__ == "__main__":
    unittest.main()
