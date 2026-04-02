#!/usr/bin/env bash
set -euo pipefail

ICEBOY_TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ICEBOY_ROOT="$(cd "${ICEBOY_TOOLS_DIR}/.." && pwd)"
ICEBOY_RUN_TESTS="${ICEBOY_ROOT}/tools/run_tests.py"
ICEBOY_ORACLE_SMOKE="${ICEBOY_ROOT}/tools/oracle_smoke.py"
ICEBOY_PYTHON_LOCK="${ICEBOY_ROOT}/toolchain/python.lock"
ICEBOY_TIER_CONFIG="${ICEBOY_ROOT}/test/tiers.yaml"

iceboy_die() {
    echo "error: $*" >&2
    exit 1
}

iceboy_require_file() {
    local path="$1"
    local label="$2"
    [[ -f "$path" ]] || iceboy_die "missing ${label} at ${path}"
}

iceboy_resolve_command() {
    local env_name="$1"
    local fallback="$2"
    if [[ -n "${!env_name:-}" ]]; then
        printf '%s\n' "${!env_name}"
        return 0
    fi
    if [[ -n "$fallback" && -x "$fallback" ]]; then
        printf '%s\n' "$fallback"
        return 0
    fi
    command -v "$fallback" 2>/dev/null || true
}

iceboy_require_command() {
    local label="$1"
    local env_hint="$2"
    local candidate="$3"
    [[ -n "$candidate" ]] || iceboy_die "missing ${label}; install it or set ${env_hint}"
    [[ -x "$candidate" ]] || iceboy_die "missing ${label} executable at ${candidate}"
    printf '%s\n' "$candidate"
}

iceboy_uv_bin() {
    iceboy_resolve_command "ICEBOY_UV_BIN" "uv"
}

iceboy_swim_bin() {
    iceboy_resolve_command "ICEBOY_SWIM_BIN" "${HOME}/.cargo/bin/swim"
}

iceboy_iverilog_bin() {
    iceboy_resolve_command "ICEBOY_IVERILOG_BIN" "iverilog"
}

iceboy_verilator_bin() {
    iceboy_resolve_command "ICEBOY_VERILATOR_BIN" "${ICEBOY_ROOT}/build/oss-cad-suite/bin/verilator"
}

iceboy_yosys_bin() {
    iceboy_resolve_command "ICEBOY_YOSYS_BIN" "${ICEBOY_ROOT}/build/oss-cad-suite/bin/yosys"
}

iceboy_nextpnr_bin() {
    iceboy_resolve_command "ICEBOY_NEXTPNR_BIN" "${ICEBOY_ROOT}/build/oss-cad-suite/bin/nextpnr-ice40"
}

iceboy_sby_bin() {
    iceboy_resolve_command "ICEBOY_SBY_BIN" "${ICEBOY_ROOT}/build/oss-cad-suite/bin/sby"
}

iceboy_version_string() {
    local tool_path="$1"
    shift
    local output
    if ! output="$("$tool_path" "$@" 2>&1)"; then
        iceboy_die "failed to query version for ${tool_path}"
    fi
    output="${output%%$'\n'*}"
    printf '%s\n' "$output"
}

iceboy_uv_package_version() {
    local uv_bin="$1"
    local package_name="$2"
    local output
    if ! output="$("$uv_bin" run --with-requirements "${ICEBOY_PYTHON_LOCK}" python -c "from importlib.metadata import version; print(version('${package_name}'))" 2>&1)"; then
        iceboy_die "failed to query ${package_name} version via uv"
    fi
    output="${output%%$'\n'*}"
    printf '%s\n' "$output"
}

iceboy_log_tool() {
    local label="$1"
    local version="$2"
    echo "[tool] ${label}: ${version}"
}

iceboy_require_simulator() {
    local sim="$1"
    case "$sim" in
        icarus)
            local iverilog_bin
            iverilog_bin="$(iceboy_require_command "iverilog" "ICEBOY_IVERILOG_BIN" "$(iceboy_iverilog_bin)")"
            iceboy_log_tool "iverilog" "$(iceboy_version_string "$iverilog_bin" -V)"
            ;;
        verilator)
            local verilator_bin
            verilator_bin="$(iceboy_require_command "verilator" "ICEBOY_VERILATOR_BIN" "$(iceboy_verilator_bin)")"
            iceboy_log_tool "verilator" "$(iceboy_version_string "$verilator_bin" --version)"
            ;;
        *)
            iceboy_die "unsupported simulator '${sim}'"
            ;;
    esac
}

iceboy_reject_tier_flag() {
    local arg="$1"
    case "$arg" in
        --tier|--tier=*)
            iceboy_die "do not pass --tier directly; use the wrapper's fixed entry point"
            ;;
        --quick)
            iceboy_die "do not pass --quick; use the wrapper's fixed entry point"
            ;;
    esac
}

iceboy_run_or_print() {
    local dry_run="$1"
    shift
    if [[ "$dry_run" == "1" ]]; then
        printf 'DRY RUN:'
        printf ' %q' "$@"
        printf '\n'
        return 0
    fi
    "$@"
}
