from __future__ import annotations

from spec.sm83_opcodes import UNPREFIXED_BY_OPCODE


GENERATED_TABLE_BEGIN = "// BEGIN GENERATED UNPREFIXED TABLE"
GENERATED_TABLE_END = "// END GENERATED UNPREFIXED TABLE"

CLASS_INVALID = 0
CLASS_LOAD = 1
CLASS_ALU = 2
CLASS_WORD_ALU = 3
CLASS_CONTROL_FLOW = 4
CLASS_BIT_OP = 5
CLASS_STACK = 6
CLASS_MISC = 7
CLASS_INTERRUPT_CONTROL = 8

ADDRESSING_IMPLIED = 0
ADDRESSING_IMMEDIATE8 = 1
ADDRESSING_IMMEDIATE16 = 2
ADDRESSING_RELATIVE8 = 3
ADDRESSING_REGISTER8 = 4
ADDRESSING_REGISTER16 = 5
ADDRESSING_MEMORY_BC = 6
ADDRESSING_MEMORY_DE = 7
ADDRESSING_MEMORY_HL = 8
ADDRESSING_MEMORY_HLI = 9
ADDRESSING_MEMORY_HLD = 10
ADDRESSING_MEMORY_IMM16 = 11
ADDRESSING_IO_IMM8 = 12
ADDRESSING_IO_C = 13
ADDRESSING_STACK = 14
ADDRESSING_PREFIX_CB = 15
ADDRESSING_SP_PLUS_E8 = 16

CONDITION_NONE = 0
CONDITION_NZ = 1
CONDITION_Z = 2
CONDITION_NC = 3
CONDITION_C = 4

CONTROL_TARGET_NONE = 0
CONTROL_TARGET_ABSOLUTE = 1
CONTROL_TARGET_RELATIVE = 2
CONTROL_TARGET_CALL = 3
CONTROL_TARGET_RETURN = 4
CONTROL_TARGET_RESTART = 5

OPERAND8_NONE = 0
OPERAND8_REGISTER = 1
OPERAND8_IMM8 = 2
OPERAND8_ADDR_HL = 3
OPERAND8_ADDR_BC = 4
OPERAND8_ADDR_DE = 5
OPERAND8_ADDR_HLI = 6
OPERAND8_ADDR_HLD = 7
OPERAND8_ADDR_IMM16 = 8
OPERAND8_IO_IMM8 = 9
OPERAND8_IO_C = 10
OPERAND8_LITERAL = 11

OPERAND16_NONE = 0
OPERAND16_REGISTER_PAIR = 1
OPERAND16_IMM16 = 2
OPERAND16_ADDR_IMM16 = 3
OPERAND16_SP_PLUS_E8 = 4
OPERAND16_LITERAL = 5

ALU_NONE = 0
ALU_ADD = 1
ALU_ADC = 2
ALU_SUB = 3
ALU_SBC = 4
ALU_AND = 5
ALU_OR = 6
ALU_XOR = 7
ALU_CP = 8
ALU_INC = 9
ALU_DEC = 10

WORD_ALU_NONE = 0
WORD_ALU_ADD_HL = 1
WORD_ALU_ADD_SP_E8 = 2
WORD_ALU_INC = 3
WORD_ALU_DEC = 4
WORD_ALU_LD_HL_SP_PLUS_E8 = 5

BIT_NONE = 0
BIT_ROT_SHIFT = 1
BIT_BIT = 2
BIT_RES = 3
BIT_SET = 4

ROT_NONE = 0
ROT_RLCA = 1
ROT_RRCA = 2
ROT_RLA = 3
ROT_RRA = 4
ROT_RLC = 5
ROT_RRC = 6
ROT_RL = 7
ROT_RR = 8
ROT_SLA = 9
ROT_SRA = 10
ROT_SRL = 11
ROT_SWAP = 12

STACK_NONE = 0
STACK_PUSH = 1
STACK_POP = 2

MISC_NONE = 0
MISC_NOP = 1
MISC_HALT = 2
MISC_STOP = 3
MISC_PREFIX_CB = 4
MISC_DAA = 5
MISC_CPL = 6
MISC_SCF = 7
MISC_CCF = 8

