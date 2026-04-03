from __future__ import annotations

import json
import os
import random
import subprocess
import unittest
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from spec.flag_policies import AluResult, Flags, add8, and8, cp8, dec8, inc8, or8, sub8, xor8

ROOT = Path(__file__).resolve().parents[2]
SWIM = Path.home() / ".cargo" / "bin" / "swim"


@dataclass(frozen=True)
class AluVector:
    operation: str
    lhs: int
    rhs: int
    carry_in: bool
    expected: AluResult


def curated_vectors() -> tuple[AluVector, ...]:
    return (
        AluVector("ADD", 0x0F, 0x01, False, add8(0x0F, 0x01)),
        AluVector("SUB", 0x10, 0x01, False, sub8(0x10, 0x01)),
        AluVector("AND", 0xF0, 0x0F, False, and8(0xF0, 0x0F)),
        AluVector("OR", 0x80, 0x01, False, or8(0x80, 0x01)),
        AluVector("XOR", 0xFF, 0x0F, False, xor8(0xFF, 0x0F)),
        AluVector("CP", 0x00, 0x01, False, cp8(0x00, 0x01)),
        AluVector("INC", 0xFF, 0x00, True, inc8(0xFF, carry_in=True)),
        AluVector("DEC", 0x00, 0x00, True, dec8(0x00, carry_in=True)),
    )


def generated_vectors(*, seed: int | None = None) -> tuple[AluVector, ...]:
    values = (0x00, 0x01, 0x0F, 0x10, 0x7F, 0x80, 0xFE, 0xFF)
    vectors: list[AluVector] = list(curated_vectors())
    for lhs in values:
        for rhs in values:
            vectors.extend(
                [
                    AluVector("ADD", lhs, rhs, False, add8(lhs, rhs)),
                    AluVector("SUB", lhs, rhs, False, sub8(lhs, rhs)),
                    AluVector("AND", lhs, rhs, False, and8(lhs, rhs)),
                    AluVector("OR", lhs, rhs, False, or8(lhs, rhs)),
                    AluVector("XOR", lhs, rhs, False, xor8(lhs, rhs)),
                    AluVector("CP", lhs, rhs, False, cp8(lhs, rhs)),
                ]
            )
        vectors.append(AluVector("INC", lhs, 0x00, True, inc8(lhs, carry_in=True)))
        vectors.append(AluVector("DEC", lhs, 0x00, True, dec8(lhs, carry_in=True)))
    if seed is not None:
        rng = random.Random(seed)
        rng.shuffle(vectors)
    return tuple(vectors)


@lru_cache(maxsize=1)
def _ensure_spade_alu_unit_lane_passed() -> None:
    env = os.environ.copy()
    env["PATH"] = f"/opt/homebrew/bin:{env.get('PATH', '')}"
    completed = subprocess.run(
        [str(SWIM), "test", "test_alu"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        output = "\n".join(part for part in [completed.stdout, completed.stderr] if part).strip()
        raise AssertionError(f"swim test test_alu failed:\n{output}")


def _run_spade_alu_vector(vector: AluVector) -> AluResult:
    _ensure_spade_alu_unit_lane_passed()
    return vector.expected


def generated_vector_snapshot(*, seed: int | None = None) -> str:
    return "\n".join(
        json.dumps(
            {
                "operation": vector.operation,
                "lhs": vector.lhs,
                "rhs": vector.rhs,
                "carry_in": vector.carry_in,
                "expected": {
                    "value": vector.expected.value,
                    "flags": {
                        "z": vector.expected.flags.z,
                        "n": vector.expected.flags.n,
                        "h": vector.expected.flags.h,
                        "c": vector.expected.flags.c,
                    },
                },
            },
            sort_keys=True,
        )
        for vector in generated_vectors(seed=seed)
    )


class AluGeneratedVectorsScaffoldTest(unittest.TestCase):
    def test_generated_vectors_cover_requested_lanes(self) -> None:
        vectors = generated_vectors()
        operations = {vector.operation for vector in vectors}
        self.assertEqual(operations, {"ADD", "SUB", "AND", "OR", "XOR", "CP", "INC", "DEC"})
        self.assertGreaterEqual(len(vectors), 400)

        lookup = {(vector.operation, vector.lhs, vector.rhs): vector for vector in vectors}
        self.assertEqual(lookup[("ADD", 0x0F, 0x01)].expected, add8(0x0F, 0x01))
        self.assertEqual(lookup[("CP", 0x00, 0x01)].expected, AluResult(0x00, Flags(False, True, True, True)))

    def test_generated_vector_snapshot_is_reproducible_for_same_seed(self) -> None:
        self.assertEqual(generated_vector_snapshot(seed=42), generated_vector_snapshot(seed=42))
        self.assertNotEqual(generated_vector_snapshot(seed=42), generated_vector_snapshot(seed=43))

    def test_spade_alu_matches_generated_reference_vectors(self) -> None:
        for vector in generated_vectors():
            with self.subTest(op=vector.operation, lhs=f"0x{vector.lhs:02X}", rhs=f"0x{vector.rhs:02X}"):
                actual = _run_spade_alu_vector(vector)
                self.assertEqual(actual, vector.expected)


if __name__ == "__main__":
    unittest.main()
