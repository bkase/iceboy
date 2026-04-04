INCLUDE "template.inc"

DEF TEST_LCD_OFF_ACCESS EQU $01
DEF TEST_MODE2_OAM_BLOCK EQU $02
DEF TEST_MODE3_VRAM_BLOCK EQU $03
DEF TEST_MODE3_OAM_BLOCK EQU $04
DEF TEST_MODE0_ACCESS EQU $05
DEF TEST_MODE1_ACCESS EQU $06

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

    ld a, $12
    ld [$8000], a
    ld a, [$8000]
    cp $12
    jp nz, fail_lcd_off_access
    ld a, $34
    ld [$FE00], a
    ld a, [$FE00]
    cp $34
    jp nz, fail_lcd_off_access

    ld a, LCDC_ON_VALUE
    ld [rLCDC], a

__checkpoint_mode2_gate:
    ld b, 2
    ld c, 0
    call WaitLyMode
    ld a, $55
    ld [$FE00], a
    ld a, [$FE00]
    cp $FF
    jr z, .mode2_read_ok
    ld b, TEST_MODE2_OAM_BLOCK
    ld d, $FF
    ld e, a
    ld c, $01
    jp FailTest
.mode2_read_ok:

__checkpoint_mode3_gate:
    ld b, 3
    ld c, 0
    call WaitLyMode
    ld a, $66
    ld [$8000], a
    ld a, [$8000]
    cp $FF
    jr z, .mode3_vram_read_ok
    ld b, TEST_MODE3_VRAM_BLOCK
    ld d, $FF
    ld e, a
    ld c, $02
    jp FailTest
.mode3_vram_read_ok:
    ld a, $77
    ld [$FE00], a
    ld a, [$FE00]
    cp $FF
    jr z, .mode3_oam_read_ok
    ld b, TEST_MODE3_OAM_BLOCK
    ld d, $FF
    ld e, a
    ld c, $03
    jp FailTest
.mode3_oam_read_ok:

__checkpoint_mode0_gate:
    ld b, 0
    ld c, 0
    call WaitLyMode
    ld a, [$8000]
    cp $12
    jr nz, fail_mode0_access
    ld a, [$FE00]
    cp $34
    jr nz, fail_mode0_access
    ld a, $56
    ld [$8000], a
    ld a, [$8000]
    cp $56
    jr nz, fail_mode0_access
    ld a, $78
    ld [$FE00], a
    ld a, [$FE00]
    cp $78
    jr nz, fail_mode0_access

__checkpoint_mode1_gate:
    ld b, 1
    ld c, 144
    call WaitLyMode
    ld a, $9A
    ld [$8000], a
    ld a, [$8000]
    cp $9A
    jr nz, fail_mode1_access
    ld a, $BC
    ld [$FE00], a
    ld a, [$FE00]
    cp $BC
    jr nz, fail_mode1_access

    ld a, 6
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE TEST_MODE1_ACCESS, $00, ABI_LOG_STATUS_PASS, $BC, $BC, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

fail_lcd_off_access:
    ld b, TEST_LCD_OFF_ACCESS
    ld d, $34
    ld e, a
    ld c, $00
    jp FailTest

fail_mode0_access:
    ld b, TEST_MODE0_ACCESS
    ld d, $56
    ld e, a
    ld c, $04
    jp FailTest

fail_mode1_access:
    ld b, TEST_MODE1_ACCESS
    ld d, $BC
    ld e, a
    ld c, $05
    jp FailTest

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
    ld a, 6
    ld [wTestCountLo], a
    ld a, 'G'
    ld [wTestName + 0], a
    ld a, 'A'
    ld [wTestName + 1], a
    ld a, 'T'
    ld [wTestName + 2], a
    ld a, 'E'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
