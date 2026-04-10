from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.pyboy.symbols import SymbolTable


def _load_trace(trace_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw_line in trace_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def _labels_by_addr(sym_path: Path) -> dict[int, tuple[str, ...]]:
    table = SymbolTable.load(sym_path)
    labels: dict[int, list[str]] = {}
    for symbol in table.executable_symbols():
        labels.setdefault(symbol.addr, []).append(symbol.label)
    return {addr: tuple(names) for addr, names in labels.items()}


def _hex_or_none(value: Any, width: int = 4) -> str | None:
    if value is None:
        return None
    return f"0x{int(value):0{width}x}"


def _record_summary(record: dict[str, Any], labels: Iterable[str] = ()) -> dict[str, Any]:
    return {
        "cycle": record.get("cycle"),
        "pc": _hex_or_none(record.get("pc")),
        "labels": list(labels),
        "ppu_ly": record.get("ppu_ly"),
        "ppu_mode": record.get("ppu_mode"),
        "scanout_x": record.get("scanout_x"),
        "scanout_y": record.get("scanout_y"),
        "scanout_source": record.get("scanout_source"),
        "scanout_shade": record.get("scanout_shade"),
        "line_obj_count": record.get("line_obj_count"),
        "slot0_x": record.get("slot0_x"),
        "slot0_oam_index": record.get("slot0_oam_index"),
        "fetcher_source": record.get("fetcher_source"),
        "line_obj_fetch_index": record.get("line_obj_fetch_index"),
        "obj_fifo_count": record.get("obj_fifo_count"),
        "bg_fifo_count": record.get("bg_fifo_count"),
        "bus_req_addr": _hex_or_none(record.get("bus_req_addr")),
        "bus_req_data": _hex_or_none(record.get("bus_req_data"), width=2),
        "preview_bus_req_addr": _hex_or_none(record.get("preview_bus_req_addr")),
        "preview_bus_req_data": _hex_or_none(record.get("preview_bus_req_data"), width=2),
    }


def _first_record(
    records: Iterable[dict[str, Any]],
    predicate,
    labels_by_addr: dict[int, tuple[str, ...]],
) -> dict[str, Any] | None:
    for record in records:
        if predicate(record):
            return _record_summary(record, labels_by_addr.get(int(record.get("pc", -1)), ()))
    return None


def _matching_records(
    records: Iterable[dict[str, Any]],
    predicate,
    labels_by_addr: dict[int, tuple[str, ...]],
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for record in records:
        if predicate(record):
            matches.append(_record_summary(record, labels_by_addr.get(int(record.get("pc", -1)), ())))
    return matches


def summarize_rom_trace(
    trace_path: Path,
    sym_path: Path,
    *,
    line: int | None = None,
    labels: Iterable[str] = (),
) -> dict[str, Any]:
    records = _load_trace(trace_path)
    table = SymbolTable.load(sym_path)
    labels_by_addr = _labels_by_addr(sym_path)
    line_filter = (lambda record: record.get("ppu_ly") == line) if line is not None else (lambda record: True)

    requested_labels: dict[str, dict[str, Any] | None] = {}
    label_stats: dict[str, dict[str, Any]] = {}
    for label in labels:
        addr = table.lookup(label).addr
        matches = _matching_records(
            records,
            lambda record, addr=addr: line_filter(record) and int(record.get("pc", -1)) == addr,
            labels_by_addr,
        )
        requested_labels[label] = matches[0] if matches else None
        label_stats[label] = {
            "count": len(matches),
            "first": matches[0] if matches else None,
            "last": matches[-1] if matches else None,
        }

    return {
        "trace_path": str(trace_path),
        "sym_path": str(sym_path),
        "line": line,
        "labels": requested_labels,
        "label_stats": label_stats,
        "milestones": {
            "first_selected_object": _first_record(
                records,
                lambda record: line_filter(record) and int(record.get("line_obj_count", 0)) > 0,
                labels_by_addr,
            ),
            "first_object_scanout": _first_record(
                records,
                lambda record: line_filter(record)
                and record.get("scanout_y") == line
                and int(record.get("scanout_source", -1)) == 2,
                labels_by_addr,
            ),
            "first_lcdc_write": _first_record(
                records,
                lambda record: line_filter(record) and int(record.get("bus_req_addr", -1)) == 0xFF40,
                labels_by_addr,
            ),
            "first_lcdc_preview_write": _first_record(
                records,
                lambda record: line_filter(record) and int(record.get("preview_bus_req_addr", -1)) == 0xFF40,
                labels_by_addr,
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--sym", required=True, type=Path)
    parser.add_argument("--line", type=int, default=None)
    parser.add_argument("--label", action="append", default=[])
    args = parser.parse_args()
    summary = summarize_rom_trace(args.trace, args.sym, line=args.line, labels=args.label)
    json.dump(summary, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
