#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
SKIP_BUILD=0
ENFORCE_BUDGET=0
TOP_LABEL=""
TOP_MODULE=""
BOARD_TOP=""
OUT_DIR="${ICEBOY_ROOT}/build/hw_verify"
SPADE_SV="${ICEBOY_ROOT}/build/spade.sv"
DEBUG_PATTERNS=("CommitTrace" "DebugTrace" "PpuDebugTrace" "SimStimulus" "BusObs" "SocLockstepTopOut")
CHECK_HW_IMPORTS="${ICEBOY_ROOT}/tools/check_hw_imports.py"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        --skip-build)
            SKIP_BUILD=1
            ;;
        --enforce-budget)
            ENFORCE_BUDGET=1
            ;;
        --top)
            [[ $# -ge 2 ]] || iceboy_die "--top requires a Spade label"
            TOP_LABEL="$2"
            shift
            ;;
        --module)
            [[ $# -ge 2 ]] || iceboy_die "--module requires a Verilog module name"
            TOP_MODULE="$2"
            shift
            ;;
        --board-top)
            [[ $# -ge 2 ]] || iceboy_die "--board-top requires a path"
            BOARD_TOP="$2"
            shift
            ;;
        --out-dir)
            [[ $# -ge 2 ]] || iceboy_die "--out-dir requires a path"
            OUT_DIR="$2"
            shift
            ;;
        --help|-h)
            cat <<'EOF'
usage: tools/verify_icebreaker_variant.sh --top <spade-label> [options]

options:
  --module <verilog-module>   Verilog top module name; defaults to the tail of --top
  --board-top <path>          Board-top source path; defaults to src/board/<module>.spade
  --out-dir <dir>             Output directory; defaults to build/hw_verify
  --skip-build                Reuse existing build/spade.sv
  --enforce-budget            Fail if LUT4/DFF/SPRAM/EBR budget checks do not pass
  --dry-run                   Print commands without executing them
EOF
            exit 0
            ;;
        *)
            iceboy_die "unexpected argument '$1'"
            ;;
    esac
    shift
done

[[ -n "${TOP_LABEL}" ]] || iceboy_die "--top is required"
if [[ -z "${TOP_MODULE}" ]]; then
    TOP_MODULE="${TOP_LABEL##*::}"
fi
if [[ -z "${BOARD_TOP}" ]]; then
    BOARD_TOP="${ICEBOY_ROOT}/src/board/${TOP_MODULE}.spade"
fi

NETLIST_JSON="${OUT_DIR}/hardware.json"
STAT_FILE="${OUT_DIR}/yosys-stat.txt"

iceboy_require_file "${BOARD_TOP}" "hardware board top"
iceboy_require_file "${CHECK_HW_IMPORTS}" "hardware import checker"

UV_BIN="$(iceboy_require_command "uv" "ICEBOY_UV_BIN" "$(iceboy_uv_bin)")"
SWIM_BIN="$(iceboy_require_command "swim" "ICEBOY_SWIM_BIN" "$(iceboy_swim_bin)")"
YOSYS_BIN="$(iceboy_require_command "yosys" "ICEBOY_YOSYS_BIN" "$(iceboy_yosys_bin)")"
UV_VERSION="$(iceboy_version_string "${UV_BIN}" --version)"
SWIM_VERSION="$(iceboy_version_string "${SWIM_BIN}" --version)"
YOSYS_VERSION="$(iceboy_version_string "${YOSYS_BIN}" -V)"
iceboy_log_tool "uv" "${UV_VERSION}"
iceboy_log_tool "swim" "${SWIM_VERSION}"
iceboy_log_tool "yosys" "${YOSYS_VERSION}"

YOSYS_SCRIPT=$(
    cat <<EOF
read_verilog -sv "${SPADE_SV}";
synth_ice40 -top ${TOP_MODULE} -json "${NETLIST_JSON}";
tee -q -o "${STAT_FILE}" stat;
EOF
)

if [[ "${DRY_RUN}" == "1" ]]; then
    if [[ "${SKIP_BUILD}" == "1" ]]; then
        echo "DRY RUN: skip swim build"
    else
        printf 'DRY RUN: %q build\n' "${SWIM_BIN}"
    fi
    echo "DRY RUN: top ${TOP_LABEL}"
    echo "DRY RUN: module ${TOP_MODULE}"
    echo "DRY RUN: source graph check ${BOARD_TOP} has no reachable lib::sim imports"
    echo "DRY RUN: forbid debug patterns ${DEBUG_PATTERNS[*]}"
    if [[ "${ENFORCE_BUDGET}" == "1" ]]; then
        echo "DRY RUN: enforce LUT4/DFF/SPRAM/EBR hardware budget"
    else
        echo "DRY RUN: report LUT4/DFF/SPRAM/EBR hardware budget without enforcing"
    fi
    echo "DRY RUN: outputs ${NETLIST_JSON} ${STAT_FILE}"
    printf 'DRY RUN: %q -q -p %q\n' "${YOSYS_BIN}" "${YOSYS_SCRIPT}"
    exit 0
fi

"${UV_BIN}" run --with-requirements "${ICEBOY_PYTHON_LOCK}" python "${CHECK_HW_IMPORTS}" \
    --board-top "${BOARD_TOP}" \
    --src-root "${ICEBOY_ROOT}/src"

mkdir -p "${OUT_DIR}"

if [[ "${SKIP_BUILD}" != "1" ]]; then
    "${SWIM_BIN}" build
fi

iceboy_require_file "${SPADE_SV}" "generated Verilog"
"${YOSYS_BIN}" -q -p "${YOSYS_SCRIPT}"
iceboy_require_file "${NETLIST_JSON}" "synthesized hardware netlist"
iceboy_require_file "${STAT_FILE}" "Yosys resource report"

for pattern in "${DEBUG_PATTERNS[@]}"; do
    if rg -n "${pattern}" "${NETLIST_JSON}" >/dev/null; then
        iceboy_die "hardware netlist contains forbidden debug symbol '${pattern}'"
    fi
done

LUT4_COUNT="$(awk '/SB_LUT4/ { print $1; exit }' "${STAT_FILE}")"
DFF_COUNT="$(awk '/SB_DFF/ { sum += $1 } END { print sum + 0 }' "${STAT_FILE}")"
SPRAM_COUNT="$(awk '/SB_SPRAM256KA/ { sum += $1 } END { print sum + 0 }' "${STAT_FILE}")"
EBR_COUNT="$(awk '$2 ~ /^SB_RAM40_4K/ { sum += $1 } END { print sum + 0 }' "${STAT_FILE}")"
[[ -n "${LUT4_COUNT}" ]] || iceboy_die "failed to parse SB_LUT4 count from ${STAT_FILE}"
[[ -n "${DFF_COUNT}" ]] || iceboy_die "failed to parse SB_DFF count from ${STAT_FILE}"
[[ -n "${SPRAM_COUNT}" ]] || iceboy_die "failed to parse SB_SPRAM256KA count from ${STAT_FILE}"
[[ -n "${EBR_COUNT}" ]] || iceboy_die "failed to parse SB_RAM40_4K count from ${STAT_FILE}"

FIT_LUT=1
FIT_DFF=1
FIT_SPRAM=1
FIT_EBR=1
if (( LUT4_COUNT > 5280 )); then
    FIT_LUT=0
fi
if (( DFF_COUNT > 1024 )); then
    FIT_DFF=0
fi
if (( SPRAM_COUNT <= 0 )); then
    FIT_SPRAM=0
fi
if (( EBR_COUNT <= 0 )); then
    FIT_EBR=0
fi

echo "Verified debug-free hardware build for ${TOP_LABEL} (${TOP_MODULE})."
echo "Resources: SB_LUT4=${LUT4_COUNT} SB_DFF=${DFF_COUNT} SB_SPRAM256KA=${SPRAM_COUNT} SB_RAM40_4K=${EBR_COUNT} fit_lut=${FIT_LUT} fit_dff=${FIT_DFF} fit_spram=${FIT_SPRAM} fit_ebr=${FIT_EBR}"

if [[ "${ENFORCE_BUDGET}" == "1" ]]; then
    if (( FIT_LUT == 0 )); then
        iceboy_die "hardware netlist exceeds UP5K LUT budget: ${LUT4_COUNT} > 5280"
    fi
    if (( FIT_DFF == 0 )); then
        iceboy_die "hardware netlist exceeds UP5K DFF budget: ${DFF_COUNT} > 1024"
    fi
    if (( FIT_SPRAM == 0 )); then
        iceboy_die "hardware netlist is missing SPRAM utilization: SB_SPRAM256KA=${SPRAM_COUNT}"
    fi
    if (( FIT_EBR == 0 )); then
        iceboy_die "hardware netlist is missing EBR utilization: SB_RAM40_4K=${EBR_COUNT}"
    fi
fi
