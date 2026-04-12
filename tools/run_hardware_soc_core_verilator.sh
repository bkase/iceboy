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

BUILD_DIR="${ICEBOY_ROOT}/build/rom_verilator/test_hardware_soc_core_native"
VERILOG_SRC="${ICEBOY_ROOT}/build/spade.sv"
VERILOG_DST="${ICEBOY_ROOT}/build/spade.verilator.sv"
WRAPPER_SRC="${ICEBOY_ROOT}/test/harness/verilog/hardware_soc_core_verilator_wrapper.sv"
MAIN_SRC="${ICEBOY_ROOT}/tools/verilator/hardware_soc_core_main.cpp"
RUNNER_BIN="${BUILD_DIR}/hardware_soc_core_runner"
EXPECTED_TOOL="${ICEBOY_ROOT}/tools/write_rendered_shaded_frame.py"
ROM_PATH="${ICEBOY_ROOT}/bench/roms/out/BG_STATIC.gb"
ROM_MEM_PATH="${BUILD_DIR}/bg_static_rom_1k.mem"
EXPECTED_RAW="${BUILD_DIR}/hardware_soc_core.expected.raw"
FRAME_CAPTURE="${BUILD_DIR}/hardware_soc_core.actual.raw"
TRACE_PATH="${BUILD_DIR}/hardware_soc_core.trace.jsonl"
MAX_CYCLES="${ICEBOY_HARDWARE_SOC_CORE_MAX_CYCLES:-4000000}"
COMPLETED_FRAMES="${ICEBOY_HARDWARE_SOC_CORE_COMPLETED_FRAMES:-3}"
PROGRESS_INTERVAL="${ICEBOY_HARDWARE_SOC_CORE_PROGRESS_INTERVAL:-0}"
EMIT_TRACE="${ICEBOY_HARDWARE_SOC_CORE_TRACE:-0}"

if [[ "$DRY_RUN" == "1" ]]; then
    echo "prepare ${VERILOG_DST} from ${VERILOG_SRC}"
    echo "build dir ${BUILD_DIR}"
    if [[ "$SKIP_BUILD" == "1" ]]; then
        echo "skip swim build"
    fi
    echo "wrapper ${WRAPPER_SRC}"
    echo "main ${MAIN_SRC}"
    echo "expected-tool ${EXPECTED_TOOL}"
    echo "rom ${ROM_PATH}"
    echo "rom-mem ${ROM_MEM_PATH}"
    echo "expected-raw ${EXPECTED_RAW}"
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python tools/prepare_verilator_sv.py "$VERILOG_SRC" "$VERILOG_DST"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' python3 -c "from pathlib import Path; rom = Path('${ROM_PATH}').read_bytes()[:1024]; Path('${ROM_MEM_PATH}').write_text(''.join(f'{byte:02x}\\n' for byte in rom), encoding='utf-8')"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$EXPECTED_TOOL" "--rom=${ROM_PATH}" "--output-raw=${EXPECTED_RAW}" "--frame-batches=3"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$VERILATOR_BIN" --cc "$VERILOG_DST" "$WRAPPER_SRC" --top-module hardware_soc_core_verilator_wrapper --exe "$MAIN_SRC" --build -j 0 --Mdir "$BUILD_DIR" -o "$(basename "$RUNNER_BIN")"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$RUNNER_BIN" "--expected-raw=${EXPECTED_RAW}" "--frame-capture=${FRAME_CAPTURE}" "--max-cycles=${MAX_CYCLES}" "--completed-frames=${COMPLETED_FRAMES}" "--progress-interval=${PROGRESS_INTERVAL}"
    if [[ "$EMIT_TRACE" == "1" ]]; then
        printf ' %q' "--trace=${TRACE_PATH}"
    fi
    printf '\n'
    exit 0
fi

mkdir -p "$BUILD_DIR"
"${ICEBOY_ROOT}/tools/ensure_swim_python_deps.sh"

python3 - <<PY
from pathlib import Path
rom = Path("${ROM_PATH}").read_bytes()[:1024]
Path("${ROM_MEM_PATH}").write_text("".join(f"{byte:02x}\n" for byte in rom), encoding="utf-8")
PY

if [[ "$SKIP_BUILD" != "1" ]]; then
    "$SWIM_BIN" build
fi

"$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python tools/prepare_verilator_sv.py "$VERILOG_SRC" "$VERILOG_DST"
"$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$EXPECTED_TOOL" \
    "--rom=${ROM_PATH}" \
    "--output-raw=${EXPECTED_RAW}" \
    "--frame-batches=3"

"$VERILATOR_BIN" \
    --cc "$VERILOG_DST" "$WRAPPER_SRC" \
    --top-module hardware_soc_core_verilator_wrapper \
    --exe "$MAIN_SRC" \
    --build \
    -j 0 \
    -O3 \
    --Mdir "$BUILD_DIR" \
    -o "$(basename "$RUNNER_BIN")"

rm -f "$FRAME_CAPTURE" "$TRACE_PATH"
RUNNER_ARGS=(
    "--expected-raw=${EXPECTED_RAW}"
    "--frame-capture=${FRAME_CAPTURE}"
    "--max-cycles=${MAX_CYCLES}"
    "--completed-frames=${COMPLETED_FRAMES}"
    "--progress-interval=${PROGRESS_INTERVAL}"
)
if [[ "$EMIT_TRACE" == "1" ]]; then
    RUNNER_ARGS+=("--trace=${TRACE_PATH}")
fi
"$RUNNER_BIN" "${RUNNER_ARGS[@]}"
