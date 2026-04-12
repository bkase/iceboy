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
PYTHON_BIN="${ICEBOY_PYTHON_BIN:-python3}"

iceboy_log_tool "uv" "$(iceboy_version_string "$UV_BIN" --version)"
iceboy_log_tool "swim" "$(iceboy_version_string "$SWIM_BIN" --version)"
iceboy_log_tool "verilator" "$(iceboy_version_string "$VERILATOR_BIN" --version)"
iceboy_log_tool "python3" "$(iceboy_version_string "$PYTHON_BIN" --version)"

export PATH="$(dirname "$VERILATOR_BIN"):$(dirname "$SWIM_BIN"):/opt/homebrew/bin:${PATH}"

BUILD_ROOT="${ICEBOY_ROOT}/build/icebreaker_visible"
VERILOG_SRC="${ICEBOY_ROOT}/build/spade.sv"
VERILOG_DST="${ICEBOY_ROOT}/build/spade.verilator.sv"
WRAPPER_SRC="${ICEBOY_ROOT}/test/harness/verilog/icebreaker_visible_top_verilator_wrapper.sv"
MAIN_SRC="${ICEBOY_ROOT}/tools/verilator/icebreaker_visible_top_main.cpp"
BG_EXPECTED_TOOL="${ICEBOY_ROOT}/bench/ref/BG_STATIC.py"
JOYPAD_EXPECTED_TOOL="${ICEBOY_ROOT}/bench/ref/joypad_bg_smoke.py"
SCHEDULE_WRITER="${ICEBOY_ROOT}/tools/write_action_script_joypad_schedule.py"
JOYPAD_ACTION_SCRIPT="${ICEBOY_ROOT}/bench/actions/joypad_bg_smoke.yaml"

BG_BUILD_DIR="${BUILD_ROOT}/bg_static"
BG_RUNNER_BIN="${BG_BUILD_DIR}/icebreaker_visible_bg_static_runner"
BG_EXPECTED_RAW="${BG_BUILD_DIR}/reference.raw"
BG_CAPTURED_RAW="${BG_BUILD_DIR}/captured.raw"
BG_CAPTURED_PNG="${BG_BUILD_DIR}/captured.png"
BG_REFERENCE_PNG="${BG_BUILD_DIR}/reference.png"
BG_DIFF_PNG="${BG_BUILD_DIR}/diff.png"

JOYPAD_BUILD_DIR="${BUILD_ROOT}/joypad_bg_smoke"
JOYPAD_RUNNER_BIN="${JOYPAD_BUILD_DIR}/icebreaker_visible_joypad_runner"
JOYPAD_EXPECTED_RAW="${JOYPAD_BUILD_DIR}/reference.raw"
JOYPAD_CAPTURED_RAW="${JOYPAD_BUILD_DIR}/captured.raw"
JOYPAD_CAPTURED_PNG="${JOYPAD_BUILD_DIR}/captured.png"
JOYPAD_REFERENCE_PNG="${JOYPAD_BUILD_DIR}/reference.png"
JOYPAD_DIFF_PNG="${JOYPAD_BUILD_DIR}/diff.png"
JOYPAD_SCHEDULE="${JOYPAD_BUILD_DIR}/joypad.schedule.txt"

BG_MAX_CYCLES="${ICEBOY_VISIBLE_BG_MAX_CYCLES:-90000000}"
BG_COMPLETED_FRAMES="${ICEBOY_VISIBLE_BG_COMPLETED_FRAMES:-24}"
JOYPAD_MAX_CYCLES="${ICEBOY_VISIBLE_JOYPAD_MAX_CYCLES:-90000000}"
JOYPAD_SETTLE_FRAMES="${ICEBOY_VISIBLE_JOYPAD_SETTLE_FRAMES:-2}"
PROGRESS_INTERVAL="${ICEBOY_VISIBLE_PROGRESS_INTERVAL:-0}"
RESET_RELEASE_CYCLES="${ICEBOY_VISIBLE_RESET_RELEASE_CYCLES:-70000}"

