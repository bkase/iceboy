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
RUN_EXTENDED="${ICEBOY_PRECOMMIT_EXTENDED:-0}"
RUN_SYNTH="${ICEBOY_PRECOMMIT_INCLUDE_SYNTH:-0}"
ENFORCE_SYNTH_BUDGET="${ICEBOY_PRECOMMIT_ENFORCE_BUDGET:-1}"
LOCK_DIR="$(pwd)/build/precommit.lock"
LOCK_PID_FILE="${LOCK_DIR}/pid"

SKIP_PYTHON_MODULES=(
    "tools.tests.test_spade_cocotb_pipeline"
    "tools.tests.test_verilator_backend"
    "tools.tests.test_alu_generated_vectors"
)

PRECOMMIT_SWIM_TESTS_DEFAULT=(
    "test/harness/test_e2e_smoke.py"
    "test/unit/test_main.py"
    "test/unit/test_reset_bridge.py"
    "test/unit/test_decode.py"
    "test/unit/test_decode_cb.py"
    "test/unit/test_event_bridge.py"
    "test/unit/test_hram_ebr.py"
    "test/unit/test_bus_fabric.py"
    "test/unit/test_membus.py"
    "test/unit/test_memory_map.py"
    "test/unit/test_regs.py"
    "test/unit/test_regs_bg_window.py"
    "test/ppu/unit/test_access_policy.py"
    "test/ppu/unit/test_bg_fetcher.py"
    "test/ppu/unit/test_line_summary.py"
    "test/ppu/unit/test_oam_dma_mode2.py"
    "test/ppu/unit/test_oam_scan.py"
    "test/ppu/unit/test_scanout_blank.py"
    "tools/run_ppu_wave_b_mealybug_verilator.sh"
    "test/unit/test_interrupt_service.py"
    "test/unit/test_joypad.py"
    "test/unit/test_joypad_interrupts.py"
    "test/unit/test_timer.py"
)

