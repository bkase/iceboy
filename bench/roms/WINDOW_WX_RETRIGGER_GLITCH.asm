INCLUDE "template.inc"
INCLUDE "ppu_wave_b.inc"

DEF TEST_RETRIGGER_REGS EQU $01

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
    ld a, 24
    ld [rWX], a
    ld a, LCDC_BG_WINDOW_9800_9C00_8000_ON
    ld [rLCDC], a

    ld a, 7
    ld [rWX], a
    ld a, 24
    ld [rWX], a

    ld a, [rWX]
    cp 24
    jr z, __checkpoint_scene_ready
    ld b, TEST_RETRIGGER_REGS
    ld d, 24
    ld e, a
    ld c, $01
    jp FailTest

__checkpoint_scene_ready:
    ICEBOY_PPU_SCENE_PASS 1, TEST_RETRIGGER_REGS, 24, 24, $00

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
    ld a, 'T'
    ld [wTestName + 1], a
    ld a, 'R'
    ld [wTestName + 2], a
    ld a, 'G'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
