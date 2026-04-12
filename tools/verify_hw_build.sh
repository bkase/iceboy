#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
SKIP_BUILD=0
ENFORCE_BUDGET=0
OUT_DIR="${ICEBOY_ROOT}/build/hw_verify"

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

CMD=(
    "${ICEBOY_ROOT}/tools/verify_icebreaker_variant.sh"
    --top "board::icebreaker_top::icebreaker_top"
    --module "icebreaker_top"
    --board-top "${ICEBOY_ROOT}/src/board/icebreaker_top.spade"
    --out-dir "${OUT_DIR}"
)

if [[ "${DRY_RUN}" == "1" ]]; then
    CMD+=(--dry-run)
fi
if [[ "${SKIP_BUILD}" == "1" ]]; then
    CMD+=(--skip-build)
fi
if [[ "${ENFORCE_BUDGET}" == "1" ]]; then
    CMD+=(--enforce-budget)
fi

exec "${CMD[@]}"
