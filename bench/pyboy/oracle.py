"""Stable PyBoy-backed oracle scaffold for lockstep tests."""

from __future__ import annotations

import io
import pickle
import re
import warnings
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, Sequence, Union

warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll.*")

from pyboy import PyBoy
from pyboy.utils import WindowEvent

from spec.profiles import ModelProfile, ResetProfile


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DMG_BOOTROM = ROOT / "roms" / "bootrom_fast_dmg.bin"
DEFAULT_PHASE_AFTER = "HookCheckpoint"
DEFAULT_BUS_KIND = "unavailable"
SYMBOL_RE = re.compile(r"^(?P<bank>[0-9A-Fa-f]{2,}):(?P<addr>[0-9A-Fa-f]{4})\s+(?P<label>\S+)$")
RESERVED_HOOK_PREFIXES = ("__checkpoint_", "__commit_")
RESERVED_HOOK_LABELS = RESERVED_HOOK_PREFIXES + ("__pass", "__fail")


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
class ButtonEvent:
    button: str
    action: Literal["tap", "press", "release"] = "tap"
    delay: int = 1


@dataclass(frozen=True)
class MemoryWriteEvent:
    addr: int
    value: int
    bank: int | None = None


@dataclass(frozen=True)
class RawInputEvent:
    event: int
    delay: int = 0


SimEvent = Union[ButtonEvent, MemoryWriteEvent, RawInputEvent]


@dataclass(frozen=True)
class _ResolvedCommitPoint:
    bank: int
    addr: int
    label: str
    opcode: int


class Oracle(Protocol):
    def reset(self, model_profile: ModelProfile | str, reset_profile: ResetProfile | str) -> None:
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

    def __enter__(self) -> "PyBoyOracle":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        if self._pyboy is not None:
            self._pyboy.stop(save=False)
            self._pyboy = None

    def reset(self, model_profile: ModelProfile | str, reset_profile: ResetProfile | str) -> None:
        model = _coerce_model_profile(model_profile)
        reset = _coerce_reset_profile(reset_profile)

        self.close()
        self._commit_queue.clear()
        self._seq = 0

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
        self._install_hooks()

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
        if isinstance(ev, ButtonEvent):
            if ev.action == "tap":
                pyboy.button(ev.button, ev.delay)
            elif ev.action == "press":
                pyboy.button_press(ev.button)
            elif ev.action == "release":
                pyboy.button_release(ev.button)
            else:
                raise ValueError(f"Unsupported button action: {ev.action}")
            return
        if isinstance(ev, MemoryWriteEvent):
            if ev.bank is None:
                pyboy.memory[ev.addr] = ev.value & 0xFF
            else:
                pyboy.memory[ev.bank, ev.addr] = ev.value & 0xFF
            return
        if isinstance(ev, RawInputEvent):
            pyboy.send_input(WindowEvent(ev.event), ev.delay)
            return
        raise TypeError(f"Unsupported simulation event: {type(ev)!r}")

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
            bus_request=BusRequest(),
            bus_response=BusResponse(),
        )
        self._commit_queue.append(commit)
        self._seq += 1

    def _install_hooks(self) -> None:
        pyboy = self._require_pyboy()
        for point in self._resolve_commit_points():
            def callback(resolved: _ResolvedCommitPoint, self: "PyBoyOracle" = self) -> None:
                self._capture_commit(resolved)

            pyboy.hook_register(point.bank, point.addr, callback, point)

    def _resolve_commit_points(self) -> tuple[_ResolvedCommitPoint, ...]:
        pyboy = self._require_pyboy()
        specs = self.commit_points
        if not specs:
            if self.sym_path is None:
                raise ValueError("commit_points or a .sym file with reserved hook labels is required")
            specs = _load_default_commit_points(self.sym_path)
        grouped: dict[tuple[int, int], list[str]] = {}
        for spec in specs:
            if isinstance(spec.addr, str):
                bank, addr = pyboy.symbol_lookup(spec.addr)
                label = spec.label or spec.addr
            else:
                bank = 0 if spec.bank is None else int(spec.bank)
                addr = int(spec.addr)
                label = spec.label or f"{bank:02X}:{addr:04X}"
            grouped.setdefault((bank, addr), []).append(label)

        resolved = []
        for (bank, addr), labels in sorted(grouped.items()):
            opcode = int(pyboy.memory[bank, addr]) & 0xFF
            label = "|".join(dict.fromkeys(labels))
            resolved.append(_ResolvedCommitPoint(bank=bank, addr=addr, label=label, opcode=opcode))
        return tuple(resolved)

    def _resolve_bootrom(self, model: ModelProfile) -> Path:
        if model is not ModelProfile.DMG:
            raise NotImplementedError("RawPowerOn is only scaffolded for DMG because no CGB boot ROM is pinned")
        if not self.bootrom_path.exists():
            raise FileNotFoundError(f"RawPowerOn requested but boot ROM is missing: {self.bootrom_path}")
        return self.bootrom_path

    def _require_pyboy(self) -> PyBoy:
        if self._pyboy is None:
            raise RuntimeError("Oracle has not been reset yet")
        return self._pyboy
