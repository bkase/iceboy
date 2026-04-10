INCLUDE "template.inc"
INCLUDE "ppu_wave_c.inc"

DEF TEST_SCENE_READY EQU $0C
DEF TARGET_LINE_START EQU 80
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
    call LoadTiles
    call FillCheckerMap
    call SeedCancelStrip
    call SeedScene

    ld a, LCDC_OBJ_9800_8000_ON
    ld [rLCDC], a
    call WaitForVBlank

__checkpoint_scene_ready:
    ld a, 1
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE TEST_SCENE_READY, $00, ABI_LOG_STATUS_PASS, $0C, $0C, $00
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
    call WaitForLineAdvanceC
    ld a, LCDC_OBJ_9800_8000_ON
    ld [rLCDC], a
    inc c
    dec b
    jr nz, .row_loop
    call WaitForVBlank
    jp FrameLoop

LoadTiles:
    ld hl, $8000
    ld de, TileCheckerA
    call Copy16Bytes
    ld hl, $8010
    ld de, TileCheckerB
    call Copy16Bytes
    ld hl, $8020
    ld de, TileBall
    call Copy16Bytes
    ld hl, $8030
    ld de, TileWhite
    call Copy16Bytes
    ret

Copy16Bytes:
.loop:
    ld a, [de]
    inc de
    ld [hl+], a
    dec b
    jr nz, .loop
    ret

FillCheckerMap:
    ld hl, $9800
    xor a
    ld d, a
    ld b, 32
.row:
    ld c, 32
    ld e, d
.col:
    ld a, e
    ld [hl+], a
    ld a, e
    xor $01
    ld e, a
    dec c
    jr nz, .col
    ld a, d
    xor $01
    ld d, a
    dec b
    jr nz, .row
    ret

SeedCancelStrip:
    ld hl, $994C
    ld a, $03
    ld [hl+], a
    ld [hl], a
    ret

SeedScene:
    ld a, 40
    ld [$FE00], a
    ld a, 32
    ld [$FE01], a
    ld a, $02
    ld [$FE02], a
    xor a
    ld [$FE03], a

    ld a, 96
    ld [$FE04], a
    ld a, 105
    ld [$FE05], a
    ld a, $02
    ld [$FE06], a
    xor a
    ld [$FE07], a
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
    ret

TileCheckerA:
    db $AA, $00, $55, $00, $AA, $00, $55, $00
    db $AA, $00, $55, $00, $AA, $00, $55, $00

TileCheckerB:
    db $55, $00, $AA, $00, $55, $00, $AA, $00
    db $55, $00, $AA, $00, $55, $00, $AA, $00

TileBall:
    db $3C, $3C, $7E, $7E, $FF, $FF, $FF, $FF
    db $FF, $FF, $FF, $FF, $7E, $7E, $3C, $3C

TileWhite:
    db $00, $00, $00, $00, $00, $00, $00, $00
    db $00, $00, $00, $00, $00, $00, $00, $00

__fail:
    jr __fail

__pass:
    jr __pass

InitAbiSignature:
    ICEBOY_INIT_SIGNATURE
    ld a, 1
    ld [wTestCountLo], a
    ld a, 'C'
    ld [wTestName + 0], a
    ld a, 'B'
    ld [wTestName + 1], a
    ld a, 'C'
    ld [wTestName + 2], a
    ld a, 'O'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
