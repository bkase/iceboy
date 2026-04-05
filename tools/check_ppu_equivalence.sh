#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

TEMPLATE="${ICEBOY_ROOT}/formal/ppu/equivalence/ppu_refactor.eqy"
OUT_DIR="${ICEBOY_ROOT}/build/formal/ppu_refactor"
GENERATED_NAME="ppu_refactor.generated.eqy"

exec "${ICEBOY_TOOLS_DIR}/check_equivalence.sh" \
    --template "${TEMPLATE}" \
    --out-dir "${OUT_DIR}" \
    --generated-name "${GENERATED_NAME}" \
    "$@"
