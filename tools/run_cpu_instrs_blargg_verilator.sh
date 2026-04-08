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

BUILD_DIR="${ICEBOY_ROOT}/build/rom_verilator/test_cpu_instrs_blargg_native"
VERILOG_SRC="${ICEBOY_ROOT}/build/spade.sv"
VERILOG_DST="${ICEBOY_ROOT}/build/spade.verilator.sv"
WRAPPER_SRC="${ICEBOY_ROOT}/test/harness/verilog/cpu_test_top_verilator_wrapper.sv"
MAIN_SRC="${ICEBOY_ROOT}/tools/verilator/cpu_instrs_blargg_main.cpp"
ROM_PATH="${ICEBOY_ROOT}/roms/cpu_instrs.gb"
RUNNER_BIN="${BUILD_DIR}/cpu_instrs_blargg_runner"
SERIAL_CAPTURE="${BUILD_DIR}/cpu_instrs.serial.out"
EXPECTED_SERIAL="${ICEBOY_ROOT}/bench/artifacts/cpu_instrs/pyboy_serial.txt"
MAX_MCYCLES="${ICEBOY_CPU_INSTRS_MAX_MCYCLES:-80000000}"
STOP_AT_SERIAL_COUNT="$(wc -c < "${EXPECTED_SERIAL}" | tr -d '[:space:]')"

if [[ "$DRY_RUN" == "1" ]]; then
    echo "prepare ${VERILOG_DST} from ${VERILOG_SRC}"
    echo "build dir ${BUILD_DIR}"
    if [[ "$SKIP_BUILD" == "1" ]]; then
        echo "skip swim build"
    fi
    echo "wrapper ${WRAPPER_SRC}"
    echo "main ${MAIN_SRC}"
    echo "rom ${ROM_PATH}"
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python tools/prepare_verilator_sv.py "$VERILOG_SRC" "$VERILOG_DST"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$VERILATOR_BIN" --cc "$VERILOG_DST" "$WRAPPER_SRC" --top-module cpu_test_top_verilator_wrapper --exe "$MAIN_SRC" --build -j 0 --Mdir "$BUILD_DIR" -o "$(basename "$RUNNER_BIN")"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$RUNNER_BIN" "--rom=${ROM_PATH}" "--serial-capture=${SERIAL_CAPTURE}" "--max-mcycles=${MAX_MCYCLES}" "--stop-at-serial-count=${STOP_AT_SERIAL_COUNT}"
    printf '\n'
    exit 0
fi

mkdir -p "$BUILD_DIR"
"${ICEBOY_ROOT}/tools/ensure_swim_python_deps.sh"

if [[ "$SKIP_BUILD" != "1" ]]; then
    "$SWIM_BIN" build
fi

"$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python tools/prepare_verilator_sv.py "$VERILOG_SRC" "$VERILOG_DST"

"$VERILATOR_BIN" \
    --cc "$VERILOG_DST" "$WRAPPER_SRC" \
    --top-module cpu_test_top_verilator_wrapper \
    --exe "$MAIN_SRC" \
    --build \
    -j 0 \
    -O3 \
    --Mdir "$BUILD_DIR" \
    -o "$(basename "$RUNNER_BIN")"

rm -f "$SERIAL_CAPTURE"
"$RUNNER_BIN" \
    "--rom=${ROM_PATH}" \
    "--serial-capture=${SERIAL_CAPTURE}" \
    "--max-mcycles=${MAX_MCYCLES}" \
    "--stop-at-serial-count=${STOP_AT_SERIAL_COUNT}"

cmp -s "$SERIAL_CAPTURE" "$EXPECTED_SERIAL" || {
    echo "cpu_instrs serial output mismatch"
    echo "--- expected"
    cat "$EXPECTED_SERIAL"
    echo "--- actual"
    cat "$SERIAL_CAPTURE"
    exit 1
}
