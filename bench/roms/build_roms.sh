#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUT_DIR="${SCRIPT_DIR}/out"
VALIDATOR="${REPO_ROOT}/bench/tools/validate_rom_abi.py"
PY_LOCK="${REPO_ROOT}/toolchain/python.lock"
UV_BIN="${UV_BIN:-$(command -v uv || true)}"

require_tool() {
    local tool="$1"
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "Missing required tool: $tool" >&2
        exit 1
    fi
}

require_tool rgbasm
require_tool rgblink
require_tool rgbfix

if [[ -z "${UV_BIN}" ]]; then
    echo "Missing uv in PATH" >&2
    exit 1
fi

mkdir -p "${OUT_DIR}"

build_one() {
    local asm_path="$1"
    local base
    local obj_path
    local rom_path
    local sym_path
    local map_path
    local title
    local mbc_type
    local ram_size

    base="$(basename "${asm_path%.asm}")"
    obj_path="${OUT_DIR}/${base}.o"
    rom_path="${OUT_DIR}/${base}.gb"
    sym_path="${OUT_DIR}/${base}.sym"
    map_path="${OUT_DIR}/${base}.map"
    title="$(printf 'ICEBOY%-10s' "${base^^}" | tr -cd 'A-Z0-9' | cut -c1-16)"
    mbc_type="0x00"
    ram_size="0x00"

    case "${base}" in
        MBC1_SWITCH)
            mbc_type="0x01"
            ;;
        MBC1_RAM)
            mbc_type="0x02"
            ram_size="0x03"
            ;;
        MBC3_SWITCH)
            mbc_type="0x11"
            ;;
        MBC3_RAM)
            mbc_type="0x10"
            ram_size="0x03"
            ;;
    esac

    rgbasm -I "${SCRIPT_DIR}" -o "${obj_path}" "${asm_path}"
    rgblink -n "${sym_path}" -m "${map_path}" -o "${rom_path}" "${obj_path}"
    rgbfix -v -p 0xFF -m "${mbc_type}" -r "${ram_size}" -t "${title}" "${rom_path}"
    "${UV_BIN}" run --with-requirements "${PY_LOCK}" python "${VALIDATOR}" --sym "${sym_path}" --asm "${asm_path}" --rom "${rom_path}"
}

mapfile -t asm_files < <(find "${SCRIPT_DIR}" -maxdepth 1 -type f -name '*.asm' | sort)

if [[ "${#asm_files[@]}" -eq 0 ]]; then
    echo "No ROM sources found under ${SCRIPT_DIR}" >&2
    exit 1
fi

for asm_path in "${asm_files[@]}"; do
    build_one "${asm_path}"
done

echo "Built ${#asm_files[@]} ROM(s) into ${OUT_DIR}"
