INCLUDE "template.inc"
INCLUDE "ppu_wave_b.inc"

DEF TEST_WINDOW_REGS EQU $01

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
    ld e, $FF
    ld b, 8
    call FillTile16

    xor a
    ld [$9800], a
    ld a, $01
    ld [$9C00], a

    xor a
    ld [rWY], a
    ld a, 15
    ld [rWX], a
    ld a, LCDC_BG_WINDOW_9800_9C00_8000_ON
    ld [rLCDC], a

    ld a, [rWX]
    cp 15
    jr z, .check_wy
    ld b, TEST_WINDOW_REGS
    ld d, 15
    ld e, a
    ld c, $01
    jp FailTest
.check_wy:
    ld a, [rWY]
    and a
    jr z, __checkpoint_scene_ready
    ld b, TEST_WINDOW_REGS
    ld d, $00
    ld e, a
    ld c, $02
    jp FailTest

__checkpoint_scene_ready:
    ICEBOY_PPU_SCENE_PASS 1, TEST_WINDOW_REGS, 15, 15, $00

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
    ld a, 'W'
    ld [wTestName + 0], a
    ld a, 'B'
    ld [wTestName + 1], a
    ld a, 'A'
    ld [wTestName + 2], a
    ld a, 'S'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
