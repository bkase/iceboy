INCLUDE "template.inc"
INCLUDE "ppu_wave_b.inc"

DEF TEST_WINEN_REGS EQU $01

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ICEBOY_PPU_SCENE_INIT

    ld a, $E4
    ld [rBGP], a

    xor a
    ld [$9800], a
    ld a, $01
    ld [$9C00], a

    xor a
    ld [rWY], a
    ld a, 7
    ld [rWX], a
    ld a, LCDC_BG_WINDOW_9800_9C00_8000_ON
    ld [rLCDC], a

    ld a, LCDC_BG_9800_8000_ON
    ld [rLCDC], a
    ld a, LCDC_BG_WINDOW_9800_9C00_8000_ON
    ld [rLCDC], a

    ld a, [rLCDC]
    cp LCDC_BG_WINDOW_9800_9C00_8000_ON
    jr z, __checkpoint_scene_ready
    ld b, TEST_WINEN_REGS
    ld d, LCDC_BG_WINDOW_9800_9C00_8000_ON
    ld e, a
    ld c, $01
    jp FailTest

__checkpoint_scene_ready:
    ICEBOY_PPU_SCENE_PASS 1, TEST_WINEN_REGS, LCDC_BG_WINDOW_9800_9C00_8000_ON, LCDC_BG_WINDOW_9800_9C00_8000_ON, $00

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
    ld a, 'R'
    ld [wTestName + 0], a
    ld a, 'E'
    ld [wTestName + 1], a
    ld a, 'A'
    ld [wTestName + 2], a
    ld a, 'R'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
