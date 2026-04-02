from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from bench.pyboy.hook_driver import HookDriver
from bench.pyboy.hooks import build_hook_manifest
from bench.pyboy.symbols import SymbolTable
from roms.build_micro_rom import build_alu_loop
from spec.profiles import ModelProfile, ResetProfile


SYMBOL_TEXT = """\
00:0150 __checkpoint_loop
00:0152 __commit_after_ld_b
00:0154 __commit_after_inc_a
00:0155 __pass
00:0156 __fail
"""


class PyBoyHookSupportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.rom_path = Path(cls._tmpdir.name) / "alu_loop.gb"
        cls.sym_path = Path(cls._tmpdir.name) / "alu_loop.sym"
        cls.rom_path.write_bytes(build_alu_loop())
        cls.sym_path.write_text(SYMBOL_TEXT, encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmpdir.cleanup()

    def test_symbol_table_loads_named_addresses(self) -> None:
        table = SymbolTable.load(self.sym_path)
        symbol = table.lookup("__pass")
        self.assertEqual((symbol.bank, symbol.addr), (0, 0x0155))
        self.assertEqual(table.labels_at(0, 0x0150), ("__checkpoint_loop",))
        self.assertEqual(len(table.sha256()), 64)

    def test_hook_manifest_collects_reserved_labels(self) -> None:
        manifest = build_hook_manifest(self.sym_path)
        self.assertEqual(manifest.sym_path, self.sym_path)
        self.assertEqual([target.joined_label for target in manifest.targets], [
            "__checkpoint_loop",
            "__commit_after_ld_b",
            "__commit_after_inc_a",
            "__pass",
            "__fail",
        ])

    def test_hook_driver_compares_live_oracle_commits(self) -> None:
        manifest = build_hook_manifest(self.sym_path)

        with HookDriver.from_manifest(self.rom_path, manifest) as expected_driver:
            expected_driver.reset(ModelProfile.DMG, ResetProfile.SkipBoot)
            expected = expected_driver.collect_commits(4)

        with HookDriver.from_manifest(self.rom_path, manifest) as actual_driver:
            actual_driver.reset(ModelProfile.DMG, ResetProfile.SkipBoot)
            result = actual_driver.compare_commits(expected)
            self.assertTrue(result.matched)
            self.assertEqual(result.commits, expected)

        bad_expected = list(expected)
        bad_expected[1] = replace(bad_expected[1], opcode=0x00)

        with HookDriver.from_manifest(self.rom_path, manifest) as mismatch_driver:
            mismatch_driver.reset(ModelProfile.DMG, ResetProfile.SkipBoot)
            result = mismatch_driver.compare_commits(bad_expected)
            self.assertFalse(result.matched)
            self.assertIsNotNone(result.mismatch)
            self.assertEqual(result.mismatch.commit_index, 1)


if __name__ == "__main__":
    unittest.main()
