INCLUDE "template.inc"
INCLUDE "ppu_wave_c.inc"

DEF TEST_SCENE_READY EQU $01
DEF OBJ_FLAG_BG_PRIORITY EQU $80

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ICEBOY_PPU_OBJ_SCENE_INIT

    ld a, $E4
    ld [rBGP], a
    ld [rOBP0], a
    ld [rOBP1], a

    call WaitForVBlank

    ld hl, $8010
    ld d, $FF
    ld e, $00
    ld b, 8
    call FillTile16

    ld hl, $8020
    ld d, $FF
    ld e, $FF
    ld b, 8
    call FillTile16

    ld a, $01
    ld [$9800], a

    ld a, 16
    ld [$FE00], a
    ld a, 8
    ld [$FE01], a
    ld a, $02
    ld [$FE02], a
    ld a, OBJ_FLAG_BG_PRIORITY
    ld [$FE03], a

    ld a, LCDC_OBJ_9800_8000_ON
    ld [rLCDC], a

__checkpoint_scene_ready:
    ld a, 1
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE TEST_SCENE_READY, $00, ABI_LOG_STATUS_PASS, $05, $05, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

FillTile16:
.loop:
    ld a, d
    ld [hl+], a
    ld a, e
    ld [hl+], a
    dec b
    jr nz, .loop
    ret

WaitForVBlank:
    ld a, [rLY]
    cp 144
    jr c, WaitForVBlank
    ret

__fail:
    jr __fail

__pass:
    jr __pass

InitAbiSignature:
    ICEBOY_INIT_SIGNATURE
    ld a, 1
    ld [wTestCountLo], a
    ld a, 'O'
    ld [wTestName + 0], a
    ld a, 'B'
    ld [wTestName + 1], a
    ld a, 'J'
    ld [wTestName + 2], a
    ld a, 'M'
    ld [wTestName + 3], a
    ld a, 'A'
    ld [wTestName + 4], a
    ld a, 'S'
    ld [wTestName + 5], a
    ld a, 'K'
    ld [wTestName + 6], a
    ret

ICEBOY_ABI_WRAM
