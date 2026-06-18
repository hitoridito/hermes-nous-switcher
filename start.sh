#!/usr/bin/env bash
# start.sh — launcher for nous_switcher.
#
# Reuses Hermes's own Python venv (where fastapi / uvicorn / ruamel.yaml
# are already installed) so we don't need a second venv. If you ever move
# this outside the Forge, run ``pip install fastapi uvicorn ruamel.yaml httpx``
# in your own venv and adjust PYTHON below.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PYTHON="$HERMES_HOME/hermes-agent/venv/bin/python3"

# Fallback: if hermes-agent venv isn't there, use system python3.
if [ ! -x "$PYTHON" ]; then
  PYTHON="$(command -v python3)"
  echo "  (using system python3 — install fastapi/uvicorn/ruamel.yaml if missing)"
fi

echo "nous_switcher → http://127.0.0.1:9120"
echo "  HERMES_HOME : $HERMES_HOME"
echo "  Python      : $PYTHON"
echo

cd "$HERE"
exec "$PYTHON" server.py
