INCLUDE "template.inc"

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ld sp, $FFFE
    call InitAbiSignature

__checkpoint_fill:
    ld hl, $C100
    ld b, 4
    ld a, $11
.fill_loop:
    ld [hli], a
    add a, $11
    dec b
    jr nz, .fill_loop

__checkpoint_verify:
    ld hl, $C100
    ld a, [hli]
    ld [wDebugCounters + 0], a
    ld a, [hli]
    ld [wDebugCounters + 1], a
    ld a, [hli]
    ld [wDebugCounters + 2], a
    ld a, [hli]
    ld [wDebugCounters + 3], a

    ICEBOY_LOG_CASE $06, $00, ABI_LOG_STATUS_PASS, $44, $44, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

__fail:
    ICEBOY_LOG_CASE $06, $00, ABI_LOG_STATUS_FAIL, $44, $00, $FF
    ICEBOY_SET_RESULT ABI_RESULT_FAIL
    jr __fail

__pass:
    jr __pass

InitAbiSignature:
    ICEBOY_INIT_SIGNATURE
    ld a, 2
    ld [wTestCountLo], a
    ld [wPassCountLo], a
    ld a, 'M'
    ld [wTestName + 0], a
    ld a, 'E'
    ld [wTestName + 1], a
    ld a, 'M'
    ld [wTestName + 2], a
    ret

ICEBOY_ABI_WRAM
