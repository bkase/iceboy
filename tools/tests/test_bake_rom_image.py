from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "bake_rom_image.py"


class BakeRomImageTest(unittest.TestCase):
    def run_tool(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(TOOL), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

    def test_bake_is_deterministic_and_validate_round_trips(self) -> None:
        rom = ROOT / "bench" / "roms" / "out" / "alu_loop.gb"
        sym = ROOT / "bench" / "roms" / "out" / "alu_loop.sym"
        with tempfile.TemporaryDirectory() as tmpdir:
            out_a = Path(tmpdir) / "alu_loop_rom_data.spade"
            out_b = Path(tmpdir) / "alu_loop_rom_data_again.spade"

            first = self.run_tool("--rom", str(rom), "--sym", str(sym), "--size", "1024", "--out", str(out_a))
            second = self.run_tool("--rom", str(rom), "--sym", str(sym), "--size", "1024", "--name", "alu_loop_rom_data", "--out", str(out_b))
            validated = self.run_tool("--rom", str(rom), "--sym", str(sym), "--size", "1024", "--validate", str(out_a))

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(validated.returncode, 0, validated.stderr)
            self.assertEqual(out_a.read_text(encoding="utf-8"), out_b.read_text(encoding="utf-8"))
            text = out_a.read_text(encoding="utf-8")
            self.assertIn("// Generated UTC: 1970-01-01T00:00:00Z", text)
            self.assertIn("// CRC32:", text)
            self.assertIn("// SHA256:", text)
            self.assertIn("pub fn alu_loop_rom_data() -> [uint<8>; 1024]", text)

    def test_symbol_overflow_fails_with_symbol_name(self) -> None:
        rom = ROOT / "bench" / "roms" / "out" / "alu_loop.gb"
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "too_small.spade"
            sym_path = Path(tmpdir) / "too_small.sym"
            sym_path.write_text("; test\n00:0400 TooFar\n", encoding="utf-8")

            completed = self.run_tool("--rom", str(rom), "--sym", str(sym_path), "--size", "256", "--out", str(out_path))

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("TooFar", completed.stderr or completed.stdout)
            self.assertIn("exceeds baked size 256", completed.stderr or completed.stdout)

    def test_missing_rom_and_oversize_fail_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "missing.spade"
            missing = self.run_tool("--rom", str(Path(tmpdir) / "missing.gb"), "--size", "16", "--out", str(out_path))
            oversize = self.run_tool(
                "--rom",
                str(ROOT / "bench" / "roms" / "out" / "alu_loop.gb"),
                "--size",
                "65536",
                "--out",
                str(out_path),
            )

            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("missing ROM file", missing.stderr or missing.stdout)
            self.assertNotEqual(oversize.returncode, 0)
            self.assertIn("exceeds ROM length", oversize.stderr or oversize.stdout)

    def test_validate_committed_generated_files(self) -> None:
        cases = (
            ("alu_loop.gb", "alu_loop.sym", "1024", "alu_loop_rom_data.spade"),
            ("BG_STATIC.gb", "BG_STATIC.sym", "1024", "bg_static_rom_data.spade"),
            ("joypad_bg_smoke.gb", "joypad_bg_smoke.sym", "2048", "joypad_bg_smoke_rom_data.spade"),
        )
        for rom_name, sym_name, size, generated_name in cases:
            with self.subTest(generated_name=generated_name):
                completed = self.run_tool(
                    "--rom",
                    str(ROOT / "bench" / "roms" / "out" / rom_name),
                    "--sym",
                    str(ROOT / "bench" / "roms" / "out" / sym_name),
                    "--size",
                    size,
                    "--validate",
                    str(ROOT / "src" / "mem" / "phys" / "generated" / generated_name),
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
