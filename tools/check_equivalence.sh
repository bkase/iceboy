#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
TOP=""
OUT_DIR="${ICEBOY_ROOT}/build/formal/cpu_refactor"
TEMPLATE="${ICEBOY_ROOT}/formal/cpu_refactor.eqy"
GENERATED_NAME="cpu_refactor.generated.eqy"
POSITIONAL=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        --top)
            [[ $# -ge 2 ]] || iceboy_die "--top requires a module name"
            TOP="$2"
            shift
            ;;
        --out-dir)
            [[ $# -ge 2 ]] || iceboy_die "--out-dir requires a path"
            OUT_DIR="$2"
            shift
            ;;
        --template)
            [[ $# -ge 2 ]] || iceboy_die "--template requires a path"
            TEMPLATE="$2"
            shift
            ;;
        --generated-name)
            [[ $# -ge 2 ]] || iceboy_die "--generated-name requires a filename"
            GENERATED_NAME="$2"
            shift
            ;;
        --help|-h)
            cat <<'EOF'
usage: tools/check_equivalence.sh --top <module> [--out-dir <dir>] [--template <eqy>] [--generated-name <file>] [--dry-run] <before.v> <after.v>
EOF
            exit 0
            ;;
        *)
            POSITIONAL+=("$1")
            ;;
    esac
    shift
done

[[ -n "${TOP}" ]] || iceboy_die "missing --top <module>"
[[ ${#POSITIONAL[@]} -eq 2 ]] || iceboy_die "expected <before.v> and <after.v>"

GOLD_VERILOG="${POSITIONAL[0]}"
GATE_VERILOG="${POSITIONAL[1]}"
GENERATED_EQY="${OUT_DIR}/${GENERATED_NAME}"

iceboy_require_file "${TEMPLATE}" "equivalence eqy template"
iceboy_require_file "${GOLD_VERILOG}" "gold verilog design"
iceboy_require_file "${GATE_VERILOG}" "gate verilog design"

EQY_BIN="$(iceboy_require_command "eqy" "ICEBOY_EQY_BIN" "$(iceboy_eqy_bin)")"
YOSYS_BIN="$(iceboy_require_command "yosys" "ICEBOY_YOSYS_BIN" "$(iceboy_yosys_bin)")"
iceboy_log_tool "eqy" "$(iceboy_version_string "${EQY_BIN}" --version)"
iceboy_log_tool "yosys" "$(iceboy_version_string "${YOSYS_BIN}" -V)"

if [[ "${DRY_RUN}" == "1" ]]; then
    echo "DRY RUN: render ${TEMPLATE} -> ${GENERATED_EQY}"
    echo "DRY RUN: top=${TOP} gold=${GOLD_VERILOG} gate=${GATE_VERILOG}"
    printf 'DRY RUN: %q --yosys %q -f -d %q %q\n' "${EQY_BIN}" "${YOSYS_BIN}" "${OUT_DIR}" "${GENERATED_EQY}"
    exit 0
fi

mkdir -p "${OUT_DIR}"
sed \
    -e "s|__TOP__|${TOP}|g" \
    -e "s|__GOLD_VERILOG__|${GOLD_VERILOG}|g" \
    -e "s|__GATE_VERILOG__|${GATE_VERILOG}|g" \
    "${TEMPLATE}" > "${GENERATED_EQY}"

"${EQY_BIN}" --yosys "${YOSYS_BIN}" -f -d "${OUT_DIR}" "${GENERATED_EQY}"
