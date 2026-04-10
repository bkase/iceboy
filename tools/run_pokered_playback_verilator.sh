#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
SKIP_BUILD=0
STATE_PATH="../gbxcule/Bulbasaur.state"
ROM_PATH="../gbxcule/red.gb"
SCRIPT_PATH="tools/pokered_walk_script.yaml"
DURATION_SECONDS=10
OUTPUT_MP4="build/pokered_playback/pokered_walk.mp4"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        --skip-build)
            SKIP_BUILD=1
            ;;
        --state=*)
            STATE_PATH="${1#*=}"
            ;;
        --rom=*)
            ROM_PATH="${1#*=}"
            ;;
        --script=*)
            SCRIPT_PATH="${1#*=}"
            ;;
        --seconds=*)
            DURATION_SECONDS="${1#*=}"
            ;;
        --out=*)
            OUTPUT_MP4="${1#*=}"
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

FFMPEG_CMD=()
FFMPEG_VERSION_STRING=""
if [[ -n "${ICEBOY_FFMPEG_BIN:-}" ]]; then
    FFMPEG_CMD=("$(iceboy_require_command "ffmpeg" "ICEBOY_FFMPEG_BIN" "${ICEBOY_FFMPEG_BIN}")")
    FFMPEG_VERSION_STRING="$(iceboy_version_string "${FFMPEG_CMD[0]}" -version)"
elif command -v ffmpeg >/dev/null 2>&1; then
    FFMPEG_CMD=("$(command -v ffmpeg)")
    FFMPEG_VERSION_STRING="$(iceboy_version_string "${FFMPEG_CMD[0]}" -version)"
elif command -v cx >/dev/null 2>&1; then
    FFMPEG_CMD=("$(command -v cx)" "ffmpeg")
    FFMPEG_VERSION_STRING="cx ffmpeg"
else
    iceboy_die "missing ffmpeg; install it, ensure 'cx ffmpeg' works, or set ICEBOY_FFMPEG_BIN"
fi

iceboy_log_tool "uv" "$(iceboy_version_string "$UV_BIN" --version)"
iceboy_log_tool "swim" "$(iceboy_version_string "$SWIM_BIN" --version)"
iceboy_log_tool "verilator" "$(iceboy_version_string "$VERILATOR_BIN" --version)"
iceboy_log_tool "ffmpeg" "${FFMPEG_VERSION_STRING}"
iceboy_log_tool "python3" "$(iceboy_version_string "$PYTHON_BIN" --version)"

export PATH="$(dirname "$VERILATOR_BIN"):$(dirname "$SWIM_BIN"):/opt/homebrew/bin:${PATH}"

BUILD_DIR="${ICEBOY_ROOT}/build/pokered_playback"
VERILOG_SRC="${ICEBOY_ROOT}/build/spade.sv"
VERILOG_DST="${ICEBOY_ROOT}/build/spade.verilator.sv"
WRAPPER_SRC="${ICEBOY_ROOT}/test/harness/verilog/soc_rom_top_verilator_wrapper.sv"
MAIN_SRC="${ICEBOY_ROOT}/tools/verilator/pokered_playback_main.cpp"
RUNNER_BIN="${BUILD_DIR}/pokered_playback_runner"
RESTORE_EXPORTER="${ICEBOY_ROOT}/tools/export_pokered_restore.py"
SCRIPT_EXPORTER="${ICEBOY_ROOT}/tools/export_pokered_walk_script.py"
FRAME_ARTIFACTS="${ICEBOY_ROOT}/tools/pokered_frame_artifacts.py"
RESTORE_DIR="${BUILD_DIR}/restore"
RESTORE_MANIFEST="${RESTORE_DIR}/restore.manifest"
SCRIPT_SCHEDULE="${BUILD_DIR}/walk.schedule"
FRAMES_RAW="${BUILD_DIR}/frames.raw"
FIRST_RAW="${BUILD_DIR}/first.raw"
MID_RAW="${BUILD_DIR}/mid.raw"
LAST_RAW="${BUILD_DIR}/last.raw"
FIRST_PNG="${BUILD_DIR}/first.png"
MID_PNG="${BUILD_DIR}/mid.png"
LAST_PNG="${BUILD_DIR}/last.png"
MAX_MCYCLES=$((DURATION_SECONDS * 1048576 + 262144))
TARGET_FRAMES=$((DURATION_SECONDS * 60))

