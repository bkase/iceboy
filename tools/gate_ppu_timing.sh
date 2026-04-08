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

criterion_wave_a_owned_roms() {
    run_swim_suite "Wave A owned ROM differential bundle" "test/rom/test_ppu_wave_a.py"
}

criterion_wave_a_mooneye() {
    gate_step \
        "Wave A mooneye timing/control subset" \
        "${ICEBOY_ROOT}/tools/run_ppu_wave_a_mooneye_verilator.sh" \
        --skip-build
}

criterion_mode_fsm() {
    run_swim_suite "PPU mode FSM unit suite" "test/ppu/unit/test_ppu_modes.py"
}

criterion_stat_lyc_irq() {
    run_swim_suite "STAT/LYC/IRQ unit suite" "test/ppu/unit/test_stat_irq.py"
}

criterion_timing_invariants() {
    run_swim_suite "PPU invariant timing subset" "test/ppu/unit/test_ppu_invariants.py"
}

criterion_video_access_policy() {
    run_swim_suite "Video access policy unit suite" "test/ppu/unit/test_access_policy.py"
}

criterion_soc_lockstep() {
    run_swim_suite "SoC lockstep PPU comparison smoke" "test/harness/test_soc_lockstep_top.py"
}

echo "=== PPU TIMING/CONTROL GATE: Milestone B Ready ==="

run_criterion "Criterion 1: Wave A owned ROM differential suites" criterion_wave_a_owned_roms
run_criterion "Criterion 2: Wave A mooneye timing/control subset" criterion_wave_a_mooneye
run_criterion "Criterion 3: PPU mode FSM unit tests" criterion_mode_fsm
run_criterion "Criterion 4: STAT/LYC/IRQ unit tests" criterion_stat_lyc_irq
run_criterion "Criterion 5: PPU invariant timing subset" criterion_timing_invariants
run_criterion "Criterion 6: Video access policy unit tests" criterion_video_access_policy
run_criterion "Criterion 7: No unexplained PPU lockstep divergence smoke" criterion_soc_lockstep

echo "=== PPU TIMING/CONTROL: ${PASS} passed, ${FAIL} failed ==="
[[ "$FAIL" -eq 0 ]]
