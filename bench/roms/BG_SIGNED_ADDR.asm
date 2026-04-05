INCLUDE "template.inc"
INCLUDE "ppu_wave_b.inc"

DEF TEST_SIGNED_MODE EQU $01

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ICEBOY_PPU_SCENE_INIT

    ld a, $E4
    ld [rBGP], a

    ld hl, $9000
    ld d, $FF
    ld e, $00
    ld b, 8
    call FillTile16
    ld hl, $8800
    ld d, $FF
    ld e, $FF
    ld b, 8
    call FillTile16
    ld hl, $97F0
    ld d, $00
    ld e, $FF
    ld b, 8
    call FillTile16

    xor a
    ld [$9800], a
    ld a, $80
    ld [$9801], a
    ld a, $7F
    ld [$9802], a

    ld a, LCDC_BG_9800_8800_ON
    ld [rLCDC], a

    ld a, [rLCDC]
    and LCDC_BG_TILE_DATA_8000
    jr z, .check_tile_id
    ld b, TEST_SIGNED_MODE
    ld d, $00
    ld e, a
    ld c, $01
    jp FailTest
.check_tile_id:
    ld a, [$9801]
    cp $80
    jr z, __checkpoint_scene_ready
    ld b, TEST_SIGNED_MODE
    ld d, $80
    ld e, a
    ld c, $02
    jp FailTest

__checkpoint_scene_ready:
    ICEBOY_PPU_SCENE_PASS 1, TEST_SIGNED_MODE, $80, $80, $00

FillTile16:
.loop:
    ld a, d
    ld [hl+], a
    ld a, e
    ld [hl+], a
    dec b
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
    ld a, 1
    ld [wTestCountLo], a
    ld a, 'S'
    ld [wTestName + 0], a
    ld a, 'G'
    ld [wTestName + 1], a
    ld a, 'N'
    ld [wTestName + 2], a
    ld a, 'D'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
