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

run_python_check() {
    local label="$1"
    local script="$2"
    echo "[GATE] ${label}"
    if [[ "$DRY_RUN" == "1" ]]; then
        printf 'DRY RUN: %q run --with-requirements %q python -c %q\n' \
            "$UV_BIN" "$ICEBOY_PYTHON_LOCK" "$script"
        return 0
    fi

    local started output duration_s
    started="${SECONDS}"
    if output=$("$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python -c "$script" 2>&1); then
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

criterion_halt_quiescence() {
    run_swim_suite "HALT quiescence suite" "test/power/test_halt_quiescence.py"
}

criterion_alu_idle_isolation() {
    run_swim_suite "ALU idle isolation duty-cycle suite" "test/power/test_duty_cycle_metrics.py"
}

criterion_activity_windows() {
    gate_step \
        "Representative activity capture windows" \
        "${ICEBOY_ROOT}/tools/run_activity_capture_windows.sh" || return 1

    run_python_check \
        "SAIF artifacts are present and non-empty" \
        $'from pathlib import Path\nroot = Path("bench/artifacts/activity_capture")\nwindows = ("boot_smoke", "alu_loop", "halt_idle", "ppu_lcd_off", "ppu_oam_scan", "ppu_hblank")\nfor name in windows:\n    saif = root / name / f"{name}.saif"\n    if not saif.is_file() or saif.stat().st_size <= 0:\n        raise SystemExit(f"missing or empty SAIF: {saif}")\nreport = root / "report.json"\nif not report.is_file() or report.stat().st_size <= 0:\n    raise SystemExit("missing activity capture report.json")\nprint("activity capture artifacts present")'
}

criterion_hardware_baseline() {
    run_python_check \
        "Recorded UP5K baseline reports passing P&R and timing" \
        $'import json\nfrom pathlib import Path\npayload = json.loads(Path("docs/hardware/icebreaker_up5k_baseline.json").read_text())\nif payload["pnr"]["status"] != "passed":\n    raise SystemExit("baseline P&R status is not passed")\nif payload["clock_constraint"]["timing_met"] is not True:\n    raise SystemExit("baseline timing is not met")\nutil = payload["utilization"]\nfor key in ("lut4_used", "dff_used", "spram_used", "ebr_used"):\n    if util.get(key) in (None, 0):\n        raise SystemExit(f"baseline missing usable {key}")\nprint("baseline ok: LUT4={lut} DFF={dff} SPRAM={spram} EBR={ebr} fmax={fmax}".format(lut=util["lut4_used"], dff=util["dff_used"], spram=util["spram_used"], ebr=util["ebr_used"], fmax=payload["clock_constraint"]["achieved_mhz"]))'
}

criterion_debug_free_hw() {
    gate_step \
        "Debug-free hardware verification" \
        "${ICEBOY_ROOT}/tools/verify_hw_build.sh" \
        --skip-build \
        --enforce-budget
}

criterion_power_metric_artifacts() {
    run_python_check \
        "Duty-cycle artifact records write-enable and ALU activity" \
        $'import json\nfrom pathlib import Path\npayload = json.loads(Path("bench/artifacts/power_metrics/test_duty_cycle_metrics.py.json").read_text())\nif not payload.get("cases"):\n    raise SystemExit("duty cycle artifact has no cases")\nmetrics = payload["cases"][-1]["metrics"]\nif metrics["alu_active_cycles"] <= 0:\n    raise SystemExit("alu_active_cycles did not record any active work")\nif metrics["reg_pc_we_cycles"] <= 0:\n    raise SystemExit("reg_pc_we_cycles missing from duty cycle artifact")\nprint("duty cycle artifact ok: alu_active={alu} reg_pc_we={pc}".format(alu=metrics["alu_active_cycles"], pc=metrics["reg_pc_we_cycles"]))'
}

echo "=== MILESTONE E GATE: Power Baseline Ready ==="

run_criterion "Criterion 1: HALT quiescence holds the core still" criterion_halt_quiescence
run_criterion "Criterion 2: ALU idle isolation is measurable" criterion_alu_idle_isolation
run_criterion "Criterion 3: Representative activity windows produce SAIF captures" criterion_activity_windows
run_criterion "Criterion 4: Recorded UP5K synthesis baseline is healthy" criterion_hardware_baseline
run_criterion "Criterion 5: Hardware build remains debug-free and within budget" criterion_debug_free_hw
run_criterion "Criterion 6: Duty-cycle power artifacts are present" criterion_power_metric_artifacts

echo "=== MILESTONE E: ${PASS} passed, ${FAIL} failed ==="
[[ "$FAIL" -eq 0 ]]
