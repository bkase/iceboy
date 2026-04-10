from __future__ import annotations

import argparse
from pathlib import Path

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.pyboy.symbols import SymbolTable


def resolve_checkpoint_pc(sym_path: Path, label: str = "__checkpoint_scene_ready") -> int:
    symbol = SymbolTable.load(sym_path).lookup(label)
    return int(symbol.addr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sym", required=True, type=Path)
    parser.add_argument("--label", default="__checkpoint_scene_ready")
    args = parser.parse_args()
    print(f"0x{resolve_checkpoint_pc(args.sym, args.label):04x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
