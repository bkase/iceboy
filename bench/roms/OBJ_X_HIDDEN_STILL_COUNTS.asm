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

    ; Hidden left (X = 0 -> off-screen, still present in OAM)
    ld a, 56
    ld [$FE00], a
    xor a
    ld [$FE01], a
    ld a, $01
    ld [$FE02], a
    xor a
    ld [$FE03], a

    ; Hidden right (X = 168 -> off-screen)
    ld a, 56
    ld [$FE04], a
    ld a, 168
    ld [$FE05], a
    ld a, $01
    ld [$FE06], a
    xor a
    ld [$FE07], a

    ; Visible sprites that would be candidates on the same line
    ld hl, $FE08
    ld b, 10
    ld c, 16
.seed_visible:
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
    jr nz, .seed_visible

    ld a, LCDC_OBJ_9800_8000_ON
    ld [rLCDC], a
    call WaitForFrameStartVisible

__checkpoint_scene_ready:
    ld a, 1
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE TEST_SCENE_READY, $00, ABI_LOG_STATUS_PASS, $07, $07, $00
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

WaitForFrameStartVisible:
    ld a, [rLY]
    cp 144
    jr nc, WaitForFrameStartVisible
    ld a, [rLY]
    and a
    jr nz, WaitForFrameStartVisible
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
    ld a, 'X'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
