from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GBXCULE = ROOT.parent / "gbxcule"
TOOLS = ROOT / "tools"

import sys

if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from export_pokered_restore import _parse_timer_state, export_restore_manifest
from export_pokered_walk_script import export_walk_script
from pokered_frame_artifacts import FRAME_SIZE, encode_png_grayscale, write_frame_artifacts
from pyboy import PyBoy


def _parse_cpu_prefix(state_bytes: bytes) -> dict[str, int]:
    state_version = state_bytes[0]
    hl = int.from_bytes(state_bytes[11:13], "little")
    ime_offset = 17
    return {
        "ime": state_bytes[ime_offset],
        "halted": state_bytes[ime_offset + 1],
        "stopped": state_bytes[ime_offset + 2],
        "ie": state_bytes[ime_offset + 3] if state_version >= 5 else 0,
        "if": state_bytes[ime_offset + 5] if state_version >= 8 else 0,
        "h": (hl >> 8) & 0xFF,
        "l": hl & 0xFF,
    }


class PokeredPlaybackToolsTest(unittest.TestCase):
    def test_default_walk_script_starts_with_idle_settle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "walk.schedule"
            fps, duration = export_walk_script(TOOLS / "pokered_walk_script.yaml", out)
            self.assertEqual((fps, duration), (60, 600))
            lines = out.read_text(encoding="utf-8").splitlines()
            self.assertEqual(
                lines[:4],
                [
                    "fps=60",
                    "duration_frames=600",
                    "0 60 0",
                    "60 180 8",
                ],
            )
            self.assertEqual(lines[-1], "540 600 128")

    def test_encode_png_grayscale_rejects_wrong_size(self) -> None:
        with self.assertRaisesRegex(ValueError, "frame size mismatch"):
            encode_png_grayscale(b"\x00" * (FRAME_SIZE - 1))

    def test_write_frame_artifacts_writes_samples_without_pyboy_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            frames_raw = tmp / "frames.raw"
            first_raw = tmp / "first.raw"
            mid_raw = tmp / "mid.raw"
            last_raw = tmp / "last.raw"
            first_png = tmp / "first.png"
            mid_png = tmp / "mid.png"
            last_png = tmp / "last.png"
            frame0 = bytes([0x00]) * FRAME_SIZE
            frame1 = bytes([0x55]) * FRAME_SIZE
            frame2 = bytes([0xAA]) * FRAME_SIZE
            frames_raw.write_bytes(frame0 + frame1 + frame2)

            byte_count = write_frame_artifacts(
                frames_raw_path=frames_raw,
                target_frames=3,
                first_raw_path=first_raw,
                mid_raw_path=mid_raw,
                last_raw_path=last_raw,
                first_png_path=first_png,
                mid_png_path=mid_png,
                last_png_path=last_png,
            )

            self.assertEqual(byte_count, FRAME_SIZE * 3)
            self.assertEqual(first_raw.read_bytes(), frame0)
            self.assertEqual(mid_raw.read_bytes(), frame1)
            self.assertEqual(last_raw.read_bytes(), frame2)
            self.assertTrue(first_png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertTrue(mid_png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertTrue(last_png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))

    def test_export_walk_script_compiles_contiguous_ranges(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            script = Path(tmpdir) / "walk.yaml"
            out = Path(tmpdir) / "walk.schedule"
            script.write_text(
                "\n".join(
                    [
                        "fps: 60",
                        "duration_frames: 12",
                        "sequence:",
                        "  - frames: 0..4",
                        "    buttons: [down]",
                        "  - frames: 4..8",
                        "    buttons: [right, a]",
                        "  - frames: 8..12",
                        "    buttons: []",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            fps, duration = export_walk_script(script, out)
            self.assertEqual((fps, duration), (60, 12))
            self.assertEqual(
                out.read_text(encoding="utf-8").splitlines(),
                [
                    "fps=60",
                    "duration_frames=12",
                    "0 4 8",
                    "4 8 17",
                    "8 12 0",
                ],
            )

    def test_export_walk_script_rejects_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            script = Path(tmpdir) / "walk.yaml"
            out = Path(tmpdir) / "walk.schedule"
            script.write_text(
                "\n".join(
                    [
                        "fps: 60",
                        "duration_frames: 10",
                        "sequence:",
                        "  - frames: 0..4",
                        "    buttons: [down]",
                        "  - frames: 5..10",
                        "    buttons: []",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "contiguous"):
                export_walk_script(script, out)

    def test_bulbasaur_state_loads_in_pyboy(self) -> None:
        rom_path = GBXCULE / "red.gb"
        state_path = GBXCULE / "Bulbasaur.state"
        if not rom_path.is_file() or not state_path.is_file():
            self.skipTest("gbxcule Bulbasaur assets are unavailable")

        pyboy = PyBoy(
            str(rom_path),
            window="null",
            sound_emulated=False,
            no_input=True,
            log_level="ERROR",
            cgb=False,
        )
        try:
            pyboy.set_emulation_speed(0)
            with state_path.open("rb") as handle:
                pyboy.load_state(handle)
            self.assertEqual(int(pyboy.memory[0xFF40]), 0xE3)
            self.assertEqual(int(pyboy.register_file.PC), 0x20B3)
        finally:
            pyboy.stop(save=False)

    def test_export_restore_manifest_roundtrips_real_bulbasaur_state(self) -> None:
        rom_path = GBXCULE / "red.gb"
        state_path = GBXCULE / "Bulbasaur.state"
        if not rom_path.is_file() or not state_path.is_file():
            self.skipTest("gbxcule Bulbasaur assets are unavailable")

        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "restore"
            manifest_path = export_restore_manifest(rom_path=rom_path, state_path=state_path, out_dir=out_dir)
            state_bytes = state_path.read_bytes()
            values = {}
            for line in manifest_path.read_text(encoding="utf-8").splitlines():
                key, value = line.split("=", 1)
                values[key] = value
            cpu_prefix = _parse_cpu_prefix(state_bytes)

            self.assertEqual(int(values["state_version"]), state_bytes[0])
            self.assertEqual(int(values["cart_type"]), 0x13)
            self.assertEqual(int(values["external_ram_count"]), 4)
            self.assertGreaterEqual(int(values["external_rom_count"]), 1)
            self.assertIn("POKEMON RED", values["title"])
            self.assertEqual(int(values["ime"]), cpu_prefix["ime"])
            self.assertEqual(int(values["halted"]), int(cpu_prefix["halted"] != 0))
            self.assertEqual(int(values["stopped"]), int(cpu_prefix["stopped"] != 0))
            timer_state = _parse_timer_state(state_bytes, int(values["state_version"]))
            self.assertEqual(int(values["timer_div"]), timer_state["timer_div"])
            self.assertEqual(int(values["timer_div_counter"]), timer_state["timer_div_counter"])
            self.assertEqual(int(values["timer_tima"]), timer_state["timer_tima"])
            self.assertEqual(int(values["timer_tma"]), timer_state["timer_tma"])
            self.assertEqual(int(values["timer_tac"]), timer_state["timer_tac"])

            vram_path = out_dir / values["vram"]
            oam_path = out_dir / values["oam"]
            wram_path = out_dir / values["wram"]
            hram_path = out_dir / values["hram"]
            cartram_path = out_dir / values["cartram"]
            self.assertEqual(vram_path.stat().st_size, 0x2000)
            self.assertEqual(oam_path.stat().st_size, 0xA0)
            self.assertEqual(wram_path.stat().st_size, 0x2000)
            self.assertEqual(hram_path.stat().st_size, 0x7F)
            self.assertEqual(cartram_path.stat().st_size, 4 * 0x2000)

            pyboy = PyBoy(
                str(rom_path),
                window="null",
                sound_emulated=False,
                no_input=True,
                log_level="ERROR",
                cgb=False,
            )
            try:
                pyboy.set_emulation_speed(0)
                with state_path.open("rb") as handle:
                    pyboy.load_state(handle)

                rf = pyboy.register_file
                memory = pyboy.memory
                self.assertEqual(int(values["a"]), int(rf.A))
                self.assertEqual(int(values["f"]), int(rf.F))
                self.assertEqual(int(values["h"]), (int(rf.HL) >> 8) & 0xFF)
                self.assertEqual(int(values["l"]), int(rf.HL) & 0xFF)
                self.assertEqual(int(values["sp"]), int(rf.SP))
                self.assertEqual(int(values["pc"]), int(rf.PC))
                self.assertEqual(int(values["if"]), int(memory[0xFF0F]))
                self.assertEqual(int(values["ie"]), int(memory[0xFFFF]))
                self.assertEqual(int(values["lcdc"]), int(memory[0xFF40]))
                self.assertEqual(int(values["stat"]), int(memory[0xFF41]))
                self.assertEqual(int(values["scx"]), int(memory[0xFF43]))
                self.assertEqual(int(values["scy"]), int(memory[0xFF42]))
                self.assertEqual(int(values["restart_scx"]), int(memory[0xFF43]))
                self.assertEqual(int(values["restart_scy"]), int(memory[0xFF42]))
                self.assertEqual(int(values["restart_wx"]), int(memory[0xFF4B]))
                self.assertEqual(int(values["restart_wy"]), int(memory[0xFF4A]))
                self.assertEqual(vram_path.read_bytes(), bytes(int(memory[address]) & 0xFF for address in range(0x8000, 0xA000)))
                self.assertEqual(oam_path.read_bytes(), bytes(int(memory[address]) & 0xFF for address in range(0xFE00, 0xFEA0)))
                self.assertEqual(wram_path.read_bytes(), bytes(int(memory[address]) & 0xFF for address in range(0xC000, 0xE000)))
                self.assertEqual(hram_path.read_bytes(), bytes(int(memory[address]) & 0xFF for address in range(0xFF80, 0xFFFF)))
            finally:
                pyboy.stop(save=False)


if __name__ == "__main__":
    unittest.main()
