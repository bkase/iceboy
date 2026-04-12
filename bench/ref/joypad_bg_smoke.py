from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.actions.generators import SeededEventScript

DEFAULT_ROM = ROOT / "bench" / "roms" / "out" / "joypad_bg_smoke.gb"
DEFAULT_ACTION_SCRIPT = ROOT / "bench" / "actions" / "joypad_bg_smoke.yaml"
SCREEN_WIDTH = 160
SCREEN_HEIGHT = 144
TILE_SIZE = 8
CURSOR_HOME_X = 10
CURSOR_HOME_Y = 9
CURSOR_MAX_X = 18
CURSOR_MAX_Y = 16
DMG_SHADE_VALUES = (0xFF, 0xAA, 0x55, 0x00)
PALETTE_TABLE = (0xE4, 0xD2, 0x39, 0x1B, 0x1B, 0x39, 0xD2, 0xE4)
CURSOR_STYLE_COLORS = (
    (3, 2, 1, 0),
    (0, 1, 3, 2),
)


@dataclass(frozen=True)
class JoypadBgSmokeState:
    cursor_x: int = CURSOR_HOME_X
    cursor_y: int = CURSOR_HOME_Y
    palette_index: int = 0
    cursor_style: int = 0
    invert_palette: int = 0
    prev_directions: int = 0
    prev_buttons: int = 0


def _direction_mask(button_names: set[str]) -> int:
    return (
        (0x1 if "right" in button_names else 0)
        | (0x2 if "left" in button_names else 0)
        | (0x4 if "up" in button_names else 0)
        | (0x8 if "down" in button_names else 0)
    )


def _button_mask(button_names: set[str]) -> int:
    return (
        (0x1 if "a" in button_names else 0)
        | (0x2 if "b" in button_names else 0)
        | (0x4 if "select" in button_names else 0)
        | (0x8 if "start" in button_names else 0)
    )


def step_joypad_bg_smoke_state(state: JoypadBgSmokeState, *, button_names: set[str]) -> JoypadBgSmokeState:
    direction_now = _direction_mask(button_names)
    direction_edges = (~state.prev_directions) & direction_now & 0xF

    cursor_x = state.cursor_x
    cursor_y = state.cursor_y
    if direction_edges & 0x4 and cursor_y > 0:
        cursor_y -= 1
    if direction_edges & 0x8 and cursor_y < CURSOR_MAX_Y:
        cursor_y += 1
    if direction_edges & 0x2 and cursor_x > 0:
        cursor_x -= 1
    if direction_edges & 0x1 and cursor_x < CURSOR_MAX_X:
        cursor_x += 1

    button_now = _button_mask(button_names)
    button_edges = (~state.prev_buttons) & button_now & 0xF

    palette_index = state.palette_index
    cursor_style = state.cursor_style
    invert_palette = state.invert_palette
    if button_edges & 0x1:
        palette_index = (palette_index + 1) & 0x3
    if button_edges & 0x2:
        cursor_style ^= 0x1
    if button_edges & 0x4:
        invert_palette ^= 0x1
    if button_edges & 0x8:
        cursor_x = CURSOR_HOME_X
        cursor_y = CURSOR_HOME_Y

    return JoypadBgSmokeState(
        cursor_x=cursor_x,
        cursor_y=cursor_y,
        palette_index=palette_index,
        cursor_style=cursor_style,
        invert_palette=invert_palette,
        prev_directions=direction_now,
        prev_buttons=button_now,
    )


def simulate_joypad_bg_smoke_state(
    *,
    action_script_path: str | Path = DEFAULT_ACTION_SCRIPT,
    settle_frames: int = 2,
) -> JoypadBgSmokeState:
    script = SeededEventScript.from_action_script(action_script_path)
    max_commit = max((event.commit_index or 0) for event in script.events)
    total_frames = max_commit + 1 + settle_frames

    state = JoypadBgSmokeState()
    current_buttons: set[str] = set()
    for frame_index in range(total_frames):
        for event in script.events_for_commit(frame_index):
            current_buttons = {
                name
                for name in ("up", "down", "left", "right", "a", "b", "start", "select")
                if bool(getattr(event.joyp_buttons, name))
            }
        state = step_joypad_bg_smoke_state(state, button_names=current_buttons)
    return state


def palette_byte_for_state(state: JoypadBgSmokeState) -> int:
    return PALETTE_TABLE[state.palette_index + (state.invert_palette * 4)]


def _palette_shade(color_id: int, bgp: int) -> int:
    shade_index = (bgp >> (color_id * 2)) & 0x3
    return DMG_SHADE_VALUES[shade_index]


def render_joypad_bg_smoke_frame(state: JoypadBgSmokeState) -> bytes:
    bgp = palette_byte_for_state(state)
    cursor_colors = CURSOR_STYLE_COLORS[state.cursor_style & 0x1]
    frame = bytearray(SCREEN_WIDTH * SCREEN_HEIGHT)
    for y in range(SCREEN_HEIGHT):
        tile_y = y // TILE_SIZE
        for x in range(SCREEN_WIDTH):
            tile_x = x // TILE_SIZE
            color_id = (tile_x + tile_y) & 0x1
            if state.cursor_x <= tile_x <= state.cursor_x + 1 and state.cursor_y <= tile_y <= state.cursor_y + 1:
                cursor_index = ((tile_y - state.cursor_y) * 2) + (tile_x - state.cursor_x)
                color_id = cursor_colors[cursor_index]
            frame[(y * SCREEN_WIDTH) + x] = _palette_shade(color_id, bgp)
    return bytes(frame)


def capture_joypad_bg_smoke_frame(
    rom_path: str | Path = DEFAULT_ROM,
    *,
    action_script_path: str | Path = DEFAULT_ACTION_SCRIPT,
    settle_frames: int = 2,
) -> bytes:
    _ = rom_path
    final_state = simulate_joypad_bg_smoke_state(action_script_path=action_script_path, settle_frames=settle_frames)
    return render_joypad_bg_smoke_frame(final_state)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture the JOYPAD_BG_SMOKE final DMG shade frame via the scripted model.")
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
