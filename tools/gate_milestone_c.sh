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
ARTIFACT_ROOT="${ICEBOY_ROOT}/bench/artifacts"
ARTIFACT_STAMP="$(mktemp "${TMPDIR:-/tmp}/iceboy-milestone-c-artifacts.XXXXXX")"
trap 'rm -f "$ARTIFACT_STAMP"' EXIT

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

run_rom_suite() {
    local rom_id="$1"
    local test_filter="$2"
    gate_step "ROM ${rom_id}" "$SWIM_BIN" test "$test_filter"
}

criterion_wave_a_roms() {
    run_rom_suite "LOADS_BASIC" "test/rom/test_loads_basic.py" || return 1
    run_rom_suite "ALU_FLAGS" "test/rom/test_alu_flags.py" || return 1
    run_rom_suite "ALU16_SP" "test/rom/test_alu16_sp.py" || return 1
    run_rom_suite "FLOW_STACK" "test/rom/test_flow_stack.py" || return 1
    run_rom_suite "CB_BITOPS" "test/rom/test_cb_bitops.py" || return 1
    run_rom_suite "MEM_RWB" "test/rom/test_mem_rwb.py" || return 1
    run_rom_suite "ALU_LOOP" "test/rom/test_alu_loop.py" || return 1
    return 0
}

criterion_formal_invariants() {
    gate_step "Formal F low nibble invariant" bash "${ICEBOY_ROOT}/tools/run_formal_cpu_invariants.sh" || return 1
    gate_step "Formal m_ce=0 hold invariant" bash "${ICEBOY_ROOT}/tools/run_formal_cpu_hold.sh" || return 1
    return 0
}

criterion_simulation_invariants() {
    gate_step "Metamorphic load invariants" "$SWIM_BIN" test "test/unit/test_cpu_invariants_loads.py" || return 1
    gate_step "Metamorphic flow invariants" "$SWIM_BIN" test "test/unit/test_cpu_invariants_flow.py" || return 1
    gate_step "Write-enable discipline" "$SWIM_BIN" test "test/unit/test_write_enable.py" || return 1
    gate_step "Simulation m_ce=0 hold" "$SWIM_BIN" test "test/harness/test_write_enable_hold.py" || return 1
    return 0
}

criterion_divergence_audit() {
    echo "[GATE] Divergence artifact audit"
    if [[ "$DRY_RUN" == "1" ]]; then
        echo "[DETAIL] inspect ${ARTIFACT_ROOT} for divergence artifacts newer than script start"
        return 0
    fi

    if [[ ! -d "${ARTIFACT_ROOT}" ]]; then
        echo "[DETAIL] artifact root missing; no divergence artifacts recorded"
        return 0
    fi

    local output
    output="$(
        find "${ARTIFACT_ROOT}" -type f -newer "${ARTIFACT_STAMP}" \
            \( -name 'divergence.json' -o -name 'divergence_summary.txt' -o -name '*divergence_window.json' \) \
            -print | sort
    )"
    if [[ -n "${output}" ]]; then
        printf '%s\n' "${output}"
        return 1
    fi

    echo "[DETAIL] no divergence artifacts created"
    return 0
}

echo "=== MILESTONE C GATE: CPU Wave A Ready ==="

run_criterion "Criterion 1: Wave A ROM differential suites" criterion_wave_a_roms
run_criterion "Criterion 2: Formal invariants" criterion_formal_invariants
run_criterion "Criterion 3: Simulation invariants and write-enable discipline" criterion_simulation_invariants
run_criterion "Criterion 4: Divergence artifact audit" criterion_divergence_audit

echo "=== MILESTONE C: ${PASS} passed, ${FAIL} failed ==="
[[ "$FAIL" -eq 0 ]]
