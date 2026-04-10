"""Stable PyBoy-backed oracle scaffold for lockstep tests."""

from __future__ import annotations

import io
import pickle
import re
import warnings
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

import numpy

warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")

from pyboy import PyBoy
from pyboy.utils import WindowEvent

from bench.actions.generators import (
    IeOverrideEvent,
    IfClearBitsEvent,
    IfSetBitsEvent,
    JoypadButtonsEvent,
    MemoryWriteEvent,
    RawInputEvent,
    SimEvent,
)
from spec.profiles import BehaviorConfig, ModelProfile, ResetProfile, default_behavior_config


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DMG_BOOTROM = ROOT / "roms" / "bootrom_fast_dmg.bin"
DEFAULT_PHASE_AFTER = "HookCheckpoint"
DEFAULT_BUS_KIND = "unavailable"
DMG_SKIPBOOT_REGISTERS = {
    "A": 0x01,
    "F": 0xB0,
    "B": 0x00,
    "C": 0x13,
    "D": 0x00,
    "E": 0xD8,
    "HL": 0x014D,
    "SP": 0xFFFE,
    "PC": 0x0100,
}
DMG_SKIPBOOT_IO = {
    0xFFFF: 0x00,
    0xFF0F: 0xE1,
    0xFF05: 0x00,
    0xFF06: 0x00,
    0xFF07: 0x00,
    0xFF00: 0xCF,
    0xFF40: 0x91,
    0xFF41: 0x85,
    0xFF42: 0x00,
    0xFF43: 0x00,
    0xFF44: 0x00,
    0xFF45: 0x00,
    0xFF47: 0xFC,
    0xFF48: 0xFF,
    0xFF49: 0xFF,
    0xFF4A: 0x00,
    0xFF4B: 0x00,
}
SYMBOL_RE = re.compile(r"^(?P<bank>[0-9A-Fa-f]{2,}):(?P<addr>[0-9A-Fa-f]{4})\s+(?P<label>\S+)$")
RESERVED_HOOK_PREFIXES = ("__checkpoint_", "__commit_")
RESERVED_HOOK_LABELS = RESERVED_HOOK_PREFIXES + ("__pass", "__fail")
DMG_SHADE_VALUES = (0x00, 0x55, 0xAA, 0xFF)
SCREEN_WIDTH = 160
SCREEN_HEIGHT = 144
TILEMAP_WIDTH = 32
TILEMAP_HEIGHT = 32
SPRITE_COUNT = 40


@dataclass(frozen=True)
class RegisterState:
    a: int
    f: int
    b: int
    c: int
    d: int
    e: int
    hl: int
    sp: int
    pc: int

    @classmethod
    def from_pyboy(cls, pyboy: PyBoy) -> "RegisterState":
        rf = pyboy.register_file
        return cls(
            a=int(rf.A),
            f=int(rf.F),
            b=int(rf.B),
            c=int(rf.C),
            d=int(rf.D),
            e=int(rf.E),
            hl=int(rf.HL),
            sp=int(rf.SP),
            pc=int(rf.PC),
        )


@dataclass(frozen=True)
class BusRequest:
    kind: str = DEFAULT_BUS_KIND
    addr: int | None = None
    data: int | None = None


@dataclass(frozen=True)
class BusResponse:
    kind: str = DEFAULT_BUS_KIND
    data: int | None = None


@dataclass(frozen=True)
class OracleCommit:
    schema_version: int
    kind: str
    seq: int
    label: str | None
    pc_before: int
    opcode: int | None
    registers_after: RegisterState
    phase_after: str
    bus_request: BusRequest
    bus_response: BusResponse


@dataclass(frozen=True)
class CommitPoint:
    bank: int | None
    addr: int | str
    label: str | None = None


@dataclass(frozen=True)
class _ResolvedCommitPoint:
    bank: int
    addr: int
    label: str
    opcode: int

    @property
    def key(self) -> tuple[int, int]:
        return (self.bank, self.addr)


@dataclass(frozen=True)
class _RuntimeHookSpec:
    point: CommitPoint
    callback: Any


@dataclass(frozen=True)
class TileMapCapture:
    width: int
    height: int
    tile_ids: tuple[int, ...]

    def tile_id(self, x: int, y: int) -> int:
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError("tile coordinates out of range")
        return self.tile_ids[(y * self.width) + x]


