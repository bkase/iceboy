#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEST_NAME="${1:-}"
LAYOUT_NAME="${2:-cpu_overview}"
LAYOUT_PATH="${ROOT}/tools/gtkwave_layouts/${LAYOUT_NAME}.gtkw"

if [[ -z "${TEST_NAME}" ]]; then
    echo "usage: tools/view_waves.sh <test_name> [layout_name]" >&2
    exit 1
fi

find_waveform() {
    if [[ -d "${ROOT}/bench/artifacts/waves/${TEST_NAME}" ]]; then
        find "${ROOT}/bench/artifacts/waves/${TEST_NAME}" -maxdepth 1 \( -name '*.fst' -o -name '*.vcd' \) | sort | tail -n 1
        return
    fi
    find "${ROOT}/build/harness" -maxdepth 2 -type f \( -name '*.fst' -o -name '*.vcd' \) | grep "/${TEST_NAME}_" | sort | tail -n 1
}

WAVEFORM="$(find_waveform || true)"
if [[ -z "${WAVEFORM}" ]]; then
    echo "no waveform found for ${TEST_NAME}" >&2
    exit 1
fi

if command -v gtkwave >/dev/null 2>&1; then
    if [[ -f "${LAYOUT_PATH}" ]]; then
        exec gtkwave "${WAVEFORM}" "${LAYOUT_PATH}"
    fi
    exec gtkwave "${WAVEFORM}"
fi

if command -v surfer >/dev/null 2>&1; then
    exec surfer "${WAVEFORM}"
fi

echo "${WAVEFORM}"
