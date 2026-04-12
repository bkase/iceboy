#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
SKIP_BUILD=0
SKIP_SYNTH=0
DO_PACK=0
DO_PROGRAM=0
TOP_LABEL=""
TOP_MODULE=""
BOARD_TOP=""
ROM_IMAGE=""
PCF_FILE="${ICEBOY_ROOT}/icebreaker.pcf"
OUT_DIR=""
SYNTH_DIR=""
RECORD_JSON=""
TARGET_FREQ_MHZ="12"
TARGET_DEVICE="iCE40UP5K-SG48"
SPADE_SV="${ICEBOY_ROOT}/build/spade.sv"
NETLIST_NAME=""
STAT_NAME="yosys-stat.txt"
YOSYS_LOG_NAME="yosys.log"
ASC_NAME=""
NEXTPNR_REPORT_NAME="nextpnr-report.json"
NEXTPNR_LOG_NAME="nextpnr.log"
RECORD_VERIFIED_BY="tools/build_icebreaker_variant.sh"
DEBUG_PATTERNS=("CommitTrace" "DebugTrace" "PpuDebugTrace" "SimStimulus" "BusObs" "SocLockstepTopOut")
SWIM_VERILOG_SOURCES=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        --skip-build)
            SKIP_BUILD=1
            ;;
        --skip-synth)
            SKIP_SYNTH=1
            ;;
        --pack)
            DO_PACK=1
            ;;
        --program)
            DO_PROGRAM=1
            DO_PACK=1
            ;;
        --top)
            [[ $# -ge 2 ]] || iceboy_die "--top requires a Spade label"
            TOP_LABEL="$2"
            shift
            ;;
        --rom-image)
            [[ $# -ge 2 ]] || iceboy_die "--rom-image requires a value"
            ROM_IMAGE="$2"
            shift
            ;;
        --module)
            [[ $# -ge 2 ]] || iceboy_die "--module requires a Verilog module name"
            TOP_MODULE="$2"
            shift
            ;;
        --board-top)
            [[ $# -ge 2 ]] || iceboy_die "--board-top requires a path"
            BOARD_TOP="$2"
            shift
            ;;
        --pcf)
            [[ $# -ge 2 ]] || iceboy_die "--pcf requires a path"
            PCF_FILE="$2"
            shift
            ;;
        --out-dir)
            [[ $# -ge 2 ]] || iceboy_die "--out-dir requires a path"
            OUT_DIR="$2"
            shift
            ;;
        --record-json)
            [[ $# -ge 2 ]] || iceboy_die "--record-json requires a path"
            RECORD_JSON="$2"
            shift
            ;;
        --freq-mhz)
            [[ $# -ge 2 ]] || iceboy_die "--freq-mhz requires a value"
            TARGET_FREQ_MHZ="$2"
            shift
            ;;
        --synth-dir)
            [[ $# -ge 2 ]] || iceboy_die "--synth-dir requires a path"
            SYNTH_DIR="$2"
            shift
            ;;
        --netlist-name)
            [[ $# -ge 2 ]] || iceboy_die "--netlist-name requires a filename"
            NETLIST_NAME="$2"
            shift
            ;;
        --stat-name)
            [[ $# -ge 2 ]] || iceboy_die "--stat-name requires a filename"
            STAT_NAME="$2"
            shift
            ;;
        --yosys-log-name)
            [[ $# -ge 2 ]] || iceboy_die "--yosys-log-name requires a filename"
            YOSYS_LOG_NAME="$2"
            shift
            ;;
        --asc-name)
            [[ $# -ge 2 ]] || iceboy_die "--asc-name requires a filename"
            ASC_NAME="$2"
            shift
            ;;
        --nextpnr-report-name)
            [[ $# -ge 2 ]] || iceboy_die "--nextpnr-report-name requires a filename"
            NEXTPNR_REPORT_NAME="$2"
            shift
            ;;
        --nextpnr-log-name)
            [[ $# -ge 2 ]] || iceboy_die "--nextpnr-log-name requires a filename"
            NEXTPNR_LOG_NAME="$2"
            shift
            ;;
        --verified-by)
            [[ $# -ge 2 ]] || iceboy_die "--verified-by requires a label"
            RECORD_VERIFIED_BY="$2"
            shift
            ;;
        --help|-h)
            cat <<'EOF'
usage: tools/build_icebreaker_variant.sh --top <spade-label> [options]

options:
  --rom-image <id>           Visible-top ROM image selector: bg_static or joypad_bg_smoke
  --module <verilog-module>   Verilog top module name; defaults to the tail of --top
  --board-top <path>          Board-top source path; defaults to src/board/<module>.spade
  --pcf <path>                Pin constraints; defaults to icebreaker.pcf
  --out-dir <dir>             Output directory; defaults to build/variants/<module>
  --record-json <path>        Optional baseline JSON output
  --freq-mhz <mhz>            nextpnr frequency target; defaults to 12
  --skip-build                Reuse existing build/spade.sv
  --skip-synth                Reuse existing synthesized netlist/stat outputs
  --pack                      Pack the ASC into a .bin via tools/pack_icebreaker_bitstream.sh
  --program                   Pack, then program the resulting .bin via tools/program_icebreaker.sh
  --dry-run                   Print commands without executing them
EOF
            exit 0
            ;;
        *)
            iceboy_die "unexpected argument '$1'"
            ;;
    esac
    shift
done

if [[ -n "${ROM_IMAGE}" ]]; then
    mapfile -t VISIBLE_VARIANT < <(iceboy_resolve_visible_rom_image "${ROM_IMAGE}")
    if [[ -z "${TOP_LABEL}" ]]; then
        TOP_LABEL="${VISIBLE_VARIANT[0]}"
    fi
    if [[ -z "${TOP_MODULE}" ]]; then
        TOP_MODULE="${VISIBLE_VARIANT[1]}"
    fi
    if [[ -z "${BOARD_TOP}" ]]; then
        BOARD_TOP="${VISIBLE_VARIANT[2]}"
    fi
fi

[[ -n "${TOP_LABEL}" ]] || iceboy_die "--top or --rom-image is required"
if [[ -z "${TOP_MODULE}" ]]; then
    TOP_MODULE="${TOP_LABEL##*::}"
fi
if [[ -z "${BOARD_TOP}" ]]; then
    BOARD_TOP="${ICEBOY_ROOT}/src/board/${TOP_MODULE}.spade"
fi
if [[ -z "${OUT_DIR}" ]]; then
    OUT_DIR="${ICEBOY_ROOT}/build/variants/${TOP_MODULE}"
fi
if [[ -z "${SYNTH_DIR}" ]]; then
    SYNTH_DIR="${OUT_DIR}/synth"
fi
if [[ -z "${NETLIST_NAME}" ]]; then
    NETLIST_NAME="${TOP_MODULE}.json"
fi
if [[ -z "${ASC_NAME}" ]]; then
    ASC_NAME="${TOP_MODULE}.asc"
fi

SYNTH_JSON="${SYNTH_DIR}/${NETLIST_NAME}"
YOSYS_STAT="${SYNTH_DIR}/${STAT_NAME}"
YOSYS_LOG="${SYNTH_DIR}/${YOSYS_LOG_NAME}"
ASC_FILE="${OUT_DIR}/${ASC_NAME}"
NEXTPNR_REPORT="${OUT_DIR}/${NEXTPNR_REPORT_NAME}"
NEXTPNR_LOG="${OUT_DIR}/${NEXTPNR_LOG_NAME}"
PACKED_BIN="${OUT_DIR}/${ASC_NAME%.asc}.bin"
PACK_SCRIPT="${ICEBOY_ROOT}/tools/pack_icebreaker_bitstream.sh"
PROGRAM_SCRIPT="${ICEBOY_ROOT}/tools/program_icebreaker.sh"
PCF_BASENAME="$(basename "${PCF_FILE}")"

iceboy_require_file "${PCF_FILE}" "icebreaker pin constraints"
iceboy_require_file "${BOARD_TOP}" "hardware board top"

UV_BIN="$(iceboy_require_command "uv" "ICEBOY_UV_BIN" "$(iceboy_uv_bin)")"
SWIM_BIN="$(iceboy_require_command "swim" "ICEBOY_SWIM_BIN" "$(iceboy_swim_bin)")"
YOSYS_BIN="$(iceboy_require_command "yosys" "ICEBOY_YOSYS_BIN" "$(iceboy_yosys_bin)")"
NEXTPNR_BIN="$(iceboy_require_command "nextpnr-ice40" "ICEBOY_NEXTPNR_BIN" "$(iceboy_nextpnr_bin)")"

UV_VERSION="$(iceboy_version_string "${UV_BIN}" --version)"
SWIM_VERSION="$(iceboy_version_string "${SWIM_BIN}" --version)"
YOSYS_VERSION="$(iceboy_version_string "${YOSYS_BIN}" -V)"
NEXTPNR_VERSION="$(iceboy_version_string "${NEXTPNR_BIN}" --version)"

iceboy_log_tool "uv" "${UV_VERSION}"
iceboy_log_tool "swim" "${SWIM_VERSION}"
iceboy_log_tool "yosys" "${YOSYS_VERSION}"
iceboy_log_tool "nextpnr-ice40" "${NEXTPNR_VERSION}"

YOSYS_SCRIPT=$(
    cat <<EOF
read_verilog -sv "${SPADE_SV}";
$(iceboy_yosys_read_swim_verilog_commands)
synth_ice40 -top ${TOP_MODULE} -json "${SYNTH_JSON}";
tee -q -o "${YOSYS_STAT}" stat;
EOF
)

if [[ "${DRY_RUN}" == "1" ]]; then
    if [[ "${SKIP_BUILD}" == "1" ]]; then
        echo "DRY RUN: skip swim build"
    else
        printf 'DRY RUN: %q build\n' "${SWIM_BIN}"
    fi
    if [[ "${SKIP_SYNTH}" == "1" ]]; then
        echo "DRY RUN: skip yosys synth"
    else
        printf 'DRY RUN: %q -q -p %q > %q 2>&1\n' "${YOSYS_BIN}" "${YOSYS_SCRIPT}" "${YOSYS_LOG}"
    fi
    if [[ -n "${ROM_IMAGE}" ]]; then
        echo "DRY RUN: rom-image ${ROM_IMAGE}"
    fi
    echo "DRY RUN: top ${TOP_LABEL}"
    echo "DRY RUN: module ${TOP_MODULE}"
    echo "DRY RUN: board-top ${BOARD_TOP}"
    echo "DRY RUN: outputs ${SYNTH_JSON} ${YOSYS_STAT} ${ASC_FILE}"
    echo "DRY RUN: forbid debug patterns ${DEBUG_PATTERNS[*]}"
    printf 'DRY RUN: %q --up5k --package sg48 --json %q --pcf %q --asc %q --freq %q --report %q --timing-allow-fail > %q 2>&1\n' \
        "${NEXTPNR_BIN}" \
        "${SYNTH_JSON}" \
        "${PCF_FILE}" \
        "${ASC_FILE}" \
        "${TARGET_FREQ_MHZ}" \
        "${NEXTPNR_REPORT}" \
        "${NEXTPNR_LOG}"
    if [[ -n "${RECORD_JSON}" ]]; then
        echo "DRY RUN: write baseline record ${RECORD_JSON}"
    fi
    if [[ "${DO_PACK}" == "1" ]]; then
        printf 'DRY RUN: %q --asc %q --out %q\n' "${PACK_SCRIPT}" "${ASC_FILE}" "${PACKED_BIN}"
    fi
    if [[ "${DO_PROGRAM}" == "1" ]]; then
        printf 'DRY RUN: %q --bin %q\n' "${PROGRAM_SCRIPT}" "${PACKED_BIN}"
    fi
    exit 0
fi

mkdir -p "${OUT_DIR}" "${SYNTH_DIR}"
if [[ -n "${RECORD_JSON}" ]]; then
    mkdir -p "$(dirname "${RECORD_JSON}")"
fi

if [[ "${SKIP_BUILD}" != "1" ]]; then
    "${SWIM_BIN}" build
fi

iceboy_require_file "${SPADE_SV}" "generated Verilog"
while IFS= read -r source; do
    [[ -n "${source}" ]] || continue
    SWIM_VERILOG_SOURCES+=("${source}")
done < <(iceboy_swim_verilog_sources)
for source in "${SWIM_VERILOG_SOURCES[@]}"; do
    iceboy_require_file "${source}" "repo Verilog source"
done
if ! rg -n "module ${TOP_MODULE}\\b" "${SPADE_SV}" >/dev/null; then
    iceboy_die "generated Verilog does not contain top '${TOP_MODULE}'"
fi
if [[ "${SKIP_SYNTH}" != "1" ]]; then
    "${YOSYS_BIN}" -q -p "${YOSYS_SCRIPT}" > "${YOSYS_LOG}" 2>&1
fi

iceboy_require_file "${SYNTH_JSON}" "synthesized hardware netlist"
iceboy_require_file "${YOSYS_STAT}" "Yosys resource report"

for pattern in "${DEBUG_PATTERNS[@]}"; do
    if rg -n "${pattern}" "${SYNTH_JSON}" >/dev/null; then
        iceboy_die "hardware netlist contains forbidden debug symbol '${pattern}'"
    fi
done

"${NEXTPNR_BIN}" \
    --up5k \
    --package sg48 \
    --json "${SYNTH_JSON}" \
    --pcf "${PCF_FILE}" \
    --asc "${ASC_FILE}" \
    --freq "${TARGET_FREQ_MHZ}" \
    --report "${NEXTPNR_REPORT}" \
    --timing-allow-fail \
    > "${NEXTPNR_LOG}" 2>&1 || true

if [[ -n "${RECORD_JSON}" ]]; then
    "${UV_BIN}" run --with-requirements "${ICEBOY_PYTHON_LOCK}" python - \
        "${YOSYS_STAT}" \
        "${NEXTPNR_REPORT}" \
        "${NEXTPNR_LOG}" \
        "${BOARD_TOP}" \
        "${RECORD_JSON}" \
        "${TARGET_FREQ_MHZ}" \
        "${TOP_LABEL}" \
        "${TARGET_DEVICE}" \
        "${SWIM_VERSION}" \
        "${YOSYS_VERSION}" \
        "${NEXTPNR_VERSION}" \
        "${ASC_FILE}" \
        "${PCF_BASENAME}" \
        "${RECORD_VERIFIED_BY}" \
        <<'PY'
import json
import re
import sys
from datetime import date
from pathlib import Path

(
    yosys_stat_path,
    nextpnr_report_path,
    nextpnr_log_path,
    board_top_path,
    record_json_path,
    target_freq_mhz,
    top_label,
    target_device,
    swim_version,
    yosys_version,
    nextpnr_version,
    asc_path,
    pcf_basename,
    verified_by,
) = sys.argv[1:]

yosys_stat = Path(yosys_stat_path).read_text(encoding="utf-8")
nextpnr_log = Path(nextpnr_log_path).read_text(encoding="utf-8")
report_path = Path(nextpnr_report_path)
report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
board_top = Path(board_top_path).read_text(encoding="utf-8")


def stat_count(prefix: str) -> int:
    total = 0
    for line in yosys_stat.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].startswith(prefix):
            total += int(parts[0])
    return total


def parse_log_utilization(name: str):
    pattern = re.compile(rf"{re.escape(name)}:\s+(\d+)/\s+(\d+)")
    match = pattern.search(nextpnr_log)
    if not match:
        return {"used": None, "available": None}
    return {"used": int(match.group(1)), "available": int(match.group(2))}


fmax_entries = report.get("fmax", {})
if fmax_entries:
    clock_name, clock_metrics = next(iter(sorted(fmax_entries.items())))
else:
    clock_name, clock_metrics = "CLK", {"achieved": None, "constraint": float(target_freq_mhz)}

utilization = report.get("utilization", {})
logic_cells = utilization.get("ICESTORM_LC", parse_log_utilization("ICESTORM_LC"))
spram = utilization.get("ICESTORM_SPRAM", parse_log_utilization("ICESTORM_SPRAM"))
ebr = utilization.get("ICESTORM_RAM", parse_log_utilization("ICESTORM_RAM"))
m_ce_loads = len(re.findall(r"\btb\.m_ce\b", board_top))
error_lines = [line for line in nextpnr_log.splitlines() if line.startswith("ERROR:")]
pnr_failed = bool(error_lines)

baseline = {
    "captured_on": date.today().isoformat(),
    "board": "iCEBreaker",
    "device": target_device,
    "top": top_label,
    "pin_constraints": pcf_basename,
    "clock_constraint": {
        "target_mhz": float(target_freq_mhz),
        "clock_name": clock_name,
        "achieved_mhz": clock_metrics.get("achieved"),
        "constraint_mhz": clock_metrics.get("constraint"),
        "timing_met": None
        if clock_metrics.get("achieved") is None
        else bool(clock_metrics.get("achieved", 0.0) >= float(target_freq_mhz)),
    },
    "utilization": {
        "logic_cells_used": logic_cells.get("used"),
        "logic_cells_available": logic_cells.get("available"),
        "lut4_used": stat_count("SB_LUT4"),
        "lut4_available": 5280,
        "dff_used": stat_count("SB_DFF"),
        "dff_available": 1024,
        "carry_used": stat_count("SB_CARRY"),
        "spram_used": spram.get("used"),
        "spram_available": spram.get("available"),
        "ebr_used": ebr.get("used"),
        "ebr_available": ebr.get("available"),
        "fits_up5k_lut4": bool(stat_count("SB_LUT4") <= 5280),
        "fits_up5k_dff": bool(stat_count("SB_DFF") <= 1024),
    },
    "clock_enable": {
        "signal": "tb.m_ce",
        "board_top_loads": m_ce_loads,
        "method": "source_occurrence_count",
    },
    "debug_free": {
        "forbidden_debug_symbols_present": False,
        "verified_by": verified_by,
    },
    "pnr": {
        "status": "failed" if pnr_failed else "passed",
        "error": error_lines[0] if error_lines else None,
        "timing_report_available": report_path.exists(),
    },
    "tool_versions": {
        "swim": swim_version,
        "yosys": yosys_version,
        "nextpnr-ice40": nextpnr_version,
    },
    "artifacts": {
        "asc": asc_path,
        "nextpnr_report": str(report_path),
        "nextpnr_log": nextpnr_log_path,
        "yosys_stat": yosys_stat_path,
    },
}

Path(record_json_path).write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
fi

if [[ "${DO_PACK}" == "1" ]]; then
    iceboy_require_file "${PACK_SCRIPT}" "bitstream pack wrapper"
    "${PACK_SCRIPT}" --asc "${ASC_FILE}" --out "${PACKED_BIN}"
fi
if [[ "${DO_PROGRAM}" == "1" ]]; then
    iceboy_require_file "${PROGRAM_SCRIPT}" "bitstream program wrapper"
    "${PROGRAM_SCRIPT}" --bin "${PACKED_BIN}"
fi

echo "Built ${TOP_LABEL} (${TOP_MODULE}) via the shared iCEBreaker variant flow."
