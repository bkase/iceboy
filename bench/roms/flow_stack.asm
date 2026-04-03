INCLUDE "template.inc"

SECTION "RST00", ROM0[$0000]
    ret

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ld sp, $FFFE
    call InitAbiSignature

__checkpoint_jp:
    jp .after_jp
    jr __fail
.after_jp:

__checkpoint_jr:
    jr .after_jr
    jr __fail
.after_jr:

__checkpoint_call_ret:
    call FlowStackSubroutine
    cp $5A
    jr nz, __fail

__checkpoint_rst:
    ld hl, .after_rst
    push hl
    rst $00
.after_rst:
    pop bc
    push bc
    pop de

    ICEBOY_LOG_CASE $04, $00, ABI_LOG_STATUS_PASS, $5A, $5A, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

FlowStackSubroutine:
    ld a, $5A
    ret

__fail:
    ICEBOY_LOG_CASE $04, $00, ABI_LOG_STATUS_FAIL, $5A, $00, $FF
    ICEBOY_SET_RESULT ABI_RESULT_FAIL
    jr __fail

__pass:
    jr __pass

InitAbiSignature:
    ICEBOY_INIT_SIGNATURE
    ld a, 4
    ld [wTestCountLo], a
    ld [wPassCountLo], a
    ld a, 'F'
    ld [wTestName + 0], a
    ld a, 'L'
    ld [wTestName + 1], a
    ld a, 'O'
    ld [wTestName + 2], a
    ld a, 'W'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
