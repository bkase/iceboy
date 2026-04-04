INCLUDE "template.inc"

DEF MBC3_TEST_REMAP EQU $01
DEF MBC3_TEST_BANK20 EQU $02
DEF MBC3_TEST_BANK40 EQU $03
DEF MBC3_TEST_BANK7F EQU $04

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ld sp, $FFFE
    call InitAbiSignature

    ld hl, $4000

    xor a
    ld [$2000], a
    ld a, [hl]
    ld [wDebugCounters + 0], a
    cp $01
    jr z, .bank20
    ld b, MBC3_TEST_REMAP
    ld d, $01
    ld e, a
    ld c, $00
    jp FailTest

.bank20:
    ld a, $20
    ld [$2000], a
    ld a, [hl]
    ld [wDebugCounters + 1], a
    cp $20
    jr z, .bank40
    ld b, MBC3_TEST_BANK20
    ld d, $20
    ld e, a
    ld c, $00
    jp FailTest

.bank40:
    ld a, $40
    ld [$2000], a
    ld a, [hl]
    ld [wDebugCounters + 2], a
    cp $40
    jr z, .bank7f
    ld b, MBC3_TEST_BANK40
    ld d, $40
    ld e, a
    ld c, $00
    jp FailTest

.bank7f:
    ld a, $7F
    ld [$2000], a
    ld a, [hl]
    ld [wDebugCounters + 3], a
    cp $7F
    jr z, .pass
    ld b, MBC3_TEST_BANK7F
    ld d, $7F
    ld e, a
    ld c, $00
    jp FailTest

.pass:
    ld a, 4
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE MBC3_TEST_BANK7F, $00, ABI_LOG_STATUS_PASS, $7F, $7F, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

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
    ld a, 'M'
    ld [wTestName + 0], a
    ld a, '3'
    ld [wTestName + 1], a
    ld a, 'S'
    ld [wTestName + 2], a
    ret

SECTION "Bank01", ROMX[$4000], BANK[$01]
    db $01

SECTION "Bank20", ROMX[$4000], BANK[$20]
    db $20

SECTION "Bank40", ROMX[$4000], BANK[$40]
    db $40

SECTION "Bank7F", ROMX[$4000], BANK[$7F]
    db $7F

ICEBOY_ABI_WRAM
