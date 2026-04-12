from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SETUP_PC = 0x0157
BODY_PC = 0x015D
DONE_PC = 0x0162
PASS_PC = 0x01B1
SP_RESET = 0xFFFE
IME_DISABLED = 0
HALT_RUNNING = 0


@dataclass(frozen=True)
class ExpectedCheckpoint:
    seq: int
    label: str
    pc: int
    a: int
    f: int
    b: int
    c: int
    d: int
    e: int
    h: int
    l: int
    sp: int
    ime_state: int = IME_DISABLED
    halt_state: int = HALT_RUNNING

    def to_tsv(self) -> str:
        return (
            f"{self.seq}\t{self.label}\t0x{self.pc:04X}\t0x{self.a:02X}\t0x{self.f:02X}\t0x{self.b:02X}\t0x{self.c:02X}"
            f"\t0x{self.d:02X}\t0x{self.e:02X}\t0x{self.h:02X}\t0x{self.l:02X}\t0x{self.sp:04X}"
            f"\t{self.ime_state}\t{self.halt_state}"
        )


def _flags(*, z: bool, n: bool, h: bool, c: bool) -> int:
    return ((0x80 if z else 0x00) | (0x40 if n else 0x00) | (0x20 if h else 0x00) | (0x10 if c else 0x00))


def _add_u8(left: int, right: int) -> tuple[int, int]:
    total = left + right
    value = total & 0xFF
    return value, _flags(z=value == 0, n=False, h=((left & 0x0F) + (right & 0x0F)) > 0x0F, c=total > 0xFF)


def _dec_u8(value: int, flags_before: int) -> tuple[int, int]:
    result = (value - 1) & 0xFF
    carry = (flags_before & 0x10) != 0
    return result, _flags(z=result == 0, n=True, h=(value & 0x0F) == 0x00, c=carry)


def expected_checkpoints() -> tuple[ExpectedCheckpoint, ...]:
    checkpoints = [
        ExpectedCheckpoint(
            seq=0,
            label="__checkpoint_loop_setup",
            pc=SETUP_PC,
            a=0x50,
            f=0x80,
            b=0x00,
            c=0x13,
            d=0x00,
            e=0xD8,
            h=0x01,
            l=0x4D,
            sp=SP_RESET,
        )
    ]

    a = 0x00
    f = 0x80
    b = 0x08
    c = 0x13
    d = 0x00
    e = 0xD8
    h = 0xC0
    l = 0x08

    for _ in range(8):
        checkpoints.append(
            ExpectedCheckpoint(
                seq=len(checkpoints),
                label="__checkpoint_loop_body|__checkpoint_loop_body.loop",
                pc=BODY_PC,
                a=a,
                f=f,
                b=b,
                c=c,
                d=d,
                e=e,
                h=h,
                l=l,
                sp=SP_RESET,
            )
        )
        a, f = _add_u8(a, b)
        b, f = _dec_u8(b, f)

    checkpoints.append(
        ExpectedCheckpoint(
            seq=len(checkpoints),
            label="__checkpoint_loop_done",
            pc=DONE_PC,
            a=a,
            f=f,
            b=b,
            c=c,
            d=d,
            e=e,
            h=h,
            l=l,
            sp=SP_RESET,
        )
    )
    checkpoints.append(
        ExpectedCheckpoint(
            seq=len(checkpoints),
            label="__pass",
            pc=PASS_PC,
            a=0x01,
            f=0xC0,
            b=0x00,
            c=0x13,
            d=0x00,
            e=0xD8,
            h=0xC0,
            l=0x08,
            sp=SP_RESET,
        )
    )
    return tuple(checkpoints)


def write_expected_trace(out_path: str | Path) -> Path:
    destination = Path(out_path)
    header = "# seq\tlabel\tpc\ta\tf\tb\tc\td\te\th\tl\tsp\time_state\thalt_state"
    text = "\n".join([header] + [checkpoint.to_tsv() for checkpoint in expected_checkpoints()]) + "\n"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    return destination
