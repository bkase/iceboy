from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Flags:
    z: bool
    n: bool
    h: bool
    c: bool


@dataclass(frozen=True)
class AluResult:
    value: int
    flags: Flags


def _mask8(value: int) -> int:
    return value & 0xFF


def _mask16(value: int) -> int:
    return value & 0xFFFF


def _carry_bit(carry_in: bool | int) -> int:
    return 1 if carry_in else 0


def sign_extend_e8(value: int) -> int:
    value = _mask8(value)
    return value - 0x100 if value & 0x80 else value


def add8(a: int, b: int) -> AluResult:
    a = _mask8(a)
    b = _mask8(b)
    raw = a + b
    result = _mask8(raw)
    return AluResult(
        value=result,
        flags=Flags(
            z=result == 0,
            n=False,
            h=((a & 0x0F) + (b & 0x0F)) > 0x0F,
            c=raw > 0xFF,
        ),
    )


def adc8(a: int, b: int, carry_in: bool | int) -> AluResult:
    a = _mask8(a)
    b = _mask8(b)
    carry = _carry_bit(carry_in)
    raw = a + b + carry
    result = _mask8(raw)
    return AluResult(
        value=result,
        flags=Flags(
            z=result == 0,
            n=False,
            h=((a & 0x0F) + (b & 0x0F) + carry) > 0x0F,
            c=raw > 0xFF,
        ),
    )


def sub8(a: int, b: int) -> AluResult:
    a = _mask8(a)
    b = _mask8(b)
    result = _mask8(a - b)
    return AluResult(
        value=result,
        flags=Flags(
            z=result == 0,
            n=True,
            h=(a & 0x0F) < (b & 0x0F),
            c=a < b,
        ),
    )


def sbc8(a: int, b: int, carry_in: bool | int) -> AluResult:
    a = _mask8(a)
    b = _mask8(b)
    carry = _carry_bit(carry_in)
    subtrahend = b + carry
    result = _mask8(a - subtrahend)
    return AluResult(
        value=result,
        flags=Flags(
            z=result == 0,
            n=True,
            h=(a & 0x0F) < ((b & 0x0F) + carry),
            c=a < subtrahend,
        ),
    )


def cp8(a: int, b: int) -> AluResult:
    compared = sub8(a, b)
    return AluResult(value=_mask8(a), flags=compared.flags)


def and8(a: int, b: int) -> AluResult:
    result = _mask8(a) & _mask8(b)
    return AluResult(value=result, flags=Flags(z=result == 0, n=False, h=True, c=False))


def or8(a: int, b: int) -> AluResult:
    result = _mask8(a) | _mask8(b)
    return AluResult(value=result, flags=Flags(z=result == 0, n=False, h=False, c=False))


def xor8(a: int, b: int) -> AluResult:
    result = _mask8(a) ^ _mask8(b)
    return AluResult(value=result, flags=Flags(z=result == 0, n=False, h=False, c=False))


def inc8(value: int, carry_in: bool) -> AluResult:
    value = _mask8(value)
    result = _mask8(value + 1)
    return AluResult(
        value=result,
        flags=Flags(
            z=result == 0,
            n=False,
            h=((value & 0x0F) + 1) > 0x0F,
            c=bool(carry_in),
        ),
    )


def dec8(value: int, carry_in: bool) -> AluResult:
    value = _mask8(value)
    result = _mask8(value - 1)
    return AluResult(
        value=result,
        flags=Flags(
            z=result == 0,
            n=True,
            h=(value & 0x0F) == 0,
            c=bool(carry_in),
        ),
    )


def daa(value: int, flags: Flags) -> AluResult:
    value = _mask8(value)
    adjustment = 0
    carry_out = flags.c

    if flags.n:
        if flags.h:
            adjustment += 0x06
        if flags.c:
            adjustment += 0x60
        result = _mask8(value - adjustment)
    else:
        if flags.h or (value & 0x0F) > 0x09:
            adjustment += 0x06
        if flags.c or value > 0x99:
            adjustment += 0x60
            carry_out = True
        else:
            carry_out = False
        result = _mask8(value + adjustment)

    return AluResult(
        value=result,
        flags=Flags(
            z=result == 0,
            n=flags.n,
            h=False,
            c=carry_out,
        ),
    )


def add16_hl(hl: int, operand: int, z_in: bool) -> AluResult:
    hl = _mask16(hl)
    operand = _mask16(operand)
    raw = hl + operand
    result = _mask16(raw)
    return AluResult(
        value=result,
        flags=Flags(
            z=bool(z_in),
            n=False,
            h=((hl & 0x0FFF) + (operand & 0x0FFF)) > 0x0FFF,
            c=raw > 0xFFFF,
        ),
    )


def add_sp_e8(sp: int, offset_e8: int) -> AluResult:
    sp = _mask16(sp)
    offset_u8 = _mask8(offset_e8)
    result = _mask16(sp + sign_extend_e8(offset_e8))
    return AluResult(
        value=result,
        flags=Flags(
            z=False,
            n=False,
            h=((sp & 0x0F) + (offset_u8 & 0x0F)) > 0x0F,
            c=((sp & 0xFF) + offset_u8) > 0xFF,
        ),
    )


