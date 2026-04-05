INCLUDE "template.inc"

DEF TEST_MODE2 EQU $01
DEF TEST_MODE3 EQU $02
DEF TEST_MODE0 EQU $03
DEF TEST_MODE1 EQU $04

DEF LCDC_BG_ON EQU $01
DEF LCDC_LCD_ON EQU $80
DEF LCDC_BG_TILE_DATA_8000 EQU $10
DEF LCDC_ON_VALUE EQU LCDC_LCD_ON | LCDC_BG_ON | LCDC_BG_TILE_DATA_8000

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ld sp, $FFFE
    call InitAbiSignature
    xor a
    ld [rIF], a
    ld [rIE], a
    ld [rLCDC], a
    ld a, LCDC_ON_VALUE
    ld [rLCDC], a

__checkpoint_mode2:
    ld b, 2
    ld c, 1
    call WaitLyMode
.mode2_ok:
__checkpoint_mode3:
    ld b, 3
    ld c, 1
    call WaitLyMode
.mode3_ok:
__checkpoint_mode0:
    ld b, 0
    ld c, 1
    call WaitLyMode
.mode0_ok:
__checkpoint_mode1:
    ld b, 1
    ld c, 144
    call WaitLyMode
.mode1_ok:
    ld a, 4
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE TEST_MODE1, $00, ABI_LOG_STATUS_PASS, $01, $01, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

WaitLyMode:
.loop:
    ld a, [rLY]
    cp c
    jr nz, .loop
    ld a, [rSTAT]
    and $03
    cp b
    jr nz, .loop
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
    ld a, 'M'
    ld [wTestName + 0], a
    ld a, 'O'
    ld [wTestName + 1], a
    ld a, 'D'
    ld [wTestName + 2], a
    ld a, 'E'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
