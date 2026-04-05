INCLUDE "template.inc"
INCLUDE "ppu_wave_b.inc"

DEF TEST_SCENE_READY EQU $01

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ICEBOY_PPU_SCENE_INIT

    ld a, $E4
    ld [rBGP], a

    ld hl, $8000
    ld d, $00
    ld e, $00
    ld b, 8
    call FillTile16
    ld hl, $8010
    ld d, $FF
    ld e, $00
    ld b, 8
    call FillTile16
    ld hl, $8020
    ld d, $00
    ld e, $FF
    ld b, 8
    call FillTile16
    ld hl, $8030
    ld d, $FF
    ld e, $FF
    ld b, 8
    call FillTile16

    xor a
    ld [$9800], a
    ld a, $01
    ld [$9801], a
    ld a, $02
    ld [$9820], a
    ld a, $03
    ld [$9821], a

    ld a, LCDC_BG_9800_8000_ON
    ld [rLCDC], a

    ld a, [rLCDC]
    cp LCDC_BG_9800_8000_ON
    jr z, .check_map
    ld b, TEST_SCENE_READY
    ld d, LCDC_BG_9800_8000_ON
    ld e, a
    ld c, $01
    jp FailTest
.check_map:
    ld a, [$9821]
    cp $03
    jr z, __checkpoint_scene_ready
    ld b, TEST_SCENE_READY
    ld d, $03
    ld e, a
    ld c, $02
    jp FailTest

__checkpoint_scene_ready:
    ICEBOY_PPU_SCENE_PASS 1, TEST_SCENE_READY, $03, $03, $00

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
    ld a, 'B'
    ld [wTestName + 0], a
    ld a, 'G'
    ld [wTestName + 1], a
    ld a, 'S'
    ld [wTestName + 2], a
    ld a, 'T'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
