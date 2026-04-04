INCLUDE "template.inc"

DEF MBC3_RAM_ENABLE EQU $01
DEF MBC3_RAM_BANKS EQU $02
DEF MBC3_RTC_LATCH EQU $03
DEF MBC3_RAM_DISABLE EQU $04

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ld sp, $FFFE
    call InitAbiSignature

    ld a, $0A
    ld [$0000], a
    xor a
    ld [$4000], a
    ld a, $12
    ld [$A000], a
    ld a, [$A000]
    ld [wDebugCounters + 0], a
    cp $12
    jr z, .bank3
    ld b, MBC3_RAM_ENABLE
    ld d, $12
    ld e, a
    ld c, $00
    jp FailTest

.bank3:
    ld a, $03
    ld [$4000], a
    ld a, $34
    ld [$A000], a
    ld a, [$A000]
    ld [wDebugCounters + 1], a
    cp $34
    jr z, .back_bank0
    ld b, MBC3_RAM_BANKS
    ld d, $34
    ld e, a
    ld c, $01
    jp FailTest

.back_bank0:
    xor a
    ld [$4000], a
    ld a, [$A000]
    cp $12
    jr z, .rtc
    ld b, MBC3_RAM_BANKS
    ld d, $12
    ld e, a
    ld c, $02
    jp FailTest

.rtc:
    ld a, $08
    ld [$4000], a
    xor a
    ld [$6000], a
    ld a, $01
    ld [$6000], a
    ld a, [$A000]
    cp $FF
    jr nz, .rtc_seen
    ld b, MBC3_RTC_LATCH
    ld d, $00
    ld e, $FF
    ld c, $01
    jp FailTest

.rtc_seen:
    ld a, $01
    ld [wDebugCounters + 2], a
    jr .disable

.disable:
    xor a
    ld [$0000], a
    ld a, [$A000]
    cp $FF
    jr z, .pass
    ld b, MBC3_RAM_DISABLE
    ld d, $FF
    ld e, a
    ld c, $00
    jp FailTest

.pass:
    ld a, 4
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE MBC3_RAM_DISABLE, $00, ABI_LOG_STATUS_PASS, $FF, $FF, $00
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
    ld a, 'R'
    ld [wTestName + 2], a
    ret

ICEBOY_ABI_WRAM
