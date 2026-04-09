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

BUILD_DIR="${ICEBOY_ROOT}/build/rom_verilator/test_dmg_acid2_native"
VERILOG_SRC="${ICEBOY_ROOT}/build/spade.sv"
VERILOG_DST="${ICEBOY_ROOT}/build/spade.verilator.sv"
WRAPPER_SRC="${ICEBOY_ROOT}/test/harness/verilog/soc_rom_top_verilator_wrapper.sv"
MAIN_SRC="${ICEBOY_ROOT}/tools/verilator/dmg_acid2_main.cpp"
RUNNER_BIN="${BUILD_DIR}/dmg_acid2_runner"
ROM_PATH="${ICEBOY_ROOT}/bench/external/dmg-acid2/dmg-acid2.gb"
EXPECTED_FRAME="${ICEBOY_ROOT}/bench/expected/suite_owned/dmg-acid2/reference-dmg.png"
RAW_CAPTURE="${BUILD_DIR}/dmg_acid2.frame.raw"
PNG_CAPTURE="${BUILD_DIR}/dmg_acid2.frame.png"
TRACE_CAPTURE="${BUILD_DIR}/dmg_acid2.trace.jsonl"
MAX_MCYCLES="${ICEBOY_DMG_ACID2_MAX_MCYCLES:-1800000}"
STABLE_FRAMES="${ICEBOY_DMG_ACID2_STABLE_FRAMES:-2}"
COMPLETED_FRAMES="${ICEBOY_DMG_ACID2_COMPLETED_FRAMES:-84}"
PROGRESS_INTERVAL="${ICEBOY_DMG_ACID2_PROGRESS_INTERVAL:-0}"

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
    printf ' %q' "$VERILATOR_BIN" --cc "$VERILOG_DST" "$WRAPPER_SRC" --top-module soc_rom_top_verilator_wrapper --exe "$MAIN_SRC" --build -j 0 --Mdir "$BUILD_DIR" -o "$(basename "$RUNNER_BIN")"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$RUNNER_BIN" "--rom=${ROM_PATH}" "--frame-capture=${RAW_CAPTURE}" "--trace=${TRACE_CAPTURE}" "--max-mcycles=${MAX_MCYCLES}" "--stable-frames=${STABLE_FRAMES}" "--completed-frames=${COMPLETED_FRAMES}" "--progress-interval=${PROGRESS_INTERVAL}"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python tools/compare_shaded_frame.py "--raw=${RAW_CAPTURE}" "--expected=${EXPECTED_FRAME}" "--output-png=${PNG_CAPTURE}"
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
    --top-module soc_rom_top_verilator_wrapper \
    --exe "$MAIN_SRC" \
    --build \
    -j 0 \
    -O3 \
    --Mdir "$BUILD_DIR" \
    -o "$(basename "$RUNNER_BIN")"

rm -f "$RAW_CAPTURE" "$PNG_CAPTURE" "$TRACE_CAPTURE"
"$RUNNER_BIN" \
    "--rom=${ROM_PATH}" \
    "--frame-capture=${RAW_CAPTURE}" \
    "--trace=${TRACE_CAPTURE}" \
    "--max-mcycles=${MAX_MCYCLES}" \
    "--stable-frames=${STABLE_FRAMES}" \
    "--completed-frames=${COMPLETED_FRAMES}" \
    "--progress-interval=${PROGRESS_INTERVAL}"

"$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python tools/compare_shaded_frame.py \
    "--raw=${RAW_CAPTURE}" \
    "--expected=${EXPECTED_FRAME}" \
    "--output-png=${PNG_CAPTURE}"
