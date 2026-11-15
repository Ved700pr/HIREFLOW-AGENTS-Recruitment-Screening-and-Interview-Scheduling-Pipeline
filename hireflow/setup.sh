#!/usr/bin/env bash
# Create .venv and install requirements (Linux / macOS / Git Bash).
# Usage:  ./setup.sh          (core)      ./setup.sh dev   (core + tests + notebook)
set -e
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python
"$PY" -c 'import sys; assert (3,10)<=sys.version_info[:2]<=(3,13), f"Python {sys.version.split()[0]} unsupported: use 3.10-3.13"'
[ -d .venv ] || "$PY" -m venv .venv
# shellcheck disable=SC1091
if [ -f .venv/bin/activate ]; then . .venv/bin/activate; else . .venv/Scripts/activate; fi
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
[ "$1" = "dev" ] && python -m pip install -r requirements-dev.txt
[ -f .env ] || cp .env.example .env
echo
echo "Done. Activate with:  source .venv/bin/activate   (Git Bash: source .venv/Scripts/activate)"
echo "Then run:             streamlit run app.py"
