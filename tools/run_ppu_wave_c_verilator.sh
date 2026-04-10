#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
SKIP_BUILD=0
ROM_IDS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        --skip-build)
            SKIP_BUILD=1
            ;;
        -t|--rom-id)
            shift
            [[ $# -gt 0 ]] || iceboy_die "missing value for --rom-id"
            ROM_IDS+=("$1")
            ;;
        *)
            iceboy_die "unsupported argument '$1'"
            ;;
    esac
    shift
done

if [[ "${#ROM_IDS[@]}" -eq 0 ]]; then
    ROM_IDS=(OBJ_10_PER_LINE OBJ_X_HIDDEN_STILL_COUNTS)
    if [[ "${ICEBOY_PPU_WAVE_C_INCLUDE_RED:-0}" == "1" ]]; then
        ROM_IDS+=(OBJ_BASIC OBJ_PRIORITY OBJ_8X16 OBJ_FLIP OBJ_BG_MASK OBJ_FETCH_CANCEL_LCDC1)
    fi
fi

UV_BIN="$(iceboy_require_command "uv" "ICEBOY_UV_BIN" "$(iceboy_uv_bin)")"
SWIM_BIN="$(iceboy_require_command "swim" "ICEBOY_SWIM_BIN" "$(iceboy_swim_bin)")"
VERILATOR_BIN="$(iceboy_require_command "verilator" "ICEBOY_VERILATOR_BIN" "$(iceboy_verilator_bin)")"
PYTHON_BIN="${ICEBOY_PYTHON_BIN:-python3}"

iceboy_log_tool "uv" "$(iceboy_version_string "$UV_BIN" --version)"
iceboy_log_tool "swim" "$(iceboy_version_string "$SWIM_BIN" --version)"
iceboy_log_tool "verilator" "$(iceboy_version_string "$VERILATOR_BIN" --version)"
iceboy_log_tool "python3" "$(iceboy_version_string "$PYTHON_BIN" --version)"

export PATH="$(dirname "$VERILATOR_BIN"):$(dirname "$SWIM_BIN"):/opt/homebrew/bin:${PATH}"

BUILD_DIR="${ICEBOY_ROOT}/build/rom_verilator/test_ppu_wave_c_native"
VERILOG_SRC="${ICEBOY_ROOT}/build/spade.sv"
VERILOG_DST="${ICEBOY_ROOT}/build/spade.verilator.sv"
WRAPPER_SRC="${ICEBOY_ROOT}/test/harness/verilog/soc_rom_top_verilator_wrapper.sv"
MAIN_SRC="${ICEBOY_ROOT}/tools/verilator/dmg_acid2_main.cpp"
RUNNER_BIN="${BUILD_DIR}/ppu_wave_c_runner"
WRITE_EXPECTED="${ICEBOY_ROOT}/tools/write_checkpoint_shaded_frame.py"
COMPARE_TOOL="${ICEBOY_ROOT}/tools/compare_shaded_frame.py"
CHECKPOINT_PC_TOOL="${ICEBOY_ROOT}/tools/resolve_checkpoint_pc.py"
MAX_MCYCLES="${ICEBOY_PPU_WAVE_C_MAX_MCYCLES:-120000}"
STABLE_FRAMES="${ICEBOY_PPU_WAVE_C_STABLE_FRAMES:-1}"
COMPLETED_FRAMES="${ICEBOY_PPU_WAVE_C_COMPLETED_FRAMES:-3}"
CHECKPOINT_COMPLETED_FRAMES="${ICEBOY_PPU_WAVE_C_CHECKPOINT_COMPLETED_FRAMES:-2}"
PROGRESS_INTERVAL="${ICEBOY_PPU_WAVE_C_PROGRESS_INTERVAL:-0}"

if [[ "$DRY_RUN" == "1" ]]; then
    echo "prepare ${VERILOG_DST} from ${VERILOG_SRC}"
    echo "build dir ${BUILD_DIR}"
    if [[ "$SKIP_BUILD" == "1" ]]; then
        echo "skip swim build"
    fi
    echo "wrapper ${WRAPPER_SRC}"
    echo "main ${MAIN_SRC}"
    echo "checkpoint-writer ${WRITE_EXPECTED}"
    echo "checkpoint-pc-tool ${CHECKPOINT_PC_TOOL}"
    echo "compare-tool ${COMPARE_TOOL}"
    echo "rom ids: ${ROM_IDS[*]}"
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python tools/prepare_verilator_sv.py "$VERILOG_SRC" "$VERILOG_DST"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$VERILATOR_BIN" --cc "$VERILOG_DST" "$WRAPPER_SRC" --top-module soc_rom_top_verilator_wrapper --exe "$MAIN_SRC" --build -j 0 --Mdir "$BUILD_DIR" -o "$(basename "$RUNNER_BIN")"
    printf '\n'
    for rom_id in "${ROM_IDS[@]}"; do
        rom_path="${ICEBOY_ROOT}/bench/roms/out/${rom_id}.gb"
        sym_path="${ICEBOY_ROOT}/bench/roms/out/${rom_id}.sym"
        expected_raw="${BUILD_DIR}/${rom_id}.expected.raw"
        actual_raw="${BUILD_DIR}/${rom_id}.actual.raw"
        actual_png="${BUILD_DIR}/${rom_id}.actual.png"
        trace_path="${BUILD_DIR}/${rom_id}.trace.jsonl"
        checkpoint_pc="$("$PYTHON_BIN" "$CHECKPOINT_PC_TOOL" "--sym=${sym_path}")"
        printf 'DRY RUN:'
        printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$WRITE_EXPECTED" "--rom=${rom_path}" "--sym=${sym_path}" "--output-raw=${expected_raw}"
        printf '\n'
        printf 'DRY RUN:'
        printf ' %q' "$RUNNER_BIN" "--rom=${rom_path}" "--frame-capture=${actual_raw}" "--trace=${trace_path}" "--max-mcycles=${MAX_MCYCLES}" "--stable-frames=${STABLE_FRAMES}" "--progress-interval=${PROGRESS_INTERVAL}" "--checkpoint-pc=${checkpoint_pc}" "--checkpoint-completed-frames=${CHECKPOINT_COMPLETED_FRAMES}"
        printf '\n'
        printf 'DRY RUN:'
        printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$COMPARE_TOOL" "--raw=${actual_raw}" "--expected-raw=${expected_raw}" "--output-png=${actual_png}"
        printf '\n'
    done
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

for rom_id in "${ROM_IDS[@]}"; do
    rom_path="${ICEBOY_ROOT}/bench/roms/out/${rom_id}.gb"
    sym_path="${ICEBOY_ROOT}/bench/roms/out/${rom_id}.sym"
    expected_raw="${BUILD_DIR}/${rom_id}.expected.raw"
    actual_raw="${BUILD_DIR}/${rom_id}.actual.raw"
    actual_png="${BUILD_DIR}/${rom_id}.actual.png"
    trace_path="${BUILD_DIR}/${rom_id}.trace.jsonl"
    checkpoint_pc="$("$PYTHON_BIN" "$CHECKPOINT_PC_TOOL" "--sym=${sym_path}")"
    rm -f "$expected_raw" "$actual_raw" "$actual_png" "$trace_path"
    echo "[wave-c] ${rom_id}"
    "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$WRITE_EXPECTED" \
        "--rom=${rom_path}" \
        "--sym=${sym_path}" \
        "--output-raw=${expected_raw}"
    "$RUNNER_BIN" \
        "--rom=${rom_path}" \
        "--frame-capture=${actual_raw}" \
        "--trace=${trace_path}" \
        "--max-mcycles=${MAX_MCYCLES}" \
        "--stable-frames=${STABLE_FRAMES}" \
        "--progress-interval=${PROGRESS_INTERVAL}" \
        "--checkpoint-pc=${checkpoint_pc}" \
        "--checkpoint-completed-frames=${CHECKPOINT_COMPLETED_FRAMES}"
    "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$COMPARE_TOOL" \
        "--raw=${actual_raw}" \
        "--expected-raw=${expected_raw}" \
        "--output-png=${actual_png}"
done
