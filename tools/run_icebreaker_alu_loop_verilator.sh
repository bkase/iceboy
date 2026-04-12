#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
SKIP_BUILD=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        --skip-build)
            SKIP_BUILD=1
            ;;
        *)
            iceboy_die "unsupported argument '$1'"
            ;;
    esac
    shift
done

UV_BIN="$(iceboy_require_command "uv" "ICEBOY_UV_BIN" "$(iceboy_uv_bin)")"
SWIM_BIN="$(iceboy_require_command "swim" "ICEBOY_SWIM_BIN" "$(iceboy_swim_bin)")"
VERILATOR_BIN="$(iceboy_require_command "verilator" "ICEBOY_VERILATOR_BIN" "$(iceboy_verilator_bin)")"

iceboy_log_tool "uv" "$(iceboy_version_string "$UV_BIN" --version)"
iceboy_log_tool "swim" "$(iceboy_version_string "$SWIM_BIN" --version)"
iceboy_log_tool "verilator" "$(iceboy_version_string "$VERILATOR_BIN" --version)"

export PATH="$(dirname "$VERILATOR_BIN"):$(dirname "$SWIM_BIN"):/opt/homebrew/bin:${PATH}"

BUILD_DIR="${ICEBOY_ROOT}/build/rom_verilator/test_icebreaker_alu_loop_native"
VERILOG_SRC="${ICEBOY_ROOT}/build/spade.sv"
VERILOG_DST="${ICEBOY_ROOT}/build/spade.verilator.sv"
WRAPPER_SRC="${ICEBOY_ROOT}/test/harness/verilog/icebreaker_alu_loop_top_verilator_wrapper.sv"
MAIN_SRC="${ICEBOY_ROOT}/tools/verilator/icebreaker_alu_loop_main.cpp"
EXPORT_TOOL="${ICEBOY_ROOT}/tools/export_alu_loop_oracle.py"
RUNNER_BIN="${BUILD_DIR}/icebreaker_alu_loop_runner"
EXPECTED_TRACE="${BUILD_DIR}/alu_loop.expected.tsv"
TRACE_PATH="${BUILD_DIR}/icebreaker_alu_loop.trace.jsonl"
VCD_PATH="${ICEBOY_ALU_LOOP_VCD_PATH:-${BUILD_DIR}/icebreaker_alu_loop.vcd}"
MAX_MCYCLES="${ICEBOY_ALU_LOOP_MAX_MCYCLES:-300000}"
PROGRESS_INTERVAL="${ICEBOY_ALU_LOOP_PROGRESS_INTERVAL:-0}"
RESET_RELEASE_CYCLES="${ICEBOY_ALU_LOOP_RESET_RELEASE_CYCLES:-60000}"
EMIT_TRACE="${ICEBOY_ALU_LOOP_TRACE:-0}"
EMIT_VCD="${ICEBOY_ALU_LOOP_VCD:-0}"

if [[ "$DRY_RUN" == "1" ]]; then
    echo "prepare ${VERILOG_DST} from ${VERILOG_SRC}"
    echo "build dir ${BUILD_DIR}"
    if [[ "$SKIP_BUILD" == "1" ]]; then
        echo "skip swim build"
    fi
    echo "wrapper ${WRAPPER_SRC}"
    echo "main ${MAIN_SRC}"
    echo "export-tool ${EXPORT_TOOL}"
    echo "expected-trace ${EXPECTED_TRACE}"
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python tools/prepare_verilator_sv.py "$VERILOG_SRC" "$VERILOG_DST"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$EXPORT_TOOL" "--output=${EXPECTED_TRACE}"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$VERILATOR_BIN" --cc "$VERILOG_DST" "$WRAPPER_SRC" --top-module icebreaker_alu_loop_top_verilator_wrapper --exe "$MAIN_SRC" --build -j 0 --trace --Mdir "$BUILD_DIR" -o "$(basename "$RUNNER_BIN")"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$RUNNER_BIN" "--expected-trace=${EXPECTED_TRACE}" "--max-mcycles=${MAX_MCYCLES}" "--progress-interval=${PROGRESS_INTERVAL}" "--reset-release-cycles=${RESET_RELEASE_CYCLES}"
    if [[ "$EMIT_TRACE" == "1" ]]; then
        printf ' %q' "--trace=${TRACE_PATH}"
    fi
    if [[ "$EMIT_VCD" == "1" ]]; then
        printf ' %q' "--vcd=${VCD_PATH}"
    fi
    printf '\n'
    exit 0
fi

mkdir -p "$BUILD_DIR"
"${ICEBOY_ROOT}/tools/ensure_swim_python_deps.sh"

if [[ "$SKIP_BUILD" != "1" ]]; then
    "$SWIM_BIN" build
fi

"$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python tools/prepare_verilator_sv.py "$VERILOG_SRC" "$VERILOG_DST"
"$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$EXPORT_TOOL" "--output=${EXPECTED_TRACE}"

"$VERILATOR_BIN" \
    --cc "$VERILOG_DST" "$WRAPPER_SRC" \
    --top-module icebreaker_alu_loop_top_verilator_wrapper \
    --exe "$MAIN_SRC" \
    --build \
    -j 0 \
    -O3 \
    --trace \
    --Mdir "$BUILD_DIR" \
    -o "$(basename "$RUNNER_BIN")"

RUNNER_ARGS=(
    "--expected-trace=${EXPECTED_TRACE}"
    "--max-mcycles=${MAX_MCYCLES}"
    "--progress-interval=${PROGRESS_INTERVAL}"
    "--reset-release-cycles=${RESET_RELEASE_CYCLES}"
)
if [[ "$EMIT_TRACE" == "1" ]]; then
    rm -f "$TRACE_PATH"
    RUNNER_ARGS+=("--trace=${TRACE_PATH}")
fi
if [[ "$EMIT_VCD" == "1" ]]; then
    rm -f "$VCD_PATH"
    RUNNER_ARGS+=("--vcd=${VCD_PATH}")
fi

"$RUNNER_BIN" "${RUNNER_ARGS[@]}"
