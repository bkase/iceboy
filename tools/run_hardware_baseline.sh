#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/entrypoint_common.sh"

DRY_RUN=0
SKIP_BUILD=0
SKIP_SYNTH=0
OUT_DIR="${ICEBOY_ROOT}/build/hw_baseline"
RECORD_JSON="${ICEBOY_ROOT}/docs/hardware/icebreaker_up5k_baseline.json"
TARGET_FREQ_MHZ="12"
PCF_FILE="${ICEBOY_ROOT}/icebreaker.pcf"
TOP_LABEL="board::icebreaker_top::icebreaker_top"
TARGET_DEVICE="iCE40UP5K-SG48"
SPADE_SV="${ICEBOY_ROOT}/build/spade.sv"
DEBUG_PATTERNS=("CommitTrace" "DebugTrace" "PpuDebugTrace" "SimStimulus" "BusObs" "SocLockstepTopOut")

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
        --help|-h)
            cat <<'EOF'
usage: tools/run_hardware_baseline.sh [--dry-run] [--skip-build] [--skip-synth] [--out-dir <dir>] [--record-json <path>] [--freq-mhz <mhz>]
EOF
            exit 0
            ;;
        *)
            iceboy_die "unexpected argument '$1'"
            ;;
    esac
    shift
done

SYNTH_DIR="${OUT_DIR}/synth"
ASC_FILE="${OUT_DIR}/icebreaker.asc"
NEXTPNR_REPORT="${OUT_DIR}/nextpnr-report.json"
NEXTPNR_LOG="${OUT_DIR}/nextpnr.log"
SYNTH_JSON="${SYNTH_DIR}/hardware.json"
YOSYS_STAT="${SYNTH_DIR}/yosys-stat.txt"
YOSYS_LOG="${SYNTH_DIR}/yosys.log"

iceboy_require_file "${PCF_FILE}" "icebreaker pin constraints"

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
synth_ice40 -top icebreaker_top -json "${SYNTH_JSON}";
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
    printf 'DRY RUN: %q --up5k --package sg48 --json %q --pcf %q --asc %q --freq %q --report %q --timing-allow-fail\n' \
        "${NEXTPNR_BIN}" \
        "${SYNTH_JSON}" \
        "${PCF_FILE}" \
        "${ASC_FILE}" \
        "${TARGET_FREQ_MHZ}" \
        "${NEXTPNR_REPORT}"
    printf 'DRY RUN: write baseline record %q\n' "${RECORD_JSON}"
    exit 0
fi

mkdir -p "${OUT_DIR}"
mkdir -p "$(dirname "${RECORD_JSON}")"
mkdir -p "${SYNTH_DIR}"

if [[ "${SKIP_BUILD}" != "1" ]]; then
    "${SWIM_BIN}" build
fi

iceboy_require_file "${SPADE_SV}" "generated Verilog"
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

"${UV_BIN}" run --with-requirements "${ICEBOY_PYTHON_LOCK}" python - \
    "${YOSYS_STAT}" \
    "${NEXTPNR_REPORT}" \
    "${NEXTPNR_LOG}" \
    "${ICEBOY_ROOT}/src/board/icebreaker_top.spade" \
    "${RECORD_JSON}" \
    "${TARGET_FREQ_MHZ}" \
    "${TOP_LABEL}" \
    "${TARGET_DEVICE}" \
    "${SWIM_VERSION}" \
    "${YOSYS_VERSION}" \
    "${NEXTPNR_VERSION}" \
    "${ASC_FILE}" \
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
    "pin_constraints": "icebreaker.pcf",
    "clock_constraint": {
        "target_mhz": float(target_freq_mhz),
        "clock_name": clock_name,
        "achieved_mhz": clock_metrics.get("achieved"),
        "constraint_mhz": clock_metrics.get("constraint"),
        "timing_met": None if clock_metrics.get("achieved") is None else bool(clock_metrics.get("achieved", 0.0) >= float(target_freq_mhz)),
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
        "verified_by": "tools/run_hardware_baseline.sh",
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
        "yosys_stat": str(Path(yosys_stat_path).resolve()),
        "nextpnr_report": str(Path(nextpnr_report_path).resolve()),
        "nextpnr_log": str(Path(nextpnr_log_path).resolve()),
        "asc": str(Path(asc_path).resolve()),
    },
}

record_path = Path(record_json_path)
record_path.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"Wrote hardware baseline to {record_path}")
PY
