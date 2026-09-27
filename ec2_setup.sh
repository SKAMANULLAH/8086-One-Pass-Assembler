#!/usr/bin/env bash
# ==============================================================================
# ec2_setup.sh - Automated Deployment Script for AWS EC2 (Ubuntu 22.04 / 24.04)
# Configures Nginx reverse proxy (Port 80) + Gunicorn + Systemd Service
# ==============================================================================

set -e

# Ensure running with sudo / root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run this script with sudo:"
    echo "   sudo bash ec2_setup.sh"
    exit 1
fi

echo "===================================================================="
echo "🚀 Starting 8086 One-Pass Assembler Web UI Deployment on AWS EC2"
echo "===================================================================="

# Determine project directory
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_USER="${SUDO_USER:-ubuntu}"
echo "📁 Project Directory: ${APP_DIR}"
echo "👤 Service User: ${CURRENT_USER}"

# 1. Update OS packages and install dependencies
echo "📦 [1/6] Updating packages & installing Python3, Nginx, and Git..."
apt-get update -y
apt-get install -y python3 python3-pip python3-venv nginx curl git

# 2. Setup Python Virtual Environment
echo "🐍 [2/6] Setting up Python virtual environment..."
if [ ! -d "${APP_DIR}/venv" ]; then
    python3 -m venv "${APP_DIR}/venv"
fi

# Set proper ownership
chown -R "${CURRENT_USER}:${CURRENT_USER}" "${APP_DIR}"

# Install requirements as the service user
echo "📥 [3/6] Installing Python packages (Flask, Gunicorn)..."
sudo -u "${CURRENT_USER}" "${APP_DIR}/venv/bin/pip" install --upgrade pip
sudo -u "${CURRENT_USER}" "${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

# 3. Configure Systemd Service
echo "⚙️  [4/6] Configuring Systemd Background Service..."
cat <<EOF > /etc/systemd/system/friendly-hubble.service
[Unit]
Description=8086 One-Pass Assembler & CPU Simulator Web App
After=network.target

[Service]
User=${CURRENT_USER}
Group=www-data
WorkingDirectory=${APP_DIR}
Environment="PATH=${APP_DIR}/venv/bin"
ExecStart=${APP_DIR}/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:5000 --timeout 60 app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable friendly-hubble
systemctl restart friendly-hubble

# 4. Configure Nginx Reverse Proxy
echo "🌐 [5/6] Configuring Nginx on Port 80..."
cat <<EOF > /etc/nginx/sites-available/friendly-hubble
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name _;
    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /static/ {
        alias ${APP_DIR}/static/;
        expires 7d;
        add_header Cache-Control "public, no-transform";
    }
}
EOF

# Enable site and remove default site
ln -sf /etc/nginx/sites-available/friendly-hubble /etc/nginx/sites-enabled/friendly-hubble
rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
nginx -t
systemctl restart nginx

# 5. Firewall Check (UFW)
if ufw status | grep -q "Status: active"; then
    echo "🛡️  Allowing Nginx HTTP and OpenSSH through firewall..."
    ufw allow 'Nginx HTTP'
    ufw allow 'OpenSSH'
fi

# 6. Fetch Public IP
PUBLIC_IP=$(curl -s --max-time 3 http://checkip.amazonaws.com || curl -s --max-time 3 ifconfig.me || echo "<YOUR-EC2-PUBLIC-IP>")

echo ""
echo "===================================================================="
echo "🎉 DEPLOYMENT SUCCESSFUL!"
echo "===================================================================="
echo "Your 8086 Assembler & CPU Simulator is now live worldwide at:"
echo "👉 http://${PUBLIC_IP}"
echo ""
echo "Useful Service Commands:"
echo "  Check app status:   sudo systemctl status friendly-hubble"
echo "  View app logs:      sudo journalctl -u friendly-hubble -f"
echo "  Restart app:        sudo systemctl restart friendly-hubble"
echo "  Restart Nginx:      sudo systemctl restart nginx"
echo "===================================================================="
