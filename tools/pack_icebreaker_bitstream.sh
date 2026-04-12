#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
RUN_ICETIME=0
ASC_FILE=""
OUT_FILE=""
PCF_FILE="${ICEBOY_ROOT}/icebreaker.pcf"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        --icetime)
            RUN_ICETIME=1
            ;;
        --asc)
            [[ $# -ge 2 ]] || iceboy_die "--asc requires a path"
            ASC_FILE="$2"
            shift
            ;;
        --out)
            [[ $# -ge 2 ]] || iceboy_die "--out requires a path"
            OUT_FILE="$2"
            shift
            ;;
        --pcf)
            [[ $# -ge 2 ]] || iceboy_die "--pcf requires a path"
            PCF_FILE="$2"
            shift
            ;;
        --help|-h)
            cat <<'EOF'
usage: tools/pack_icebreaker_bitstream.sh --asc <path> --out <path> [options]

options:
  --pcf <path>     Pin constraints for optional icetime sanity check; defaults to icebreaker.pcf
  --icetime        Run icetime -d up5k -p <pcf> <asc> after packing
  --dry-run        Print commands without executing them
EOF
            exit 0
            ;;
        *)
            iceboy_die "unexpected argument '$1'"
            ;;
    esac
    shift
done

[[ -n "${ASC_FILE}" ]] || iceboy_die "--asc is required"
[[ -n "${OUT_FILE}" ]] || iceboy_die "--out is required"

ICEPACK_BIN="$(iceboy_require_command "icepack" "ICEBOY_ICEPACK_BIN" "$(iceboy_icepack_bin)")"
ICEPACK_DESC="${ICEPACK_BIN}"
iceboy_log_tool "icepack" "${ICEPACK_DESC}"

if [[ "${RUN_ICETIME}" == "1" ]]; then
    ICETIME_BIN="$(iceboy_require_command "icetime" "ICEBOY_ICETIME_BIN" "$(iceboy_icetime_bin)")"
    iceboy_log_tool "icetime" "${ICETIME_BIN}"
else
    ICETIME_BIN=""
fi

if [[ "${DRY_RUN}" == "1" ]]; then
    printf 'DRY RUN: %q %q %q\n' "${ICEPACK_BIN}" "${ASC_FILE}" "${OUT_FILE}"
    echo "DRY RUN: report packed bitstream size for ${OUT_FILE}"
    if [[ "${RUN_ICETIME}" == "1" ]]; then
        printf 'DRY RUN: %q -d up5k -p %q %q\n' "${ICETIME_BIN}" "${PCF_FILE}" "${ASC_FILE}"
    fi
    exit 0
fi

iceboy_require_file "${ASC_FILE}" "ASCII bitstream"
if [[ "${RUN_ICETIME}" == "1" ]]; then
    iceboy_require_file "${PCF_FILE}" "pin constraints"
fi

mkdir -p "$(dirname "${OUT_FILE}")"
"${ICEPACK_BIN}" "${ASC_FILE}" "${OUT_FILE}"
iceboy_require_file "${OUT_FILE}" "packed bitstream"

BITSTREAM_BYTES="$(wc -c < "${OUT_FILE}")"
[[ -n "${BITSTREAM_BYTES}" ]] || iceboy_die "failed to determine bitstream size for ${OUT_FILE}"
echo "Packed bitstream: ${OUT_FILE} (${BITSTREAM_BYTES} bytes)"

if [[ "${RUN_ICETIME}" == "1" ]]; then
    "${ICETIME_BIN}" -d up5k -p "${PCF_FILE}" "${ASC_FILE}"
fi
