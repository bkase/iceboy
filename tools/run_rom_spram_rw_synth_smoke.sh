#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
SKIP_BUILD=0
OUT_DIR="${ICEBOY_ROOT}/build/hw_probes/rom_spram_rw"
VERIFY_SCRIPT="${ICEBOY_ROOT}/tools/verify_icebreaker_variant.sh"
TOP_LABEL="mem::phys::rom_spram_rw_synth_top::rom_spram_rw_synth_top"
TOP_MODULE="rom_spram_rw_synth_top"
BOARD_TOP="${ICEBOY_ROOT}/src/mem/phys/rom_spram_rw_synth_top.spade"
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
usage: tools/run_rom_spram_rw_synth_smoke.sh [--dry-run] [--skip-build] [--out-dir <dir>]
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
    echo "DRY RUN: parse ${STAT_FILE} for SB_SPRAM256KA and SB_RAM40_4K"
    exit 0
fi

iceboy_require_file "${STAT_FILE}" "Yosys resource report"

LUT4_COUNT="$(awk '/SB_LUT4/ { print $1; exit }' "${STAT_FILE}")"
SPRAM_COUNT="$(awk '/SB_SPRAM256KA/ { sum += $1 } END { print sum + 0 }' "${STAT_FILE}")"
EBR_COUNT="$(awk '$2 ~ /^SB_RAM40_4K/ { sum += $1 } END { print sum + 0 }' "${STAT_FILE}")"

[[ -n "${LUT4_COUNT}" ]] || iceboy_die "failed to parse SB_LUT4 count from ${STAT_FILE}"
[[ -n "${SPRAM_COUNT}" ]] || iceboy_die "failed to parse SB_SPRAM256KA count from ${STAT_FILE}"
[[ -n "${EBR_COUNT}" ]] || iceboy_die "failed to parse SB_RAM40_4K count from ${STAT_FILE}"

echo "ROM SPRAM RW resources: SB_LUT4=${LUT4_COUNT} SB_SPRAM256KA=${SPRAM_COUNT} SB_RAM40_4K=${EBR_COUNT}"

if (( SPRAM_COUNT != 1 )); then
    iceboy_die "expected rom_spram_rw to use exactly 1 SB_SPRAM256KA block, got ${SPRAM_COUNT}"
fi
if (( EBR_COUNT != 0 )); then
    iceboy_die "expected rom_spram_rw to avoid EBR, got SB_RAM40_4K=${EBR_COUNT}"
fi
