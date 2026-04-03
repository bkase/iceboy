#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

SWIM="${HOME}/.cargo/bin/swim"
UV_BIN="$(command -v uv || true)"
export PATH="/opt/homebrew/bin:$PATH"
ACTIVE_PID=""
RUN_FORMAL="${ICEBOY_PRECOMMIT_INCLUDE_FORMAL:-0}"

SKIP_PYTHON_MODULES=(
    "tools.tests.test_spade_cocotb_pipeline"
    "tools.tests.test_verilator_backend"
    "tools.tests.test_alu_generated_vectors"
)

PRECOMMIT_SWIM_TESTS=(
    "test/harness/test_spade_cocotb_integration.py"
    "test/harness/test_e2e_smoke.py"
    "test/harness/test_reset_profile.py"
    "test/unit/test_main.py"
    "test/unit/test_alu.py"
    "test/unit/test_decode.py"
    "test/unit/test_decode_cb.py"
    "test/unit/test_interrupt_service.py"
    "test/unit/test_interrupts_basic.py"
    "test/unit/test_timer.py"
    "test/unit/test_timebase.py"
    "test/lockstep/test_cpu_lockstep.py"
    "test/lockstep/test_interrupt_injection.py"
    "test/lockstep/test_ei_halt_corners.py"
    "test/rom/test_loads_basic.py"
    "test/rom/test_alu16_sp.py"
)

if [[ ! -x "$SWIM" ]]; then
    echo -e "${RED}Missing swim at ${SWIM}${NC}"
    exit 1
fi

if [[ -z "$UV_BIN" ]]; then
    echo -e "${RED}Missing uv in PATH${NC}"
    exit 1
fi

collect_descendants() {
    local root="$1"
    ps -axo pid=,ppid= | awk -v root="$root" '
        {
            pid = $1
            ppid = $2
            children[ppid] = children[ppid] " " pid
        }
        END {
            head = 1
            tail = 1
            queue[tail] = root
            while (head <= tail) {
                current = queue[head++]
                split(children[current], items, " ")
                for (i in items) {
                    if (items[i] == "") {
                        continue
                    }
                    print items[i]
                    queue[++tail] = items[i]
                }
            }
        }
    '
}

cleanup_active_process() {
    local pid descendants

    pid="${ACTIVE_PID:-}"
    if [[ -z "$pid" ]]; then
        return
    fi

    descendants="$(collect_descendants "$pid")"
    if [[ -n "$descendants" ]]; then
        kill -TERM $descendants 2>/dev/null || true
    fi
    kill -TERM "$pid" 2>/dev/null || true
    sleep 1
    descendants="$(collect_descendants "$pid")"
    if [[ -n "$descendants" ]]; then
        kill -KILL $descendants 2>/dev/null || true
    fi
    kill -KILL "$pid" 2>/dev/null || true
    ACTIVE_PID=""
}

trap cleanup_active_process EXIT INT TERM

run_checked() {
    local output_file output rc

    output_file="$(mktemp)"
    set +e
    "$@" >"$output_file" 2>&1 &
    ACTIVE_PID=$!
    wait "$ACTIVE_PID"
    rc=$?
    ACTIVE_PID=""
    set -e

    output="$(cat "$output_file")"
    rm -f "$output_file"

    if [[ $rc -eq 0 ]]; then
        echo -e "${GREEN}OK${NC}"
        return 0
    fi

    echo -e "${RED}FAILED${NC}"
    [[ -n "$output" ]] && echo "$output"
    exit "$rc"
}

module_is_skipped() {
    local module="$1"
    local skip

    for skip in "${SKIP_PYTHON_MODULES[@]}"; do
        if [[ "$module" == "$skip" ]]; then
            return 0
        fi
    done

    return 1
}

python_precommit_modules() {
    local test_file module

    while IFS= read -r test_file; do
        module="${test_file%.py}"
        module="${module//\//.}"
        if module_is_skipped "$module"; then
            continue
        fi
        printf '%s\n' "$module"
    done < <(find tools/tests -type f -name 'test_*.py' | sort)
}

patch_cocotb_config_wrapper() {
    local bindir
    local config
    local config_py

    bindir="$(pwd)/build/oss-cad-suite/bin"
    config="${bindir}/cocotb-config"
    config_py="${bindir}/cocotb-config.py"

    if [[ ! -f "$config" ]]; then
        return
    fi

    cat >"$config_py" <<'EOF'
import re
import sys
from cocotb.config import main

if __name__ == "__main__":
    sys.argv[0] = re.sub(r"(-script\.pyw|\.exe)?$", "", sys.argv[0])
    raise SystemExit(main())
EOF

    cat >"$config" <<EOF
#!/usr/bin/env bash
set -euo pipefail
bindir="\$(cd "\$(dirname "\$0")" && pwd)"
repo_root="\$(cd "\$bindir/../.." && pwd)"
case "\$PWD" in
  "\$repo_root"/build/*) ln -sfn "\$bindir/../lib" "\$PWD/lib" ;;
esac
exec "\$bindir/tabbypy3" "\$bindir/cocotb-config.py" "\$@"
EOF
    chmod +x "$config_py"
    chmod +x "$config"
}

echo "=== Pre-commit checks ==="

echo -n "Validating ROM manifests... "
run_checked "$UV_BIN" run --with-requirements toolchain/python.lock python tools/validate_rom_manifests.py

echo -n "Building ROM templates... "
run_checked bench/roms/build_roms.sh

if find tools/tests -type f -name 'test_*.py' -print -quit | grep -q .; then
    PRECOMMIT_PYTHON_MODULES=()
    while IFS= read -r module; do
        PRECOMMIT_PYTHON_MODULES+=("$module")
    done < <(python_precommit_modules)

    if [[ ${#PRECOMMIT_PYTHON_MODULES[@]} -gt 0 ]]; then
        echo -n "Running fast Python spec tests... "
        run_checked "$UV_BIN" run --with-requirements toolchain/python.lock python -m unittest "${PRECOMMIT_PYTHON_MODULES[@]}"
    fi
fi

echo -n "Compiling... "
run_checked "$SWIM" build

echo -n "Synthesizing... "
run_checked "$SWIM" synth

if [[ "$RUN_FORMAL" == "1" ]]; then
    echo -n "Running formal checks... "
    run_checked "$UV_BIN" run --with-requirements toolchain/python.lock python tools/run_tests.py --tier formal
else
    echo -e "Formal checks: ${YELLOW}skipped in pre-commit (set ICEBOY_PRECOMMIT_INCLUDE_FORMAL=1 to enable)${NC}"
fi

patch_cocotb_config_wrapper

if find test -type f -name 'test_*.py' -print -quit | grep -q .; then
    if command -v iverilog >/dev/null 2>&1 || command -v verilator >/dev/null 2>&1 || [[ -x /opt/homebrew/bin/verilator ]]; then
        echo -n "Provisioning simulator Python deps... "
        run_checked tools/ensure_swim_python_deps.sh

        echo "Running curated simulator suites..."
        for test_file in "${PRECOMMIT_SWIM_TESTS[@]}"; do
            printf '  %s... ' "$test_file"
            run_checked "$SWIM" test "$test_file"
        done
    else
        echo -e "Tests: ${YELLOW}skipped (no simulator: install icarus-verilog or verilator)${NC}"
    fi
else
    echo -e "Tests: ${YELLOW}skipped (no test files)${NC}"
fi

echo -e "${GREEN}All checks passed.${NC}"
