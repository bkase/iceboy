#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
SKIP_BUILD=0
SIZE=""
OUT_DIR=""
VERIFY_SCRIPT="${ICEBOY_ROOT}/tools/verify_icebreaker_variant.sh"
TOP_LABEL=""
TOP_MODULE=""
EXPECTED_EBR=0
BOARD_TOP="${ICEBOY_ROOT}/src/mem/phys/rom_baked_ebr_synth_top.spade"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        --skip-build)
            SKIP_BUILD=1
            ;;
        --size)
            [[ $# -ge 2 ]] || iceboy_die "--size requires a value"
            SIZE="$2"
            shift
            ;;
        --out-dir)
            [[ $# -ge 2 ]] || iceboy_die "--out-dir requires a path"
            OUT_DIR="$2"
            shift
            ;;
        --help|-h)
            cat <<'EOF'
usage: tools/run_rom_baked_ebr_synth_smoke.sh --size <1024|4096> [--dry-run] [--skip-build] [--out-dir <dir>]
EOF
            exit 0
            ;;
        *)
            iceboy_die "unexpected argument '$1'"
            ;;
    esac
    shift
done

case "${SIZE}" in
    1024)
        TOP_LABEL="mem::phys::rom_baked_ebr_synth_top::rom_baked_ebr_1k_synth_top"
        TOP_MODULE="rom_baked_ebr_1k_synth_top"
        EXPECTED_EBR=2
        ;;
    4096)
        TOP_LABEL="mem::phys::rom_baked_ebr_synth_top::rom_baked_ebr_4k_synth_top"
        TOP_MODULE="rom_baked_ebr_4k_synth_top"
        EXPECTED_EBR=8
        ;;
    *)
        iceboy_die "--size must be 1024 or 4096"
        ;;
esac

if [[ -z "${OUT_DIR}" ]]; then
    OUT_DIR="${ICEBOY_ROOT}/build/rom_baked_ebr_synth_${SIZE}"
fi

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
    echo "DRY RUN: parse ${STAT_FILE} for SB_RAM40_4K and require ${EXPECTED_EBR}"
    exit 0
fi

iceboy_require_file "${STAT_FILE}" "Yosys resource report"

EBR_COUNT="$(awk '$2 ~ /^SB_RAM40_4K/ { sum += $1 } END { print sum + 0 }' "${STAT_FILE}")"
[[ -n "${EBR_COUNT}" ]] || iceboy_die "failed to parse SB_RAM40_4K count from ${STAT_FILE}"

if (( EBR_COUNT != EXPECTED_EBR )); then
    iceboy_die "expected ${TOP_MODULE} to use ${EXPECTED_EBR} SB_RAM40_4K blocks, got ${EBR_COUNT}"
fi

echo "Verified ${TOP_MODULE} maps to ${EXPECTED_EBR} SB_RAM40_4K blocks."
