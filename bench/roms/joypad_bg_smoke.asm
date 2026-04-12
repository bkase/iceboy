INCLUDE "template.inc"
INCLUDE "ppu_wave_b.inc"

DEF JOYP_SELECT_BUTTONS EQU $10
DEF JOYP_SELECT_DIRECTIONS EQU $20

DEF CURSOR_HOME_X EQU 10
DEF CURSOR_HOME_Y EQU 9
DEF CURSOR_MAX_X EQU 18
DEF CURSOR_MAX_Y EQU 16
DEF SCRIPT_FRAME_COUNT EQU 20

DEF BG_TILE_LIGHT EQU $00
DEF BG_TILE_DARK EQU $01
DEF CURSOR_TILE_BASE EQU $02
DEF CURSOR_TILE_ALT EQU $06

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ICEBOY_PPU_SCENE_INIT
    call LoadTiles
    call FillBackgroundMap
    call ResetSceneState
    call ApplyVisualState

    ld a, LCDC_BG_9800_8000_ON
    ld [rLCDC], a

__checkpoint_scene_ready:
MainLoop:
    call WaitFrameBoundary
__checkpoint_poll:
    call SampleInputs
    call HandleInputEdges
    call ApplyVisualState

    ld a, [wFrameCounter]
    inc a
    ld [wFrameCounter], a
    cp SCRIPT_FRAME_COUNT
    jr c, MainLoop

    ld a, 1
    ld [wPassCountLo], a
    ld a, [wCursorX]
    ld d, a
    ld a, [wCursorY]
    ld e, a
    ld a, [wCursorStyle]
    and $01
    ld c, a
    ld a, [wInvertPalette]
    and $01
    add a, a
    or c
    ld c, a
    ICEBOY_LOG_CASE $01, $00, ABI_LOG_STATUS_PASS, d, e, c
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

WaitFrameBoundary:
.wait_visible:
    ld a, [rLY]
    cp 144
    jr nc, .wait_visible
.wait_vblank:
    ld a, [rLY]
    cp 144
    jr c, .wait_vblank
    ret

SampleInputs:
    ld a, JOYP_SELECT_DIRECTIONS
    ld [rJOYP], a
    ld a, [rJOYP]
    cpl
    and $0F
    ld b, a
    ld a, [wPrevDirections]
    cpl
    and b
    ld [wDirectionEdges], a
    ld a, b
    ld [wPrevDirections], a

    ld a, JOYP_SELECT_BUTTONS
    ld [rJOYP], a
    ld a, [rJOYP]
    cpl
    and $0F
    ld b, a
    ld a, [wPrevButtons]
    cpl
    and b
    ld [wButtonEdges], a
    ld a, b
    ld [wPrevButtons], a

    ld a, $30
    ld [rJOYP], a
    ret

HandleInputEdges:
    call HandleDirectionEdges
    call HandleButtonEdges
    ret

HandleDirectionEdges:
    ld a, [wDirectionEdges]
    bit 2, a
    jr z, .check_down
    ld a, [wCursorY]
    and a
    jr z, .check_down
    dec a
    ld [wCursorY], a
.check_down:
    ld a, [wDirectionEdges]
    bit 3, a
    jr z, .check_left
    ld a, [wCursorY]
    cp CURSOR_MAX_Y
    jr z, .check_left
    inc a
    ld [wCursorY], a
.check_left:
    ld a, [wDirectionEdges]
    bit 1, a
    jr z, .check_right
    ld a, [wCursorX]
    and a
    jr z, .check_right
    dec a
    ld [wCursorX], a
.check_right:
    ld a, [wDirectionEdges]
    bit 0, a
    ret z
    ld a, [wCursorX]
    cp CURSOR_MAX_X
    ret z
    inc a
    ld [wCursorX], a
    ret

HandleButtonEdges:
    ld a, [wButtonEdges]
    bit 0, a
    jr z, .check_b
    ld a, [wPaletteIndex]
    inc a
    and $03
    ld [wPaletteIndex], a
.check_b:
    ld a, [wButtonEdges]
    bit 1, a
    jr z, .check_select
    ld a, [wCursorStyle]
    xor $01
    ld [wCursorStyle], a
.check_select:
    ld a, [wButtonEdges]
    bit 2, a
    jr z, .check_start
    ld a, [wInvertPalette]
    xor $01
    ld [wInvertPalette], a
.check_start:
    ld a, [wButtonEdges]
    bit 3, a
    ret z
    ld a, CURSOR_HOME_X
    ld [wCursorX], a
    ld a, CURSOR_HOME_Y
    ld [wCursorY], a
    ret

ApplyVisualState:
    call RestoreCursorCells
    call DrawCursorCells
    call ApplyPalette
    ld a, [wCursorX]
    ld [wPrevCursorX], a
    ld a, [wCursorY]
    ld [wPrevCursorY], a
    ret

