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

BUILD_DIR="${ICEBOY_ROOT}/build/rom_verilator/test_hardware_soc_core_joypad_native"
BG_BUILD_DIR="${ICEBOY_ROOT}/build/rom_verilator/test_hardware_soc_core_native"
VERILOG_SRC="${ICEBOY_ROOT}/build/spade.sv"
VERILOG_DST="${ICEBOY_ROOT}/build/spade.verilator.sv"
WRAPPER_SRC="${ICEBOY_ROOT}/test/harness/verilog/hardware_soc_core_verilator_wrapper.sv"
MAIN_SRC="${ICEBOY_ROOT}/tools/verilator/hardware_soc_core_main.cpp"
RUNNER_BIN="${BUILD_DIR}/hardware_soc_core_joypad_runner"
EXPECTED_TOOL="${ICEBOY_ROOT}/bench/ref/joypad_bg_smoke.py"
COMPARE_TOOL="${ICEBOY_ROOT}/tools/compare_shaded_frame.py"
SCHEDULE_WRITER="${ICEBOY_ROOT}/tools/write_action_script_joypad_schedule.py"
ROM_PATH="${ICEBOY_ROOT}/bench/roms/out/joypad_bg_smoke.gb"
ACTION_SCRIPT="${ICEBOY_ROOT}/bench/actions/joypad_bg_smoke.yaml"
ROM_MEM_PATH="${BUILD_DIR}/joypad_bg_smoke_rom_2k.mem"
BG_ROM_PATH="${ICEBOY_ROOT}/bench/roms/out/BG_STATIC.gb"
BG_ROM_MEM_PATH="${BG_BUILD_DIR}/bg_static_rom_1k.mem"
EXPECTED_RAW="${BUILD_DIR}/joypad_bg_smoke.expected.raw"
FRAME_CAPTURE="${BUILD_DIR}/joypad_bg_smoke.actual.raw"
FRAME_PNG="${BUILD_DIR}/joypad_bg_smoke.actual.png"
TRACE_PATH="${BUILD_DIR}/joypad_bg_smoke.trace.jsonl"
SCHEDULE_PATH="${BUILD_DIR}/joypad_bg_smoke.schedule.txt"
MAX_CYCLES="${ICEBOY_HARDWARE_SOC_CORE_JOYPAD_MAX_CYCLES:-30000000}"
COMPLETED_FRAMES="${ICEBOY_HARDWARE_SOC_CORE_JOYPAD_COMPLETED_FRAMES:-20}"
PROGRESS_INTERVAL="${ICEBOY_HARDWARE_SOC_CORE_JOYPAD_PROGRESS_INTERVAL:-0}"
EMIT_TRACE="${ICEBOY_HARDWARE_SOC_CORE_JOYPAD_TRACE:-0}"

