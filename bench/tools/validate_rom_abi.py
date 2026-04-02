from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ASM_PATH = ROOT / "bench" / "roms" / "template.asm"
TEMPLATE_SYM_PATH = ROOT / "bench" / "roms" / "template.sym"

REQUIRED_EXECUTABLE_LABELS = ("__pass", "__fail")
OPTIONAL_LABEL_PREFIXES = (
    "__checkpoint_",
    "__commit_",
    "__inject_begin_",
    "__inject_end_",
)
RESERVED_LABEL_PREFIXES = REQUIRED_EXECUTABLE_LABELS + OPTIONAL_LABEL_PREFIXES
SYMBOL_RE = re.compile(r"^(?P<bank>[0-9A-Fa-f]{2,}):(?P<addr>[0-9A-Fa-f]{4})\s+(?P<label>\S+)$")


@dataclass(frozen=True)
class Symbol:
    bank: int
    addr: int
    label: str


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"ROM ABI validation failed: {message}")


def parse_sym(text: str) -> dict[str, Symbol]:
    symbols: dict[str, Symbol] = {}
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith(";"):
            continue
        match = SYMBOL_RE.match(line)
        if not match:
            fail(f"invalid .sym line {lineno}: {raw_line}")
        symbol = Symbol(
            bank=int(match.group("bank"), 16),
            addr=int(match.group("addr"), 16),
            label=match.group("label"),
        )
        symbols[symbol.label] = symbol
    return symbols


def is_executable_symbol(symbol: Symbol) -> bool:
    if symbol.bank == 0:
        return 0x0000 <= symbol.addr < 0x8000
    return 0x4000 <= symbol.addr < 0x8000


def validate_sym_text(text: str) -> list[str]:
    symbols = parse_sym(text)

    for label in REQUIRED_EXECUTABLE_LABELS:
        if label not in symbols:
            fail(f"missing required symbol {label}")

    for label, symbol in symbols.items():
        if not label.startswith(RESERVED_LABEL_PREFIXES):
            continue
        if not is_executable_symbol(symbol):
            fail(f"reserved label {label} must point at executable ROM space, got {symbol.bank:02X}:{symbol.addr:04X}")

    return sorted(label for label in symbols if label.startswith(RESERVED_LABEL_PREFIXES))


def validate_asm_text(text: str) -> None:
    required_snippets = [
        'SECTION "Entry", ROM0[$0150]',
        "di",
        "__pass:",
        "__fail:",
        'SECTION "ABI Signature", WRAM0[$C000]',
        "db $01",
        'ds 16',
    ]
    for snippet in required_snippets:
        if snippet not in text:
            fail(f"assembly source is missing required ABI snippet: {snippet}")


def validate_files(sym_path: Path, asm_path: Path | None = None) -> None:
    reserved_labels = validate_sym_text(sym_path.read_text(encoding="utf-8"))
    if asm_path is not None:
        validate_asm_text(asm_path.read_text(encoding="utf-8"))

    print(
        f"Validated ROM ABI for {sym_path.relative_to(ROOT)}"
        + (f" and {asm_path.relative_to(ROOT)}" if asm_path is not None else "")
        + f" ({len(reserved_labels)} reserved labels)."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the custom ROM checkpoint ABI.")
    parser.add_argument("--sym", type=Path, default=TEMPLATE_SYM_PATH, help="RGBDS-compatible .sym file")
    parser.add_argument("--asm", type=Path, default=TEMPLATE_ASM_PATH, help="Assembly source to validate alongside the .sym")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_files(sym_path=args.sym, asm_path=args.asm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
