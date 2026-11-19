#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VENV_PATH="$PROJECT_ROOT/.venv"

if [ ! -x "$VENV_PATH/bin/python" ]; then
  python3 -m venv "$VENV_PATH"
fi

"$VENV_PATH/bin/python" -m pip install --disable-pip-version-check -r "$PROJECT_ROOT/requirements.txt"
cd "$PROJECT_ROOT"
exec "$VENV_PATH/bin/python" -m uvicorn backend.server:app --host 127.0.0.1 --port "${PORT:-4317}"
