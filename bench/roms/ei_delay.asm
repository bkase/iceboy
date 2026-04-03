INCLUDE "template.inc"

DEF TEST_EI_NOP EQU $01
DEF TEST_EI_DI EQU $02
DEF TEST_RETI_CHAIN EQU $03

DEF SCENARIO_EI_NOP EQU $01
DEF SCENARIO_EI_DI EQU $02
DEF SCENARIO_RETI_CHAIN EQU $03

ICEBOY_ROM_HEADER

SECTION "Timer Vector", ROM0[$0050]
TimerVector:
    pop hl
    ld a, [wDebugCounters + 0]
    ld b, a
    ld a, b
    and a
    jr nz, .store_second
    ld a, l
    ld [wDebugCounters + 1], a
    ld a, h
    ld [wDebugCounters + 2], a
    jr .stored
.store_second:
    ld a, l
    ld [wDebugCounters + 3], a
    ld a, h
    ld [wDebugCounters + 4], a
.stored:
    push hl
    ld a, b
    inc a
    ld [wDebugCounters + 0], a
    ld a, [wDebugCounters + 5]
    cp SCENARIO_RETI_CHAIN
    jr nz, .done
    ld a, b
    and a
    jr nz, .done
    ld a, IEF_TIMER
    ld [rIF], a
.done:
    reti

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ld sp, $FFFE
    call InitAbiSignature
    xor a
    ld [rIF], a
    ld a, IEF_TIMER
    ld [rIE], a

__checkpoint_ei_nop:
    call ClearTrace
    ld a, SCENARIO_EI_NOP
    ld [wDebugCounters + 5], a
    ld a, IEF_TIMER
    ei
    ld [rIF], a
.after_ei_request:
    nop
    ld a, [wDebugCounters + 0]
    cp 1
    jr z, .ei_nop_count_ok
    ld b, TEST_EI_NOP
    ld d, 1
    ld e, a
    ld c, $01
    jp FailTest
.ei_nop_count_ok:
    ld a, [wDebugCounters + 1]
    cp LOW(.after_ei_request)
    jr z, .ei_nop_lo_ok
    ld b, TEST_EI_NOP
    ld d, LOW(.after_ei_request)
    ld e, a
    ld c, $02
    jp FailTest
.ei_nop_lo_ok:
    ld a, [wDebugCounters + 2]
    cp HIGH(.after_ei_request)
    jr z, .ei_nop_done
    ld b, TEST_EI_NOP
    ld d, HIGH(.after_ei_request)
    ld e, a
    ld c, $03
    jp FailTest
.ei_nop_done:
    xor a
    ld [rIF], a

__checkpoint_ei_di:
    call ClearTrace
    ld a, SCENARIO_EI_DI
    ld [wDebugCounters + 5], a
    ei
    di
    ld a, IEF_TIMER
    ld [rIF], a
    nop
    nop
    ld a, [wDebugCounters + 0]
    and a
    jr z, .ei_di_count_ok
    ld b, TEST_EI_DI
    ld d, $00
    ld e, a
    ld c, $04
    jp FailTest
.ei_di_count_ok:
    ld a, [rIF]
    and IEF_TIMER
    cp IEF_TIMER
    jr z, .ei_di_done
    ld b, TEST_EI_DI
    ld d, IEF_TIMER
    ld e, a
    ld c, $05
    jp FailTest
.ei_di_done:
    xor a
    ld [rIF], a

__checkpoint_reti:
    call ClearTrace
    ld a, SCENARIO_RETI_CHAIN
    ld [wDebugCounters + 5], a
    ld hl, .reti_slot
    push hl
    jp TimerVector
.reti_slot:
    nop
    ld a, [wDebugCounters + 0]
    cp 2
    jr z, .reti_count_ok
    ld b, TEST_RETI_CHAIN
    ld d, 2
    ld e, a
    ld c, $06
    jp FailTest
.reti_count_ok:
    ld a, [wDebugCounters + 1]
    cp LOW(.reti_slot)
    jr z, .reti_lo0_ok
    ld b, TEST_RETI_CHAIN
    ld d, LOW(.reti_slot)
    ld e, a
    ld c, $07
    jp FailTest
.reti_lo0_ok:
    ld a, [wDebugCounters + 2]
    cp HIGH(.reti_slot)
    jr z, .reti_hi0_ok
    ld b, TEST_RETI_CHAIN
    ld d, HIGH(.reti_slot)
    ld e, a
    ld c, $08
    jp FailTest
.reti_hi0_ok:
    ld a, [wDebugCounters + 3]
    cp LOW(.reti_slot)
    jr z, .reti_lo1_ok
    ld b, TEST_RETI_CHAIN
    ld d, LOW(.reti_slot)
    ld e, a
    ld c, $09
    jp FailTest
.reti_lo1_ok:
    ld a, [wDebugCounters + 4]
    cp HIGH(.reti_slot)
    jr z, .pass
    ld b, TEST_RETI_CHAIN
    ld d, HIGH(.reti_slot)
    ld e, a
    ld c, $0A
    jp FailTest

.pass:
    xor a
    ld [rIF], a
    ld [rIE], a
    ld a, 3
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE TEST_RETI_CHAIN, $00, ABI_LOG_STATUS_PASS, $02, $02, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

ClearTrace:
    xor a
    ld [wDebugCounters + 0], a
    ld [wDebugCounters + 1], a
    ld [wDebugCounters + 2], a
    ld [wDebugCounters + 3], a
    ld [wDebugCounters + 4], a
    ld [wDebugCounters + 5], a
    ret

FailTest:
    ICEBOY_LOG_CASE b, $00, ABI_LOG_STATUS_FAIL, d, e, c
    ICEBOY_SET_RESULT ABI_RESULT_FAIL
    jp __fail

__fail:
    jr __fail

__pass:
    jr __pass

InitAbiSignature:
    ICEBOY_INIT_SIGNATURE
    ld a, 3
    ld [wTestCountLo], a
    ld a, 'E'
    ld [wTestName + 0], a
    ld a, 'I'
    ld [wTestName + 1], a
    ld a, 'D'
    ld [wTestName + 2], a
    ld a, 'L'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
