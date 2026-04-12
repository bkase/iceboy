#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
SKIP_BUILD=0
OUT_DIR="${ICEBOY_ROOT}/build/hw_probes/ebr_rom"
VERIFY_SCRIPT="${ICEBOY_ROOT}/tools/verify_icebreaker_variant.sh"
TOP_LABEL="mem::phys::ebr_rom_probe_top::ebr_rom_probe_top"
TOP_MODULE="ebr_rom_probe_top"
BOARD_TOP="${ICEBOY_ROOT}/src/mem/phys/ebr_rom_probe_top.spade"
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
usage: tools/run_ebr_rom_synth_probe.sh [--dry-run] [--skip-build] [--out-dir <dir>]
EOF
            exit 0
            ;;
        *)
            iceboy_die "unexpected argument '$1'"
            ;;
    esac
    shift
done

STAT_FILE="${OUT_DIR}/yosys-stat.txt"

CMD=(
    "${VERIFY_SCRIPT}"
    --top "${TOP_LABEL}"
    --module "${TOP_MODULE}"
    --board-top "${BOARD_TOP}"
    --out-dir "${OUT_DIR}"
)

if [[ "${DRY_RUN}" == "1" ]]; then
    CMD+=(--dry-run)
fi
if [[ "${SKIP_BUILD}" == "1" ]]; then
    CMD+=(--skip-build)
fi

"${CMD[@]}"

if [[ "${DRY_RUN}" == "1" ]]; then
    echo "DRY RUN: parse ${STAT_FILE} for SB_RAM40_4K, SB_LUT4, and SB_DFF"
    exit 0
fi

iceboy_require_file "${STAT_FILE}" "Yosys resource report"

LUT4_COUNT="$(awk '/SB_LUT4/ { print $1; exit }' "${STAT_FILE}")"
DFF_COUNT="$(awk '/SB_DFF/ { sum += $1 } END { print sum + 0 }' "${STAT_FILE}")"
EBR_COUNT="$(awk '$2 ~ /^SB_RAM40_4K/ { sum += $1 } END { print sum + 0 }' "${STAT_FILE}")"
[[ -n "${LUT4_COUNT}" ]] || iceboy_die "failed to parse SB_LUT4 count from ${STAT_FILE}"
[[ -n "${DFF_COUNT}" ]] || iceboy_die "failed to parse SB_DFF count from ${STAT_FILE}"
[[ -n "${EBR_COUNT}" ]] || iceboy_die "failed to parse SB_RAM40_4K count from ${STAT_FILE}"

echo "EBR ROM probe resources: SB_RAM40_4K=${EBR_COUNT} SB_LUT4=${LUT4_COUNT} SB_DFF=${DFF_COUNT}"

if (( EBR_COUNT < 2 )); then
    iceboy_die "expected initialized 1 KiB ROM probe to map to at least 2 SB_RAM40_4K blocks, got ${EBR_COUNT}"
fi
