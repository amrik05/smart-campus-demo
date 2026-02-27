#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip

# Install API + dashboard deps for local dev
pip install -r requirements-api.txt -r requirements-dashboard.txt

echo "Venv ready. Activate with: source .venv/bin/activate"