PRECOMMIT_SWIM_TESTS_EXTENDED=(
    "test/harness/test_spade_cocotb_integration.py"
    "test/harness/test_reset_profile.py"
    "test/unit/test_main.py"
    "test/unit/test_alu.py"
    "test/unit/test_halt_bug.py"
    "test/unit/test_membus.py"
    "test/unit/test_membus_alu_loop.py"
    "test/unit/test_oam_dma.py"
    "test/unit/test_hram_ebr.py"
    "test/unit/test_oam_ebr.py"
    "test/unit/test_rom_baked_ebr.py"
    "test/unit/test_rom_spram_rw.py"
    "test/unit/test_rom_spram.py"
    "test/unit/test_semantics_alu.py"
    "test/unit/test_semantics_flow.py"
    "test/unit/test_semantics_loads.py"
    "test/unit/test_spram.py"
    "test/unit/test_semantics_wordalu.py"
    "test/unit/test_write_enable.py"
    "test/unit/test_event_bridge.py"
    "test/unit/test_frame_sink.py"
    "test/unit/test_interrupts_basic.py"
    "test/unit/test_joypad.py"
    "test/unit/test_joypad_interrupts.py"
    "test/unit/test_rom_uploader.py"
    "test/unit/test_serial.py"
    "test/unit/test_st7789_lcd.py"
    "test/unit/test_button_bank.py"
    "test/unit/test_uart_rx.py"
    "test/unit/test_icebreaker_alu_loop_top.py"
    "test/unit/test_framebuffer_spram.py"
    "test/unit/test_hw_backend.py"
    "test/unit/test_vram_ebr.py"
    "test/unit/test_timebase.py"
    "test/unit/test_ppu_timing.py"
    "test/unit/test_video_backend_adapter.py"
    "test/lockstep/test_cpu_lockstep.py"
    "test/lockstep/test_ei_halt_corners.py"
    "test/lockstep/test_interrupt_injection.py"
    "test/power/test_duty_cycle_metrics.py"
    "test/power/test_halt_quiescence.py"
    "test/rom/test_dma_oam_copy.py"
    "test/rom/test_oam_dma_isolation.py"
    "test/rom/test_ei_delay.py"
    "test/rom/test_alu16_sp.py"
    "test/rom/test_joy_diverge_persist.py"
    "tools/run_joypad_bg_smoke_verilator.sh"
    "test/rom/test_mbc1_switch.py"
    "test/rom/test_mbc1_ram.py"
    "test/rom/test_mbc3_ram.py"
    "test/rom/test_mbc3_switch.py"
    "test/ppu/unit/test_ppu_modes.py"
    "test/ppu/unit/test_stat_irq.py"
    "test/ppu/unit/test_ppu_invariants.py"
    "test/harness/test_arch_time_invariants.py"
    "test/harness/test_soc_lockstep_top.py"
    "test/harness/test_soc_rom_top.py"
    "test/rom/test_ppu_wave_a.py"
    "tools/run_ppu_wave_a_mooneye_verilator.sh"
    "test/rom/test_ppu_wave_b.py"
    "tools/run_ppu_wave_c_verilator.sh"
    "tools/run_ppu_checker_ball_verilator.sh"
    "tools/run_dma_mode2_hide_verilator.sh"
    "tools/run_obj_dma_metadata_corrupt_verilator.sh"
    "test/rom/test_timer_div_basic.py"
    "test/rom/test_timer_irq_halt.py"
    "test/rom/test_loads_basic.py"
    "tools/run_icebreaker_alu_loop_verilator.sh"
    "tools/run_cpu_instrs_blargg_verilator.sh"
    "test/ppu/unit/test_ppu_core_smoke.py"
    "test/ppu/unit/test_bg_transfer_live.py"
    "test/ppu/unit/test_bg_fifo.py"
    "test/ppu/unit/test_mixer.py"
    "test/ppu/unit/test_obj_observe.py"
    "test/ppu/unit/test_obj_priority.py"
    "test/ppu/unit/test_obj_fetch.py"
    "test/ppu/unit/test_transfer_penalty.py"
    "test/ppu/unit/test_obj_transfer_live.py"
    "test/ppu/unit/test_window.py"
    "test/ppu/unit/test_tile.py"
    "test/power/test_ppu_power_quiescence.py"
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

release_precommit_lock() {
    if [[ -f "$LOCK_PID_FILE" ]] && [[ "$(cat "$LOCK_PID_FILE" 2>/dev/null || true)" == "$$" ]]; then
        rm -rf "$LOCK_DIR"
    fi
}

acquire_precommit_lock() {
    local holder_pid=""

    mkdir -p "$(dirname "$LOCK_DIR")"
    if mkdir "$LOCK_DIR" 2>/dev/null; then
        printf '%s\n' "$$" >"$LOCK_PID_FILE"
        return 0
    fi

    if [[ -f "$LOCK_PID_FILE" ]]; then
        holder_pid="$(cat "$LOCK_PID_FILE" 2>/dev/null || true)"
    fi

    if [[ -n "$holder_pid" ]] && kill -0 "$holder_pid" 2>/dev/null; then
        echo -e "${RED}Another pre-commit hook is already running (pid ${holder_pid}). Refusing to start a duplicate run.${NC}" >&2
        echo -e "${YELLOW}Wait for the existing hook to finish or stop it before retrying the commit.${NC}" >&2
        exit 1
    fi

    rm -rf "$LOCK_DIR"
    if mkdir "$LOCK_DIR" 2>/dev/null; then
        printf '%s\n' "$$" >"$LOCK_PID_FILE"
        return 0
    fi

    echo -e "${RED}Failed to acquire pre-commit lock at ${LOCK_DIR}.${NC}" >&2
    exit 1
}

trap 'cleanup_active_process; release_precommit_lock' EXIT INT TERM

acquire_precommit_lock

run_checked() {
    local output_file output rc
    local -a clean_env_cmd
    local git_env_var

    output_file="$(mktemp)"
    clean_env_cmd=(env)
    if command -v git >/dev/null 2>&1; then
        while IFS= read -r git_env_var; do
            [[ -n "$git_env_var" ]] || continue
            clean_env_cmd+=("-u" "$git_env_var")
        done < <(git rev-parse --local-env-vars 2>/dev/null || true)
    fi

    set +e
    "${clean_env_cmd[@]}" "$@" >"$output_file" 2>&1 &
    ACTIVE_PID=$!
    wait "$ACTIVE_PID"
    rc=$?
    ACTIVE_PID=""
    set -e

    if [[ $rc -eq 0 ]]; then
        rm -f "$output_file"
        echo -e "${GREEN}OK${NC}"
        return 0
    fi

    output="$(cat "$output_file")"
    rm -f "$output_file"
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

if [[ "$RUN_SYNTH" == "1" ]]; then
    echo -n "Synthesizing... "
    if [[ "$ENFORCE_SYNTH_BUDGET" == "0" ]]; then
        echo -e "${YELLOW}budget enforcement bypassed via ICEBOY_PRECOMMIT_ENFORCE_BUDGET=0${NC}"
        echo -n "  Synthesis report... "
        run_checked tools/verify_hw_build.sh --skip-build
    else
        run_checked tools/verify_hw_build.sh --skip-build --enforce-budget
    fi
else
    echo -e "Hardware synthesis: ${YELLOW}skipped in pre-commit (set ICEBOY_PRECOMMIT_INCLUDE_SYNTH=1 to enable)${NC}"
fi

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

        PRECOMMIT_SWIM_TESTS=("${PRECOMMIT_SWIM_TESTS_DEFAULT[@]}")
        if [[ "$RUN_EXTENDED" == "1" ]]; then
            PRECOMMIT_SWIM_TESTS+=("${PRECOMMIT_SWIM_TESTS_EXTENDED[@]}")
        else
            echo -e "Extended simulator suites: ${YELLOW}skipped in pre-commit (set ICEBOY_PRECOMMIT_EXTENDED=1 to enable)${NC}"
        fi

        echo "Running curated simulator suites..."
        for test_file in "${PRECOMMIT_SWIM_TESTS[@]}"; do
            printf '  %s... ' "$test_file"
            if [[ "$test_file" == *.sh ]]; then
                run_checked "$test_file" --skip-build
            else
                run_checked "$SWIM" test "$test_file"
            fi
        done
    else
        echo -e "Tests: ${YELLOW}skipped (no simulator: install icarus-verilog or verilator)${NC}"
    fi
else
    echo -e "Tests: ${YELLOW}skipped (no test files)${NC}"
fi

echo -e "${GREEN}All checks passed.${NC}"
