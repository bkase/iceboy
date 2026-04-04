#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

export PATH="${ICEBOY_ROOT}/build/oss-cad-suite/bin:/opt/homebrew/bin:${PATH}"

SWIM_BIN="$(iceboy_require_command "swim" "ICEBOY_SWIM_BIN" "$(iceboy_swim_bin)")"
YOSYS_BIN="$(iceboy_require_command "yosys" "ICEBOY_YOSYS_BIN" "$(iceboy_yosys_bin)")"
SBY_BIN="$(iceboy_require_command "sby" "ICEBOY_SBY_BIN" "$(iceboy_sby_bin)")"

iceboy_require_file "${ICEBOY_ROOT}/formal/ppu/safety/ppu_irq.sby" "ppu irq sby job"
iceboy_require_file "${ICEBOY_ROOT}/formal/ppu/safety/ppu_irq_formal.sv" "ppu irq formal harness"

"${SWIM_BIN}" build >/dev/null
"${SBY_BIN}" --yosys "${YOSYS_BIN}" -f -d "${ICEBOY_ROOT}/build/formal/ppu_irq" "${ICEBOY_ROOT}/formal/ppu/safety/ppu_irq.sby"
