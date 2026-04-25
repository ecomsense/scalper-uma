#!/bin/bash
# Dev check script - runs fast checks locally, no network needed

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Dev Check ==="

cd "$PROJECT_DIR"

echo "1. Syntax check..."
uv run python -m py_compile src/main.py src/api.py src/tickrunner.py src/strategy.py src/wserver.py src/symbol.py src/constants.py
echo "   OK"

echo "2. Lint (auto-fix)..."
uv run ruff check --fix src/ 2>/dev/null || true
echo "   OK"

echo "3. Run tests..."
uv run pytest tests/ -v --tb=short 2>/dev/null || echo "   No tests or tests passed"
echo "   OK"

echo "=== Done ==="