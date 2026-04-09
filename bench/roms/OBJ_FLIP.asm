INCLUDE "template.inc"
INCLUDE "ppu_wave_c.inc"

DEF TEST_SCENE_READY EQU $01
DEF OBJ_FLAG_YFLIP EQU $40
DEF OBJ_FLAG_XFLIP EQU $20

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

    xor a
    ld hl, $8040
    ld b, 16
.clear_tile:
    ld [hl+], a
    dec b
    jr nz, .clear_tile

    ld a, $F0
    ld [$8040], a
    ld [$8041], a
    ld a, $0F
    ld [$804E], a
    xor a
    ld [$804F], a

    ld a, 56
    ld [$FE00], a
    ld a, 40
    ld [$FE01], a
    ld a, $04
    ld [$FE02], a
    ld a, OBJ_FLAG_XFLIP | OBJ_FLAG_YFLIP
    ld [$FE03], a

    ld a, LCDC_OBJ_9800_8000_ON
    ld [rLCDC], a

__checkpoint_scene_ready:
    ld a, 1
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE TEST_SCENE_READY, $00, ABI_LOG_STATUS_PASS, $04, $04, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

__fail:
    jr __fail

__pass:
    jr __pass

WaitForVBlank:
    ld a, [rLY]
    cp 144
    jr c, WaitForVBlank
    ret

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
    ld a, 'F'
    ld [wTestName + 3], a
    ld a, 'L'
    ld [wTestName + 4], a
    ld a, 'I'
    ld [wTestName + 5], a
    ld a, 'P'
    ld [wTestName + 6], a
    ret

ICEBOY_ABI_WRAM