RestoreCursorCells:
    ld a, [wPrevCursorX]
    ld b, a
    ld a, [wPrevCursorY]
    ld c, a
    call RestoreBackgroundCell
    inc b
    call RestoreBackgroundCell
    dec b
    inc c
    call RestoreBackgroundCell
    inc b
    call RestoreBackgroundCell
    ret

RestoreBackgroundCell:
    ld a, b
    add a, c
    and $01
    call WriteMapTile
    ret

DrawCursorCells:
    ld a, [wCursorStyle]
    and $01
    ld e, CURSOR_TILE_BASE
    jr z, .base_ready
    ld e, CURSOR_TILE_ALT
.base_ready:
    ld a, [wCursorX]
    ld b, a
    ld a, [wCursorY]
    ld c, a
    ld a, e
    call WriteMapTile
    inc b
    ld a, e
    inc a
    call WriteMapTile
    dec b
    inc c
    ld a, e
    add a, $02
    call WriteMapTile
    inc b
    ld a, e
    add a, $03
    call WriteMapTile
    ret

ApplyPalette:
    ld a, [wInvertPalette]
    and $01
    add a, a
    add a, a
    ld e, a
    ld d, $00
    ld a, [wPaletteIndex]
    add a, e
    ld e, a
    ld d, $00
    ld hl, PaletteTable
    add hl, de
    ld a, [hl]
    ld [rBGP], a
    ret

WriteMapTile:
    push af
    ld h, $00
    ld l, c
    add hl, hl
    add hl, hl
    add hl, hl
    add hl, hl
    add hl, hl
    ld d, $00
    ld e, b
    add hl, de
    ld de, $9800
    add hl, de
    pop af
    ld [hl], a
    ret

LoadTiles:
    ld hl, $8000

    ld d, $00
    ld e, $00
    ld b, 8
    call FillTile16

    ld d, $FF
    ld e, $00
    ld b, 8
    call FillTile16

    ld d, $FF
    ld e, $FF
    ld b, 8
    call FillTile16

    ld d, $00
    ld e, $FF
    ld b, 8
    call FillTile16

    ld d, $FF
    ld e, $00
    ld b, 8
    call FillTile16

    ld d, $00
    ld e, $00
    ld b, 8
    call FillTile16

    ld d, $00
    ld e, $00
    ld b, 8
    call FillTile16

    ld d, $FF
    ld e, $FF
    ld b, 8
    call FillTile16

    ld d, $00
    ld e, $FF
    ld b, 8
    call FillTile16

    ld d, $FF
    ld e, $00
    ld b, 8
    call FillTile16
    ret

FillTile16:
.loop:
    ld a, d
    ld [hl+], a
    ld a, e
    ld [hl+], a
    dec b
    jr nz, .loop
    ret

FillBackgroundMap:
    ld hl, $9800
    ld b, 32
    ld d, $00
.row:
    ld c, 32
    ld a, d
    and $01
    ld e, a
.col:
    ld a, e
    ld [hl+], a
    ld a, e
    xor $01
    ld e, a
    dec c
    jr nz, .col
    inc d
    dec b
    jr nz, .row
    ret

ResetSceneState:
    xor a
    ld [wFrameCounter], a
    ld [wPaletteIndex], a
    ld [wCursorStyle], a
    ld [wInvertPalette], a
    ld [wPrevDirections], a
    ld [wPrevButtons], a
    ld [wDirectionEdges], a
    ld [wButtonEdges], a

    ld a, CURSOR_HOME_X
    ld [wCursorX], a
    ld [wPrevCursorX], a
    ld a, CURSOR_HOME_Y
    ld [wCursorY], a
    ld [wPrevCursorY], a
    ret

PaletteTable:
    db $E4, $D2, $39, $1B
    db $1B, $39, $D2, $E4

__fail:
    ICEBOY_LOG_CASE $01, $00, ABI_LOG_STATUS_FAIL, $00, $00, $FF
    ICEBOY_SET_RESULT ABI_RESULT_FAIL
    jr __fail

__pass:
    jr __pass

InitAbiSignature:
    ICEBOY_INIT_SIGNATURE
    ld a, 1
    ld [wTestCountLo], a
    ld a, 'J'
    ld [wTestName + 0], a
    ld a, 'B'
    ld [wTestName + 1], a
    ld a, 'G'
    ld [wTestName + 2], a
    ld a, 'S'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM

SECTION "JoypadBgSmokeState", WRAM0[$C030]
wFrameCounter:
    ds 1
wCursorX:
    ds 1
wCursorY:
    ds 1
wPrevCursorX:
    ds 1
wPrevCursorY:
    ds 1
wPaletteIndex:
    ds 1
wCursorStyle:
    ds 1
wInvertPalette:
    ds 1
wPrevDirections:
    ds 1
wPrevButtons:
    ds 1
wDirectionEdges:
    ds 1
wButtonEdges:
    ds 1
