from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path


REPEATED_CONCAT_ASSIGN_RE = re.compile(r"^(\s*assign\s+\S+\s*=\s*\{)(.*)(\};\s*)$")
LONG_LINE_THRESHOLD = 40000
VERILOG_SOURCES_RE = re.compile(r"^sources\s*=\s*(\[.*\])\s*$")


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


def parse_swim_verilog_sources(swim_toml: Path) -> list[Path]:
    if not swim_toml.is_file():
        return []

    in_verilog_block = False
    for raw_line in swim_toml.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_verilog_block = line == "[verilog]"
            continue
        if not in_verilog_block:
            continue
        match = VERILOG_SOURCES_RE.match(line)
        if match is None:
            continue
        parsed = ast.literal_eval(match.group(1))
        if not isinstance(parsed, list):
            raise ValueError(f"expected a list for [verilog].sources in {swim_toml}")
        return [swim_toml.parent / Path(item) for item in parsed]
    return []


def build_verilator_source(src: Path, root: Path) -> str:
    combined = src.read_text(encoding="utf-8")
    extra_sources = parse_swim_verilog_sources(root / "swim.toml")
    if not extra_sources:
        return combined

    appended_parts = [combined.rstrip()]
    for extra_source in extra_sources:
        appended_parts.append(f"// --- begin included verilog: {extra_source.as_posix()} ---")
        appended_parts.append(extra_source.read_text(encoding="utf-8").rstrip())
        appended_parts.append(f"// --- end included verilog: {extra_source.as_posix()} ---")
    return "\n\n".join(appended_parts) + "\n"


def write_sanitized_verilog(src: Path, dst: Path, *, root: Path) -> int:
    sanitized, rewritten = sanitize_verilator_source(build_verilator_source(src, root))
    dst.write_text(sanitized, encoding="utf-8")
    return rewritten


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rewrite Verilator-hostile repeated-concat assignments.")
    parser.add_argument("src", type=Path)
    parser.add_argument("dst", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    rewritten = write_sanitized_verilog(args.src, args.dst, root=args.root)
    print(f"rewrote {rewritten} long repeated-concat line(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
