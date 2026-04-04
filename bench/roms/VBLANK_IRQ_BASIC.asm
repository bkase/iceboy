INCLUDE "template.inc"

DEF TEST_VBLANK_IRQ_COUNT EQU $01
DEF TEST_VBLANK_IF_SEEN EQU $02
DEF TEST_VBLANK_LINE EQU $03

DEF LCDC_BG_ON EQU $01
DEF LCDC_LCD_ON EQU $80
DEF LCDC_BG_TILE_DATA_8000 EQU $10
DEF LCDC_ON_VALUE EQU LCDC_LCD_ON | LCDC_BG_ON | LCDC_BG_TILE_DATA_8000

ICEBOY_ROM_HEADER

SECTION "VBlank Vector", ROM0[$0040]
VBlankVector:
    ld a, [wDebugCounters + 0]
    inc a
    ld [wDebugCounters + 0], a
    ld a, [rIF]
    ld [wDebugCounters + 1], a
    ld a, [rLY]
    ld [wDebugCounters + 2], a
    xor a
    ld [rIF], a
    reti

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ld sp, $FFFE
    call InitAbiSignature
    xor a
    ld [rIF], a
    ld [rIE], a
    ld [rLCDC], a
    ld [wDebugCounters + 0], a
    ld [wDebugCounters + 1], a
    ld [wDebugCounters + 2], a

    ld a, IEF_VBLANK
    ld [rIE], a
    ld a, LCDC_ON_VALUE
    ld [rLCDC], a

__checkpoint_wait_vblank:
    ei
    halt
    nop

    ld a, [wDebugCounters + 0]
    cp 1
    jr z, .irq_count_ok
    ld b, TEST_VBLANK_IRQ_COUNT
    ld d, 1
    ld e, a
    ld c, $01
    jp FailTest
.irq_count_ok:
    ld a, [wDebugCounters + 1]
    and IEF_VBLANK
    cp IEF_VBLANK
    jr z, .if_seen_ok
    ld b, TEST_VBLANK_IF_SEEN
    ld d, IEF_VBLANK
    ld e, a
    ld c, $02
    jp FailTest
.if_seen_ok:
    ld a, [wDebugCounters + 2]
    cp 144
    jr z, .line_ok
    ld b, TEST_VBLANK_LINE
    ld d, 144
    ld e, a
    ld c, $03
    jp FailTest
.line_ok:
    di
    xor a
    ld [rIE], a
    ld [rIF], a
    ld a, 3
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE TEST_VBLANK_LINE, $00, ABI_LOG_STATUS_PASS, 144, 144, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

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
    ld a, 3
    ld [wTestCountLo], a
    ld a, 'V'
    ld [wTestName + 0], a
    ld a, 'B'
    ld [wTestName + 1], a
    ld a, 'L'
    ld [wTestName + 2], a
    ld a, 'K'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
