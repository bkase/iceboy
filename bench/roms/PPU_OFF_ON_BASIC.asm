INCLUDE "template.inc"

DEF TEST_LCDC_OFF_MODE EQU $01
DEF TEST_LCDC_OFF_LY EQU $02
DEF TEST_VRAM_OFF_RW EQU $03
DEF TEST_OAM_OFF_RW EQU $04

DEF LCDC_BG_ON EQU $01
DEF LCDC_LCD_ON EQU $80
DEF LCDC_BG_TILE_DATA_8000 EQU $10
DEF LCDC_BG_TILEMAP_9800 EQU $00
DEF LCDC_ON_VALUE EQU LCDC_LCD_ON | LCDC_BG_ON | LCDC_BG_TILE_DATA_8000 | LCDC_BG_TILEMAP_9800

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ld sp, $FFFE
    call InitAbiSignature

__checkpoint_lcd_off:
    xor a
    ld [rIF], a
    ld [rIE], a
    ld [rLCDC], a

    ld a, [rSTAT]
    and $03
    jr z, .off_mode_ok
    ld b, TEST_LCDC_OFF_MODE
    ld d, $00
    ld e, a
    ld c, $01
    jp FailTest
.off_mode_ok:
    ld a, [rLY]
    and a
    jr z, .off_ly_ok
    ld b, TEST_LCDC_OFF_LY
    ld d, $00
    ld e, a
    ld c, $02
    jp FailTest
.off_ly_ok:
    ld a, $12
    ld [$8000], a
    ld a, [$8000]
    cp $12
    jr z, .vram_rw_ok
    ld b, TEST_VRAM_OFF_RW
    ld d, $12
    ld e, a
    ld c, $03
    jp FailTest
.vram_rw_ok:
    ld a, $34
    ld [$FE00], a
    ld a, [$FE00]
    cp $34
    jr z, .oam_rw_ok
    ld b, TEST_OAM_OFF_RW
    ld d, $34
    ld e, a
    ld c, $04
    jp FailTest
.oam_rw_ok:
    ld a, 4
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE TEST_OAM_OFF_RW, $00, ABI_LOG_STATUS_PASS, $34, $34, $00
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
    ld a, 'O'
    ld [wTestName + 0], a
    ld a, 'N'
    ld [wTestName + 1], a
    ld a, 'O'
    ld [wTestName + 2], a
    ld a, 'F'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
