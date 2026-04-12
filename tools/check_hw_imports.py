from __future__ import annotations

import argparse
import re
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path


USE_RE = re.compile(r"^\s*use\s+(.+?)\s*;\s*$")
TOKEN_RE = re.compile(r"::|[{},]|[A-Za-z_][A-Za-z0-9_]*")
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Edge:
    parent: Path
    import_path: str
    line: int


@dataclass(frozen=True)
class Offense:
    file_path: Path
    line: int
    import_path: str
    reachability: str


def display_path(path: Path, display_root: Path) -> str:
    try:
        return str(path.relative_to(display_root))
    except ValueError:
        return str(path)


def iter_use_statements(source: str) -> list[tuple[int, str]]:
    statements: list[tuple[int, str]] = []
    current: list[str] = []
    start_line: int | None = None

    for lineno, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if start_line is None:
            if not stripped.startswith("use "):
                continue
            start_line = lineno
        current.append(stripped)
        if ";" in stripped:
            statement = " ".join(part for part in current if part)
            statements.append((start_line, statement))
            current = []
            start_line = None

    return statements


def parse_import_paths(spec: str) -> list[tuple[str, ...]]:
    tokens = TOKEN_RE.findall(spec)
    if not tokens:
        return []

    position = 0

    def parse_group(prefix: list[str]) -> list[tuple[str, ...]]:
        nonlocal position
        paths: list[tuple[str, ...]] = []

        while position < len(tokens) and tokens[position] != "}":
            if tokens[position] == ",":
                position += 1
                continue

            segments = list(prefix)
            while position < len(tokens):
                token = tokens[position]
                if not IDENT_RE.fullmatch(token):
                    raise ValueError(f"unexpected token {token!r} in use spec {spec!r}")
                segments.append(token)
                position += 1

                if position < len(tokens) and tokens[position] == "::":
                    position += 1
                    if position < len(tokens) and tokens[position] == "{":
                        position += 1
                        paths.extend(parse_group(segments))
                        if position >= len(tokens) or tokens[position] != "}":
                            raise ValueError(f"unterminated group in use spec {spec!r}")
                        position += 1
                        break
                    continue

                paths.append(tuple(segments))
                break

            if position < len(tokens) and tokens[position] == ",":
                position += 1

        return paths

    parsed = parse_group([])
    if position != len(tokens):
        raise ValueError(f"failed to consume use spec {spec!r}")
    return parsed


def resolve_import_file(import_path: tuple[str, ...], src_root: Path) -> Path | None:
    if len(import_path) < 2 or import_path[0] != "lib":
        return None

    relative_segments = list(import_path[1:])
    for end in range(len(relative_segments), 0, -1):
        stem = src_root.joinpath(*relative_segments[:end])
        direct = stem.with_suffix(".spade")
        if direct.is_file():
            return direct.resolve()
        main_file = stem / "main.spade"
        if main_file.is_file():
            return main_file.resolve()
    return None


def format_reachability(
    target: Path,
    board_top: Path,
    predecessors: dict[Path, Edge | None],
    display_root: Path,
) -> str:
    if target == board_top:
        return display_path(board_top, display_root)

    steps: list[tuple[Path, str, Path]] = []
    current = target
    while current != board_top:
        edge = predecessors.get(current)
        if edge is None:
            break
        steps.append((edge.parent, edge.import_path, current))
        current = edge.parent
    steps.reverse()

    parts = [display_path(board_top, display_root)]
    for _, import_path, child in steps:
        parts.append(f"--{import_path}-->")
        parts.append(display_path(child, display_root))
    return " ".join(parts)


def collect_offenses(board_top: Path, src_root: Path) -> list[Offense]:
    board_top = board_top.resolve()
    src_root = src_root.resolve()
    display_root = src_root.parent

    queue: deque[Path] = deque([board_top])
    predecessors: dict[Path, Edge | None] = {board_top: None}
    visited: set[Path] = {board_top}
    offenses: list[Offense] = []

    while queue:
        current = queue.popleft()
        source = current.read_text(encoding="utf-8")
        for line, statement in iter_use_statements(source):
            match = USE_RE.match(statement)
            if match is None:
                continue
            spec = match.group(1).strip()
            if not spec.startswith("lib::"):
                continue
            if spec.startswith("lib::sim::"):
                offenses.append(
                    Offense(
                        file_path=current,
                        line=line,
                        import_path=spec,
                        reachability=format_reachability(current, board_top, predecessors, display_root),
                    )
                )
                continue

            for import_path in parse_import_paths(spec):
                resolved = resolve_import_file(import_path, src_root)
                if resolved is None or resolved == current or resolved in visited:
                    continue
                visited.add(resolved)
                predecessors[resolved] = Edge(parent=current, import_path="::".join(import_path), line=line)
                queue.append(resolved)

    return offenses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reject hardware tops that transitively import lib::sim::*.")
    parser.add_argument("--board-top", required=True, help="Path to the hardware board-top .spade file")
    parser.add_argument(
        "--src-root",
        default=str(Path(__file__).resolve().parents[1] / "src"),
        help="Path to the repository src/ root",
    )
    args = parser.parse_args(argv)

    board_top = Path(args.board_top)
    src_root = Path(args.src_root)
    display_root = src_root.resolve().parent

    if not board_top.is_file():
        print(f"error: missing board top at {board_top}", file=sys.stderr)
        return 1
    if not src_root.is_dir():
        print(f"error: missing src root at {src_root}", file=sys.stderr)
        return 1

    offenses = collect_offenses(board_top, src_root)
    if offenses:
        print("error: reachable lib::sim imports are forbidden in hardware tops", file=sys.stderr)
        for offense in offenses:
            print(
                f"  offending source: {display_path(offense.file_path, display_root)}:{offense.line}",
                file=sys.stderr,
            )
            print(f"  import path: {offense.import_path}", file=sys.stderr)
            print(f"  reachability path: {offense.reachability}", file=sys.stderr)
        return 1

    print(f"Hardware import graph is sim-free: {display_path(board_top.resolve(), display_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