PREFIX_NONE = 0
PREFIX_CB = 1

R8_CODE = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "H": 5, "L": 6}
PAIR_CODE = {"BC": 0, "DE": 1, "HL": 2, "SP": 3, "AF": 4}
COND_CODE = {"NZ": CONDITION_NZ, "Z": CONDITION_Z, "NC": CONDITION_NC, "C": CONDITION_C}

R8_BY_INDEX = ("B", "C", "D", "E", "H", "L", "[HL]", "A")
PAIR_BY_INDEX = ("BC", "DE", "HL", "SP")
STACK_PAIR_BY_INDEX = ("BC", "DE", "HL", "AF")
ALU_BY_INDEX = (
    ALU_ADD,
    ALU_ADC,
    ALU_SUB,
    ALU_SBC,
    ALU_AND,
    ALU_XOR,
    ALU_OR,
    ALU_CP,
)


def _projection(**updates: int) -> dict[str, int]:
    base = {
        "invalid": 0,
        "class_id": CLASS_INVALID,
        "addressing": ADDRESSING_IMPLIED,
        "condition": CONDITION_NONE,
        "control_target": CONTROL_TARGET_NONE,
        "control_return_enable_interrupts": 0,
        "dst8_kind": OPERAND8_NONE,
        "dst8_reg": 0,
        "src8_kind": OPERAND8_NONE,
        "src8_reg": 0,
        "dst16_kind": OPERAND16_NONE,
        "dst16_reg": 0,
        "src16_kind": OPERAND16_NONE,
        "src16_reg": 0,
        "alu_kind": ALU_NONE,
        "word_alu_kind": WORD_ALU_NONE,
        "bit_kind": BIT_NONE,
        "rot_shift_kind": ROT_NONE,
        "bit_index": 0,
        "zero_on_result": 0,
        "stack_kind": STACK_NONE,
        "stack_pair": 0,
        "misc_kind": MISC_NONE,
        "interrupt_enable": 0,
        "prefix": PREFIX_NONE,
        "rst_vector": 0,
    }
    base.update(updates)
    return base


def _register8(name: str) -> tuple[int, int]:
    return OPERAND8_REGISTER, R8_CODE[name]


def _register16(name: str) -> tuple[int, int]:
    return OPERAND16_REGISTER_PAIR, PAIR_CODE[name]


def _r8_operand_by_index(index: int) -> tuple[int, int]:
    name = R8_BY_INDEX[index]
    if name == "[HL]":
        return OPERAND8_ADDR_HL, 0
    return _register8(name)


def _jp_call_target_kind(name: str) -> tuple[int, int]:
    if name == "HL":
        return _register16("HL")
    return OPERAND16_IMM16, 0


