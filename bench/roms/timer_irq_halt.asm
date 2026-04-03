INCLUDE "template.inc"

DEF TEST_HALT_WAKE EQU $01

ICEBOY_ROM_HEADER

SECTION "Timer Vector", ROM0[$0050]
TimerVector:
__checkpoint_isr_execute:
    pop hl
    ld a, l
    ld [wDebugCounters + 1], a
    ld a, h
    ld [wDebugCounters + 2], a
    push hl
    ld a, [wDebugCounters + 0]
    inc a
    ld [wDebugCounters + 0], a
    ld a, $42
    ld [wDebugCounters + 3], a
    reti

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ld sp, $FFFE
    call InitAbiSignature
    call ResetTrace

__checkpoint_irq_fire:
    xor a
    ld [rIF], a
    ld [rIE], a
    ld [rTAC], a
    ld [rDIV], a
    ld a, $3C
    ld [rTMA], a
    ld a, $FE
    ld [rTIMA], a
    ld a, $05
    ld [rTAC], a
    ld a, IEF_TIMER
    ld [rIE], a

__checkpoint_halt_enter:
    ei
    halt

__checkpoint_halt_wake:
    nop
    ld a, [wDebugCounters + 0]
    cp 1
    jr z, .count_ok
    ld b, TEST_HALT_WAKE
    ld d, 1
    ld e, a
    ld c, $01
    jp FailTest
.count_ok:
    ld a, [wDebugCounters + 1]
    cp LOW(__checkpoint_halt_wake)
    jr z, .ret_lo_ok
    ld b, TEST_HALT_WAKE
    ld d, LOW(__checkpoint_halt_wake)
    ld e, a
    ld c, $02
    jp FailTest
.ret_lo_ok:
    ld a, [wDebugCounters + 2]
    cp HIGH(__checkpoint_halt_wake)
    jr z, .ret_hi_ok
    ld b, TEST_HALT_WAKE
    ld d, HIGH(__checkpoint_halt_wake)
    ld e, a
    ld c, $03
    jp FailTest
.ret_hi_ok:
    ld a, [wDebugCounters + 3]
    cp $42
    jr z, .pass
    ld b, TEST_HALT_WAKE
    ld d, $42
    ld e, a
    ld c, $04
    jp FailTest

.pass:
    di
    xor a
    ld [rIE], a
    ld [rIF], a
    ld [rTAC], a
    ld a, 4
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE TEST_HALT_WAKE, $00, ABI_LOG_STATUS_PASS, $42, $42, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

ResetTrace:
    xor a
    ld [wDebugCounters + 0], a
    ld [wDebugCounters + 1], a
    ld [wDebugCounters + 2], a
    ld [wDebugCounters + 3], a
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
    ld a, 4
    ld [wTestCountLo], a
    ld a, 'H'
    ld [wTestName + 0], a
    ld a, 'A'
    ld [wTestName + 1], a
    ld a, 'L'
    ld [wTestName + 2], a
    ld a, 'T'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
