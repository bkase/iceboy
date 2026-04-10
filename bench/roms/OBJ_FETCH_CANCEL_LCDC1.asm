INCLUDE "template.inc"
INCLUDE "ppu_wave_c.inc"

DEF TEST_SCENE_READY EQU $08
DEF TARGET_LINE_START EQU 40
DEF TARGET_LINE_COUNT EQU 8

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
    call ClearBgMap9800
    call ClearOam

    ld hl, $8000
    xor a
    ld d, a
    ld e, a
    ld b, 8
    call FillTile16

    ld hl, $8010
    ld d, $FF
    ld e, $FF
    ld b, 8
    call FillTile16

    ld hl, $FE00
    ld b, 3
    ld c, 128
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
    add a, 16
    ld c, a
    dec b
    jr nz, .seed_objs

    ld a, LCDC_OBJ_9800_8000_ON
    ld [rLCDC], a
    call WaitForVBlank

__checkpoint_scene_ready:
    ld a, 1
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE TEST_SCENE_READY, $00, ABI_LOG_STATUS_PASS, $08, $08, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS

FrameLoop:
    ld a, LCDC_OBJ_9800_8000_ON
    ld [rLCDC], a
    ld c, TARGET_LINE_START
    ld b, TARGET_LINE_COUNT
.row_loop:
    call WaitForLineC
    call WaitForMode3
    call DelayCancel
    ld a, LCDC_BG_9800_8000_ON
    ld [rLCDC], a
    call DelayRestoreObj
    ld a, LCDC_OBJ_9800_8000_ON
    ld [rLCDC], a
    call WaitForLineAdvanceC
    inc c
    dec b
    jr nz, .row_loop
    call WaitForVBlank
    jp FrameLoop

FillTile16:
.loop:
    ld a, d
    ld [hl+], a
    ld a, e
    ld [hl+], a
    dec b
    jr nz, .loop
    ret

ClearBgMap9800:
    ld hl, $9800
    ld b, 4
.page_loop:
    ld c, 0
.byte_loop:
    xor a
    ld [hl+], a
    dec c
    jr nz, .byte_loop
    dec b
    jr nz, .page_loop
    ret

ClearOam:
    ld hl, $FE00
    ld b, 160
.oam_loop:
    xor a
    ld [hl+], a
    dec b
    jr nz, .oam_loop
    ret

WaitForVBlank:
    ld a, [rLY]
    cp 144
    jr c, WaitForVBlank
    ret

WaitForLineC:
    ld a, [rLY]
    cp c
    jr nz, WaitForLineC
    ret

WaitForLineAdvanceC:
    ld a, [rLY]
    cp c
    jr z, WaitForLineAdvanceC
    ret

WaitForMode3:
    ld a, [rSTAT]
    and $03
    cp $03
    jr nz, WaitForMode3
    ret

DelayCancel:
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    ret

DelayRestoreObj:
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
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
    ld a, 'C'
    ld [wTestName + 3], a
    ld a, 'A'
    ld [wTestName + 4], a
    ld a, 'N'
    ld [wTestName + 5], a
    ret

ICEBOY_ABI_WRAM
