INCLUDE "template.inc"
INCLUDE "ppu_wave_c.inc"

DEF TEST_SCENE_READY EQU $01

DEF DMA_SOURCE_BASE EQU $C200
DEF HRAM_ROUTINE_ADDR EQU $FF80
DEF SPRITE_SLOT EQU 0
DEF SPRITE_OAM_OFFSET EQU SPRITE_SLOT * 4
DEF SPRITE_Y EQU 56
DEF SPRITE_X EQU 48
DEF SPRITE_TILE EQU $01
DEF SCENE_LCDC EQU LCDC_OBJ_9800_8000_ON
DEF TARGET_LINE EQU SPRITE_Y - 16
DEF DMA_START_LINE EQU TARGET_LINE - 1

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

    call ClearTile0
    call FillSpriteTile
    call ClearDmaSource
    ld a, SPRITE_Y
    ld [$FE00 + SPRITE_OAM_OFFSET + 0], a
    ld a, SPRITE_X
    ld [$FE00 + SPRITE_OAM_OFFSET + 1], a
    ld a, SPRITE_TILE
    ld [$FE00 + SPRITE_OAM_OFFSET + 2], a
    xor a
    ld [$FE00 + SPRITE_OAM_OFFSET + 3], a
    call CopyHramRoutine
    xor a
    ld [wDebugCounters + 8], a

    ld a, SCENE_LCDC
    ld [rLCDC], a

__checkpoint_scene_ready:
    ld a, 1
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE TEST_SCENE_READY, $00, ABI_LOG_STATUS_PASS, $01, $01, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS

FrameLoop:
    call WaitForVBlank
    ld a, [wDebugCounters + 8]
    and a
    jr nz, .run_dma
    inc a
    ld [wDebugCounters + 8], a
    call WaitForVisible
    jr FrameLoop
.run_dma:
    call WaitForDmaStartLine
    call HRAM_ROUTINE_ADDR
    jr FrameLoop

ClearTile0:
    ld hl, $8000
    xor a
    ld b, 16
.loop:
    ld [hl+], a
    dec b
    jr nz, .loop
    ret

FillSpriteTile:
    ld hl, $8010
    ld a, $FF
    ld b, 16
.loop:
    ld [hl+], a
    dec b
    jr nz, .loop
    ret

InitSpriteDmaSource:
    ld hl, DMA_SOURCE_BASE
    ld bc, $00A0
.clear:
    xor a
    ld [hl+], a
    dec bc
    ld a, b
    or c
    jr nz, .clear

    ld a, SPRITE_Y
    ld [DMA_SOURCE_BASE + SPRITE_OAM_OFFSET + 0], a
    ld a, SPRITE_X
    ld [DMA_SOURCE_BASE + SPRITE_OAM_OFFSET + 1], a
    ld a, SPRITE_TILE
    ld [DMA_SOURCE_BASE + SPRITE_OAM_OFFSET + 2], a
    xor a
    ld [DMA_SOURCE_BASE + SPRITE_OAM_OFFSET + 3], a
    ret

ClearDmaSource:
    ld hl, DMA_SOURCE_BASE
    ld bc, $00A0
.clear:
    xor a
    ld [hl+], a
    dec bc
    ld a, b
    or c
    jr nz, .clear
    ret

CopyHramRoutine:
    ld hl, HramRoutine
    ld de, HRAM_ROUTINE_ADDR
    ld bc, HramRoutineEnd - HramRoutine
.copy:
    ld a, [hl+]
    ld [de], a
    inc de
    dec bc
    ld a, b
    or c
    jr nz, .copy
    ret

WaitForVBlank:
    ld a, [rLY]
    cp 144
    jr c, WaitForVBlank
    ret

WaitForVisible:
    ld a, [rLY]
    cp 144
    jr nc, WaitForVisible
    ret

WaitForDmaStartLine:
.wait_line:
    ld a, [rLY]
    cp DMA_START_LINE
    jr nz, .wait_line
    ret

__fail:
    jr __fail

__pass:
    jr __pass

InitAbiSignature:
    ICEBOY_INIT_SIGNATURE
    ld a, 1
    ld [wTestCountLo], a
    ld a, 'D'
    ld [wTestName + 0], a
    ld a, 'M'
    ld [wTestName + 1], a
    ld a, 'A'
    ld [wTestName + 2], a
    ld a, 'M'
    ld [wTestName + 3], a
    ld a, '2'
    ld [wTestName + 4], a
    ret

HramRoutine:
    ld a, HIGH(DMA_SOURCE_BASE)
    ld [rDMA], a
    ld de, $0200
.wait_loop:
    dec de
    ld a, d
    or e
    jr nz, .wait_loop
    ret
HramRoutineEnd:

ICEBOY_ABI_WRAM
