INCLUDE "template.inc"

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ld sp, $FFFE
    call InitAbiSignature

__checkpoint_rotate:
    ld b, $80
    rlc b
    ld a, b
    ld [wDebugCounters + 0], a

__checkpoint_shift:
    ld c, $81
    sra c
    ld a, c
    ld [wDebugCounters + 1], a
    ld hl, wDebugCounters + 2
    ld [hl], $01
    srl [hl]

__checkpoint_bit:
    ld d, $20
    bit 5, d
    ld a, [wDebugCounters + 2]
    ld [wDebugCounters + 3], a

__checkpoint_res_set:
    ld e, $00
    set 7, e
    res 7, e
    swap e
    ld a, e
    ld [wDebugCounters + 4], a

    ICEBOY_LOG_CASE $05, $00, ABI_LOG_STATUS_PASS, $00, $00, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

__fail:
    ICEBOY_LOG_CASE $05, $00, ABI_LOG_STATUS_FAIL, $00, $FF, $FF
    ICEBOY_SET_RESULT ABI_RESULT_FAIL
    jr __fail

__pass:
    jr __pass

InitAbiSignature:
    ICEBOY_INIT_SIGNATURE
    ld a, 4
    ld [wTestCountLo], a
    ld [wPassCountLo], a
    ld a, 'C'
    ld [wTestName + 0], a
    ld a, 'B'
    ld [wTestName + 1], a
    ld a, 'O'
    ld [wTestName + 2], a
    ld a, 'P'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