def projection_for_unprefixed_opcode(opcode: int) -> dict[str, int]:
    entry = UNPREFIXED_BY_OPCODE[opcode]
    x = opcode >> 6
    y = (opcode >> 3) & 0x7
    z = opcode & 0x7
    p = y >> 1
    q = y & 0x1

    if entry.is_illegal:
        return _projection(invalid=1, class_id=CLASS_INVALID)

    if x == 0:
        if z == 0:
            if y == 0:
                return _projection(class_id=CLASS_MISC, misc_kind=MISC_NOP)
            if y == 1:
                return _projection(
                    class_id=CLASS_LOAD,
                    dst16_kind=OPERAND16_ADDR_IMM16,
                    src16_kind=OPERAND16_REGISTER_PAIR,
                    src16_reg=PAIR_CODE["SP"],
                    addressing=ADDRESSING_MEMORY_IMM16,
                )
            if y == 2:
                return _projection(class_id=CLASS_MISC, misc_kind=MISC_STOP, addressing=ADDRESSING_IMMEDIATE8)
            if y == 3:
                return _projection(class_id=CLASS_CONTROL_FLOW, control_target=CONTROL_TARGET_RELATIVE, addressing=ADDRESSING_RELATIVE8)
            return _projection(
                class_id=CLASS_CONTROL_FLOW,
                condition=COND_CODE[("NZ", "Z", "NC", "C")[y - 4]],
                control_target=CONTROL_TARGET_RELATIVE,
                addressing=ADDRESSING_RELATIVE8,
            )
        if z == 1:
            pair = PAIR_BY_INDEX[p]
            if q == 0:
                return _projection(
                    class_id=CLASS_LOAD,
                    dst16_kind=OPERAND16_REGISTER_PAIR,
                    dst16_reg=PAIR_CODE[pair],
                    src16_kind=OPERAND16_IMM16,
                    addressing=ADDRESSING_IMMEDIATE16,
                )
            return _projection(
                class_id=CLASS_WORD_ALU,
                word_alu_kind=WORD_ALU_ADD_HL,
                dst16_kind=OPERAND16_REGISTER_PAIR,
                dst16_reg=PAIR_CODE["HL"],
                src16_kind=OPERAND16_REGISTER_PAIR,
                src16_reg=PAIR_CODE[pair],
                addressing=ADDRESSING_REGISTER16,
            )
        if z == 2:
            pair = PAIR_BY_INDEX[p]
            if p == 0:
                op8_kind = OPERAND8_ADDR_BC
                addressing = ADDRESSING_MEMORY_BC
            elif p == 1:
                op8_kind = OPERAND8_ADDR_DE
                addressing = ADDRESSING_MEMORY_DE
            elif p == 2:
                op8_kind = OPERAND8_ADDR_HLI
                addressing = ADDRESSING_MEMORY_HLI
            else:
                op8_kind = OPERAND8_ADDR_HLD
                addressing = ADDRESSING_MEMORY_HLD
            if q == 0:
                return _projection(
                    class_id=CLASS_LOAD,
                    dst8_kind=op8_kind,
                    src8_kind=OPERAND8_REGISTER,
                    src8_reg=R8_CODE["A"],
                    addressing=addressing,
                )
            return _projection(
                class_id=CLASS_LOAD,
                dst8_kind=OPERAND8_REGISTER,
                dst8_reg=R8_CODE["A"],
                src8_kind=op8_kind,
                addressing=addressing,
            )
        if z == 3:
            pair = PAIR_BY_INDEX[p]
            return _projection(
                class_id=CLASS_WORD_ALU,
                word_alu_kind=WORD_ALU_INC if q == 0 else WORD_ALU_DEC,
                dst16_kind=OPERAND16_REGISTER_PAIR,
                dst16_reg=PAIR_CODE[pair],
                addressing=ADDRESSING_REGISTER16,
            )
        if z == 4 or z == 5:
            operand_kind, operand_reg = _r8_operand_by_index(y)
            return _projection(
                class_id=CLASS_ALU,
                alu_kind=ALU_INC if z == 4 else ALU_DEC,
                dst8_kind=operand_kind,
                dst8_reg=operand_reg,
                src8_kind=operand_kind,
                src8_reg=operand_reg,
                addressing=ADDRESSING_MEMORY_HL if operand_kind == OPERAND8_ADDR_HL else ADDRESSING_REGISTER8,
            )
        if z == 6:
            operand_kind, operand_reg = _r8_operand_by_index(y)
            return _projection(
                class_id=CLASS_LOAD,
                dst8_kind=operand_kind,
                dst8_reg=operand_reg,
                src8_kind=OPERAND8_IMM8,
                addressing=ADDRESSING_MEMORY_HL if operand_kind == OPERAND8_ADDR_HL else ADDRESSING_IMMEDIATE8,
            )
        if y == 0:
            return _projection(
                class_id=CLASS_BIT_OP,
                bit_kind=BIT_ROT_SHIFT,
                rot_shift_kind=ROT_RLCA,
                dst8_kind=OPERAND8_REGISTER,
                dst8_reg=R8_CODE["A"],
                zero_on_result=0,
            )
        if y == 1:
            return _projection(
                class_id=CLASS_BIT_OP,
                bit_kind=BIT_ROT_SHIFT,
                rot_shift_kind=ROT_RRCA,
                dst8_kind=OPERAND8_REGISTER,
                dst8_reg=R8_CODE["A"],
                zero_on_result=0,
            )
        if y == 2:
            return _projection(
                class_id=CLASS_BIT_OP,
                bit_kind=BIT_ROT_SHIFT,
                rot_shift_kind=ROT_RLA,
                dst8_kind=OPERAND8_REGISTER,
                dst8_reg=R8_CODE["A"],
                zero_on_result=0,
            )
        if y == 3:
            return _projection(
                class_id=CLASS_BIT_OP,
                bit_kind=BIT_ROT_SHIFT,
                rot_shift_kind=ROT_RRA,
                dst8_kind=OPERAND8_REGISTER,
                dst8_reg=R8_CODE["A"],
                zero_on_result=0,
            )
        if y == 4:
            return _projection(class_id=CLASS_MISC, misc_kind=MISC_DAA)
        if y == 5:
            return _projection(class_id=CLASS_MISC, misc_kind=MISC_CPL)
        if y == 6:
            return _projection(class_id=CLASS_MISC, misc_kind=MISC_SCF)
        return _projection(class_id=CLASS_MISC, misc_kind=MISC_CCF)

    if x == 1:
        if y == 6 and z == 6:
            return _projection(class_id=CLASS_MISC, misc_kind=MISC_HALT)
        dst_kind, dst_reg = _r8_operand_by_index(y)
        src_kind, src_reg = _r8_operand_by_index(z)
        return _projection(
            class_id=CLASS_LOAD,
            dst8_kind=dst_kind,
            dst8_reg=dst_reg,
            src8_kind=src_kind,
            src8_reg=src_reg,
            addressing=ADDRESSING_MEMORY_HL if dst_kind == OPERAND8_ADDR_HL or src_kind == OPERAND8_ADDR_HL else ADDRESSING_REGISTER8,
        )

    if x == 2:
        src_kind, src_reg = _r8_operand_by_index(z)
        return _projection(
            class_id=CLASS_ALU,
            alu_kind=ALU_BY_INDEX[y],
            dst8_kind=OPERAND8_REGISTER,
            dst8_reg=R8_CODE["A"],
            src8_kind=src_kind,
            src8_reg=src_reg,
            addressing=ADDRESSING_MEMORY_HL if src_kind == OPERAND8_ADDR_HL else ADDRESSING_REGISTER8,
        )

    if z == 0:
        if y <= 3:
            return _projection(
                class_id=CLASS_CONTROL_FLOW,
                condition=COND_CODE[("NZ", "Z", "NC", "C")[y]],
                control_target=CONTROL_TARGET_RETURN,
                addressing=ADDRESSING_IMPLIED,
            )
        if y == 4:
            return _projection(
                class_id=CLASS_LOAD,
                dst8_kind=OPERAND8_IO_IMM8,
                src8_kind=OPERAND8_REGISTER,
                src8_reg=R8_CODE["A"],
                addressing=ADDRESSING_IO_IMM8,
            )
        if y == 5:
            return _projection(
                class_id=CLASS_WORD_ALU,
                word_alu_kind=WORD_ALU_ADD_SP_E8,
                dst16_kind=OPERAND16_REGISTER_PAIR,
                dst16_reg=PAIR_CODE["SP"],
                src16_kind=OPERAND16_SP_PLUS_E8,
                addressing=ADDRESSING_SP_PLUS_E8,
            )
        if y == 6:
            return _projection(
                class_id=CLASS_LOAD,
                dst8_kind=OPERAND8_REGISTER,
                dst8_reg=R8_CODE["A"],
                src8_kind=OPERAND8_IO_IMM8,
                addressing=ADDRESSING_IO_IMM8,
            )
        return _projection(
            class_id=CLASS_WORD_ALU,
            word_alu_kind=WORD_ALU_LD_HL_SP_PLUS_E8,
            dst16_kind=OPERAND16_REGISTER_PAIR,
            dst16_reg=PAIR_CODE["HL"],
            src16_kind=OPERAND16_SP_PLUS_E8,
            addressing=ADDRESSING_SP_PLUS_E8,
        )

    if z == 1:
        if q == 0:
            pair = STACK_PAIR_BY_INDEX[p]
            return _projection(
                class_id=CLASS_STACK,
                stack_kind=STACK_POP,
                stack_pair=PAIR_CODE[pair],
                addressing=ADDRESSING_STACK,
            )
        if p == 0:
            return _projection(class_id=CLASS_CONTROL_FLOW, control_target=CONTROL_TARGET_RETURN)
        if p == 1:
            return _projection(
                class_id=CLASS_CONTROL_FLOW,
                control_target=CONTROL_TARGET_RETURN,
                control_return_enable_interrupts=1,
            )
        if p == 2:
            return _projection(
                class_id=CLASS_CONTROL_FLOW,
                control_target=CONTROL_TARGET_ABSOLUTE,
                dst16_kind=OPERAND16_REGISTER_PAIR,
                dst16_reg=PAIR_CODE["HL"],
                addressing=ADDRESSING_REGISTER16,
            )
        return _projection(
            class_id=CLASS_LOAD,
            dst16_kind=OPERAND16_REGISTER_PAIR,
            dst16_reg=PAIR_CODE["SP"],
            src16_kind=OPERAND16_REGISTER_PAIR,
            src16_reg=PAIR_CODE["HL"],
            addressing=ADDRESSING_REGISTER16,
        )

    if z == 2:
        if y <= 3:
            return _projection(
                class_id=CLASS_CONTROL_FLOW,
                condition=COND_CODE[("NZ", "Z", "NC", "C")[y]],
                control_target=CONTROL_TARGET_ABSOLUTE,
                dst16_kind=OPERAND16_IMM16,
                addressing=ADDRESSING_IMMEDIATE16,
            )
        if y == 4:
            return _projection(
                class_id=CLASS_LOAD,
                dst8_kind=OPERAND8_IO_C,
                src8_kind=OPERAND8_REGISTER,
                src8_reg=R8_CODE["A"],
                addressing=ADDRESSING_IO_C,
            )
        if y == 5:
            return _projection(
                class_id=CLASS_LOAD,
                dst8_kind=OPERAND8_ADDR_IMM16,
                src8_kind=OPERAND8_REGISTER,
                src8_reg=R8_CODE["A"],
                addressing=ADDRESSING_MEMORY_IMM16,
            )
        if y == 6:
            return _projection(
                class_id=CLASS_LOAD,
                dst8_kind=OPERAND8_REGISTER,
                dst8_reg=R8_CODE["A"],
                src8_kind=OPERAND8_IO_C,
                addressing=ADDRESSING_IO_C,
            )
        return _projection(
            class_id=CLASS_LOAD,
            dst8_kind=OPERAND8_REGISTER,
            dst8_reg=R8_CODE["A"],
            src8_kind=OPERAND8_ADDR_IMM16,
            addressing=ADDRESSING_MEMORY_IMM16,
        )

    if z == 3:
        if y == 0:
            return _projection(
                class_id=CLASS_CONTROL_FLOW,
                control_target=CONTROL_TARGET_ABSOLUTE,
                dst16_kind=OPERAND16_IMM16,
                addressing=ADDRESSING_IMMEDIATE16,
            )
        if y == 1:
            return _projection(
                class_id=CLASS_MISC,
                misc_kind=MISC_PREFIX_CB,
                prefix=PREFIX_CB,
                addressing=ADDRESSING_PREFIX_CB,
            )
        if y == 6:
            return _projection(class_id=CLASS_INTERRUPT_CONTROL, interrupt_enable=0)
        if y == 7:
            return _projection(class_id=CLASS_INTERRUPT_CONTROL, interrupt_enable=1)
        return _projection(invalid=1, class_id=CLASS_INVALID)

    if z == 4:
        if y <= 3:
            return _projection(
                class_id=CLASS_CONTROL_FLOW,
                condition=COND_CODE[("NZ", "Z", "NC", "C")[y]],
                control_target=CONTROL_TARGET_CALL,
                dst16_kind=OPERAND16_IMM16,
                addressing=ADDRESSING_IMMEDIATE16,
            )
        return _projection(invalid=1, class_id=CLASS_INVALID)

    if z == 5:
        if q == 0:
            pair = STACK_PAIR_BY_INDEX[p]
            return _projection(
                class_id=CLASS_STACK,
                stack_kind=STACK_PUSH,
                stack_pair=PAIR_CODE[pair],
                addressing=ADDRESSING_STACK,
            )
        if p == 0:
            return _projection(
                class_id=CLASS_CONTROL_FLOW,
                control_target=CONTROL_TARGET_CALL,
                dst16_kind=OPERAND16_IMM16,
                addressing=ADDRESSING_IMMEDIATE16,
            )
        return _projection(invalid=1, class_id=CLASS_INVALID)

    if z == 6:
        return _projection(
            class_id=CLASS_ALU,
            alu_kind=ALU_BY_INDEX[y],
            dst8_kind=OPERAND8_REGISTER,
            dst8_reg=R8_CODE["A"],
            src8_kind=OPERAND8_IMM8,
            addressing=ADDRESSING_IMMEDIATE8,
        )

    return _projection(
        class_id=CLASS_CONTROL_FLOW,
        control_target=CONTROL_TARGET_RESTART,
        rst_vector=y * 8,
    )