@dataclass(frozen=True)
class SpriteCapture:
    sprite_index: int
    x: int
    y: int
    tile_identifier: int
    on_screen: bool
    width: int
    height: int
    palette_number: int
    x_flip: bool
    y_flip: bool
    obj_bg_priority: bool
    cgb_bank_number: bool


@dataclass(frozen=True)
class LineScrollCapture:
    line: int
    scx: int
    scy: int
    wx: int
    wy: int


@dataclass(frozen=True)
class FrameSemanticCapture:
    bg_tilemap: TileMapCapture
    window_tilemap: TileMapCapture
    sprites: tuple[SpriteCapture, ...]
    line_scroll: tuple[LineScrollCapture, ...]


@dataclass(frozen=True)
class HookTimingCapture:
    seq: int
    frame: int
    label: str
    pc: int
    ly: int
    stat: int
    lcdc: int
    scx: int
    scy: int
    wx: int
    wy: int


class VideoOracle(Protocol):
    def reset(
        self,
        model_profile: ModelProfile | str,
        reset_profile: ResetProfile | str,
        behavior_config: BehaviorConfig | Mapping[str, object] | None = None,
    ) -> None:
        ...

    def frame_semantics(self) -> FrameSemanticCapture:
        ...

    def shade_buffer(self) -> bytes:
        ...

    def frame_buffer_rgba(self) -> numpy.ndarray[Any, Any]:
        ...

    def snapshot(self) -> bytes:
        ...

    def restore(self, snapshot: bytes) -> None:
        ...


class Oracle(Protocol):
    def reset(
        self,
        model_profile: ModelProfile | str,
        reset_profile: ResetProfile | str,
        behavior_config: BehaviorConfig | Mapping[str, object] | None = None,
    ) -> None:
        ...

    def step_commit(self) -> OracleCommit:
        ...

    def read_mem(self, addr: int) -> int:
        ...

    def write_event(self, ev: SimEvent) -> None:
        ...

    def snapshot(self) -> bytes:
        ...

    def restore(self, snapshot: bytes) -> None:
        ...


def _coerce_model_profile(model_profile: ModelProfile | str) -> ModelProfile:
    if isinstance(model_profile, ModelProfile):
        return model_profile
    return ModelProfile(str(model_profile))


def _coerce_reset_profile(reset_profile: ResetProfile | str) -> ResetProfile:
    if isinstance(reset_profile, ResetProfile):
        return reset_profile
    return ResetProfile(str(reset_profile))


def _coerce_behavior_config(
    behavior_config: BehaviorConfig | Mapping[str, object] | None,
    model_profile: ModelProfile,
) -> BehaviorConfig:
    if behavior_config is None:
        return default_behavior_config(model_profile)
    if isinstance(behavior_config, BehaviorConfig):
        config = behavior_config
    else:
        config = BehaviorConfig.from_mapping(behavior_config)
    if config.model is not model_profile:
        raise ValueError(
            f"BehaviorConfig.model ({config.model.value}) does not match requested model profile {model_profile.value}"
        )
    return config


def _normalize_rgba_to_dmg_shades(rgba: numpy.ndarray[Any, Any]) -> bytes:
    array = numpy.asarray(rgba, dtype=numpy.uint8)
    if array.shape != (SCREEN_HEIGHT, SCREEN_WIDTH, 4):
        raise ValueError(f"expected RGBA frame shape {(SCREEN_HEIGHT, SCREEN_WIDTH, 4)}, got {array.shape}")
    rgb = array[:, :, :3]
    flat_rgb = rgb.reshape(-1, 3)
    shade_map: dict[tuple[int, int, int], int] = {}
    for color in numpy.unique(flat_rgb, axis=0):
        rgb_key = tuple(int(channel) for channel in color)
        luminance = sum(rgb_key) // 3
        shade_map[rgb_key] = min(DMG_SHADE_VALUES, key=lambda shade: abs(shade - luminance))
    normalized = bytearray(flat_rgb.shape[0])
    for index, color in enumerate(flat_rgb):
        normalized[index] = shade_map[tuple(int(channel) for channel in color)]
    return bytes(normalized)


