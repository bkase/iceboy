INCLUDE "template.inc"

DEF JOYP_SELECT_BUTTONS EQU $10
DEF JOYP_SELECT_DIRECTIONS EQU $20
DEF POLL_COUNT EQU $04

ICEBOY_ROM_HEADER

SECTION "Entry", ROM0[$0150]
Entry:
    di
    ld sp, $FFFE
    call InitAbiSignature
    xor a
    ld [rIF], a
    ld [wDebugCounters + 0], a
    ld [wDebugCounters + 1], a
    ld [wDebugCounters + 2], a
    ld [wDebugCounters + 3], a
    ld [wDebugCounters + 4], a
    ld [wDebugCounters + 5], a
    ld [wDebugCounters + 6], a
    ld [wDebugCounters + 7], a
    ld a, IEF_JOYPAD
    ld [rIE], a

PollLoop:
__checkpoint_poll:
    call SampleInputs
    call FoldSample
    xor a
    ld [rIF], a
    call DelayBetweenPolls
    ld a, [wDebugCounters + 0]
    inc a
    ld [wDebugCounters + 0], a
    cp POLL_COUNT
    jr nz, PollLoop

    ld a, POLL_COUNT
    ld [wPassCountLo], a
    ICEBOY_LOG_CASE $01, $00, ABI_LOG_STATUS_PASS, $00, $00, $00
    ld a, [wDebugCounters + 4]
    ld [wLogExpected], a
    ld a, [wDebugCounters + 5]
    ld [wLogActual], a
    ld a, [wDebugCounters + 6]
    ld [wLogFlags], a
    ICEBOY_SET_RESULT ABI_RESULT_PASS
    jp __pass

SampleInputs:
    ld a, JOYP_SELECT_DIRECTIONS
    ld [rJOYP], a
    ld a, [rJOYP]
__joyp_dir_after_read:
    and $0F
    ld [wDebugCounters + 4], a
    ld a, JOYP_SELECT_BUTTONS
    ld [rJOYP], a
    ld a, [rJOYP]
__joyp_button_after_read:
    and $0F
    ld [wDebugCounters + 5], a
    ld a, [rIF]
__joyp_if_after_read:
    and IEF_JOYPAD
    ld [wDebugCounters + 6], a
    ret

FoldSample:
    ld a, [wDebugCounters + 1]
    ld b, a
    ld a, [wDebugCounters + 4]
    add a, b
    ld b, a
    ld a, [wDebugCounters + 0]
    add a, b
    ld [wDebugCounters + 1], a

    ld a, [wDebugCounters + 2]
    ld b, a
    ld a, [wDebugCounters + 5]
    xor b
    ld b, a
    ld a, [wDebugCounters + 6]
    xor b
    ld [wDebugCounters + 2], a

    ld a, [wDebugCounters + 3]
    ld b, a
    ld a, [wDebugCounters + 4]
    add a, a
    add a, b
    ld b, a
    ld a, [wDebugCounters + 5]
    add a, b
    ld b, a
    ld a, [wDebugCounters + 6]
    add a, b
    ld [wDebugCounters + 3], a
    ret

DelayBetweenPolls:
    ld de, $0100
.loop:
    dec de
    ld a, d
    or e
    jr nz, .loop
    ret

__fail:
    di
.fail_halt:
    halt
    jr .fail_halt

__pass:
    di
.pass_halt:
    halt
    jr .pass_halt

InitAbiSignature:
    ICEBOY_INIT_SIGNATURE
    ld a, POLL_COUNT
    ld [wTestCountLo], a
    ld a, 'J'
    ld [wTestName + 0], a
    ld a, 'O'
    ld [wTestName + 1], a
    ld a, 'Y'
    ld [wTestName + 2], a
    ld a, 'P'
    ld [wTestName + 3], a
    ret

ICEBOY_ABI_WRAM
