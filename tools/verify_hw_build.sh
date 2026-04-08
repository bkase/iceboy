#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
SKIP_BUILD=0
ENFORCE_BUDGET=0
OUT_DIR="${ICEBOY_ROOT}/build/hw_verify"
TOP_MODULE="icebreaker_top"
SPADE_SV="${ICEBOY_ROOT}/build/spade.sv"
BOARD_TOP="${ICEBOY_ROOT}/src/board/icebreaker_top.spade"
NETLIST_JSON=""
STAT_FILE=""
DEBUG_PATTERNS=("CommitTrace" "DebugTrace" "PpuDebugTrace" "SimStimulus" "BusObs" "SocLockstepTopOut")

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
        --out-dir)
            [[ $# -ge 2 ]] || iceboy_die "--out-dir requires a path"
            OUT_DIR="$2"
            shift
            ;;
        --help|-h)
            cat <<'EOF'
usage: tools/verify_hw_build.sh [--dry-run] [--skip-build] [--enforce-budget] [--out-dir <dir>]
EOF
            exit 0
            ;;
        *)
            iceboy_die "unexpected argument '$1'"
            ;;
    esac
    shift
done

NETLIST_JSON="${OUT_DIR}/hardware.json"
STAT_FILE="${OUT_DIR}/yosys-stat.txt"

iceboy_require_file "${BOARD_TOP}" "hardware board top"

SWIM_BIN="$(iceboy_require_command "swim" "ICEBOY_SWIM_BIN" "$(iceboy_swim_bin)")"
YOSYS_BIN="$(iceboy_require_command "yosys" "ICEBOY_YOSYS_BIN" "$(iceboy_yosys_bin)")"
iceboy_log_tool "swim" "$(iceboy_version_string "${SWIM_BIN}" --version)"
iceboy_log_tool "yosys" "$(iceboy_version_string "${YOSYS_BIN}" -V)"

if rg -n 'lib::sim::|sim::' "${BOARD_TOP}" >/dev/null; then
    iceboy_die "hardware board top references simulation namespaces"
fi

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
    echo "DRY RUN: source check ${BOARD_TOP} has no sim:: references"
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

echo "Verified debug-free hardware build."
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
