#!/bin/bash
# Install the Debian packages this app/infra needs on a fresh server.
# Run once, with sudo:  sudo ./scripts/install-dev.sh
#
# Python deps are NOT handled here - scripts/deploy.sh (uv, from pyproject.toml) covers those.
set -e

echo "Installing Debian packages..."

apt-get update
apt-get install -y \
    nginx \
    apache2-utils \
    psmisc \
    git \
    curl \
    python3-venv \
    build-essential \
    pkg-config \
    libssl-dev

echo "Installing uv (Python version/package manager used by deploy.sh)..."
if ! command -v uv >/dev/null 2>&1; then
    # Install system-wide so it's on PATH for any user (not just root's home)
    curl -LsSf https://astral.sh/uv | UV_INSTALL_DIR=/usr/local/bin sh
else
    echo "uv already installed: $(uv --version)"
fi

echo "Done!"
