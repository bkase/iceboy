from __future__ import annotations

import unittest
from pathlib import Path

from tools.ppu_backend_diff import DEFAULT_MANIFEST, compare_manifest


ROOT = Path(__file__).resolve().parents[3]


class BackendDiffSmokeTest(unittest.TestCase):
    def test_checked_in_backend_diff_manifest_matches_for_all_scenarios(self) -> None:
        outcomes = compare_manifest(DEFAULT_MANIFEST)
        self.assertTrue(outcomes)
        self.assertTrue(all(item.matched for item in outcomes), outcomes)


if __name__ == "__main__":
    unittest.main()