def ld_hl_sp_plus_e8(sp: int, offset_e8: int) -> AluResult:
    return add_sp_e8(sp, offset_e8)


def rlc8(value: int, zero_affects: bool = True) -> AluResult:
    value = _mask8(value)
    carry_out = bool(value & 0x80)
    result = _mask8((value << 1) | (value >> 7))
    return AluResult(value=result, flags=Flags(z=zero_affects and result == 0, n=False, h=False, c=carry_out))


def rrc8(value: int, zero_affects: bool = True) -> AluResult:
    value = _mask8(value)
    carry_out = bool(value & 0x01)
    result = _mask8((value >> 1) | ((value & 0x01) << 7))
    return AluResult(value=result, flags=Flags(z=zero_affects and result == 0, n=False, h=False, c=carry_out))


def rl8(value: int, carry_in: bool, zero_affects: bool = True) -> AluResult:
    value = _mask8(value)
    carry_out = bool(value & 0x80)
    result = _mask8((value << 1) | _carry_bit(carry_in))
    return AluResult(value=result, flags=Flags(z=zero_affects and result == 0, n=False, h=False, c=carry_out))


def rr8(value: int, carry_in: bool, zero_affects: bool = True) -> AluResult:
    value = _mask8(value)
    carry_out = bool(value & 0x01)
    result = _mask8((value >> 1) | (_carry_bit(carry_in) << 7))
    return AluResult(value=result, flags=Flags(z=zero_affects and result == 0, n=False, h=False, c=carry_out))


def sla8(value: int) -> AluResult:
    value = _mask8(value)
    carry_out = bool(value & 0x80)
    result = _mask8(value << 1)
    return AluResult(value=result, flags=Flags(z=result == 0, n=False, h=False, c=carry_out))


def sra8(value: int) -> AluResult:
    value = _mask8(value)
    carry_out = bool(value & 0x01)
    result = _mask8((value >> 1) | (value & 0x80))
    return AluResult(value=result, flags=Flags(z=result == 0, n=False, h=False, c=carry_out))


def srl8(value: int) -> AluResult:
    value = _mask8(value)
    carry_out = bool(value & 0x01)
    result = value >> 1
    return AluResult(value=result, flags=Flags(z=result == 0, n=False, h=False, c=carry_out))


def swap8(value: int) -> AluResult:
    value = _mask8(value)
    result = _mask8((value >> 4) | ((value & 0x0F) << 4))
    return AluResult(value=result, flags=Flags(z=result == 0, n=False, h=False, c=False))


def bit_test(value: int, bit_index: int, carry_in: bool) -> AluResult:
    value = _mask8(value)
    bit = (value >> bit_index) & 0x01
    return AluResult(value=value, flags=Flags(z=bit == 0, n=False, h=True, c=bool(carry_in)))


def scf(z_in: bool) -> Flags:
    return Flags(z=bool(z_in), n=False, h=False, c=True)


def ccf(z_in: bool, carry_in: bool) -> Flags:
    return Flags(z=bool(z_in), n=False, h=False, c=not bool(carry_in))


def cpl(value: int, z_in: bool, carry_in: bool) -> AluResult:
    result = _mask8(~value)
    return AluResult(value=result, flags=Flags(z=bool(z_in), n=True, h=True, c=bool(carry_in)))


FLAG_POLICY_FUNCTIONS = {
    "ADD8": add8,
    "ADC8": adc8,
    "SUB8": sub8,
    "SBC8": sbc8,
    "CP8": cp8,
    "AND8": and8,
    "OR8": or8,
    "XOR8": xor8,
    "INC8": inc8,
    "DEC8": dec8,
    "DAA": daa,
    "ADD16_HL": add16_hl,
    "ADD_SP_E8": add_sp_e8,
    "LD_HL_SP_PLUS_E8": ld_hl_sp_plus_e8,
    "RLC8": rlc8,
    "RRC8": rrc8,
    "RL8": rl8,
    "RR8": rr8,
    "SLA8": sla8,
    "SRA8": sra8,
    "SRL8": srl8,
    "SWAP8": swap8,
    "BIT": bit_test,
    "SCF": scf,
    "CCF": ccf,
    "CPL": cpl,
}


__all__ = [
    "AluResult",
    "FLAG_POLICY_FUNCTIONS",
    "Flags",
    "add16_hl",
    "add8",
    "add_sp_e8",
    "adc8",
    "and8",
    "bit_test",
    "ccf",
    "cp8",
    "cpl",
    "daa",
    "dec8",
    "inc8",
    "ld_hl_sp_plus_e8",
    "or8",
    "rl8",
    "rlc8",
    "rr8",
    "rrc8",
    "scf",
    "sign_extend_e8",
    "sla8",
    "sra8",
    "srl8",
    "sub8",
    "sbc8",
    "swap8",
    "xor8",
]
