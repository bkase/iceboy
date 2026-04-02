#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

SWIM="${HOME}/.cargo/bin/swim"
export PATH="/opt/homebrew/bin:$PATH"

if [[ ! -x "$SWIM" ]]; then
    echo -e "${RED}Missing swim at ${SWIM}${NC}"
    exit 1
fi

echo "=== Pre-commit checks ==="

echo -n "Compiling... "
if build_output=$("$SWIM" build 2>&1); then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
    echo "$build_output"
    exit 1
fi

if find test -type f -name 'test_*.py' -print -quit | grep -q .; then
    if command -v iverilog >/dev/null 2>&1 || command -v verilator >/dev/null 2>&1 || [[ -x /opt/homebrew/bin/verilator ]]; then
        echo -n "Running tests... "
        if test_output=$("$SWIM" test 2>&1); then
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
