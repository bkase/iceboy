INCLUDE "template.inc"

DEF MBC1_TEST_REMAP EQU $01
DEF MBC1_TEST_BANK2 EQU $02
DEF MBC1_TEST_BANK21 EQU $03

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ld sp, $FFFE
    call InitAbiSignature

    ld hl, $4000

    ld a, $00
    ld [$2000], a
    ld a, [hl]
    ld [wDebugCounters + 0], a
    cp $01
    jr z, .bank2
    ld b, MBC1_TEST_REMAP
    ld d, $01
    ld e, a
    ld c, $00
    jp FailTest

.bank2:
    ld a, $02
    ld [$2000], a
    ld a, [hl]
    ld [wDebugCounters + 1], a
    cp $02
    jr z, .bank21
    ld b, MBC1_TEST_BANK2
    ld d, $02
    ld e, a
    ld c, $00
    jp FailTest

.bank21:
    ld a, $01
    ld [$4000], a
    xor a
    ld [$2000], a
    ld a, [hl]
    ld [wDebugCounters + 2], a
    cp $21
    jr z, .pass
    ld b, MBC1_TEST_BANK21
    ld d, $21
    ld e, a
    ld c, $00
    jp FailTest

.pass:
    ld a, 3
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE MBC1_TEST_BANK21, $00, ABI_LOG_STATUS_PASS, $21, $21, $00
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
    ld a, 3
    ld [wTestCountLo], a
    ld a, 'M'
    ld [wTestName + 0], a
    ld a, '1'
    ld [wTestName + 1], a
    ld a, 'S'
    ld [wTestName + 2], a
    ret

SECTION "Bank01", ROMX[$4000], BANK[$01]
    db $01

SECTION "Bank02", ROMX[$4000], BANK[$02]
    db $02

SECTION "Bank21", ROMX[$4000], BANK[$21]
    db $21

ICEBOY_ABI_WRAM
