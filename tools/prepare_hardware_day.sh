#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
BUILD_SCRIPT="${ICEBOY_ROOT}/tools/build_icebreaker_variant.sh"
SKIP_BUILD_AFTER_FIRST=0

run_variant() {
    local artifact_stem="$1"
    shift

    local args=(
        "${BUILD_SCRIPT}"
        --pack
        --out-dir "${ICEBOY_ROOT}/build/bitstreams"
        --synth-dir "${ICEBOY_ROOT}/build/bitstreams/synth_${artifact_stem}"
        --asc-name "${artifact_stem}.asc"
        --nextpnr-report-name "${artifact_stem}.nextpnr-report.json"
        --nextpnr-log-name "${artifact_stem}.nextpnr.log"
    )

    if [[ "${DRY_RUN}" == "1" ]]; then
        args+=(--dry-run)
    fi
    if [[ "${SKIP_BUILD_AFTER_FIRST}" == "1" ]]; then
        args+=(--skip-build)
    fi

    echo "==> ${artifact_stem}"
    args+=("$@")
    "${args[@]}"
    SKIP_BUILD_AFTER_FIRST=1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        --help|-h)
            cat <<'EOF'
usage: tools/prepare_hardware_day.sh [options]

options:
  --dry-run         Print the underlying build commands without executing them
EOF
            exit 0
            ;;
        *)
            iceboy_die "unexpected argument '$1'"
            ;;
    esac
    shift
done

run_variant \
    "lcd_test_pattern" \
    --top "board::icebreaker_lcd_test_top::icebreaker_lcd_test_top" \
    --module "icebreaker_lcd_test_top" \
    --board-top "${ICEBOY_ROOT}/src/board/icebreaker_lcd_test_top.spade"

run_variant \
    "alu_loop_icebreaker" \
    --top "board::icebreaker_alu_loop_top::icebreaker_alu_loop_top" \
    --module "icebreaker_alu_loop_top" \
    --board-top "${ICEBOY_ROOT}/src/board/icebreaker_alu_loop_top.spade"

run_variant \
    "bg_static_icebreaker" \
    --rom-image "bg_static"

run_variant \
    "joypad_smoke_icebreaker" \
    --rom-image "joypad_bg_smoke"

run_variant \
    "uart_rom_icebreaker" \
    --top "board::icebreaker_uart_rom_top::icebreaker_uart_rom_top" \
    --module "icebreaker_uart_rom_top" \
    --board-top "${ICEBOY_ROOT}/src/board/icebreaker_uart_rom_top.spade"
