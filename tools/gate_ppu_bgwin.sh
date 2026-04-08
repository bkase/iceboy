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

criterion_wave_b_owned_roms() {
    run_swim_suite "Wave B owned ROM differential bundle" "test/rom/test_ppu_wave_b.py"
}

criterion_bg_window_unit_mechanics() {
    run_swim_suite "BG fetcher unit suite" "test/ppu/unit/test_bg_fetcher.py" || return 1
    run_swim_suite "BG FIFO + SCX discard unit suite" "test/ppu/unit/test_bg_fifo.py" || return 1
    return 0
}

criterion_tile_and_window_units() {
    run_swim_suite "Tile decode unit suite" "test/ppu/unit/test_tile.py" || return 1
    run_swim_suite "Window trigger/counter unit suite" "test/ppu/unit/test_window.py" || return 1
    return 0
}

criterion_scanline_semantics() {
    run_swim_suite "PPU invariant scanline suite" "test/ppu/unit/test_ppu_invariants.py" || return 1
    run_swim_suite "SoC lockstep PPU semantic/scanout smoke" "test/harness/test_soc_lockstep_top.py" || return 1
    return 0
}

criterion_pyboy_semantics() {
    gate_step \
        "PyBoy tilemap/window semantic reference scenes" \
        "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python -m unittest tools.tests.test_ppu_wave_b_reference
}

criterion_mealybug_canary() {
    gate_step "Wave B.5 mealybug canary subset" "${ICEBOY_ROOT}/tools/run_ppu_wave_b_mealybug_verilator.sh"
}

echo "=== PPU BG/WINDOW GATE: Milestone C Ready ==="

run_criterion "Criterion 1: Wave B owned ROM differential suites" criterion_wave_b_owned_roms
run_criterion "Criterion 2: BG fetch and SCX discard unit suites" criterion_bg_window_unit_mechanics
run_criterion "Criterion 3: Tile decode and window trigger unit suites" criterion_tile_and_window_units
run_criterion "Criterion 4: Integrated scanline semantic suites" criterion_scanline_semantics
run_criterion "Criterion 5: PyBoy tilemap/window semantic references" criterion_pyboy_semantics
run_criterion "Criterion 6: Wave B.5 mealybug canary subset" criterion_mealybug_canary

echo "=== PPU BG/WINDOW: ${PASS} passed, ${FAIL} failed ==="
[[ "$FAIL" -eq 0 ]]
