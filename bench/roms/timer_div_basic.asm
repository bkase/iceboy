INCLUDE "template.inc"

DEF TEST_DIV_COUNT EQU $01
DEF TEST_DIV_RESET EQU $02
DEF TEST_TAC_PRESCALER EQU $03
DEF TEST_TMA_RELOAD EQU $04

MACRO VERIFY_TAC_INCREMENT
    call ResetTimerState
    ld a, \1
    ld [rTAC], a
    call WaitForTimaNonZero
    jr nz, .ok\@
    ld b, TEST_TAC_PRESCALER
    ld d, \1
    ld e, $00
    ld c, \2
    jp FailTest
.ok\@:
    ld [\3], a
ENDM

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ld sp, $FFFE
    call InitAbiSignature
    call ResetTimerState

__checkpoint_div_count:
    ld a, [rDIV]
    ld [wDebugCounters + 0], a
    ld b, a
    ld de, $4000
.wait_for_div:
    ld a, [rDIV]
    cp b
    jr nz, .div_changed
    dec de
    ld a, d
    or e
    jr nz, .wait_for_div
    ld b, TEST_DIV_COUNT
    ld d, $01
    ld e, $00
    ld c, $01
    jp FailTest
.div_changed:
    ld [wDebugCounters + 1], a

__checkpoint_div_reset:
    ld a, $FF
    ld [rDIV], a
    ld a, [rDIV]
    ld [wDebugCounters + 2], a
    and a
    jr z, .div_reset_ok
    ld b, TEST_DIV_RESET
    ld d, $00
    ld e, a
    ld c, $00
    jp FailTest
.div_reset_ok:

__checkpoint_tac_prescaler:
    VERIFY_TAC_INCREMENT $04, $10, wDebugCounters + 3
    VERIFY_TAC_INCREMENT $05, $11, wDebugCounters + 4
    VERIFY_TAC_INCREMENT $06, $12, wDebugCounters + 5
    VERIFY_TAC_INCREMENT $07, $13, wDebugCounters + 6

__checkpoint_tma_reload:
    call ResetTimerState
    xor a
    ld [rIF], a
    ld a, $A5
    ld [rTMA], a
    ld a, $FE
    ld [rTIMA], a
    ld a, $05
    ld [rTAC], a
    call WaitForReloadValue
    cp $A5
    jr z, .reload_seen
    ld b, TEST_TMA_RELOAD
    ld d, $A5
    ld e, a
    ld c, $20
    jp FailTest
.reload_seen:
    ld [wDebugCounters + 7], a
    ld a, [rIF]
    and IEF_TIMER
    cp IEF_TIMER
    jr z, .pass
    ld b, TEST_TMA_RELOAD
    ld d, IEF_TIMER
    ld e, a
    ld c, $21
    jp FailTest

.pass:
    ld a, 4
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE TEST_TMA_RELOAD, $00, ABI_LOG_STATUS_PASS, $A5, $A5, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

WaitForTimaNonZero:
    ld de, $8000
.loop:
    ld a, [rTIMA]
    and a
    ret nz
    dec de
    ld a, d
    or e
    jr nz, .loop
    xor a
    ret

WaitForReloadValue:
    ld de, $8000
.loop:
    ld a, [rTIMA]
    cp $A5
    ret z
    dec de
    ld a, d
    or e
    jr nz, .loop
    xor a
    ret

ResetTimerState:
    xor a
    ld [rIE], a
    ld [rIF], a
    ld [rTAC], a
    ld [rTIMA], a
    ld [rTMA], a
    ld [rDIV], a
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
    ld a, 'T'
    ld [wTestName + 0], a
    ld a, 'D'
    ld [wTestName + 1], a
    ld a, 'I'
    ld [wTestName + 2], a
    ld a, 'V'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
