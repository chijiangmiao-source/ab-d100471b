#!/bin/sh
# One-shot verification entrypoint.  Exits non-zero on the first failing stage
# so Compose reports the result via the container's exit code.
set -e

echo "=== [1/3] backend unit + API tests (pytest) ==="
cd /workspace/backend
python -m pytest -q

echo "=== [2/3] frontend build check (vite) ==="
cd /workspace/frontend
npm run build
test -f dist/index.html

echo "=== [3/3] live API smoke (real HTTP) ==="
cd /workspace
python verify/smoke_api.py

echo "=== VERIFY OK ==="
