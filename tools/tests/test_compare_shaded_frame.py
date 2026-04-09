from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

import sys

sys.path.insert(0, str(ROOT / "tools"))

from compare_shaded_frame import _encode_png_grayscale, compare_shaded_frame


class CompareShadedFrameTest(unittest.TestCase):
    def test_compare_shaded_frame_accepts_exact_match_and_writes_png(self) -> None:
        rows = (
            (0xFF, 0xAA),
            (0x55, 0x00),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            raw = tmp / "frame.raw"
            expected = tmp / "expected.png"
            actual_png = tmp / "actual.png"
            raw.write_bytes(bytes(value for row in rows for value in row))
            expected.write_bytes(_encode_png_grayscale(rows))

            mismatches, first = compare_shaded_frame(
                raw_path=raw,
                expected_path=expected,
                output_png=actual_png,
                width=2,
                height=2,
            )

            self.assertEqual(mismatches, 0)
            self.assertIsNone(first)
            self.assertTrue(actual_png.is_file())

    def test_compare_shaded_frame_reports_first_mismatch(self) -> None:
        rows = (
            (0xFF, 0xAA),
            (0x55, 0x00),
        )
        mismatched_rows = (
            (0xFF, 0x00),
            (0x55, 0x00),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            raw = tmp / "frame.raw"
            expected = tmp / "expected.png"
            raw.write_bytes(bytes(value for row in mismatched_rows for value in row))
            expected.write_bytes(_encode_png_grayscale(rows))

            mismatches, first = compare_shaded_frame(
                raw_path=raw,
                expected_path=expected,
                width=2,
                height=2,
            )

            self.assertEqual(mismatches, 1)
            self.assertEqual(first, (1, 0, 0x00, 0xAA))


if __name__ == "__main__":
    unittest.main()
