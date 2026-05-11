#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/umikok7/Desktop/python/my-deer-flow"
VENV="$ROOT/artifacts/gpt-sovits-roxy/.venv"

if [ ! -x "$VENV/bin/python" ]; then
  echo "Missing virtualenv: $VENV"
  exit 1
fi

exec "$VENV/bin/python" "$ROOT/scripts/tts/roxy_gsv_service.py"
