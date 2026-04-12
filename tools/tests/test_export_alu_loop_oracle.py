from __future__ import annotations

import unittest

from bench.ref.alu_loop import expected_checkpoints
from tools.export_alu_loop_oracle import ExpectedCheckpoint


class ExportAluLoopOracleTest(unittest.TestCase):
    def test_expected_trace_matches_known_alu_loop_progression(self) -> None:
        checkpoints = expected_checkpoints()
        self.assertEqual(len(checkpoints), 11)
        self.assertEqual(checkpoints[0].label, "__checkpoint_loop_setup")
        self.assertEqual(checkpoints[1].label, "__checkpoint_loop_body|__checkpoint_loop_body.loop")
        self.assertEqual(checkpoints[-2].label, "__checkpoint_loop_done")
        self.assertEqual(checkpoints[-1].label, "__pass")
        self.assertEqual(checkpoints[-1].pc, 0x01B1)
        self.assertEqual(checkpoints[-1].ime_state, 0)
        self.assertEqual(checkpoints[-1].halt_state, 0)

    def test_expected_checkpoint_formats_tsv_with_control_state(self) -> None:
        checkpoint = ExpectedCheckpoint(
            seq=3,
            label="__checkpoint_loop_body|__checkpoint_loop_body.loop",
            pc=0x015D,
            a=0x15,
            f=0x40,
            b=0x05,
            c=0x13,
            d=0x00,
            e=0xD8,
            h=0xC0,
            l=0x08,
            sp=0xFFFE,
            ime_state=0,
            halt_state=0,
        )
        self.assertEqual(
            checkpoint.to_tsv(),
            "3\t__checkpoint_loop_body|__checkpoint_loop_body.loop\t0x015D\t0x15\t0x40\t0x05\t0x13\t0x00\t0xD8\t0xC0\t0x08\t0xFFFE\t0\t0",
        )


if __name__ == "__main__":
    unittest.main()
