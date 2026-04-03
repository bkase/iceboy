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

criterion_alu_tests() {
    gate_step "ALU curated + generated vectors" "$SWIM_BIN" test test/unit/test_alu.py
}

criterion_decode_tests() {
    gate_step "Decode snapshots (unprefixed)" "$SWIM_BIN" test test/unit/test_decode.py || return 1
    gate_step "Decode snapshots (CB-prefixed)" "$SWIM_BIN" test test/unit/test_decode_cb.py || return 1
    return 0
}

criterion_single_op_tests() {
    gate_step "Single-op milestone families" "$SWIM_BIN" test test/unit/test_cpu_single_op.py
}

criterion_family_coverage() {
    local output
    if ! output=$("$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python - <<'PY' 2>&1
from test.harness.coverage_tracker import opcode_family_count_lines, opcode_family_counts

suites = ("test_alu.py", "test_decode.py", "test_decode_cb.py", "test_cpu_single_op.py")
counts = opcode_family_counts(suites)

print("=== Opcode Family Coverage ===")
for line in opcode_family_count_lines(suites):
    print(line)

missing = [family for family, count in counts.items() if count == 0]
if missing:
    print(f"Zero coverage families: {', '.join(missing)}")
    raise SystemExit(1)

print("Zero coverage families: none")
PY
    ); then
        printf '%s\n' "$output"
        return 1
    fi

    printf '%s\n' "$output"
    return 0
}

echo "=== MILESTONE B GATE: ALU + Decode Ready ==="

run_criterion "Criterion 1: ALU unit tests" criterion_alu_tests
run_criterion "Criterion 2: Decode snapshot tests" criterion_decode_tests
run_criterion "Criterion 3: Single-op differential tests" criterion_single_op_tests
run_criterion "Criterion 4: Opcode family coverage report" criterion_family_coverage

echo "=== MILESTONE B: ${PASS} passed, ${FAIL} failed ==="
[[ "$FAIL" -eq 0 ]]
