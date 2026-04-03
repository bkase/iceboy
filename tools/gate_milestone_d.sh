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

criterion_wave_b_roms() {
    run_swim_suite "ROM EI_DELAY" "test/rom/test_ei_delay.py" || return 1
    run_swim_suite "ROM TIMER_DIV_BASIC" "test/rom/test_timer_div_basic.py" || return 1
    run_swim_suite "ROM TIMER_IRQ_HALT" "test/rom/test_timer_irq_halt.py" || return 1
    return 0
}

criterion_lockstep_subsets() {
    run_swim_suite "Targeted strict lockstep subsets" "test/lockstep/test_cpu_lockstep.py"
}

criterion_interrupt_injection() {
    run_swim_suite "Interrupt injection scenarios" "test/lockstep/test_interrupt_injection.py"
}

criterion_ei_halt_edges() {
    run_swim_suite "EI+HALT and HALT wake edge cases" "test/lockstep/test_ei_halt_corners.py"
}

criterion_timer_interrupt_units() {
    run_swim_suite "Timer unit tests" "test/unit/test_timer.py" || return 1
    run_swim_suite "Interrupt controller unit tests" "test/unit/test_interrupts_basic.py" || return 1
    run_swim_suite "Interrupt service phase tests" "test/unit/test_interrupt_service.py" || return 1
    return 0
}

criterion_joypad_differential() {
    run_swim_suite "ROM JOY_DIVERGE_PERSIST" "test/rom/test_joy_diverge_persist.py"
}

criterion_interrupt_coverage() {
    local output
    if ! output=$("$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python - <<'PY' 2>&1
from __future__ import annotations

from test.harness.coverage_tracker import SUITE_COVERAGE, build_coverage_snapshot

suites = (
    "test_timer.py",
    "test_interrupts_basic.py",
    "test_interrupt_service.py",
    "test_cpu_lockstep.py",
    "test_interrupt_injection.py",
    "test_ei_halt_corners.py",
    "test_ei_delay.py",
    "test_timer_div_basic.py",
    "test_timer_irq_halt.py",
    "test_joy_diverge_persist.py",
)
required = ("timer", "serial", "joypad", "vblank")
all_causes = ("vblank", "stat", "timer", "serial", "joypad")

snapshot = build_coverage_snapshot(suites)
coverage = {cause: [] for cause in all_causes}
for label in suites:
    suite_coverage = SUITE_COVERAGE.get(label)
    if suite_coverage is None:
        continue
    for cause in suite_coverage.interrupt_causes:
        coverage[cause].append(label)

print("=== Interrupt Source Coverage ===")
print(snapshot.dimensions["interrupt_causes"].summary_line())
for cause in all_causes:
    providers = ", ".join(sorted(coverage[cause])) if coverage[cause] else "missing"
    print(f"{cause}: {providers}")

missing = [cause for cause in required if not coverage[cause]]
if missing:
    print(f"Missing required interrupt sources: {', '.join(missing)}")
    raise SystemExit(1)

print("Required interrupt sources: covered")
PY
    ); then
        printf '%s\n' "$output"
        return 1
    fi

    printf '%s\n' "$output"
    return 0
}

echo "=== MILESTONE D GATE: Interrupt/Timer Ready ==="

run_criterion "Criterion 1: Wave B ROM differential suites" criterion_wave_b_roms
run_criterion "Criterion 2: Strict lockstep timer/interrupt subsets" criterion_lockstep_subsets
run_criterion "Criterion 3: Seeded interrupt injection scenarios" criterion_interrupt_injection
run_criterion "Criterion 4: EI+HALT edge cases and HALT wake behavior" criterion_ei_halt_edges
run_criterion "Criterion 5: Timer and interrupt unit suites" criterion_timer_interrupt_units
run_criterion "Criterion 6: Deterministic joypad differential" criterion_joypad_differential
run_criterion "Criterion 7: Interrupt source coverage matrix" criterion_interrupt_coverage

echo "=== MILESTONE D: ${PASS} passed, ${FAIL} failed ==="
[[ "$FAIL" -eq 0 ]]