def _bool_expr(value: int) -> str:
    return "true" if value else "false"


def _operand8_expr(kind: int, reg: int) -> str | None:
    if kind == OPERAND8_NONE:
        return None
    if kind == OPERAND8_REGISTER:
        name = next(name for name, code in R8_CODE.items() if code == reg)
        return f"Operand8::Register$(r8: R8::{name})"
    if kind == OPERAND8_IMM8:
        return "Operand8::Imm8"
    if kind == OPERAND8_ADDR_HL:
        return "Operand8::AddrHl"
    if kind == OPERAND8_ADDR_BC:
        return "Operand8::AddrBc"
    if kind == OPERAND8_ADDR_DE:
        return "Operand8::AddrDe"
    if kind == OPERAND8_ADDR_HLI:
        return "Operand8::AddrHli"
    if kind == OPERAND8_ADDR_HLD:
        return "Operand8::AddrHld"
    if kind == OPERAND8_ADDR_IMM16:
        return "Operand8::AddrImm16"
    if kind == OPERAND8_IO_IMM8:
        return "Operand8::IoImm8"
    if kind == OPERAND8_IO_C:
        return "Operand8::IoC"
    raise ValueError(kind)


def _operand16_expr(kind: int, reg: int) -> str | None:
    if kind == OPERAND16_NONE:
        return None
    if kind == OPERAND16_REGISTER_PAIR:
        name = next(name for name, code in PAIR_CODE.items() if code == reg)
        return f"Operand16::RegisterPair$(pair: RegPair::{name})"
    if kind == OPERAND16_IMM16:
        return "Operand16::Imm16"
    if kind == OPERAND16_ADDR_IMM16:
        return "Operand16::AddrImm16"
    if kind == OPERAND16_SP_PLUS_E8:
        return "Operand16::SpPlusE8"
    raise ValueError(kind)


