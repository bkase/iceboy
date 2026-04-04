INCLUDE "template.inc"

DEF TEST_STAT_LYC_FLAG EQU $01
DEF TEST_STAT_IRQ_COUNT EQU $02
DEF TEST_STAT_IRQ_LINE EQU $03
DEF TEST_LYC_CLEAR EQU $04
DEF TEST_LY_WRAP EQU $05

DEF LCDC_BG_ON EQU $01
DEF LCDC_LCD_ON EQU $80
DEF LCDC_BG_TILE_DATA_8000 EQU $10
DEF LCDC_ON_VALUE EQU LCDC_LCD_ON | LCDC_BG_ON | LCDC_BG_TILE_DATA_8000
DEF STAT_LYC_IRQ_ENABLE EQU $40

ICEBOY_ROM_HEADER

SECTION "STAT Vector", ROM0[$0048]
StatVector:
    ld a, [wDebugCounters + 0]
    inc a
    ld [wDebugCounters + 0], a
    ld a, [rLY]
    ld [wDebugCounters + 1], a
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

    ld a, 2
    ld [rLYC], a
    ld a, STAT_LYC_IRQ_ENABLE
    ld [rSTAT], a
    ld a, IEF_STAT
    ld [rIE], a

    ld a, LCDC_ON_VALUE
    ld [rLCDC], a

    call WaitLy2Match
    ld a, [rSTAT]
    bit 2, a
    jr nz, .lyc_flag_ok
    ld b, TEST_STAT_LYC_FLAG
    ld d, $04
    ld e, a
    ld c, $01
    jp FailTest
.lyc_flag_ok:
    ei
    halt
    nop

    ld a, [wDebugCounters + 0]
    cp 1
    jr z, .irq_count_ok
    ld b, TEST_STAT_IRQ_COUNT
    ld d, 1
    ld e, a
    ld c, $02
    jp FailTest
.irq_count_ok:
    ld a, [wDebugCounters + 1]
    cp 2
    jr z, .irq_line_ok
    ld b, TEST_STAT_IRQ_LINE
    ld d, 2
    ld e, a
    ld c, $03
    jp FailTest
.irq_line_ok:
    call WaitLyValue3
    ld a, [rSTAT]
    bit 2, a
    jr z, .lyc_clear_ok
    ld b, TEST_LYC_CLEAR
    ld d, $00
    ld e, a
    ld c, $04
    jp FailTest
.lyc_clear_ok:
    call WaitLy153
    call WaitLy0

    ld a, [rLY]
    and a
    jr z, .ly_wrap_ok
    ld b, TEST_LY_WRAP
    ld d, $00
    ld e, a
    ld c, $05
    jp FailTest
.ly_wrap_ok:
    di
    xor a
    ld [rIE], a
    ld [rIF], a
    ld a, 5
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE TEST_LY_WRAP, $00, ABI_LOG_STATUS_PASS, $00, $00, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

WaitLy2Match:
__checkpoint_lyc_match:
.wait_line:
    ld a, [rLY]
    cp 2
    jr nz, .wait_line
    ld a, [rSTAT]
    bit 2, a
    jr z, .wait_line
    ret

WaitLyValue3:
.loop:
    ld a, [rLY]
    cp 3
    jr nz, .loop
    ret

WaitLy153:
__checkpoint_ly_153:
.loop:
    ld a, [rLY]
    cp 153
    jr nz, .loop
    ret

WaitLy0:
.wait_nonzero:
    ld a, [rLY]
    and a
    jr z, .wait_nonzero
.wait_zero:
    ld a, [rLY]
    and a
    jr nz, .wait_zero
    ret

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
    ld a, 5
    ld [wTestCountLo], a
    ld a, 'L'
    ld [wTestName + 0], a
    ld a, 'Y'
    ld [wTestName + 1], a
    ld a, 'C'
    ld [wTestName + 2], a
    ld a, 'Y'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
