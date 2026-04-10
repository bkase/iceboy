#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        *)
            iceboy_die "unsupported argument: $1"
            ;;
    esac
    shift
done

UV_BIN="$(iceboy_require_command "uv" "ICEBOY_UV_BIN" "$(iceboy_uv_bin)")"
SWIM_BIN="$(iceboy_require_command "swim" "ICEBOY_SWIM_BIN" "$(iceboy_swim_bin)")"

PASS=0
FAIL=0

gate_step() {
    local label="$1"
    shift
    echo "[GATE] ${label}"
    if [[ "$DRY_RUN" == "1" ]]; then
        printf 'DRY RUN:'
        printf ' %q' "$@"
        printf '\n'
        return 0
    fi

    local started output duration_s
    started="${SECONDS}"
    if output=$("$@" 2>&1); then
        duration_s=$((SECONDS - started))
        [[ -n "$output" ]] && printf '%s\n' "$output"
        echo "[DETAIL] duration=${duration_s}s"
        return 0
    fi

    duration_s=$((SECONDS - started))
    [[ -n "$output" ]] && printf '%s\n' "$output"
    echo "[DETAIL] duration=${duration_s}s"
    return 1
}

run_criterion() {
    local title="$1"
    local fn="$2"

    echo "--- ${title} ---"
    if "$fn"; then
        echo "[GATE PASS] ${title}"
        PASS=$((PASS + 1))
    else
        echo "[GATE FAIL] ${title}"
        FAIL=$((FAIL + 1))
    fi
}

run_swim_suite() {
    local label="$1"
    local test_filter="$2"
    gate_step "$label" "$SWIM_BIN" test "$test_filter"
}

criterion_wave_c_owned_roms() {
    gate_step \
        "Wave C owned ROM differential bundle" \
        env ICEBOY_PPU_WAVE_C_INCLUDE_RED=1 "${ICEBOY_ROOT}/tools/run_ppu_wave_c_verilator.sh" --skip-build || return 1
    gate_step \
        "Wave C DMA mode-2 hide owned ROM" \
        "${ICEBOY_ROOT}/tools/run_dma_mode2_hide_verilator.sh" --skip-build || return 1
    gate_step \
        "Wave C OBJ DMA metadata corruption owned ROM" \
        "${ICEBOY_ROOT}/tools/run_obj_dma_metadata_corrupt_verilator.sh" --skip-build || return 1
    return 0
}

criterion_object_priority_units() {
    run_swim_suite "Object selection and draw-priority unit suite" "test/ppu/unit/test_obj_priority.py"
}

criterion_dmg_acid2() {
    gate_step \
        "dmg-acid2 reference image comparison" \
        "${ICEBOY_ROOT}/tools/run_dmg_acid2_verilator.sh" \
        --skip-build
}

criterion_selection_invariants() {
    gate_step \
        "PyBoy Wave C selection invariants" \
        "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python -m unittest tools.tests.test_ppu_wave_c_reference
}

criterion_draw_priority_invariants() {
    gate_step \
        "Wave C object fetch/FIFO unit suites" \
        "$SWIM_BIN" test test/ppu/unit/test_obj_fetch.py || return 1
    gate_step \
        "Wave C live OBJ transfer timing suite" \
        "$SWIM_BIN" test test/ppu/unit/test_obj_transfer_live.py
}

criterion_full_frame_pyboy_comparison() {
    gate_step \
        "Full-frame PyBoy composition scenes" \
        "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python -m unittest tools.tests.test_ppu_spatial_oracle_wave_c
}

echo "=== PPU COMPOSITION GATE: Milestone D Ready ==="

run_criterion "Criterion 1: Wave C owned ROM differential bundle" criterion_wave_c_owned_roms
run_criterion "Criterion 2: Object selection and draw-priority unit tests" criterion_object_priority_units
run_criterion "Criterion 3: dmg-acid2 reference image comparison" criterion_dmg_acid2
run_criterion "Criterion 4: Object-selection invariants" criterion_selection_invariants
run_criterion "Criterion 5: Draw-priority invariants" criterion_draw_priority_invariants
run_criterion "Criterion 6: Full-frame PyBoy composition scenes" criterion_full_frame_pyboy_comparison

echo "=== PPU COMPOSITION: ${PASS} passed, ${FAIL} failed ==="
[[ "$FAIL" -eq 0 ]]