run_bg_dry() {
    printf 'DRY RUN:'
    printf ' %q' "$VERILATOR_BIN" --cc "$VERILOG_DST" "$WRAPPER_SRC" --top-module icebreaker_visible_top_verilator_wrapper -GROM_SELECT=0 --exe "$MAIN_SRC" --build -j 0 -O3 --Mdir "$BG_BUILD_DIR" -o "$(basename "$BG_RUNNER_BIN")"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$BG_EXPECTED_TOOL" "--out=${BG_EXPECTED_RAW}"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$BG_RUNNER_BIN" "--expected-raw=${BG_EXPECTED_RAW}" "--captured-raw=${BG_CAPTURED_RAW}" "--captured-png=${BG_CAPTURED_PNG}" "--reference-png=${BG_REFERENCE_PNG}" "--diff-png=${BG_DIFF_PNG}" "--max-cycles=${BG_MAX_CYCLES}" "--completed-frames=${BG_COMPLETED_FRAMES}" "--progress-interval=${PROGRESS_INTERVAL}" "--reset-release-cycles=${RESET_RELEASE_CYCLES}"
    printf '\n'
}

run_joypad_dry() {
    printf 'DRY RUN:'
    printf ' %q' "$VERILATOR_BIN" --cc "$VERILOG_DST" "$WRAPPER_SRC" --top-module icebreaker_visible_top_verilator_wrapper -GROM_SELECT=1 --exe "$MAIN_SRC" --build -j 0 -O3 --Mdir "$JOYPAD_BUILD_DIR" -o "$(basename "$JOYPAD_RUNNER_BIN")"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$SCHEDULE_WRITER" "--action-script=${JOYPAD_ACTION_SCRIPT}" "--settle-frames=${JOYPAD_SETTLE_FRAMES}" "--output=${JOYPAD_SCHEDULE}"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$JOYPAD_EXPECTED_TOOL" "--action-script=${JOYPAD_ACTION_SCRIPT}" "--out=${JOYPAD_EXPECTED_RAW}"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$JOYPAD_RUNNER_BIN" "--expected-raw=${JOYPAD_EXPECTED_RAW}" "--captured-raw=${JOYPAD_CAPTURED_RAW}" "--captured-png=${JOYPAD_CAPTURED_PNG}" "--reference-png=${JOYPAD_REFERENCE_PNG}" "--diff-png=${JOYPAD_DIFF_PNG}" "--joypad-schedule=${JOYPAD_SCHEDULE}" "--max-cycles=${JOYPAD_MAX_CYCLES}" "--completed-frames=\$(wc -l < ${JOYPAD_SCHEDULE})" "--progress-interval=${PROGRESS_INTERVAL}" "--reset-release-cycles=${RESET_RELEASE_CYCLES}"
    printf '\n'
}

if [[ "$DRY_RUN" == "1" ]]; then
    echo "prepare ${VERILOG_DST} from ${VERILOG_SRC}"
    echo "wrapper ${WRAPPER_SRC}"
    echo "main ${MAIN_SRC}"
    echo "bg-expected-tool ${BG_EXPECTED_TOOL}"
    echo "joypad-expected-tool ${JOYPAD_EXPECTED_TOOL}"
    echo "schedule-writer ${SCHEDULE_WRITER}"
    if [[ "$SKIP_BUILD" == "1" ]]; then
        echo "skip swim build"
    fi
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python tools/prepare_verilator_sv.py "$VERILOG_SRC" "$VERILOG_DST"
    printf '\n'
    run_bg_dry
    run_joypad_dry
    exit 0
fi

mkdir -p "$BG_BUILD_DIR" "$JOYPAD_BUILD_DIR"
"${ICEBOY_ROOT}/tools/ensure_swim_python_deps.sh"

