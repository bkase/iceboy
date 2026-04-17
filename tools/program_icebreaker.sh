#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
CHECK_DEVICE=0
BIN_FILE=""

run_iceprog_or_die() {
    local action="$1"
    shift
    local output=""
    local rc=0

    set +e
    output="$("$@" 2>&1)"
    rc=$?
    set -e

    if [[ "${rc}" -ne 0 ]]; then
        echo "error: ${action} failed; iceprog could not find or talk to an attached iCEBreaker. Connect the board, check the USB cable, and make sure no other tool is using it." >&2
        if [[ -n "${output}" ]]; then
            echo "${output}" >&2
        fi
        exit "${rc}"
    fi

    if [[ -n "${output}" ]]; then
        printf '%s\n' "${output}"
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        --check-device)
            CHECK_DEVICE=1
            ;;
        --bin)
            [[ $# -ge 2 ]] || iceboy_die "--bin requires a path"
            BIN_FILE="$2"
            shift
            ;;
        --help|-h)
            cat <<'EOF'
usage: tools/program_icebreaker.sh [options]

options:
  --bin <path>      Packed bitstream to flash; required
  --check-device    Probe the board first via iceprog -t
  --dry-run         Print commands without executing them
EOF
            exit 0
            ;;
        *)
            iceboy_die "unexpected argument '$1'"
            ;;
    esac
    shift
done

if [[ -z "${BIN_FILE}" ]]; then
    iceboy_die "--bin is required; refusing to auto-select the newest bitstream under ${ICEBOY_ROOT}/build/bitstreams"
fi

iceboy_require_file "${BIN_FILE}" "packed bitstream"

ICEPROG_CANDIDATE="$(iceboy_iceprog_bin)"
if [[ "${DRY_RUN}" == "1" ]]; then
    ICEPROG_BIN="${ICEPROG_CANDIDATE:-iceprog}"
else
    ICEPROG_BIN="$(iceboy_require_command "iceprog" "ICEBOY_ICEPROG_BIN" "${ICEPROG_CANDIDATE}")"
fi
iceboy_log_tool "iceprog" "${ICEPROG_BIN}"

if [[ "${DRY_RUN}" == "1" ]]; then
    if [[ "${CHECK_DEVICE}" == "1" ]]; then
        printf 'DRY RUN: %q -t\n' "${ICEPROG_BIN}"
    fi
    printf 'DRY RUN: %q %q\n' "${ICEPROG_BIN}" "${BIN_FILE}"
    exit 0
fi

if [[ "${CHECK_DEVICE}" == "1" ]]; then
    run_iceprog_or_die "device probe" "${ICEPROG_BIN}" -t
fi

run_iceprog_or_die "bitstream programming" "${ICEPROG_BIN}" "${BIN_FILE}"
