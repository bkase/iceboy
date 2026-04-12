from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "ref_st7789_transcript.py"


def load_tool_module():
    spec = importlib.util.spec_from_file_location("ref_st7789_transcript", TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module spec for {TOOL}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RefSt7789TranscriptTest(unittest.TestCase):
    def test_generate_init_transcript_matches_controller_literal(self) -> None:
        tool = load_tool_module()
        transcript = tool.generate_init_transcript()

        expected = [
            (False, 0x01),
            (False, 0x11),
            (False, 0x3A),
            (True, 0x55),
            (False, 0x36),
            (True, 0x00),
            (False, 0x2A),
            (True, 0x00),
            (True, 0x00),
            (True, 0x01),
            (True, 0x3F),
            (False, 0x2B),
            (True, 0x00),
            (True, 0x00),
            (True, 0x00),
            (True, 0xEF),
            (False, 0x21),
            (False, 0x13),
            (False, 0x29),
        ]
        self.assertEqual(len(transcript), 19)
        self.assertEqual([(dc, byte) for dc, byte, _ in transcript], expected)

    def test_generate_windowed_frame_transcript_supports_small_smoke_case(self) -> None:
        tool = load_tool_module()

        transcript = tool.generate_windowed_frame_transcript(bytes([0, 1, 2, 3]), width=2, height=2)

        self.assertEqual(len(transcript), 19)
        self.assertEqual(
            [(dc, byte) for dc, byte, _ in transcript[:11]],
            [
                (False, 0x2A),
                (True, 0x00),
                (True, 0x9F),
                (True, 0x00),
                (True, 0xA0),
                (False, 0x2B),
                (True, 0x00),
                (True, 0x77),
                (True, 0x00),
                (True, 0x78),
                (False, 0x2C),
            ],
        )
        self.assertEqual(
            [byte for _, byte, _ in transcript[11:]],
            [0xFF, 0xFF, 0xAD, 0x55, 0x52, 0xAA, 0x00, 0x00],
        )

    def test_generate_frame_transcript_requires_full_frame_size(self) -> None:
        tool = load_tool_module()

        with self.assertRaisesRegex(ValueError, "expected 23040 frame bytes"):
            tool.generate_frame_transcript(bytes([0, 1, 2, 3]))

    def test_cli_modes_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            frame = tmp / "frame.raw"
            out_a = tmp / "a.json"
            out_b = tmp / "b.json"
            frame.write_bytes(bytes([0]) * (160 * 144))

            init = subprocess.run(
                ["python3", str(TOOL), "--mode", "init"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            init_payload = json.loads(init.stdout)
            self.assertEqual(len(init_payload), 19)
            self.assertEqual(init_payload[0], {"dc": False, "byte": 0x01, "label": "SWRESET"})

            subprocess.run(
                ["python3", str(TOOL), "--mode", "frame", "--input", str(frame), "--output", str(out_a)],
                cwd=ROOT,
                check=True,
            )
            subprocess.run(
                ["python3", str(TOOL), "--mode", "frame", "--input", str(frame), "--output", str(out_b)],
                cwd=ROOT,
                check=True,
            )

            self.assertEqual(out_a.read_text(encoding="utf-8"), out_b.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
