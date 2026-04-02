; iceboy custom ROM ABI template
; Assemble with RGBDS, emit symbols with the build pipeline in bench/roms/build_roms.sh
; Finalize header with rgbfix after linking.

INCLUDE "template.inc"

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    call InitAbiSignature

__checkpoint_boot:
__commit_setup:
    ld a, ABI_RESULT_RUNNING
    ld [wAbiResult], a

__inject_begin_buttons:
    nop
__inject_end_buttons:

    ; Template success path writes a known diagnostic record to WRAM.
    ICEBOY_LOG_CASE $01, $00, ABI_LOG_STATUS_PASS, $42, $42, $00
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

__fail:
    ICEBOY_LOG_CASE $01, $00, ABI_LOG_STATUS_FAIL, $42, $00, $FF
    ICEBOY_SET_RESULT ABI_RESULT_FAIL
    jr __fail

__pass:
    jr __pass

InitAbiSignature:
    ICEBOY_INIT_SIGNATURE
    ld a, 1
    ld [wTestCountLo], a
    ld [wPassCountLo], a
    ld a, 'T'
    ld [wTestName + 0], a
    ld a, 'M'
    ld [wTestName + 1], a
    ld a, 'P'
    ld [wTestName + 2], a
    ld a, 'L'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
