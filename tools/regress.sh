#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
SIM="icarus"
TIER="full"
FORWARD=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        --nightly)
            TIER="nightly"
            ;;
        --sim)
            [[ $# -ge 2 ]] || iceboy_die "--sim requires a value"
            SIM="$2"
            FORWARD+=("$1" "$2")
            shift
            ;;
        --sim=*)
            SIM="${1#--sim=}"
            FORWARD+=("$1")
            ;;
        *)
            iceboy_reject_tier_flag "$1"
            FORWARD+=("$1")
            ;;
    esac
    shift
done

iceboy_require_file "${ICEBOY_RUN_TESTS}" "canonical runner"
iceboy_require_file "${ICEBOY_TIER_CONFIG}" "tier config"

UV_BIN="$(iceboy_require_command "uv" "ICEBOY_UV_BIN" "$(iceboy_uv_bin)")"
SWIM_BIN="$(iceboy_require_command "swim" "ICEBOY_SWIM_BIN" "$(iceboy_swim_bin)")"
iceboy_log_tool "uv" "$(iceboy_version_string "${UV_BIN}" --version)"
iceboy_log_tool "swim" "$(iceboy_version_string "${SWIM_BIN}" --version)"
iceboy_require_simulator "${SIM}"

iceboy_run_or_print "${DRY_RUN}" \
    "${UV_BIN}" run --with-requirements "${ICEBOY_PYTHON_LOCK}" python "${ICEBOY_RUN_TESTS}" --tier "${TIER}" "${FORWARD[@]}"
