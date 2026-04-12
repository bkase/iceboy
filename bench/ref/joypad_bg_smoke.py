from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.actions.generators import SeededEventScript
from bench.pyboy.oracle import PyBoyOracle
from spec.profiles import ModelProfile, ResetProfile

DEFAULT_ROM = ROOT / "bench" / "roms" / "out" / "joypad_bg_smoke.gb"
DEFAULT_ACTION_SCRIPT = ROOT / "bench" / "actions" / "joypad_bg_smoke.yaml"


def capture_joypad_bg_smoke_frame(
    rom_path: str | Path = DEFAULT_ROM,
    *,
    action_script_path: str | Path = DEFAULT_ACTION_SCRIPT,
    settle_frames: int = 2,
) -> bytes:
    script = SeededEventScript.from_action_script(action_script_path)
    max_commit = max((event.commit_index or 0) for event in script.events)
    total_frames = max_commit + 1 + settle_frames

    with PyBoyOracle(rom_path) as oracle:
        oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)
        pyboy = oracle._require_pyboy()
        for frame_index in range(total_frames):
            for event in script.events_for_commit(frame_index):
                oracle.write_event(event)
            pyboy.tick(1, True, False)
        return oracle.shade_buffer()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture the JOYPAD_BG_SMOKE final DMG shade frame via PyBoy.")
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--action-script", type=Path, default=DEFAULT_ACTION_SCRIPT)
    parser.add_argument("--out", type=Path, default=None, help="Optional output path for the raw 160x144 DMG shade bytes")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = capture_joypad_bg_smoke_frame(args.rom, action_script_path=args.action_script)
    if args.out is None:
        print(payload.hex())
    else:
        args.out.write_bytes(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
