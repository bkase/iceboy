#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

SWIM="${HOME}/.cargo/bin/swim"
UV_BIN="$(command -v uv || true)"
export PATH="/opt/homebrew/bin:$PATH"

if [[ ! -x "$SWIM" ]]; then
    echo -e "${RED}Missing swim at ${SWIM}${NC}"
    exit 1
fi

if [[ -z "$UV_BIN" ]]; then
    echo -e "${RED}Missing uv in PATH${NC}"
    exit 1
fi

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
if manifest_output=$("$UV_BIN" run --with-requirements toolchain/python.lock python tools/validate_rom_manifests.py 2>&1); then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
    echo "$manifest_output"
    exit 1
fi

echo -n "Building ROM templates... "
if rom_build_output=$(bench/roms/build_roms.sh 2>&1); then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
    echo "$rom_build_output"
    exit 1
fi

if find tools/tests -type f -name 'test_*.py' -print -quit | grep -q .; then
    echo -n "Running Python spec tests... "
    if spec_output=$("$UV_BIN" run --with-requirements toolchain/python.lock python -m unittest discover -s tools/tests -p 'test_*.py' 2>&1); then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED}FAILED${NC}"
        echo "$spec_output"
        exit 1
    fi
fi

echo -n "Compiling... "
if build_output=$("$SWIM" build 2>&1); then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
    echo "$build_output"
    exit 1
fi

echo -n "Synthesizing... "
if synth_output=$("$SWIM" synth 2>&1); then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
    echo "$synth_output"
    exit 1
fi

patch_cocotb_config_wrapper

if find test -type f -name 'test_*.py' -print -quit | grep -q .; then
    if command -v iverilog >/dev/null 2>&1 || command -v verilator >/dev/null 2>&1 || [[ -x /opt/homebrew/bin/verilator ]]; then
        echo -n "Running tests... "
        if test_output=$("$SWIM" test test_ 2>&1); then
            echo -e "${GREEN}OK${NC}"
        else
            echo -e "${RED}FAILED${NC}"
            echo "$test_output"
            exit 1
        fi
    else
        echo -e "Tests: ${YELLOW}skipped (no simulator: install icarus-verilog or verilator)${NC}"
    fi
else
    echo -e "Tests: ${YELLOW}skipped (no test files)${NC}"
fi

echo -e "${GREEN}All checks passed.${NC}"
