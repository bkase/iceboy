INCLUDE "template.inc"
INCLUDE "ppu_wave_c.inc"

DEF TEST_SCENE_READY EQU $01

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
    ld e, $FF
    ld b, 8
    call FillTile16

    ld hl, $FE00
    ld b, 11
    ld c, 16
.seed_objs:
    ld a, 56
    ld [hl+], a
    ld a, c
    ld [hl+], a
    ld a, $01
    ld [hl+], a
    xor a
    ld [hl+], a
    ld a, c
    add a, 8
    ld c, a
    dec b
    jr nz, .seed_objs

__checkpoint_scene_ready:
    ld a, 1
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE TEST_SCENE_READY, $00, ABI_LOG_STATUS_PASS, $06, $06, $00
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
    ld a, '1'
    ld [wTestName + 3], a
    ld a, '0'
    ld [wTestName + 4], a
    ret

ICEBOY_ABI_WRAM
