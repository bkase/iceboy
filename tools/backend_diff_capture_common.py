from __future__ import annotations

import json
import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge, Timer


MODE_NAMES = {
    0: "LcdOff",
    1: "OamScan",
    2: "PixelTransfer",
    3: "HBlank",
    4: "VBlank",
}

IRQ_EDGE_NAMES = {
    0: "None",
    1: "VBlank",
    2: "Stat",
    3: "Both",
}

SCANOUT_KIND_NAMES = {
    0: "Pixel",
    1: "Blank",
    2: "FrameStart",
    3: "LineStart",
}

REGION_NAMES = {
    0: "Vram",
    1: "Oam",
}

CLIENT_NAMES = {
    0: "Cpu",
    1: "BgFetcher",
    2: "ObjFetcher",
    3: "OamScanner",
    4: "Dma",
}


def decode_output(value: int) -> dict[str, int | bool]:
    return {
        "ly_after": value & 0xFF,
        "mode_after": (value >> 8) & 0x7,
        "stat_line_after": bool((value >> 11) & 0x1),
        "irq_edge": (value >> 12) & 0x3,
        "scanout_valid": bool((value >> 14) & 0x1),
        "scanout_kind": (value >> 15) & 0x3,
        "scanout_y": (value >> 17) & 0xFF,
        "mem_req_count": (value >> 25) & 0x7,
        "req_addr": (value >> 28) & 0xFFFF,
        "req_region": (value >> 44) & 0x1,
        "req_client": (value >> 45) & 0x7,
        "req_id": (value >> 48) & 0xF,
        "semantic_valid": bool((value >> 52) & 0x1),
    }


def scanout_payload(snapshot: dict[str, int | bool]) -> dict[str, object] | None:
    if not bool(snapshot["scanout_valid"]):
        return None
    return {
        "kind": SCANOUT_KIND_NAMES[int(snapshot["scanout_kind"])],
        "y": int(snapshot["scanout_y"]),
    }


def mem_req_payload(snapshot: dict[str, int | bool]) -> dict[str, object] | None:
    if int(snapshot["mem_req_count"]) == 0:
        return None
    return {
        "addr": int(snapshot["req_addr"]),
        "region": REGION_NAMES[int(snapshot["req_region"])],
        "client": CLIENT_NAMES[int(snapshot["req_client"])],
        "id": int(snapshot["req_id"]),
    }


def dot_commit_entry(snapshot: dict[str, int | bool]) -> dict[str, object]:
    return {
        "semantic_valid": bool(snapshot["semantic_valid"]),
        "ly_after": int(snapshot["ly_after"]),
        "mode_after": MODE_NAMES[int(snapshot["mode_after"])],
        "stat_line_after": bool(snapshot["stat_line_after"]),
        "irq_edge": IRQ_EDGE_NAMES[int(snapshot["irq_edge"])],
        "scanout": scanout_payload(snapshot),
        "mem_req_count": int(snapshot["mem_req_count"]),
        "mem_req": mem_req_payload(snapshot),
    }


def capture_path() -> Path:
    raw = os.environ.get("ICEBOY_BACKEND_DIFF_CAPTURE_PATH")
    if not raw:
        raise RuntimeError("ICEBOY_BACKEND_DIFF_CAPTURE_PATH is required")
    return Path(raw)


def capture_payload(*, scenario: str, backend: str, dot_commit: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "scenario": scenario,
        "backend": backend,
        "dot_commit": dot_commit,
        "scanline_summary": [],
        "frame_hash": [],
    }


def write_capture(*, scenario: str, backend: str, dot_commit: list[dict[str, object]]) -> None:
    target = capture_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(capture_payload(scenario=scenario, backend=backend, dot_commit=dot_commit), indent=2) + "\n",
        encoding="utf-8",
    )


async def reset_dut(dut) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    dut.dot_ce_i.value = 0
    dut.rst_i.value = 1
    await ClockCycles(dut.clk_i, 3)
    dut.rst_i.value = 0
    await ReadOnly()
    await Timer(1, units="ps")


async def step(dut, *, dot_ce: bool = True) -> dict[str, int | bool]:
    dut.dot_ce_i.value = int(dot_ce)
    await RisingEdge(dut.clk_i)
    await ReadOnly()
    snapshot = decode_output(int(dut.output__.value))
    await Timer(1, units="ps")
    return snapshot


async def capture_dot_commit(dut, *, dots: int) -> list[dict[str, object]]:
    commits: list[dict[str, object]] = []
    for _ in range(dots):
        commits.append(dot_commit_entry(await step(dut)))
    return commits