def capture_rendered_frame_rgba(
    rom_path: str | Path,
    *,
    cgb: bool = False,
    frame_batches: Sequence[int] = (84,),
) -> numpy.ndarray[Any, Any]:
    pyboy = PyBoy(
        str(rom_path),
        window="null",
        sound_emulated=False,
        no_input=True,
        log_level="ERROR",
        cgb=cgb,
    )
    try:
        pyboy.set_emulation_speed(0)
        for frame_count in frame_batches:
            pyboy.tick(int(frame_count), True, False)
        return numpy.array(pyboy.screen.ndarray, copy=True)
    finally:
        pyboy.stop(save=False)


def capture_rendered_frame_dmg_shades(
    rom_path: str | Path,
    *,
    frame_batches: Sequence[int] = (84,),
) -> bytes:
    return _normalize_rgba_to_dmg_shades(
        capture_rendered_frame_rgba(rom_path, cgb=False, frame_batches=frame_batches)
    )


def capture_checkpoint_frame_dmg_shades(
    rom_path: str | Path,
    *,
    sym_path: str | Path,
    checkpoint_label: str = "__checkpoint_scene_ready",
    settle_rendered_frames: int = 2,
) -> bytes:
    with PyBoyOracle(
        rom_path,
        sym_path=sym_path,
        commit_points=(CommitPoint(bank=None, addr=checkpoint_label),),
    ) as oracle:
        oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)
        oracle.step_commit()
        if settle_rendered_frames > 0:
            oracle._require_pyboy().tick(int(settle_rendered_frames), True, False)
        return oracle.shade_buffer()


def capture_checkpoint_hook_timings(
    rom_path: str | Path,
    *,
    sym_path: str | Path,
    hook_points: Sequence[CommitPoint],
    checkpoint_label: str = "__checkpoint_scene_ready",
    settle_rendered_frames: int = 2,
    target_line: int | None = None,
) -> tuple[HookTimingCapture, ...]:
    captures: list[HookTimingCapture] = []
    current_frame = {"value": 0}

    with PyBoyOracle(
        rom_path,
        sym_path=sym_path,
        commit_points=(CommitPoint(bank=None, addr=checkpoint_label),),
    ) as oracle:
        def capture(resolved: _ResolvedCommitPoint) -> None:
            pyboy = oracle._require_pyboy()
            registers = RegisterState.from_pyboy(pyboy)
            ly = int(pyboy.memory[0xFF44]) & 0xFF
            if target_line is not None and ly != target_line:
                return
            captures.append(
                HookTimingCapture(
                    seq=len(captures),
                    frame=current_frame["value"],
                    label=resolved.label,
                    pc=registers.pc,
                    ly=ly,
                    stat=int(pyboy.memory[0xFF41]) & 0xFF,
                    lcdc=int(pyboy.memory[0xFF40]) & 0xFF,
                    scx=int(pyboy.memory[0xFF43]) & 0xFF,
                    scy=int(pyboy.memory[0xFF42]) & 0xFF,
                    wx=int(pyboy.memory[0xFF4B]) & 0xFF,
                    wy=int(pyboy.memory[0xFF4A]) & 0xFF,
                )
            )

        for point in hook_points:
            oracle.register_runtime_hook(bank=point.bank, addr=point.addr, callback=capture, label=point.label)

        oracle.reset(ModelProfile.DMG, ResetProfile.SkipBoot)
        oracle.step_commit()
        pyboy = oracle._require_pyboy()
        for frame in range(int(settle_rendered_frames)):
            current_frame["value"] = frame + 1
            pyboy.tick(1, True, False)

    return tuple(captures)


def _is_executable_rom(bank: int, addr: int) -> bool:
    if bank == 0:
        return 0x0000 <= addr < 0x8000
    return 0x4000 <= addr < 0x8000


def _load_default_commit_points(sym_path: Path) -> tuple[CommitPoint, ...]:
    grouped: dict[tuple[int, int], list[str]] = {}
    for raw_line in sym_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(";"):
            continue
        match = SYMBOL_RE.match(line)
        if not match:
            continue
        bank = int(match.group("bank"), 16)
        addr = int(match.group("addr"), 16)
        label = match.group("label")
        if not label.startswith(RESERVED_HOOK_LABELS):
            continue
        if not _is_executable_rom(bank, addr):
            continue
        grouped.setdefault((bank, addr), []).append(label)

    commit_points = []
    for (bank, addr), labels in sorted(grouped.items()):
        label = "|".join(dict.fromkeys(labels))
        commit_points.append(CommitPoint(bank=bank, addr=addr, label=label))
    return tuple(commit_points)


