#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SWIM_PYTHON="${ROOT}/build/oss-cad-suite/py3bin/python3.11"
UV_BIN="$(command -v uv || true)"

if [[ ! -x "${SWIM_PYTHON}" ]]; then
    echo "swim python not present yet at ${SWIM_PYTHON}" >&2
    exit 1
fi

if [[ -z "${UV_BIN}" ]]; then
    echo "uv is required to provision swim python dependencies" >&2
    exit 1
fi

if "${SWIM_PYTHON}" - <<'PY' >/dev/null 2>&1
import pyboy
import yaml
PY
then
    exit 0
fi

"${UV_BIN}" pip install --python "${SWIM_PYTHON}" pyboy==2.7.0 pyyaml==6.0.3
