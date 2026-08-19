#!/usr/bin/env bash
set -euo pipefail

# Root of the repository
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Running Python tests (pytest)..."
cd "$ROOT_DIR"

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
else
  echo "WARN: .venv not found. Make sure dependencies are installed globally or create a virtualenv."
fi

pytest -q

echo
echo "==> Running Manifest Registry tests (mocha)..."
cd "$ROOT_DIR/oracle/registry"

if [ ! -d "node_modules" ]; then
  echo "INFO: node_modules not found, running npm install..."
  npm install
fi

npm test

echo
echo "==> All tests passed."

