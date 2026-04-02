#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
FORWARD=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        *)
            FORWARD+=("$1")
            ;;
    esac
    shift
done

iceboy_require_file "${ICEBOY_ORACLE_SMOKE}" "oracle smoke tool"
iceboy_require_file "${ICEBOY_PYTHON_LOCK}" "python lockfile"

UV_BIN="$(iceboy_require_command "uv" "ICEBOY_UV_BIN" "$(iceboy_uv_bin)")"
iceboy_log_tool "uv" "$(iceboy_version_string "${UV_BIN}" --version)"
iceboy_log_tool "pyboy" "$(iceboy_uv_package_version "${UV_BIN}" "pyboy")"

iceboy_run_or_print "${DRY_RUN}" \
    "${UV_BIN}" run --with-requirements "${ICEBOY_PYTHON_LOCK}" python "${ICEBOY_ORACLE_SMOKE}" "${FORWARD[@]}"
