from __future__ import annotations

import argparse
import re
from pathlib import Path


REPEATED_CONCAT_ASSIGN_RE = re.compile(r"^(\s*assign\s+\S+\s*=\s*\{)(.*)(\};\s*)$")
LONG_LINE_THRESHOLD = 40000


def rewrite_repeated_concat_line(line: str) -> str:
    if len(line) <= LONG_LINE_THRESHOLD:
        return line
    match = REPEATED_CONCAT_ASSIGN_RE.match(line)
    if match is None:
        return line
    items = [item.strip() for item in match.group(2).split(",")]
    if not items or any(not item for item in items):
        return line
    repeated_item = items[0]
    if any(item != repeated_item for item in items[1:]):
        return line
    return f"{match.group(1)}{len(items)}{{{repeated_item}}}{match.group(3)}"


def sanitize_verilator_source(text: str) -> tuple[str, int]:
    rewritten = 0
    output_lines: list[str] = []
    for line in text.splitlines():
        updated = rewrite_repeated_concat_line(line)
        if updated != line:
            rewritten += 1
        output_lines.append(updated)
    return ("\n".join(output_lines) + "\n", rewritten)


def write_sanitized_verilog(src: Path, dst: Path) -> int:
    sanitized, rewritten = sanitize_verilator_source(src.read_text(encoding="utf-8"))
    dst.write_text(sanitized, encoding="utf-8")
    return rewritten


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rewrite Verilator-hostile repeated-concat assignments.")
    parser.add_argument("src", type=Path)
    parser.add_argument("dst", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    rewritten = write_sanitized_verilog(args.src, args.dst)
    print(f"rewrote {rewritten} long repeated-concat line(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
