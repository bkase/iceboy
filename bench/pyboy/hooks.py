"""Reserved hook manifest support for strict PyBoy lockstep."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from bench.pyboy.oracle import CommitPoint
from bench.pyboy.symbols import SymbolTable


REQUIRED_LABELS = ("__pass", "__fail")
OPTIONAL_PREFIXES = ("__checkpoint_", "__commit_")


@dataclass(frozen=True)
class HookTarget:
    bank: int
    addr: int
    labels: tuple[str, ...]

    @property
    def joined_label(self) -> str:
        return "|".join(self.labels)

    def to_commit_point(self) -> CommitPoint:
        return CommitPoint(bank=self.bank, addr=self.addr, label=self.joined_label)


@dataclass(frozen=True)
class HookManifest:
    sym_path: Path
    sym_sha256: str
    targets: tuple[HookTarget, ...]

    def commit_points(self) -> tuple[CommitPoint, ...]:
        return tuple(target.to_commit_point() for target in self.targets)

    def terminal_labels(self) -> tuple[str, ...]:
        return REQUIRED_LABELS


def _is_reserved_label(label: str) -> bool:
    return label in REQUIRED_LABELS or label.startswith(OPTIONAL_PREFIXES)


def build_hook_manifest(
    sym_path: str | Path,
    *,
    checkpoint_symbols: Sequence[str] = (),
) -> HookManifest:
    table = SymbolTable.load(sym_path)
    grouped: dict[tuple[int, int], list[str]] = {}

    for label in REQUIRED_LABELS:
        symbol = table.lookup(label)
        if not symbol.is_executable:
            raise ValueError(f"Required hook label {label} is not in executable ROM space")
        grouped.setdefault(symbol.key, []).append(label)

    for symbol in table.executable_symbols():
        if _is_reserved_label(symbol.label):
            grouped.setdefault(symbol.key, []).append(symbol.label)

    for label in checkpoint_symbols:
        symbol = table.lookup(label)
        if not symbol.label.startswith("__checkpoint_"):
            raise ValueError(f"checkpoint_symbols entry must use __checkpoint_* labels: {label}")
        if not symbol.is_executable:
            raise ValueError(f"Checkpoint hook label {label} is not in executable ROM space")
        grouped.setdefault(symbol.key, []).append(label)

    targets = []
    for (bank, addr), labels in sorted(grouped.items()):
        targets.append(HookTarget(bank=bank, addr=addr, labels=tuple(dict.fromkeys(labels))))

    return HookManifest(
        sym_path=Path(sym_path),
        sym_sha256=table.sha256(),
        targets=tuple(targets),
    )
