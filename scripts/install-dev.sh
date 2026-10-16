#!/bin/bash
# Setup dev environment - run once
set -e

cd "$(dirname "$0")"

echo "Installing dev tools..."

# Install uv if not present
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv | sh
fi

# Install hooks
uv run pre-commit install

echo "Done!"