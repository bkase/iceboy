#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
SKIP_BUILD=0
TESTCASE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        --skip-build)
            SKIP_BUILD=1
            ;;
        -t|--testcase)
            shift
            [[ $# -gt 0 ]] || iceboy_die "missing value for --testcase"
            TESTCASE="$1"
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

BUILD_DIR="${ICEBOY_ROOT}/build/rom_verilator/test_ppu_wave_b_mealybug"
VERILOG_SRC="${ICEBOY_ROOT}/build/spade.sv"
VERILOG_DST="${ICEBOY_ROOT}/build/spade.verilator.sv"
WRAPPER_SRC="${ICEBOY_ROOT}/test/harness/verilog/soc_rom_top_verilator_wrapper.sv"
MODULE="test_ppu_wave_b_mealybug"
TOPLEVEL="soc_rom_top_verilator_wrapper"
TOP_MODULE_PLUSARG="+TOP_MODULE=iceboy::sim::soc_rom_top::soc_rom_top"
PYTHON_BIN_LINK="${ICEBOY_ROOT}/build/oss-cad-suite/bin/python"
PYTHON_SO_LINK="${ICEBOY_ROOT}/build/oss-cad-suite/lib/libpython3.11.so"

ensure_oss_cad_python_shims() {
    if [[ ! -e "$PYTHON_BIN_LINK" ]]; then
        ln -sfn ../py3bin/python3 "$PYTHON_BIN_LINK"
    fi
    if [[ ! -e "$PYTHON_SO_LINK" && -e "${ICEBOY_ROOT}/build/oss-cad-suite/lib/libpython3.11.dylib" ]]; then
        ln -sfn libpython3.11.dylib "$PYTHON_SO_LINK"
    fi
}

MAKE_CMD=(
    make
    -C "$BUILD_DIR"
    "VERILOG_SOURCES=${VERILOG_DST} ${WRAPPER_SRC}"
    "VERILOG_INCLUDE_DIRS="
    "TOPLEVEL=${TOPLEVEL}"
    "MODULE=${MODULE}"
    "SIM=verilator"
    "EXTRA_ARGS="
    "SIM_ARGS=-n"
    "TOPLEVEL_LANG=verilog"
    -s
    "PLUSARGS=${TOP_MODULE_PLUSARG}"
)

if [[ -n "$TESTCASE" ]]; then
    MAKE_CMD+=("TESTCASE=${TESTCASE}")
fi

if [[ "$DRY_RUN" == "1" ]]; then
    echo "prepare ${VERILOG_DST} from ${VERILOG_SRC}"
    echo "build dir ${BUILD_DIR}"
    if [[ "$SKIP_BUILD" == "1" ]]; then
        echo "skip swim build"
    fi
    echo "wrapper ${WRAPPER_SRC}"
    printf 'DRY RUN:'
    printf ' %q' "$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python tools/prepare_verilator_sv.py "$VERILOG_SRC" "$VERILOG_DST"
    printf '\n'
    printf 'DRY RUN:'
    printf ' %q' "${MAKE_CMD[@]}"
    printf '\n'
    exit 0
fi

mkdir -p "$BUILD_DIR"
ln -sfn "${ICEBOY_ROOT}/build/oss-cad-suite/lib" "${BUILD_DIR}/lib"
ensure_oss_cad_python_shims

"${ICEBOY_ROOT}/tools/ensure_swim_python_deps.sh"

if [[ "$SKIP_BUILD" != "1" ]]; then
    "$SWIM_BIN" build
fi

"$UV_BIN" run --with-requirements "$ICEBOY_PYTHON_LOCK" python tools/prepare_verilator_sv.py "$VERILOG_SRC" "$VERILOG_DST"

. "${ICEBOY_ROOT}/build/oss-cad-suite/environment"
COCOTB_MAKEFILES_DIR="$(cocotb-config --makefiles)"
MAKE_CMD=(
    make
    -C "$BUILD_DIR"
    -f "${COCOTB_MAKEFILES_DIR}/Makefile.sim"
    "${MAKE_CMD[@]:3}"
)

env \
    PYGPI_PYTHON_BIN="${ICEBOY_ROOT}/build/oss-cad-suite/bin/python" \
    PYTHONHOME="${ICEBOY_ROOT}/build/oss-cad-suite" \
    DYLD_LIBRARY_PATH="${ICEBOY_ROOT}/build/oss-cad-suite/lib" \
    PYTHONPATH="${ICEBOY_ROOT}/test/rom:${ICEBOY_ROOT}:${ICEBOY_ROOT}/test/harness" \
    "${MAKE_CMD[@]}"
