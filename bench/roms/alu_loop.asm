INCLUDE "template.inc"

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ld sp, $FFFE
    call InitAbiSignature

__checkpoint_loop_setup:
    xor a
    ld b, 8
    ld hl, wDebugCounters

__checkpoint_loop_body:
.loop:
    add a, b
    dec b
    jr nz, .loop
    ld [hl], a

__checkpoint_loop_done:
    cp $24
    jr nz, __fail

    ICEBOY_LOG_CASE $07, $00, ABI_LOG_STATUS_PASS, $24, $24, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

__fail:
    ICEBOY_LOG_CASE $07, $00, ABI_LOG_STATUS_FAIL, $24, $00, $FF
    ICEBOY_SET_RESULT ABI_RESULT_FAIL
    jr __fail

__pass:
    jr __pass

InitAbiSignature:
    ICEBOY_INIT_SIGNATURE
    ld a, 3
    ld [wTestCountLo], a
    ld [wPassCountLo], a
    ld a, 'L'
    ld [wTestName + 0], a
    ld a, 'O'
    ld [wTestName + 1], a
    ld a, 'O'
    ld [wTestName + 2], a
    ld a, 'P'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
