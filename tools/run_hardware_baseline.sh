#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
SKIP_BUILD=0
SKIP_SYNTH=0
OUT_DIR="${ICEBOY_ROOT}/build/hw_baseline"
RECORD_JSON="${ICEBOY_ROOT}/docs/hardware/icebreaker_up5k_baseline.json"
TARGET_FREQ_MHZ="12"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        --skip-build)
            SKIP_BUILD=1
            ;;
        --skip-synth)
            SKIP_SYNTH=1
            ;;
        --out-dir)
            [[ $# -ge 2 ]] || iceboy_die "--out-dir requires a path"
            OUT_DIR="$2"
            shift
            ;;
        --record-json)
            [[ $# -ge 2 ]] || iceboy_die "--record-json requires a path"
            RECORD_JSON="$2"
            shift
            ;;
        --freq-mhz)
            [[ $# -ge 2 ]] || iceboy_die "--freq-mhz requires a value"
            TARGET_FREQ_MHZ="$2"
            shift
            ;;
        --help|-h)
            cat <<'EOF'
usage: tools/run_hardware_baseline.sh [--dry-run] [--skip-build] [--skip-synth] [--out-dir <dir>] [--record-json <path>] [--freq-mhz <mhz>]
EOF
            exit 0
            ;;
        *)
            iceboy_die "unexpected argument '$1'"
            ;;
    esac
    shift
done

CMD=(
    "${ICEBOY_ROOT}/tools/build_icebreaker_variant.sh"
    --top "board::icebreaker_top::icebreaker_top"
    --module "icebreaker_top"
    --board-top "${ICEBOY_ROOT}/src/board/icebreaker_top.spade"
    --pcf "${ICEBOY_ROOT}/icebreaker.pcf"
    --out-dir "${OUT_DIR}"
    --record-json "${RECORD_JSON}"
    --freq-mhz "${TARGET_FREQ_MHZ}"
    --synth-dir "${OUT_DIR}/synth"
    --netlist-name "hardware.json"
    --stat-name "yosys-stat.txt"
    --yosys-log-name "yosys.log"
    --asc-name "icebreaker.asc"
    --verified-by "tools/run_hardware_baseline.sh"
)

if [[ "${DRY_RUN}" == "1" ]]; then
    CMD+=(--dry-run)
fi
if [[ "${SKIP_BUILD}" == "1" ]]; then
    CMD+=(--skip-build)
fi
if [[ "${SKIP_SYNTH}" == "1" ]]; then
    CMD+=(--skip-synth)
fi

exec "${CMD[@]}"
