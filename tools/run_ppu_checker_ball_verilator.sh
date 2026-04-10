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

BUILD_DIR="${ICEBOY_ROOT}/build/rom_verilator/test_ppu_checker_ball_native"
VERILOG_SRC="${ICEBOY_ROOT}/build/spade.sv"
VERILOG_DST="${ICEBOY_ROOT}/build/spade.verilator.sv"
WRAPPER_SRC="${ICEBOY_ROOT}/test/harness/verilog/soc_rom_top_verilator_wrapper.sv"
MAIN_SRC="${ICEBOY_ROOT}/tools/verilator/dmg_acid2_main.cpp"
RUNNER_BIN="${BUILD_DIR}/ppu_checker_ball_runner"
WRITE_EXPECTED="${ICEBOY_ROOT}/tools/write_checkpoint_shaded_frame.py"
COMPARE_TOOL="${ICEBOY_ROOT}/tools/compare_shaded_frame.py"
CHECKPOINT_PC_TOOL="${ICEBOY_ROOT}/tools/resolve_checkpoint_pc.py"
MAX_MCYCLES="${ICEBOY_PPU_CHECKER_BALL_MAX_MCYCLES:-160000}"
PROGRESS_INTERVAL="${ICEBOY_PPU_CHECKER_BALL_PROGRESS_INTERVAL:-0}"

ROM_IDS=(CHECKER_BALL CHECKER_BALL_CANCEL)
if [[ "${ICEBOY_PPU_CHECKER_BALL_INCLUDE_RED:-0}" == "1" ]]; then
    ROM_IDS+=(CHECKER_BALL_CANCEL_OVERLAP)
fi

settles_for_rom() {
    case "$1" in
        CHECKER_BALL)
            echo "1 2 3"
            ;;
        CHECKER_BALL_CANCEL)
            echo "1"
            ;;
        CHECKER_BALL_CANCEL_OVERLAP)
            echo "1"
            ;;
        *)
            iceboy_die "unsupported checker-ball rom '$1'"
            ;;
    esac
}

checkpoint_frames_for_rom() {
    case "$1" in
        CHECKER_BALL)
            echo "3 4 5"
            ;;
        CHECKER_BALL_CANCEL)
            echo "2"
            ;;
        CHECKER_BALL_CANCEL_OVERLAP)
            echo "2"
            ;;
        *)
            iceboy_die "unsupported checker-ball rom '$1'"
            ;;
    esac
}

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
        echo "rom id: ${rom_id}"
        read -r -a expected_settles <<<"$(settles_for_rom "$rom_id")"
        read -r -a checkpoint_completed_frames <<<"$(checkpoint_frames_for_rom "$rom_id")"
        echo "expected settles: ${expected_settles[*]}"
        echo "checkpoint completed frames: ${checkpoint_completed_frames[*]}"
        rom_path="${ICEBOY_ROOT}/bench/roms/out/${rom_id}.gb"
        sym_path="${ICEBOY_ROOT}/bench/roms/out/${rom_id}.sym"
        checkpoint_pc="$("$PYTHON_BIN" "$CHECKPOINT_PC_TOOL" "--sym=${sym_path}")"
        for index in "${!expected_settles[@]}"; do
            settle="${expected_settles[$index]}"
            checkpoint_completed="${checkpoint_completed_frames[$index]}"
            expected_raw="${BUILD_DIR}/${rom_id}.frame${settle}.expected.raw"
            actual_raw="${BUILD_DIR}/${rom_id}.frame${settle}.actual.raw"
            actual_png="${BUILD_DIR}/${rom_id}.frame${settle}.actual.png"
            trace_path="${BUILD_DIR}/${rom_id}.frame${settle}.trace.jsonl"
            printf 'DRY RUN:'
            printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$WRITE_EXPECTED" "--rom=${rom_path}" "--sym=${sym_path}" "--settle-rendered-frames=${settle}" "--output-raw=${expected_raw}"
            printf '\n'
            printf 'DRY RUN:'
            printf ' %q' "$RUNNER_BIN" "--rom=${rom_path}" "--frame-capture=${actual_raw}" "--trace=${trace_path}" "--max-mcycles=${MAX_MCYCLES}" "--progress-interval=${PROGRESS_INTERVAL}" "--checkpoint-pc=${checkpoint_pc}" "--checkpoint-completed-frames=${checkpoint_completed}"
            printf '\n'
            printf 'DRY RUN:'
            printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$COMPARE_TOOL" "--raw=${actual_raw}" "--expected-raw=${expected_raw}" "--output-png=${actual_png}"
            printf '\n'
        done
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
    checkpoint_pc="$("$PYTHON_BIN" "$CHECKPOINT_PC_TOOL" "--sym=${sym_path}")"
    read -r -a expected_settles <<<"$(settles_for_rom "$rom_id")"
    read -r -a checkpoint_completed_frames <<<"$(checkpoint_frames_for_rom "$rom_id")"

    for index in "${!expected_settles[@]}"; do
        settle="${expected_settles[$index]}"
        checkpoint_completed="${checkpoint_completed_frames[$index]}"
        expected_raw="${BUILD_DIR}/${rom_id}.frame${settle}.expected.raw"
        actual_raw="${BUILD_DIR}/${rom_id}.frame${settle}.actual.raw"
        actual_png="${BUILD_DIR}/${rom_id}.frame${settle}.actual.png"
        trace_path="${BUILD_DIR}/${rom_id}.frame${settle}.trace.jsonl"
        rm -f "$expected_raw" "$actual_raw" "$actual_png" "$trace_path"
        echo "[checker-ball] ${rom_id} settle ${settle} via completed frame ${checkpoint_completed}"
        "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$WRITE_EXPECTED" \
            "--rom=${rom_path}" \
            "--sym=${sym_path}" \
            "--settle-rendered-frames=${settle}" \
            "--output-raw=${expected_raw}"
        "$RUNNER_BIN" \
            "--rom=${rom_path}" \
            "--frame-capture=${actual_raw}" \
            "--trace=${trace_path}" \
            "--max-mcycles=${MAX_MCYCLES}" \
            "--progress-interval=${PROGRESS_INTERVAL}" \
            "--checkpoint-pc=${checkpoint_pc}" \
            "--checkpoint-completed-frames=${checkpoint_completed}"
        "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$COMPARE_TOOL" \
            "--raw=${actual_raw}" \
            "--expected-raw=${expected_raw}" \
            "--output-png=${actual_png}"
    done
done