class PyBoyOracle:
    def __init__(
        self,
        rom_path: str | Path,
        *,
        sym_path: str | Path | None = None,
        commit_points: Sequence[CommitPoint] | None = None,
        bootrom_path: str | Path | None = None,
        max_frames_per_commit: int = 180,
    ) -> None:
        self.rom_path = Path(rom_path)
        inferred_sym_path = self.rom_path.with_suffix(".sym")
        if sym_path is None and inferred_sym_path.exists():
            sym_path = inferred_sym_path
        self.sym_path = Path(sym_path) if sym_path is not None else None
        self.bootrom_path = Path(bootrom_path) if bootrom_path is not None else DEFAULT_DMG_BOOTROM
        self.commit_points = tuple(commit_points) if commit_points is not None else ()
        self.max_frames_per_commit = max_frames_per_commit

        self._pyboy: PyBoy | None = None
        self._commit_queue: deque[OracleCommit] = deque()
        self._seq = 0
        self._pressed_buttons: set[str] = set()
        self._runtime_hooks: list[_RuntimeHookSpec] = []

    def __enter__(self) -> "PyBoyOracle":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        if self._pyboy is not None:
            self._pyboy.stop(save=False)
            self._pyboy = None
        self._pressed_buttons.clear()

    def reset(
        self,
        model_profile: ModelProfile | str,
        reset_profile: ResetProfile | str,
        behavior_config: BehaviorConfig | Mapping[str, object] | None = None,
    ) -> None:
        model = _coerce_model_profile(model_profile)
        reset = _coerce_reset_profile(reset_profile)
        _coerce_behavior_config(behavior_config, model)

        self.close()
        self._commit_queue.clear()
        self._seq = 0
        self._pressed_buttons.clear()

        kwargs: dict[str, object] = {
            "window": "null",
            "sound_emulated": False,
            "no_input": True,
            "log_level": "ERROR",
            "cgb": model is ModelProfile.CGB,
        }
        if self.sym_path is not None:
            kwargs["symbols"] = str(self.sym_path)
        if reset is ResetProfile.RawPowerOn:
            bootrom = self._resolve_bootrom(model)
            kwargs["bootrom"] = str(bootrom)

        self._pyboy = PyBoy(str(self.rom_path), **kwargs)
        self._pyboy.set_emulation_speed(0)
        if reset is ResetProfile.SkipBoot:
            self._apply_skipboot_state(model)
        self._install_hooks()

    def frame_buffer_rgba(self) -> numpy.ndarray[Any, Any]:
        pyboy = self._require_pyboy()
        return numpy.array(pyboy.screen.ndarray, copy=True)

    def shade_buffer(self) -> bytes:
        return _normalize_rgba_to_dmg_shades(self.frame_buffer_rgba())

    def frame_semantics(self) -> FrameSemanticCapture:
        pyboy = self._require_pyboy()
        return FrameSemanticCapture(
            bg_tilemap=_capture_tilemap(pyboy.tilemap_background),
            window_tilemap=_capture_tilemap(pyboy.tilemap_window),
            sprites=tuple(_capture_sprite(pyboy.get_sprite(index)) for index in range(SPRITE_COUNT)),
            line_scroll=_capture_line_scroll(pyboy.screen.tilemap_position_list),
        )

    def step_commit(self) -> OracleCommit:
        pyboy = self._require_pyboy()
        if self._commit_queue:
            return self._commit_queue.popleft()

        for _ in range(self.max_frames_per_commit):
            running = pyboy.tick(1, False, False)
            if self._commit_queue:
                return self._commit_queue.popleft()
            if not running:
                break
        raise TimeoutError(f"No commit hook fired within {self.max_frames_per_commit} frame(s)")

    def read_mem(self, addr: int) -> int:
        pyboy = self._require_pyboy()
        return int(pyboy.memory[addr]) & 0xFF

    def write_event(self, ev: SimEvent) -> None:
        pyboy = self._require_pyboy()
        if isinstance(ev, JoypadButtonsEvent):
            target = set(ev.joyp_buttons.pressed_buttons())
            for button in sorted(self._pressed_buttons - target):
                pyboy.button_release(button)
            for button in sorted(target - self._pressed_buttons):
                pyboy.button_press(button)
            self._pressed_buttons = target
            return
        if isinstance(ev, MemoryWriteEvent):
            if ev.bank is None:
                pyboy.memory[ev.addr] = ev.value & 0xFF
            else:
                pyboy.memory[ev.bank, ev.addr] = ev.value & 0xFF
            return
        if isinstance(ev, IfSetBitsEvent):
            current = int(pyboy.memory[0xFF0F]) & 0xFF
            pyboy.memory[0xFF0F] = (current & 0xE0) | ((current | ev.bits) & 0x1F)
            return
        if isinstance(ev, IfClearBitsEvent):
            current = int(pyboy.memory[0xFF0F]) & 0xFF
            pyboy.memory[0xFF0F] = (current & 0xE0) | ((current & ~ev.bits) & 0x1F)
            return
        if isinstance(ev, IeOverrideEvent):
            current = int(pyboy.memory[0xFFFF]) & 0xFF
            pyboy.memory[0xFFFF] = (current & 0xE0) | (ev.value & 0x1F)
            return
        if isinstance(ev, RawInputEvent):
            pyboy.send_input(WindowEvent(ev.event), ev.delay)
            return
        raise NotImplementedError(f"PyBoy oracle does not support sideband event {type(ev).__name__}")

    def register_runtime_hook(
        self,
        *,
        bank: int | None = None,
        addr: int | str,
        callback: Any,
        label: str | None = None,
    ) -> None:
        self._runtime_hooks.append(
            _RuntimeHookSpec(point=CommitPoint(bank=bank, addr=addr, label=label), callback=callback)
        )

    def snapshot(self) -> bytes:
        pyboy = self._require_pyboy()
        state = io.BytesIO()
        pyboy.save_state(state)
        queued_input = getattr(pyboy, "queued_input", None)
        payload = {
            "pyboy_state": state.getvalue(),
            "commit_queue": list(self._commit_queue),
            "events": [int(event) for event in getattr(pyboy, "events", [])],
            "queued_input": [(frame, int(event)) for frame, event in queued_input] if queued_input is not None else [],
            "pressed_buttons": sorted(self._pressed_buttons),
            "seq": self._seq,
        }
        return pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)

    def restore(self, snapshot: bytes) -> None:
        pyboy = self._require_pyboy()
        payload = pickle.loads(snapshot)
        state = io.BytesIO(payload["pyboy_state"])
        pyboy.load_state(state)
        restored_events = [WindowEvent(event) for event in payload.get("events", [])]
        pyboy.events.clear()
        pyboy.events.extend(restored_events)
        queued_input = getattr(pyboy, "queued_input", None)
        if queued_input is not None:
            queued_input.clear()
            queued_input.extend((frame, event) for frame, event in payload.get("queued_input", []))
        self._commit_queue = deque(payload.get("commit_queue", []))
        self._pressed_buttons = set(payload.get("pressed_buttons", []))
        self._seq = int(payload.get("seq", 0))

    def _capture_commit(self, point: _ResolvedCommitPoint) -> None:
        pyboy = self._require_pyboy()
        registers = RegisterState.from_pyboy(pyboy)
        commit = OracleCommit(
            schema_version=1,
            kind="Checkpoint",
            seq=self._seq,
            label=point.label,
            pc_before=registers.pc,
            opcode=point.opcode,
            registers_after=registers,
            phase_after=DEFAULT_PHASE_AFTER,
            bus_request=BusRequest(kind="read", addr=point.addr, data=None),
            bus_response=BusResponse(kind="data", data=point.opcode),
        )
        self._commit_queue.append(commit)
        self._seq += 1

    def _install_hooks(self) -> None:
        pyboy = self._require_pyboy()
        commit_points = {point.key: point for point in self._resolve_commit_points()}
        runtime_points: dict[tuple[int, int], list[tuple[_ResolvedCommitPoint, Any]]] = {}
        for spec in self._runtime_hooks:
            resolved = self._resolve_point(spec.point)
            runtime_points.setdefault(resolved.key, []).append((resolved, spec.callback))

        for key in sorted(set(commit_points) | set(runtime_points)):
            commit_point = commit_points.get(key)
            callbacks = runtime_points.get(key, ())
            resolved = commit_point if commit_point is not None else callbacks[0][0]

            def callback(
                callback_resolved: _ResolvedCommitPoint,
                hook_callbacks: tuple[tuple[_ResolvedCommitPoint, Any], ...] = tuple(callbacks),
                commit_resolved: _ResolvedCommitPoint | None = commit_point,
                self: "PyBoyOracle" = self,
            ) -> None:
                for runtime_resolved, runtime_callback in hook_callbacks:
                    runtime_callback(runtime_resolved)
                if commit_resolved is not None:
                    self._capture_commit(commit_resolved)

            pyboy.hook_register(resolved.bank, resolved.addr, callback, resolved)

    def _resolve_commit_points(self) -> tuple[_ResolvedCommitPoint, ...]:
        return tuple(self._resolve_point(spec) for spec in self._iter_commit_specs())

    def _iter_commit_specs(self) -> tuple[CommitPoint, ...]:
        pyboy = self._require_pyboy()
        specs = self.commit_points
        if not specs:
            if self.sym_path is None:
                raise ValueError("commit_points or a .sym file with reserved hook labels is required")
            specs = _load_default_commit_points(self.sym_path)
        return tuple(specs)

    def _resolve_point(self, spec: CommitPoint) -> _ResolvedCommitPoint:
        pyboy = self._require_pyboy()
        if isinstance(spec.addr, str):
            bank, addr = pyboy.symbol_lookup(spec.addr)
            label = spec.label or spec.addr
        else:
            bank = 0 if spec.bank is None else int(spec.bank)
            addr = int(spec.addr)
            label = spec.label or f"{bank:02X}:{addr:04X}"
        grouped: dict[tuple[int, int], list[str]] = {(bank, addr): [label]}
        resolved = []
        for (bank, addr), labels in sorted(grouped.items()):
            opcode = int(pyboy.memory[bank, addr]) & 0xFF
            label = "|".join(dict.fromkeys(labels))
            resolved.append(_ResolvedCommitPoint(bank=bank, addr=addr, label=label, opcode=opcode))
        return resolved[0]

    def _resolve_bootrom(self, model: ModelProfile) -> Path:
        if model is not ModelProfile.DMG:
            raise NotImplementedError("RawPowerOn is only scaffolded for DMG because no CGB boot ROM is pinned")
        if not self.bootrom_path.exists():
            raise FileNotFoundError(f"RawPowerOn requested but boot ROM is missing: {self.bootrom_path}")
        return self.bootrom_path

    def _apply_skipboot_state(self, model: ModelProfile) -> None:
        pyboy = self._require_pyboy()
        if model is not ModelProfile.DMG:
            raise NotImplementedError("SkipBoot is only scaffolded for DMG because no CGB post-boot state is pinned")

        rf = pyboy.register_file
        for name, value in DMG_SKIPBOOT_REGISTERS.items():
            setattr(rf, name, value)
        for addr, value in DMG_SKIPBOOT_IO.items():
            pyboy.memory[addr] = value

    def _require_pyboy(self) -> PyBoy:
        if self._pyboy is None:
            raise RuntimeError("Oracle has not been reset yet")
        return self._pyboy