def _addressing_expr(code: int) -> str:
    return {
        ADDRESSING_IMPLIED: "AddressingMode::Implied",
        ADDRESSING_IMMEDIATE8: "AddressingMode::Immediate8",
        ADDRESSING_IMMEDIATE16: "AddressingMode::Immediate16",
        ADDRESSING_RELATIVE8: "AddressingMode::Relative8",
        ADDRESSING_REGISTER8: "AddressingMode::Register8",
        ADDRESSING_REGISTER16: "AddressingMode::Register16",
        ADDRESSING_MEMORY_BC: "AddressingMode::MemoryViaRegPair$(pair: RegPair::BC)",
        ADDRESSING_MEMORY_DE: "AddressingMode::MemoryViaRegPair$(pair: RegPair::DE)",
        ADDRESSING_MEMORY_HL: "AddressingMode::MemoryViaHl",
        ADDRESSING_MEMORY_HLI: "AddressingMode::MemoryViaHlIncrement",
        ADDRESSING_MEMORY_HLD: "AddressingMode::MemoryViaHlDecrement",
        ADDRESSING_MEMORY_IMM16: "AddressingMode::MemoryImm16",
        ADDRESSING_IO_IMM8: "AddressingMode::IoImm8",
        ADDRESSING_IO_C: "AddressingMode::IoC",
        ADDRESSING_STACK: "AddressingMode::Stack",
        ADDRESSING_PREFIX_CB: "AddressingMode::Prefixed$(prefix: PrefixKind::Cb)",
        ADDRESSING_SP_PLUS_E8: "AddressingMode::SpPlusE8",
    }[code]


