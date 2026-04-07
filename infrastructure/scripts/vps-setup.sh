#!/usr/bin/env bash
set -euo pipefail

# Propyte — First-time VPS setup
# Run ON the VPS as root
# Usage: curl -sSL <url> | bash
# Or: ssh root@vps < vps-setup.sh

echo "=== Propyte VPS Setup ==="

# 1. System updates
echo "[setup] Updating system..."
apt-get update && apt-get upgrade -y

# 2. Install Docker
echo "[setup] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# 3. Install Docker Compose plugin
echo "[setup] Installing Docker Compose..."
apt-get install -y docker-compose-plugin

# 4. Install SOPS
echo "[setup] Installing SOPS..."
if ! command -v sops &> /dev/null; then
    SOPS_VERSION="3.9.4"
    curl -Lo /usr/local/bin/sops "https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.linux.amd64"
    chmod +x /usr/local/bin/sops
fi

# 5. Install age
echo "[setup] Installing age..."
if ! command -v age &> /dev/null; then
    apt-get install -y age
fi

# 6. Install yq (YAML parser for deploy script)
echo "[setup] Installing yq..."
if ! command -v yq &> /dev/null; then
    YQ_VERSION="v4.44.1"
    curl -Lo /usr/local/bin/yq "https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_amd64"
    chmod +x /usr/local/bin/yq
fi

# 7. Generate age key (if not exists)
AGE_KEY_DIR="/root/.config/sops/age"
if [ ! -f "${AGE_KEY_DIR}/keys.txt" ]; then
    echo "[setup] Generating age encryption key..."
    mkdir -p "${AGE_KEY_DIR}"
    age-keygen -o "${AGE_KEY_DIR}/keys.txt" 2>&1
    chmod 600 "${AGE_KEY_DIR}/keys.txt"
    echo ""
    echo "=== IMPORTANT: Save the PUBLIC KEY below ==="
    echo "Put it in secrets/.sops.yaml on your local machine"
    grep "public key" "${AGE_KEY_DIR}/keys.txt"
    echo "============================================="
else
    echo "[setup] Age key already exists"
fi

# 8. Create project directory
mkdir -p /opt/datamktmx
chmod 755 /opt/datamktmx

# 9. Create log directory for scraper cron output
mkdir -p /var/log/datamktmx
chmod 755 /var/log/datamktmx

# 10. Firewall — only allow SSH, HTTP, HTTPS
echo "[setup] Configuring firewall..."
if command -v ufw &> /dev/null; then
    ufw allow ssh
    ufw allow http
    ufw allow https
    ufw --force enable
fi

# 11. Disable password auth (SSH keys only)
echo "[setup] Hardening SSH..."
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl reload sshd

echo ""
echo "=== VPS Setup Complete ==="
echo "Next steps:"
echo "  1. Copy the age public key to secrets/.sops.yaml"
echo "  2. Create and encrypt secrets/production.yaml"
echo "  3. Run: ./infrastructure/scripts/deploy.sh root@<vps-ip>"