if [[ "$DRY_RUN" == "1" ]]; then
echo "prepare ${VERILOG_DST} from ${VERILOG_SRC}"
    echo "build dir ${BUILD_DIR}"
    if [[ "$SKIP_BUILD" == "1" ]]; then
        echo "skip swim build"
    fi
    echo "wrapper ${WRAPPER_SRC}"
    echo "main ${MAIN_SRC}"
    echo "state ${STATE_PATH}"
    echo "rom ${ROM_PATH}"
    echo "script ${SCRIPT_PATH}"
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python tools/prepare_verilator_sv.py "$VERILOG_SRC" "$VERILOG_DST"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$VERILATOR_BIN" --cc "$VERILOG_DST" "$WRAPPER_SRC" --top-module soc_rom_top_verilator_wrapper --exe "$MAIN_SRC" --build -j 0 --Mdir "$BUILD_DIR" -o "$(basename "$RUNNER_BIN")"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$RESTORE_EXPORTER" "--rom=${ROM_PATH}" "--state=${STATE_PATH}" "--out-dir=${RESTORE_DIR}"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$SCRIPT_EXPORTER" "--script=${SCRIPT_PATH}" "--output=${SCRIPT_SCHEDULE}"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$RUNNER_BIN" "--rom=${ROM_PATH}" "--restore-manifest=${RESTORE_MANIFEST}" "--script-schedule=${SCRIPT_SCHEDULE}" "--frames-raw=${FRAMES_RAW}" "--max-mcycles=${MAX_MCYCLES}" "--target-frames=${TARGET_FRAMES}"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "$PYTHON_BIN" "$FRAME_ARTIFACTS" "--frames-raw=${FRAMES_RAW}" "--target-frames=${TARGET_FRAMES}" "--first-raw=${FIRST_RAW}" "--mid-raw=${MID_RAW}" "--last-raw=${LAST_RAW}" "--first-png=${FIRST_PNG}" "--mid-png=${MID_PNG}" "--last-png=${LAST_PNG}"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "${FFMPEG_CMD[@]}" -y -framerate 60 -f rawvideo -pix_fmt gray -s 160x144 -i "$FRAMES_RAW" -vf "scale=640:576:flags=neighbor" -c:v libx264 -pix_fmt yuv420p -crf 18 "$OUTPUT_MP4"
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

rm -rf "$RESTORE_DIR"
rm -f "$SCRIPT_SCHEDULE" "$FRAMES_RAW" "$FIRST_RAW" "$MID_RAW" "$LAST_RAW" "$FIRST_PNG" "$MID_PNG" "$LAST_PNG" "$OUTPUT_MP4"

"$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$RESTORE_EXPORTER" \
    "--rom=${ROM_PATH}" \
    "--state=${STATE_PATH}" \
    "--out-dir=${RESTORE_DIR}"

"$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python "$SCRIPT_EXPORTER" \
    "--script=${SCRIPT_PATH}" \
    "--output=${SCRIPT_SCHEDULE}"

"$RUNNER_BIN" \
    "--rom=${ROM_PATH}" \
    "--restore-manifest=${RESTORE_MANIFEST}" \
    "--script-schedule=${SCRIPT_SCHEDULE}" \
    "--frames-raw=${FRAMES_RAW}" \
    "--max-mcycles=${MAX_MCYCLES}" \
    "--target-frames=${TARGET_FRAMES}"

"$PYTHON_BIN" "$FRAME_ARTIFACTS" \
    "--frames-raw=${FRAMES_RAW}" \
    "--target-frames=${TARGET_FRAMES}" \
    "--first-raw=${FIRST_RAW}" \
    "--mid-raw=${MID_RAW}" \
    "--last-raw=${LAST_RAW}" \
    "--first-png=${FIRST_PNG}" \
    "--mid-png=${MID_PNG}" \
    "--last-png=${LAST_PNG}"

"${FFMPEG_CMD[@]}" -y \
    -framerate 60 \
    -f rawvideo \
    -pix_fmt gray \
    -s 160x144 \
    -i "$FRAMES_RAW" \
    -vf "scale=640:576:flags=neighbor" \
    -c:v libx264 \
    -pix_fmt yuv420p \
    -crf 18 \
    "$OUTPUT_MP4"

echo "pokered playback mp4 written to ${OUTPUT_MP4}"