def _condition_expr(code: int) -> str:
    if code == CONDITION_NONE:
        return "Option::None"
    name = {CONDITION_NZ: "Nz", CONDITION_Z: "Z", CONDITION_NC: "Nc", CONDITION_C: "C"}[code]
    return f"some_condition(ConditionCode::{name})"


def _prefix_expr(code: int) -> str:
    if code == PREFIX_NONE:
        return "Option::None"
    return "some_prefix(PrefixKind::Cb)"


def _bit_index_expr(code: int) -> str:
    if code == 0:
        return "Option::None"
    return f"some_bit_index({code - 1}u3)"


def _operand8_option(kind: int, reg: int) -> str:
    operand = _operand8_expr(kind, reg)
    return "Option::None" if operand is None else f"some8({operand})"


def _operand16_option(kind: int, reg: int) -> str:
    operand = _operand16_expr(kind, reg)
    return "Option::None" if operand is None else f"some16({operand})"


def _alu_kind_expr(code: int) -> str:
    return {
        ALU_ADD: "AluKind::Add",
        ALU_ADC: "AluKind::Adc",
        ALU_SUB: "AluKind::Sub",
        ALU_SBC: "AluKind::Sbc",
        ALU_AND: "AluKind::And",
        ALU_OR: "AluKind::Or",
        ALU_XOR: "AluKind::Xor",
        ALU_CP: "AluKind::Cp",
        ALU_INC: "AluKind::Inc",
        ALU_DEC: "AluKind::Dec",
    }[code]


