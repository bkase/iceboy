#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
SKIP_BUILD=0
PASSTHRU=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            PASSTHRU+=("$1")
            ;;
        --skip-build)
            SKIP_BUILD=1
            PASSTHRU+=("$1")
            ;;
        *)
            iceboy_die "unsupported argument '$1'"
            ;;
    esac
    shift
done

# This ROM checkpoints before the first rendered sprite frame. The first
# rendered frame after the checkpoint is the clean baseline, and the second
# rendered frame is the metadata-corrupted frame. The native runner counts
# completed frames at frame start, so it needs one extra completed frame to
# land on the same image that PyBoy reaches with settle_rendered_frames=2.
export ICEBOY_PPU_WAVE_C_CHECKPOINT_COMPLETED_FRAMES="${ICEBOY_PPU_WAVE_C_CHECKPOINT_COMPLETED_FRAMES:-3}"
export ICEBOY_PPU_WAVE_C_SETTLE_RENDERED_FRAMES="${ICEBOY_PPU_WAVE_C_SETTLE_RENDERED_FRAMES:-2}"
export ICEBOY_PPU_WAVE_C_MAX_MCYCLES="${ICEBOY_PPU_WAVE_C_MAX_MCYCLES:-120000}"

exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/run_ppu_wave_c_verilator.sh" "${PASSTHRU[@]}" --rom-id OBJ_DMA_METADATA_CORRUPT
