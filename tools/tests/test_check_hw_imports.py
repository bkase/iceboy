from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
CHECK_HW_IMPORTS = TOOLS / "check_hw_imports.py"


class CheckHwImportsTest(unittest.TestCase):
    def run_tool(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CHECK_HW_IMPORTS), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def test_current_icebreaker_top_is_sim_free(self) -> None:
        completed = self.run_tool("--board-top", "src/board/icebreaker_top.spade")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Hardware import graph is sim-free", completed.stdout)
        self.assertIn("src/board/icebreaker_top.spade", completed.stdout)

    def test_real_ppu_core_import_is_rejected_with_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            board_top = Path(tempdir) / "synthetic_top.spade"
            board_top.write_text(
                "use lib::ppu::rtl::core::ppu_core;\n\nentity synthetic_top() {}\n",
                encoding="utf-8",
            )

            completed = self.run_tool(
                "--board-top",
                str(board_top),
                "--src-root",
                str(ROOT / "src"),
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("reachable lib::sim imports are forbidden", completed.stderr)
        self.assertIn("src/ppu/rtl/core.spade:22", completed.stderr)
        self.assertIn("lib::sim::ppu_support", completed.stderr)
        self.assertIn("synthetic_top.spade", completed.stderr)
        self.assertIn("src/ppu/rtl/core.spade", completed.stderr)

    def test_transitive_reachability_path_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            src_root = root / "src"
            (src_root / "board").mkdir(parents=True)
            (src_root / "ppu" / "rtl").mkdir(parents=True)
            (src_root / "ppu").mkdir(exist_ok=True)

            (src_root / "board" / "icebreaker_top.spade").write_text(
                "use lib::ppu::wrapper::ppu_hw;\n",
                encoding="utf-8",
            )
            (src_root / "ppu" / "wrapper.spade").write_text(
                "use lib::ppu::rtl::core::ppu_core;\n",
                encoding="utf-8",
            )
            (src_root / "ppu" / "rtl" / "core.spade").write_text(
                "use lib::sim::ppu_support::ppu_debug_trace;\n",
                encoding="utf-8",
            )

            completed = self.run_tool(
                "--board-top",
                str(src_root / "board" / "icebreaker_top.spade"),
                "--src-root",
                str(src_root),
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("src/ppu/rtl/core.spade:1", completed.stderr)
        self.assertIn("lib::sim::ppu_support::ppu_debug_trace", completed.stderr)
        self.assertIn("src/board/icebreaker_top.spade", completed.stderr)
        self.assertIn("src/ppu/wrapper.spade", completed.stderr)
        self.assertIn("src/ppu/rtl/core.spade", completed.stderr)
