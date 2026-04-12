from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from bench.ref.alu_loop import ExpectedCheckpoint, write_expected_trace


def export_expected_trace(out_path: Path, *, rom_id: str = "ALU_LOOP") -> int:
    if rom_id != "ALU_LOOP":
        raise ValueError(f"unsupported rom id: {rom_id}")
    destination = write_expected_trace(out_path)
    print(f"wrote {len(destination.read_text(encoding='utf-8').splitlines()) - 1} checkpoints to {destination}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export the ALU_LOOP PyBoy checkpoint oracle for the native board-top runner.")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--rom-id", default="ALU_LOOP")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return export_expected_trace(args.output, rom_id=args.rom_id)


if __name__ == "__main__":
    raise SystemExit(main())