if [[ "$SKIP_BUILD" != "1" ]]; then
    "$SWIM_BIN" build
fi

"$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python tools/prepare_verilator_sv.py "$VERILOG_SRC" "$VERILOG_DST"

rm -f "$BG_EXPECTED_RAW" "$BG_CAPTURED_RAW" "$BG_CAPTURED_PNG" "$BG_REFERENCE_PNG" "$BG_DIFF_PNG"
rm -f "$JOYPAD_EXPECTED_RAW" "$JOYPAD_CAPTURED_RAW" "$JOYPAD_CAPTURED_PNG" "$JOYPAD_REFERENCE_PNG" "$JOYPAD_DIFF_PNG" "$JOYPAD_SCHEDULE"

"$VERILATOR_BIN" \
    --cc "$VERILOG_DST" "$WRAPPER_SRC" \
    --top-module icebreaker_visible_top_verilator_wrapper \
    -GROM_SELECT=0 \
    --exe "$MAIN_SRC" \
    --build \
    -j 0 \
    -O3 \
    --Mdir "$BG_BUILD_DIR" \
    -o "$(basename "$BG_RUNNER_BIN")"

"$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$BG_EXPECTED_TOOL" \
    "--out=${BG_EXPECTED_RAW}"

"$BG_RUNNER_BIN" \
    "--expected-raw=${BG_EXPECTED_RAW}" \
    "--captured-raw=${BG_CAPTURED_RAW}" \
    "--captured-png=${BG_CAPTURED_PNG}" \
    "--reference-png=${BG_REFERENCE_PNG}" \
    "--diff-png=${BG_DIFF_PNG}" \
    "--max-cycles=${BG_MAX_CYCLES}" \
    "--completed-frames=${BG_COMPLETED_FRAMES}" \
    "--progress-interval=${PROGRESS_INTERVAL}" \
    "--reset-release-cycles=${RESET_RELEASE_CYCLES}"

"$VERILATOR_BIN" \
    --cc "$VERILOG_DST" "$WRAPPER_SRC" \
    --top-module icebreaker_visible_top_verilator_wrapper \
    -GROM_SELECT=1 \
    --exe "$MAIN_SRC" \
    --build \
    -j 0 \
    -O3 \
    --Mdir "$JOYPAD_BUILD_DIR" \
    -o "$(basename "$JOYPAD_RUNNER_BIN")"

"$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$SCHEDULE_WRITER" \
    "--action-script=${JOYPAD_ACTION_SCRIPT}" \
    "--settle-frames=${JOYPAD_SETTLE_FRAMES}" \
    "--output=${JOYPAD_SCHEDULE}"

JOYPAD_COMPLETED_FRAMES="$(wc -l < "$JOYPAD_SCHEDULE" | tr -d '[:space:]')"

"$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$JOYPAD_EXPECTED_TOOL" \
    "--action-script=${JOYPAD_ACTION_SCRIPT}" \
    "--out=${JOYPAD_EXPECTED_RAW}"

"$JOYPAD_RUNNER_BIN" \
    "--expected-raw=${JOYPAD_EXPECTED_RAW}" \
    "--captured-raw=${JOYPAD_CAPTURED_RAW}" \
    "--captured-png=${JOYPAD_CAPTURED_PNG}" \
    "--reference-png=${JOYPAD_REFERENCE_PNG}" \
    "--diff-png=${JOYPAD_DIFF_PNG}" \
    "--joypad-schedule=${JOYPAD_SCHEDULE}" \
    "--max-cycles=${JOYPAD_MAX_CYCLES}" \
    "--completed-frames=${JOYPAD_COMPLETED_FRAMES}" \
    "--progress-interval=${PROGRESS_INTERVAL}" \
    "--reset-release-cycles=${RESET_RELEASE_CYCLES}"

echo "icebreaker visible full-stack artifacts written under ${BUILD_ROOT}"
