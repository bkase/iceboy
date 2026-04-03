INCLUDE "template.inc"

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ld sp, $FFFE
    call InitAbiSignature

__checkpoint_ld_r_r:
    ld b, $12
    ld c, b
    ld a, c
    ld [wDebugCounters + 0], a

__checkpoint_ld_r_n8:
    ld d, $34
    ld e, $56
    ld a, e
    ld [wDebugCounters + 1], a

__checkpoint_ld_mem:
    ld hl, wDebugCounters + 2
    ld [hl], $78
    ld a, [hl]
    ld [wDebugCounters + 3], a
    ld a, $9A
    ld bc, wDebugCounters + 4
    ld [bc], a
    ld a, [bc]
    ld [wDebugCounters + 5], a

__checkpoint_ld_r16:
    ld de, $C010
    ld hl, $C012
    ld sp, $FFFC
    ld [wDebugCounters + 6], a

    ICEBOY_LOG_CASE $01, $00, ABI_LOG_STATUS_PASS, $9A, $9A, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

__fail:
    ICEBOY_LOG_CASE $01, $00, ABI_LOG_STATUS_FAIL, $9A, $00, $FF
    ICEBOY_SET_RESULT ABI_RESULT_FAIL
    jr __fail

__pass:
    jr __pass

InitAbiSignature:
    ICEBOY_INIT_SIGNATURE
    ld a, 4
    ld [wTestCountLo], a
    ld [wPassCountLo], a
    ld a, 'L'
    ld [wTestName + 0], a
    ld a, 'O'
    ld [wTestName + 1], a
    ld a, 'A'
    ld [wTestName + 2], a
    ld a, 'D'
    ld [wTestName + 3], a
    ld a, 'S'
    ld [wTestName + 4], a
    ret

ICEBOY_ABI_WRAM