def _capture_tilemap(tilemap: Any) -> TileMapCapture:
    width = int(tilemap.shape[0])
    height = int(tilemap.shape[1])
    tile_ids = []
    for y in range(height):
        for x in range(width):
            tile_ids.append(int(tilemap.tile_identifier(x, y)))
    return TileMapCapture(width=width, height=height, tile_ids=tuple(tile_ids))


def _capture_sprite(sprite: Any) -> SpriteCapture:
    shape = getattr(sprite, "shape", (8, 8))
    return SpriteCapture(
        sprite_index=int(sprite.sprite_index),
        x=int(sprite.x),
        y=int(sprite.y),
        tile_identifier=int(sprite.tile_identifier),
        on_screen=bool(sprite.on_screen),
        width=int(shape[0]),
        height=int(shape[1]),
        palette_number=int(sprite.attr_palette_number),
        x_flip=bool(sprite.attr_x_flip),
        y_flip=bool(sprite.attr_y_flip),
        obj_bg_priority=bool(sprite.attr_obj_bg_priority),
        cgb_bank_number=bool(sprite.attr_cgb_bank_number),
    )


def _capture_line_scroll(position_list: Sequence[Sequence[int]]) -> tuple[LineScrollCapture, ...]:
    captures = []
    for line, entry in enumerate(position_list):
        if len(entry) != 4:
            raise ValueError(f"expected tilemap position entry with 4 fields, got {entry!r}")
        scx, scy, wx_internal, wy = (int(value) for value in entry)
        captures.append(LineScrollCapture(line=line, scx=scx, scy=scy, wx=wx_internal + 7, wy=wy))
    return tuple(captures)
