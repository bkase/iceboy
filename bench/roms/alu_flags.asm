INCLUDE "template.inc"

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ld sp, $FFFE
    call InitAbiSignature

__checkpoint_add:
    ld a, $0F
    add a, $01
    ld [wDebugCounters + 0], a

__checkpoint_adc:
    scf
    ld a, $0F
    adc a, $00
    ld [wDebugCounters + 1], a

__checkpoint_sub:
    ld a, $10
    sub $01
    ld [wDebugCounters + 2], a

__checkpoint_sbc:
    scf
    ld a, $10
    sbc a, $00
    ld [wDebugCounters + 3], a

__checkpoint_logic:
    ld a, $F0
    and $0F
    xor $0F
    or $80
    cp $80
    ld [wDebugCounters + 4], a

    ICEBOY_LOG_CASE $02, $00, ABI_LOG_STATUS_PASS, $80, $80, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

__fail:
    ICEBOY_LOG_CASE $02, $00, ABI_LOG_STATUS_FAIL, $80, $00, $FF
    ICEBOY_SET_RESULT ABI_RESULT_FAIL
    jr __fail

__pass:
    jr __pass

InitAbiSignature:
    ICEBOY_INIT_SIGNATURE
    ld a, 5
    ld [wTestCountLo], a
    ld [wPassCountLo], a
    ld a, 'A'
    ld [wTestName + 0], a
    ld a, 'L'
    ld [wTestName + 1], a
    ld a, 'U'
    ld [wTestName + 2], a
    ld a, 'F'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
