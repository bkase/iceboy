#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
SKIP_BUILD=0
OUT_DIR="${ICEBOY_ROOT}/build/ebr_synth_smoke"
SPADE_SV="${ICEBOY_ROOT}/build/spade.sv"
WRAPPER_SV="${ICEBOY_ROOT}/tools/verilog/ebr_synth_smoke_top.v"
TOP_MODULE="ebr_synth_smoke_top"
NETLIST_JSON=""
STAT_FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        --skip-build)
            SKIP_BUILD=1
            ;;
        --out-dir)
            [[ $# -ge 2 ]] || iceboy_die "--out-dir requires a path"
            OUT_DIR="$2"
            shift
            ;;
        --help|-h)
            cat <<'EOF'
usage: tools/run_ebr_synth_smoke.sh [--dry-run] [--skip-build] [--out-dir <dir>]
EOF
            exit 0
            ;;
        *)
            iceboy_die "unexpected argument '$1'"
            ;;
    esac
    shift
done

NETLIST_JSON="${OUT_DIR}/ebr_synth_test_top.json"
STAT_FILE="${OUT_DIR}/yosys-stat.txt"

SWIM_BIN="$(iceboy_require_command "swim" "ICEBOY_SWIM_BIN" "$(iceboy_swim_bin)")"
YOSYS_BIN="$(iceboy_require_command "yosys" "ICEBOY_YOSYS_BIN" "$(iceboy_yosys_bin)")"
iceboy_log_tool "swim" "$(iceboy_version_string "${SWIM_BIN}" --version)"
iceboy_log_tool "yosys" "$(iceboy_version_string "${YOSYS_BIN}" -V)"

YOSYS_SCRIPT=$(
    cat <<EOF
read_verilog -sv "${SPADE_SV}";
read_verilog -sv "${WRAPPER_SV}";
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
    echo "DRY RUN: top ${TOP_MODULE}"
    echo "DRY RUN: wrapper ${WRAPPER_SV}"
    echo "DRY RUN: outputs ${NETLIST_JSON} ${STAT_FILE}"
    printf 'DRY RUN: %q -q -p %q\n' "${YOSYS_BIN}" "${YOSYS_SCRIPT}"
    exit 0
fi

mkdir -p "${OUT_DIR}"

if [[ "${SKIP_BUILD}" != "1" ]]; then
    "${SWIM_BIN}" build
fi

iceboy_require_file "${SPADE_SV}" "generated Verilog"
iceboy_require_file "${WRAPPER_SV}" "EBR smoke wrapper"
"${YOSYS_BIN}" -q -p "${YOSYS_SCRIPT}"
iceboy_require_file "${NETLIST_JSON}" "synthesized netlist"
iceboy_require_file "${STAT_FILE}" "Yosys resource report"

if ! rg -n "SB_RAM40_4K|ICESTORM_RAM" "${STAT_FILE}" "${NETLIST_JSON}" >/dev/null; then
    iceboy_die "expected EBR primitive usage in ${STAT_FILE} or ${NETLIST_JSON}"
fi

echo "Verified EBR primitive usage for ${TOP_MODULE}."
