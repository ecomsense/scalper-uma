#!/bin/bash
# UMA Scalper setup - Debian bookworm and later
# App runs as a systemd USER unit: fastapi_app.service (see factory/fastapi_app.service)
set -e

# Resolve repo root from this script's own location (works wherever the repo is cloned)
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE="fastapi_app.service"

echo "=== UMA Scalper Setup ==="
echo "App dir: $APP_DIR"

echo "Updating apt..."
sudo apt update

echo "Installing deps (nginx, htpasswd, fuser, venv, git, curl)..."
sudo apt install -y nginx apache2-utils psmisc python3-venv git curl

echo "Installing uv (Python version/package manager used by deploy.sh)..."
if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | bash
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "uv already installed: $(uv --version)"
fi

HTPASSWD=/etc/nginx/uma-scalper.htpasswd
if sudo test -f "$HTPASSWD"; then
  echo "$HTPASSWD already exists, skipping."
else
  echo "Creating $HTPASSWD (nginx basic auth, root:www-data 640)..."
  sudo htpasswd -c "$HTPASSWD" trader
  sudo chown root:www-data "$HTPASSWD"
  sudo chmod 640 "$HTPASSWD"
fi

echo "Setting up nginx..."
sed "s|__APP_DIR__|$APP_DIR|g" "$APP_DIR/factory/nginx.conf" | sudo tee /etc/nginx/sites-available/uma-scalper >/dev/null
sudo ln -sf /etc/nginx/sites-available/uma-scalper /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

echo "Generating user systemd service..."
mkdir -p ~/.config/systemd/user
sed "s|__APP_DIR__|$APP_DIR|g" "$APP_DIR/factory/fastapi_app.service" > ~/.config/systemd/user/$SERVICE
systemctl --user daemon-reload

echo "Enabling linger (start at boot without login)..."
sudo loginctl enable-linger "$USER"

echo "Enabling and starting $SERVICE..."
systemctl --user enable $SERVICE
systemctl --user restart $SERVICE

echo "Status:"
systemctl --user status $SERVICE --no-pager -l || true

echo ""
echo "=== Setup Complete ==="
echo "App (direct): http://127.0.0.1:8000"
echo "App (nginx):  http://$(curl -s ifconfig.me)/"
echo ""
echo "Useful commands:"
echo "  systemctl --user restart $SERVICE  # Restart app"
echo "  systemctl --user status $SERVICE    # Check status"
echo "  journalctl --user -u $SERVICE -f    # View journal"
echo "  tail -50 $APP_DIR/data/log.txt      # View app log"
echo "  curl -s http://127.0.0.1:8000/api/schedule"
