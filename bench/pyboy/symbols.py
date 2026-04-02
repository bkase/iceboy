"""RGBDS symbol loading for PyBoy hook manifests."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


SYMBOL_RE = re.compile(r"^(?P<bank>[0-9A-Fa-f]{2,}):(?P<addr>[0-9A-Fa-f]{4})\s+(?P<label>\S+)$")


@dataclass(frozen=True)
class Symbol:
    bank: int
    addr: int
    label: str

    @property
    def key(self) -> tuple[int, int]:
        return (self.bank, self.addr)

    @property
    def is_executable(self) -> bool:
        if self.bank == 0:
            return 0x0000 <= self.addr < 0x8000
        return 0x4000 <= self.addr < 0x8000


@dataclass(frozen=True)
class SymbolTable:
    path: Path
    symbols: tuple[Symbol, ...]

    @classmethod
    def load(cls, path: str | Path) -> "SymbolTable":
        sym_path = Path(path)
        symbols = []
        for lineno, raw_line in enumerate(sym_path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith(";"):
                continue
            match = SYMBOL_RE.match(line)
            if not match:
                raise ValueError(f"Invalid RGBDS .sym line {lineno}: {raw_line}")
            symbols.append(
                Symbol(
                    bank=int(match.group("bank"), 16),
                    addr=int(match.group("addr"), 16),
                    label=match.group("label"),
                )
            )
        return cls(path=sym_path, symbols=tuple(symbols))

    def lookup(self, label: str) -> Symbol:
        for symbol in self.symbols:
            if symbol.label == label:
                return symbol
        raise KeyError(f"Unknown symbol: {label}")

    def labels_at(self, bank: int, addr: int) -> tuple[str, ...]:
        return tuple(symbol.label for symbol in self.symbols if symbol.bank == bank and symbol.addr == addr)

    def executable_symbols(self) -> tuple[Symbol, ...]:
        return tuple(symbol for symbol in self.symbols if symbol.is_executable)

    def sha256(self) -> str:
        data = self.path.read_bytes()
        return hashlib.sha256(data).hexdigest()