def _word_alu_kind_expr(code: int) -> str:
    return {
        WORD_ALU_ADD_HL: "WordAluKind::AddHl",
        WORD_ALU_ADD_SP_E8: "WordAluKind::AddSpE8",
        WORD_ALU_INC: "WordAluKind::Inc",
        WORD_ALU_DEC: "WordAluKind::Dec",
        WORD_ALU_LD_HL_SP_PLUS_E8: "WordAluKind::LdHlSpPlusE8",
    }[code]


def _rot_shift_kind_expr(code: int) -> str:
    return {
        ROT_RLCA: "RotShiftKind::Rlca",
        ROT_RRCA: "RotShiftKind::Rrca",
        ROT_RLA: "RotShiftKind::Rla",
        ROT_RRA: "RotShiftKind::Rra",
        ROT_RLC: "RotShiftKind::Rlc",
        ROT_RRC: "RotShiftKind::Rrc",
        ROT_RL: "RotShiftKind::Rl",
        ROT_RR: "RotShiftKind::Rr",
        ROT_SLA: "RotShiftKind::Sla",
        ROT_SRA: "RotShiftKind::Sra",
        ROT_SRL: "RotShiftKind::Srl",
        ROT_SWAP: "RotShiftKind::Swap",
    }[code]


def _bit_kind_expr(kind: int, rot_shift_kind: int) -> str:
    if kind == BIT_ROT_SHIFT:
        return f"BitOpKind::RotateShift$(kind: {_rot_shift_kind_expr(rot_shift_kind)})"
    return {
        BIT_BIT: "BitOpKind::Bit",
        BIT_RES: "BitOpKind::Res",
        BIT_SET: "BitOpKind::Set",
    }[kind]


def _misc_kind_expr(code: int) -> str:
    if code == MISC_PREFIX_CB:
        return "MiscKind::Prefix$(prefix: PrefixKind::Cb)"
    return {
        MISC_NOP: "MiscKind::Nop",
        MISC_HALT: "MiscKind::Halt",
        MISC_STOP: "MiscKind::Stop",
        MISC_DAA: "MiscKind::Daa",
        MISC_CPL: "MiscKind::Cpl",
        MISC_SCF: "MiscKind::Scf",
        MISC_CCF: "MiscKind::Ccf",
    }[code]


