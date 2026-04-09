# top = sim::backend_diff_trace_top::backend_diff_trace_top
from __future__ import annotations

import os
import sys
from pathlib import Path

import cocotb

HERE = Path(__file__).resolve().parent
ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "swim.toml").exists())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.backend_diff_capture_common import capture_dot_commit, reset_dut, write_capture


@cocotb.test()
async def test_capture_backend_diff_trace_top(dut):
    await reset_dut(dut)
    dot_commit = await capture_dot_commit(dut, dots=int(os.environ.get("ICEBOY_BACKEND_DIFF_CAPTURE_DOTS", "8")))
    write_capture(
        scenario=os.environ["ICEBOY_BACKEND_DIFF_SCENARIO"],
        backend=os.environ["ICEBOY_BACKEND_DIFF_BACKEND"],
        dot_commit=dot_commit,
    )
