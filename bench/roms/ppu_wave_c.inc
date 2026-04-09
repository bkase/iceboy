INCLUDE "ppu_wave_b.inc"

DEF LCDC_OBJ_9800_8000_ON EQU LCDC_LCD_ON | LCDC_BG_ON | LCDC_OBJ_ON | LCDC_BG_TILE_DATA_8000
DEF LCDC_OBJ_8X16_9800_8000_ON EQU LCDC_OBJ_9800_8000_ON | LCDC_OBJ_8X16

MACRO ICEBOY_PPU_OBJ_SCENE_INIT
    di
    ld sp, $FFFE
    call InitAbiSignature
    xor a
    ld [rIF], a
    ld [rIE], a
    ld [rSCY], a
    ld [rSCX], a
    ld [rLYC], a
    ld [rWY], a
    ld [rWX], a
ENDM

MACRO ICEBOY_PPU_OBJ_SCENE_PASS
    ld a, \1
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE \2, $00, ABI_LOG_STATUS_PASS, \3, \4, \5
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass
ENDM