def render_projection_spade(projection: dict[str, int]) -> str:
    class_id = projection["class_id"]
    if class_id == CLASS_INVALID:
        return "DecodedOp::Invalid"
    if class_id == CLASS_LOAD:
        return (
            "load("
            f"{_operand8_option(projection['dst8_kind'], projection['dst8_reg'])}, "
            f"{_operand8_option(projection['src8_kind'], projection['src8_reg'])}, "
            f"{_operand16_option(projection['dst16_kind'], projection['dst16_reg'])}, "
            f"{_operand16_option(projection['src16_kind'], projection['src16_reg'])}, "
            f"{_addressing_expr(projection['addressing'])})"
        )
    if class_id == CLASS_ALU:
        return (
            "alu("
            f"{_alu_kind_expr(projection['alu_kind'])}, "
            f"{_operand8_expr(projection['dst8_kind'], projection['dst8_reg'])}, "
            f"{_operand8_expr(projection['src8_kind'], projection['src8_reg'])}, "
            f"{_addressing_expr(projection['addressing'])})"
        )
    if class_id == CLASS_WORD_ALU:
        return (
            "word_alu("
            f"{_word_alu_kind_expr(projection['word_alu_kind'])}, "
            f"{_operand16_expr(projection['dst16_kind'], projection['dst16_reg'])}, "
            f"{_operand16_option(projection['src16_kind'], projection['src16_reg'])}, "
            f"{_addressing_expr(projection['addressing'])})"
        )
    if class_id == CLASS_CONTROL_FLOW:
        if projection["control_target"] == CONTROL_TARGET_ABSOLUTE:
            target = f"ControlTarget::Absolute$(target: {_operand16_expr(projection['dst16_kind'], projection['dst16_reg'])})"
        elif projection["control_target"] == CONTROL_TARGET_RELATIVE:
            target = "ControlTarget::Relative"
        elif projection["control_target"] == CONTROL_TARGET_CALL:
            target = f"ControlTarget::Call$(target: {_operand16_expr(projection['dst16_kind'], projection['dst16_reg'])})"
        elif projection["control_target"] == CONTROL_TARGET_RETURN:
            target = "ControlTarget::Return$(enable_interrupts: " + _bool_expr(projection["control_return_enable_interrupts"]) + ")"
        else:
            target = f"ControlTarget::Restart$(vector: 0x{projection['rst_vector']:02X}u8)"
        return f"control({_condition_expr(projection['condition'])}, {target}, {_addressing_expr(projection['addressing'])})"
    if class_id == CLASS_BIT_OP:
        return (
            "bit_op("
            f"{_bit_kind_expr(projection['bit_kind'], projection['rot_shift_kind'])}, "
            f"{_prefix_expr(projection['prefix'])}, "
            f"{_operand8_expr(projection['dst8_kind'], projection['dst8_reg'])}, "
            f"{_bit_index_expr(projection['bit_index'])}, "
            f"{_bool_expr(projection['zero_on_result'])}, "
            f"{_addressing_expr(projection['addressing'])})"
        )
    if class_id == CLASS_STACK:
        stack_kind = {STACK_PUSH: "StackOpKind::Push", STACK_POP: "StackOpKind::Pop"}[projection["stack_kind"]]
        pair_name = next(name for name, code in PAIR_CODE.items() if code == projection["stack_pair"])
        return f"stack({stack_kind}, RegPair::{pair_name}, {_addressing_expr(projection['addressing'])})"
    if class_id == CLASS_MISC:
        return f"misc({_misc_kind_expr(projection['misc_kind'])}, {_addressing_expr(projection['addressing'])})"
    if class_id == CLASS_INTERRUPT_CONTROL:
        return f"interrupt_control({_bool_expr(projection['interrupt_enable'])}, {_addressing_expr(projection['addressing'])})"
    raise ValueError(class_id)


def render_unprefixed_decode_cases() -> str:
    return "\n".join(
        f"        0x{opcode:02X}u8 => {render_projection_spade(projection_for_unprefixed_opcode(opcode))},"
        for opcode in range(0x100)
    )


def extract_generated_table(text: str) -> str:
    start = text.index(GENERATED_TABLE_BEGIN) + len(GENERATED_TABLE_BEGIN)
    end = text.index(GENERATED_TABLE_END)
    return text[start:end].strip()

