DEF ABI_SIGNATURE_BASE EQU $C000
DEF ABI_VERSION EQU $01
DEF ABI_RESULT_RUNNING EQU $00
DEF ABI_RESULT_PASS EQU $01
DEF ABI_RESULT_FAIL EQU $FF

DEF ABI_LOG_BASE EQU $C020
DEF ABI_LOG_STATUS_NOT_RUN EQU $00
DEF ABI_LOG_STATUS_PASS EQU $01
DEF ABI_LOG_STATUS_FAIL EQU $FF

DEF rDIV EQU $FF04
DEF rTIMA EQU $FF05
DEF rTMA EQU $FF06
DEF rTAC EQU $FF07
DEF rIF EQU $FF0F
DEF rIE EQU $FFFF
DEF rJOYP EQU $FF00
DEF rLCDC EQU $FF40
DEF rSTAT EQU $FF41
DEF rSCY EQU $FF42
DEF rSCX EQU $FF43
DEF rLY EQU $FF44
DEF rLYC EQU $FF45
DEF rDMA EQU $FF46
DEF rBGP EQU $FF47
DEF rOBP0 EQU $FF48
DEF rOBP1 EQU $FF49
DEF rWY EQU $FF4A
DEF rWX EQU $FF4B

DEF IEF_VBLANK EQU $01
DEF IEF_STAT EQU $02
DEF IEF_TIMER EQU $04
DEF IEF_JOYPAD EQU $10

MACRO ICEBOY_ROM_HEADER
SECTION "Header Entry", ROM0[$0100]
    nop
    jp Entry
ENDM

MACRO ICEBOY_INIT_SIGNATURE
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
    ld [wLogStatus], a
    ld [wLogExpected], a
    ld [wLogActual], a
    ld [wLogFlags], a
ENDM

MACRO ICEBOY_SET_RESULT
    ld a, \1
    ld [wAbiResult], a
ENDM

MACRO ICEBOY_LOG_CASE
    ld a, \1
    ld [wLogTestIdLo], a
    ld a, \2
    ld [wLogTestIdHi], a
    ld a, \3
    ld [wLogStatus], a
    ld a, \4
    ld [wLogExpected], a
    ld a, \5
    ld [wLogActual], a
    ld a, \6
    ld [wLogFlags], a
ENDM

MACRO ICEBOY_ABI_WRAM
SECTION "ABI Signature", WRAM0[$C000]
wAbiVersion:
    ds 1
wAbiResult:
    ds 1
wTestCountLo:
    ds 1
wTestCountHi:
    ds 1
wPassCountLo:
    ds 1
wPassCountHi:
    ds 1
wFailCountLo:
    ds 1
wFailCountHi:
    ds 1
wDebugCounters:
    ds 8
wTestName:
    ds 16

SECTION "ABI Log", WRAM0[$C020]
wLogTestIdLo:
    ds 1
wLogTestIdHi:
    ds 1
wLogStatus:
    ds 1
wLogExpected:
    ds 1
wLogActual:
    ds 1
wLogFlags:
    ds 1
ENDM
