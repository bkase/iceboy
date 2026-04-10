INCLUDE "template.inc"

DEF TEST_HRAM EQU $01
DEF TEST_IO EQU $02
DEF TEST_WRAM EQU $03
DEF TEST_VRAM EQU $04

DEF HRAM_TARGET EQU $FF81
DEF IO_TARGET EQU rBGP
DEF WRAM_TARGET EQU $C100
DEF DMA_SOURCE_BASE EQU $C200
DEF HRAM_ROUTINE_ADDR EQU $FF80

DEF PRE_HRAM EQU $11
DEF DMA_HRAM EQU $22
DEF PRE_IO EQU $E4
DEF DMA_IO EQU $1B
DEF PRE_WRAM EQU $55
DEF DMA_WRAM EQU $66
DEF PRE_VRAM EQU $77
DEF DMA_VRAM EQU $88

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ld sp, $FFFE
    call InitAbiSignature

    xor a
    ld [rLCDC], a

    ld a, PRE_HRAM
    ld [HRAM_TARGET], a
    ld a, PRE_IO
    ld [IO_TARGET], a
    ld a, PRE_WRAM
    ld [WRAM_TARGET], a
    ld a, PRE_VRAM
    ld [$8000], a

    call FillDmaSourceBuffer
    call CopyHramRoutine
    call HRAM_ROUTINE_ADDR

    ld a, [HRAM_TARGET]
    ld [wDebugCounters + 0], a
    cp DMA_HRAM
    jr z, .check_io
    ld b, TEST_HRAM
    ld d, DMA_HRAM
    ld e, a
    ld c, $01
    jp FailTest

.check_io:
    ld a, [IO_TARGET]
    ld [wDebugCounters + 1], a
    cp PRE_IO
    jr z, .check_wram
    ld b, TEST_IO
    ld d, PRE_IO
    ld e, a
    ld c, $02
    jp FailTest

.check_wram:
    ld a, [WRAM_TARGET]
    ld [wDebugCounters + 2], a
    cp PRE_WRAM
    jr z, .check_vram
    ld b, TEST_WRAM
    ld d, PRE_WRAM
    ld e, a
    ld c, $03
    jp FailTest

.check_vram:
    ld a, [$8000]
    ld [wDebugCounters + 3], a
    cp PRE_VRAM
    jr z, .pass
    ld b, TEST_VRAM
    ld d, PRE_VRAM
    ld e, a
    ld c, $04
    jp FailTest

.pass:
    ld a, 4
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE TEST_VRAM, $00, ABI_LOG_STATUS_PASS, PRE_VRAM, PRE_VRAM, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

FillDmaSourceBuffer:
    ld hl, DMA_SOURCE_BASE
    ld bc, $00A0
    xor a
.loop:
    ld [hl+], a
    inc a
    dec bc
    ld d, b
    ld e, c
    ld a, d
    or e
    jr nz, .loop
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
    ld a, 4
    ld [wTestCountLo], a
    ld a, 'D'
    ld [wTestName + 0], a
    ld a, 'M'
    ld [wTestName + 1], a
    ld a, 'A'
    ld [wTestName + 2], a
    ld a, 'I'
    ld [wTestName + 3], a
    ret

HramRoutine:
    ld a, HIGH(DMA_SOURCE_BASE)
    ld [rDMA], a
    ld a, DMA_HRAM
    ld [HRAM_TARGET], a
    ld a, DMA_IO
    ld [IO_TARGET], a
    ld a, DMA_WRAM
    ld [WRAM_TARGET], a
    ld a, DMA_VRAM
    ld [$8000], a
    ld de, $0200
.wait_loop:
    dec de
    ld a, d
    or e
    jr nz, .wait_loop
    ret
HramRoutineEnd:

ICEBOY_ABI_WRAM