if [[ "$DRY_RUN" == "1" ]]; then
    echo "prepare ${VERILOG_DST} from ${VERILOG_SRC}"
    echo "build dir ${BUILD_DIR}"
    if [[ "$SKIP_BUILD" == "1" ]]; then
        echo "skip swim build"
    fi
    echo "wrapper ${WRAPPER_SRC}"
    echo "main ${MAIN_SRC}"
    echo "expected-tool ${EXPECTED_TOOL}"
    echo "compare-tool ${COMPARE_TOOL}"
    echo "schedule-writer ${SCHEDULE_WRITER}"
    echo "rom ${ROM_PATH}"
    echo "action-script ${ACTION_SCRIPT}"
    echo "rom-mem ${ROM_MEM_PATH}"
    echo "bg-rom ${BG_ROM_PATH}"
    echo "bg-rom-mem ${BG_ROM_MEM_PATH}"
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python tools/prepare_verilator_sv.py "$VERILOG_SRC" "$VERILOG_DST"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' python3 -c "from pathlib import Path; rom = Path('${ROM_PATH}').read_bytes()[:2048]; Path('${ROM_MEM_PATH}').write_text(''.join(f'{byte:02x}\\n' for byte in rom), encoding='utf-8')"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' python3 -c "from pathlib import Path; rom = Path('${BG_ROM_PATH}').read_bytes()[:1024]; Path('${BG_ROM_MEM_PATH}').write_text(''.join(f'{byte:02x}\\n' for byte in rom), encoding='utf-8')"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$VERILATOR_BIN" --cc "$VERILOG_DST" "$WRAPPER_SRC" --top-module hardware_soc_core_verilator_wrapper --exe "$MAIN_SRC" --build -j 0 --Mdir "$BUILD_DIR" -o "$(basename "$RUNNER_BIN")"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$EXPECTED_TOOL" "--rom=${ROM_PATH}" "--action-script=${ACTION_SCRIPT}" "--out=${EXPECTED_RAW}"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$SCHEDULE_WRITER" "--action-script=${ACTION_SCRIPT}" "--frame-count=${COMPLETED_FRAMES}" "--output=${SCHEDULE_PATH}"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$RUNNER_BIN" "--rom-id=joypad_bg_smoke" "--expected-raw=${EXPECTED_RAW}" "--frame-capture=${FRAME_CAPTURE}" "--max-cycles=${MAX_CYCLES}" "--completed-frames=${COMPLETED_FRAMES}" "--progress-interval=${PROGRESS_INTERVAL}" "--joypad-schedule=${SCHEDULE_PATH}"
    if [[ "$EMIT_TRACE" == "1" ]]; then
        printf ' %q' "--trace=${TRACE_PATH}"
    fi
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$COMPARE_TOOL" "--raw=${FRAME_CAPTURE}" "--expected-raw=${EXPECTED_RAW}" "--output-png=${FRAME_PNG}"
    printf '\n'
    exit 0
fi

mkdir -p "$BUILD_DIR" "$BG_BUILD_DIR"
"${ICEBOY_ROOT}/tools/ensure_swim_python_deps.sh"

python3 - <<PY
from pathlib import Path
rom = Path("${ROM_PATH}").read_bytes()[:2048]
Path("${ROM_MEM_PATH}").write_text("".join(f"{byte:02x}\n" for byte in rom), encoding="utf-8")
PY
python3 - <<PY
from pathlib import Path
rom = Path("${BG_ROM_PATH}").read_bytes()[:1024]
Path("${BG_ROM_MEM_PATH}").write_text("".join(f"{byte:02x}\n" for byte in rom), encoding="utf-8")
PY

if [[ "$SKIP_BUILD" != "1" ]]; then
    "$SWIM_BIN" build
fi

"$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python tools/prepare_verilator_sv.py "$VERILOG_SRC" "$VERILOG_DST"
"$VERILATOR_BIN" \
    --cc "$VERILOG_DST" "$WRAPPER_SRC" \
    --top-module hardware_soc_core_verilator_wrapper \
    --exe "$MAIN_SRC" \
    --build \
    -j 0 \
    -O3 \
    --Mdir "$BUILD_DIR" \
    -o "$(basename "$RUNNER_BIN")"

rm -f "$EXPECTED_RAW" "$FRAME_CAPTURE" "$FRAME_PNG" "$TRACE_PATH" "$SCHEDULE_PATH"
"$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$EXPECTED_TOOL" \
    "--rom=${ROM_PATH}" \
    "--action-script=${ACTION_SCRIPT}" \
    "--out=${EXPECTED_RAW}"
"$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$SCHEDULE_WRITER" \
    "--action-script=${ACTION_SCRIPT}" \
    "--frame-count=${COMPLETED_FRAMES}" \
    "--output=${SCHEDULE_PATH}"
RUNNER_ARGS=(
    "--rom-id=joypad_bg_smoke"
    "--expected-raw=${EXPECTED_RAW}"
    "--frame-capture=${FRAME_CAPTURE}"
    "--max-cycles=${MAX_CYCLES}"
    "--completed-frames=${COMPLETED_FRAMES}"
    "--progress-interval=${PROGRESS_INTERVAL}"
    "--joypad-schedule=${SCHEDULE_PATH}"
)
if [[ "$EMIT_TRACE" == "1" ]]; then
    RUNNER_ARGS+=("--trace=${TRACE_PATH}")
fi
"$RUNNER_BIN" "${RUNNER_ARGS[@]}"
"$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$COMPARE_TOOL" \
    "--raw=${FRAME_CAPTURE}" \
    "--expected-raw=${EXPECTED_RAW}" \
    "--output-png=${FRAME_PNG}"
