; iceboy custom ROM ABI template
; Assemble with RGBDS, emit symbols with: rgblink -n bench/roms/template.sym
; Finalize header with rgbfix.

DEF ABI_SIGNATURE_BASE EQU $C000
DEF ABI_VERSION EQU $01
DEF ABI_RESULT_RUNNING EQU $00
DEF ABI_RESULT_PASS EQU $01
DEF ABI_RESULT_FAIL EQU $FF

SECTION "Header Entry", ROM0[$0100]
    nop
    jp Entry

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

    ; Template success path
    ld a, ABI_RESULT_PASS
    ld [wAbiResult], a
    jp __pass

__fail:
    ld a, ABI_RESULT_FAIL
    ld [wAbiResult], a
    jr __fail

__pass:
    jr __pass

InitAbiSignature:
    ld a, ABI_VERSION
    ld [wAbiVersion], a
    ld a, ABI_RESULT_RUNNING
    ld [wAbiResult], a
    xor a
    ld [wTestCountLo], a
    ld [wTestCountHi], a
    ld [wPassCountLo], a
    ld [wPassCountHi], a
    ld [wFailCountLo], a
    ld [wFailCountHi], a
    ret

SECTION "ABI Signature", WRAM0[$C000]
wAbiVersion:
    db $01
wAbiResult:
    db $00
wTestCountLo:
    db $00
wTestCountHi:
    db $00
wPassCountLo:
    db $00
wPassCountHi:
    db $00
wFailCountLo:
    db $00
wFailCountHi:
    db $00
wDebugCounters:
    ds 8
wTestName:
    ds 16
