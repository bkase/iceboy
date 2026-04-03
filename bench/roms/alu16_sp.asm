INCLUDE "template.inc"

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ld sp, $FFF8
    call InitAbiSignature

__checkpoint_add_hl:
    ld hl, $0FFF
    ld bc, $0001
    add hl, bc
    ld a, h
    ld [wDebugCounters + 0], a
    ld a, l
    ld [wDebugCounters + 1], a

__checkpoint_add_sp_e8:
    add sp, 8
    ld hl, sp + 0
    ld a, h
    ld [wDebugCounters + 2], a
    ld a, l
    ld [wDebugCounters + 3], a

__checkpoint_ld_hl_sp_e8:
    ld hl, sp - 1
    ld a, h
    ld [wDebugCounters + 4], a
    ld a, l
    ld [wDebugCounters + 5], a
    inc sp
    dec sp

    ICEBOY_LOG_CASE $03, $00, ABI_LOG_STATUS_PASS, $FF, $FF, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

__fail:
    ICEBOY_LOG_CASE $03, $00, ABI_LOG_STATUS_FAIL, $FF, $00, $FF
    ICEBOY_SET_RESULT ABI_RESULT_FAIL
    jr __fail

__pass:
    jr __pass

InitAbiSignature:
    ICEBOY_INIT_SIGNATURE
    ld a, 3
    ld [wTestCountLo], a
    ld [wPassCountLo], a
    ld a, 'S'
    ld [wTestName + 0], a
    ld a, 'P'
    ld [wTestName + 1], a
    ld a, '1'
    ld [wTestName + 2], a
    ld a, '6'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
