INCLUDE "template.inc"

DEF rDMA EQU $FF46
DEF rLCDC EQU $FF40
DEF DMA_TEST_HRAM EQU $01
DEF DMA_TEST_VERIFY EQU $02

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ld sp, $FFFE
    call InitAbiSignature

    ld a, $5A
    ld [wDebugCounters + 0], a
    xor a
    ld [rLCDC], a
    ld a, $C3
    ld [rIE], a
    ld a, $A5
    ld [$FF80], a

__checkpoint_dma_trigger:
    call FillSourceBuffer
    ld a, $C1
    ld [rDMA], a
    ld a, [$FF80]
    ld [wDebugCounters + 1], a
    cp $A5
    jr z, .wait_dma
    ld b, DMA_TEST_HRAM
    ld d, $A5
    ld e, a
    ld c, $01
    jp FailTest

.wait_dma:
    ld de, $0200
.wait_loop:
    dec de
    ld a, d
    or e
    jr nz, .wait_loop

__checkpoint_dma_complete:
__checkpoint_oam_verify:
    call VerifyOamCopy
    ld a, DMA_TEST_VERIFY
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE DMA_TEST_VERIFY, $00, ABI_LOG_STATUS_PASS, $9F, $9F, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

FillSourceBuffer:
    ld hl, $C100
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

VerifyOamCopy:
    ld hl, $FE00
    ld bc, $00A0
    xor a
.loop:
    cp [hl]
    jr z, .next
    ld b, DMA_TEST_VERIFY
    ld d, a
    ld e, [hl]
    ld c, $02
    jp FailTest
.next:
    inc hl
    inc a
    dec bc
    ld d, b
    ld e, c
    ld a, d
    or e
    jr nz, .loop
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
    ld a, 2
    ld [wTestCountLo], a
    ld a, 'D'
    ld [wTestName + 0], a
    ld a, 'M'
    ld [wTestName + 1], a
    ld a, 'A'
    ld [wTestName + 2], a
    ret

ICEBOY_ABI_WRAM
