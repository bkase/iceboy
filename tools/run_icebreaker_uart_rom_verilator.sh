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

BUILD_DIR="${ICEBOY_ROOT}/build/uart_rom_verilator/bg_static"
VERILOG_SRC="${ICEBOY_ROOT}/build/spade.sv"
VERILOG_DST="${ICEBOY_ROOT}/build/spade.verilator.sv"
WRAPPER_SRC="${ICEBOY_ROOT}/test/harness/verilog/icebreaker_uart_rom_top_verilator_wrapper.sv"
MAIN_SRC="${ICEBOY_ROOT}/tools/verilator/icebreaker_uart_rom_top_main.cpp"
RUNNER_BIN="${BUILD_DIR}/icebreaker_uart_rom_runner"
ROM_PATH="${ICEBOY_ROOT}/bench/roms/out/bg_static.gb"
EXPECTED_TOOL="${ICEBOY_ROOT}/bench/ref/BG_STATIC.py"
EXPECTED_RAW="${BUILD_DIR}/reference.raw"
CAPTURED_RAW="${BUILD_DIR}/captured.raw"
CAPTURED_PNG="${BUILD_DIR}/captured.png"
REFERENCE_PNG="${BUILD_DIR}/reference.png"
DIFF_PNG="${BUILD_DIR}/diff.png"
MAX_CYCLES="${ICEBOY_UART_ROM_MAX_CYCLES:-40000000}"
COMPLETED_FRAMES="${ICEBOY_UART_ROM_COMPLETED_FRAMES:-24}"
PROGRESS_INTERVAL="${ICEBOY_UART_ROM_PROGRESS_INTERVAL:-0}"
RESET_RELEASE_CYCLES="${ICEBOY_UART_ROM_RESET_RELEASE_CYCLES:-70000}"
ROM_PREFIX_LEN="${ICEBOY_UART_ROM_ROM_PREFIX_LEN:-1024}"

if [[ "$DRY_RUN" == "1" ]]; then
    echo "prepare ${VERILOG_DST} from ${VERILOG_SRC}"
    echo "wrapper ${WRAPPER_SRC}"
    echo "main ${MAIN_SRC}"
    echo "rom ${ROM_PATH}"
    echo "expected-tool ${EXPECTED_TOOL}"
    if [[ "$SKIP_BUILD" == "1" ]]; then
        echo "skip swim build"
    fi
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python tools/prepare_verilator_sv.py "$VERILOG_SRC" "$VERILOG_DST"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$EXPECTED_TOOL" "--out=${EXPECTED_RAW}"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$VERILATOR_BIN" --cc "$VERILOG_DST" "$WRAPPER_SRC" --top-module icebreaker_uart_rom_top_verilator_wrapper --exe "$MAIN_SRC" --build -j 0 -O3 --Mdir "$BUILD_DIR" -o "$(basename "$RUNNER_BIN")"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$RUNNER_BIN" "--rom-path=${ROM_PATH}" "--rom-prefix-len=${ROM_PREFIX_LEN}" "--expected-raw=${EXPECTED_RAW}" "--captured-raw=${CAPTURED_RAW}" "--captured-png=${CAPTURED_PNG}" "--reference-png=${REFERENCE_PNG}" "--diff-png=${DIFF_PNG}" "--max-cycles=${MAX_CYCLES}" "--completed-frames=${COMPLETED_FRAMES}" "--progress-interval=${PROGRESS_INTERVAL}" "--reset-release-cycles=${RESET_RELEASE_CYCLES}"
    printf '\n'
    exit 0
fi

mkdir -p "$BUILD_DIR"
"${ICEBOY_ROOT}/tools/ensure_swim_python_deps.sh"

if [[ "$SKIP_BUILD" != "1" ]]; then
    "$SWIM_BIN" build
fi

"$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python tools/prepare_verilator_sv.py "$VERILOG_SRC" "$VERILOG_DST"
"$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$EXPECTED_TOOL" "--out=${EXPECTED_RAW}"

"$VERILATOR_BIN" \
    --cc "$VERILOG_DST" "$WRAPPER_SRC" \
    --top-module icebreaker_uart_rom_top_verilator_wrapper \
    --exe "$MAIN_SRC" \
    --build \
    -j 0 \
    -O3 \
    --Mdir "$BUILD_DIR" \
    -o "$(basename "$RUNNER_BIN")"

"$RUNNER_BIN" \
    "--rom-path=${ROM_PATH}" \
    "--rom-prefix-len=${ROM_PREFIX_LEN}" \
    "--expected-raw=${EXPECTED_RAW}" \
    "--captured-raw=${CAPTURED_RAW}" \
    "--captured-png=${CAPTURED_PNG}" \
    "--reference-png=${REFERENCE_PNG}" \
    "--diff-png=${DIFF_PNG}" \
    "--max-cycles=${MAX_CYCLES}" \
    "--completed-frames=${COMPLETED_FRAMES}" \
    "--progress-interval=${PROGRESS_INTERVAL}" \
    "--reset-release-cycles=${RESET_RELEASE_CYCLES}"
