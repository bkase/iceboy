INCLUDE "template.inc"
INCLUDE "ppu_wave_b.inc"

DEF TEST_SCROLL_REGS EQU $01

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
    ld [$981F], a
    ld a, $02
    ld [$9BE0], a
    ld a, $03
    ld [$9BFF], a

    ld a, $FF
    ld [rSCX], a
    ld a, $80
    ld [rSCY], a
    ld a, LCDC_BG_9800_8000_ON
    ld [rLCDC], a

    ld a, [rSCX]
    cp $FF
    jr z, .check_scy
    ld b, TEST_SCROLL_REGS
    ld d, $FF
    ld e, a
    ld c, $01
    jp FailTest
.check_scy:
    ld a, [rSCY]
    cp $80
    jr z, __checkpoint_scene_ready
    ld b, TEST_SCROLL_REGS
    ld d, $80
    ld e, a
    ld c, $02
    jp FailTest

__checkpoint_scene_ready:
    ICEBOY_PPU_SCENE_PASS 1, TEST_SCROLL_REGS, $80, $80, $00

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
    ld a, 'C'
    ld [wTestName + 1], a
    ld a, 'R'
    ld [wTestName + 2], a
    ld a, 'L'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
