#!/bin/bash
# UMA Scalper setup - Debian bookworm and later
# App runs as a systemd USER unit: fastapi_app.service (see factory/fastapi_app.service)
set -e

APP_DIR="/home/uma/no_env/uma_scalper"
SERVICE="fastapi_app.service"

echo "=== UMA Scalper Setup ==="

echo "Updating apt..."
sudo apt update

echo "Installing deps (nginx, htpasswd, fuser, venv)..."
sudo apt install -y nginx apache2-utils psmisc python3-venv

echo "Setting up nginx..."
sudo cp "$APP_DIR/factory/nginx.conf" /etc/nginx/sites-available/uma-scalper
sudo ln -sf /etc/nginx/sites-available/uma-scalper /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

if [ ! -f "$APP_DIR/data/.htpasswd" ]; then
  echo "Creating $APP_DIR/data/.htpasswd (nginx basic auth)..."
  htpasswd -c "$APP_DIR/data/.htpasswd" trader
else
  echo ".htpasswd already exists, skipping."
fi

echo "Linking user systemd service..."
mkdir -p ~/.config/systemd/user
ln -sf "$APP_DIR/factory/fastapi_app.service" ~/.config/systemd/user/$SERVICE
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
