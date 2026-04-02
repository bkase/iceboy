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

    local output
    if output=$("$@" 2>&1); then
        [[ -n "$output" ]] && printf '%s\n' "$output"
        return 0
    fi

    [[ -n "$output" ]] && printf '%s\n' "$output"
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

criterion_generators() {
    local seed=42
    local left right
    left="$(mktemp)"
    right="$(mktemp)"

    if [[ "$DRY_RUN" == "1" ]]; then
        gate_step "Generator snapshot A" \
            "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python -c "generated_vector_snapshot(seed=${seed})"
        gate_step "Generator snapshot B" \
            "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python -c "generated_vector_snapshot(seed=${seed})"
        echo "[DETAIL] seed=${seed} snapshots match"
        rm -f "$left" "$right"
        return 0
    fi

    "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python - <<'PY' "$seed" > "$left"
from __future__ import annotations

import sys

from tools.tests.test_alu_generated_vectors import generated_vector_snapshot

seed = int(sys.argv[1])
print(generated_vector_snapshot(seed=seed))
PY

    "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python - <<'PY' "$seed" > "$right"
from __future__ import annotations

import sys

from tools.tests.test_alu_generated_vectors import generated_vector_snapshot

seed = int(sys.argv[1])
print(generated_vector_snapshot(seed=seed))
PY

    if ! cmp -s "$left" "$right"; then
        diff -u "$left" "$right" || true
        rm -f "$left" "$right"
        return 1
    fi

    echo "[DETAIL] seed=${seed} snapshots match"
    rm -f "$left" "$right"
    return 0
}

criterion_smoke_scripts() {
    gate_step "Oracle smoke" "${ICEBOY_ROOT}/tools/oracle.sh" || return 1
    gate_step "Cocotb smoke" "${ICEBOY_ROOT}/tools/smoke.sh" || return 1
    gate_step "Synthesis smoke" "$SWIM_BIN" synth || return 1
    gate_step "Formal smoke" "${ICEBOY_ROOT}/tools/formal.sh" || return 1
    return 0
}

criterion_harness_tests() {
    gate_step "Decode completeness scaffold" \
        "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python -m unittest tools.tests.test_decode_completeness || return 1
    gate_step "Reset profile harness" "$SWIM_BIN" test test_reset_profile || return 1
    gate_step "Event script determinism harness" "$SWIM_BIN" test test_event_script_determinism || return 1
    return 0
}

criterion_lockstep_semantic_failure() {
    local log_path="${ICEBOY_ROOT}/build/lockstep/test_cpu_lockstep_test_cpu_lockstep_placeholder_xfail/log.txt"
    local source_path="${ICEBOY_ROOT}/test/lockstep/test_cpu_lockstep.py"

    gate_step "Lockstep placeholder xfail" "$SWIM_BIN" test test_cpu_lockstep || return 1
    if [[ "$DRY_RUN" == "1" ]]; then
        echo "[DETAIL] expect log to contain semantic xfail signature"
        return 0
    fi

    [[ -f "$log_path" ]] || {
        echo "[DETAIL] missing lockstep log: ${log_path}"
        return 1
    }

    grep -q "failed as expected (result was AssertionError)" "$log_path" || {
        echo "[DETAIL] lockstep log missing expected AssertionError xfail marker"
        return 1
    }
    grep -q "semantic value mismatch:" "$source_path" || {
        echo "[DETAIL] lockstep test source missing semantic mismatch assertion"
        return 1
    }
    if grep -Eq "ImportError|ModuleNotFoundError|TimeoutError|SyntaxError|No such file or directory" "$log_path"; then
        echo "[DETAIL] lockstep log contains infrastructural failure markers"
        return 1
    fi

    echo "[DETAIL] lockstep xfail stayed semantic"
    return 0
}

echo "=== MILESTONE A GATE: Harness Ready ==="

run_criterion "Criterion 1: Generator reproducibility" criterion_generators
run_criterion "Criterion 2: Smoke scripts" criterion_smoke_scripts
run_criterion "Criterion 3: Harness tests" criterion_harness_tests
run_criterion "Criterion 4: Semantic failure" criterion_lockstep_semantic_failure

echo "=== MILESTONE A: ${PASS} passed, ${FAIL} failed ==="
[[ "$FAIL" -eq 0 ]]
