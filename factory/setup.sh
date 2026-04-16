#!/bin/bash

set -e

echo "=== UMA Scalper Setup ==="

# Update apt
echo "Updating apt..."
sudo apt update

# Install nginx, apache2-utils (for htpasswd)
echo "Installing nginx and apache2-utils..."
sudo apt install -y nginx apache2-utils

# Copy nginx config
echo "Setting up nginx..."
sudo cp /home/uma/no_env/uma_scalper/factory/nginx.conf /etc/nginx/sites-available/uma-scalper
sudo ln -sf /etc/nginx/sites-available/uma-scalper /etc/nginx/sites-enabled/
sudo nginx -t

# Remove default nginx site
sudo rm -f /etc/nginx/sites-enabled/default

# Reload nginx
sudo systemctl enable nginx
sudo systemctl restart nginx

# Copy systemd service
echo "Setting up systemd service..."
sudo cp /home/uma/no_env/uma_scalper/factory/uma-scalper.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start service
echo "Starting uma-scalper service..."
sudo systemctl enable uma-scalper
sudo systemctl start uma-scalper

# Check status
sudo systemctl status uma-scalper --no-pager

echo ""
echo "=== Setup Complete ==="
echo "Access the app at: http://$(curl -s ifconfig.me):8000"
echo ""
echo "Credentials:"
echo "  User: trader"
echo "  Pass: trader123"
echo ""
echo "JWT Token is saved in: /home/uma/no_env/uma_scalper/data/jwt_token.txt"
echo ""
echo "Useful commands:"
echo "  sudo systemctl restart uma-scalper  # Restart app"
echo "  sudo systemctl status uma-scalper   # Check status"
echo "  sudo journalctl -u uma-scalper -f    # View logs"
