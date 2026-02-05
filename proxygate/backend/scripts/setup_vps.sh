#!/bin/bash
# ProxyGate VPS Setup Script
# Ubuntu 24.04 LTS
# Run: sudo bash setup_vps.sh

set -e

echo "=== ProxyGate VPS Setup ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo)"
    exit 1
fi

# 1. System update
echo "[1/10] Updating system..."
apt update && apt upgrade -y

# 2. Install packages
echo "[2/10] Installing packages..."
apt install -y \
    strongswan strongswan-pki libcharon-extra-plugins libstrongswan-extra-plugins \
    charon-systemd \
    nginx certbot python3-certbot-nginx \
    python3-pip python3-venv \
    git curl ufw fail2ban \
    build-essential

# Disable old strongswan-starter, enable charon-systemd (swanctl)
systemctl disable strongswan-starter 2>/dev/null || true
systemctl stop strongswan-starter 2>/dev/null || true
systemctl enable strongswan
systemctl start strongswan

# 3. Configure firewall
echo "[3/10] Configuring firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 443/tcp         # HTTPS
ufw allow 80/tcp          # HTTP (certbot)
ufw allow 500/udp         # IKEv2 (IKE)
ufw allow 4500/udp        # IKEv2 (NAT-T)
ufw allow 3128/tcp        # HTTP Proxy
ufw allow 1080/tcp        # SOCKS5
ufw --force enable

# 4. Enable IP forwarding (CRITICAL for VPN!)
echo "[4/10] Enabling IP forwarding..."

# Remove any existing settings to avoid duplicates/conflicts
sed -i '/net.ipv4.ip_forward/d' /etc/sysctl.conf
sed -i '/net.ipv6.conf.all.forwarding/d' /etc/sysctl.conf
sed -i '/net.ipv4.conf.all.accept_redirects/d' /etc/sysctl.conf
sed -i '/net.ipv4.conf.all.send_redirects/d' /etc/sysctl.conf

# Add IP forwarding settings
cat >> /etc/sysctl.conf << 'EOF'

# ProxyGate VPN - IP Forwarding (required for VPN to work!)
net.ipv4.ip_forward=1
net.ipv6.conf.all.forwarding=1
net.ipv4.conf.all.accept_redirects=0
net.ipv4.conf.all.send_redirects=0
EOF

# Apply settings
sysctl -p

# Verify IP forwarding is enabled
if [ "$(cat /proc/sys/net/ipv4/ip_forward)" != "1" ]; then
    echo "WARNING: IP forwarding failed to enable! Trying direct method..."
    sysctl -w net.ipv4.ip_forward=1
fi
echo "IP forwarding status: $(cat /proc/sys/net/ipv4/ip_forward) (should be 1)"

# 5. Configure iptables for NAT
echo "[5/10] Configuring NAT..."
IFACE=$(ip route | grep default | awk '{print $5}' | head -1)
iptables -t nat -A POSTROUTING -s 10.0.0.0/24 -o $IFACE -j MASQUERADE
iptables -A FORWARD -s 10.0.0.0/24 -j ACCEPT
iptables -A FORWARD -d 10.0.0.0/24 -j ACCEPT

# Save iptables rules
apt install -y iptables-persistent
netfilter-persistent save

# 6. Setup strongSwan directories
echo "[6/10] Setting up strongSwan..."
mkdir -p /etc/swanctl/conf.d
mkdir -p /etc/swanctl/x509      # Server certificate
mkdir -p /etc/swanctl/private   # Private key
mkdir -p /etc/swanctl/x509ca    # CA chain

# Initial connections config
cat > /etc/swanctl/conf.d/connections.conf << 'EOF'
connections {
    proxygate {
        version = 2
        proposals = aes256-sha256-ecp256,aes256-sha256-modp2048,aes128-sha256-ecp256,aes128-sha256-modp2048
        rekey_time = 0s
        unique = replace
        pools = client_pool
        fragmentation = yes
        dpd_delay = 30s
        send_certreq = no

        local {
            auth = pubkey
            certs = fullchain.pem
            id = vpn.yourdomain.com
        }

        remote {
            auth = eap-mschapv2
            eap_id = %any
        }

        children {
            proxygate-net {
                local_ts = 0.0.0.0/0
                esp_proposals = aes256-sha256,aes128-sha256
                dpd_action = clear
                rekey_time = 0s
            }
        }
    }
}

pools {
    client_pool {
        addrs = 10.0.0.0/24
        dns = 1.1.1.1, 8.8.8.8
    }
}
EOF

# Initial secrets config
cat > /etc/swanctl/conf.d/secrets.conf << 'EOF'
secrets {
    private-server {
        file = privkey.pem
    }
}
EOF

# 7. Install 3proxy
echo "[7/10] Installing 3proxy..."
cd /tmp
git clone https://github.com/3proxy/3proxy.git
cd 3proxy
ln -s Makefile.Linux Makefile
make -f Makefile.Linux
make -f Makefile.Linux install
mkdir -p /etc/3proxy /var/log/3proxy

# Initial 3proxy config
cat > /etc/3proxy/3proxy.cfg << 'EOF'
nserver 1.1.1.1
nserver 8.8.8.8
nscache 65536
timeouts 1 5 30 60 180 1800 15 60
log /var/log/3proxy/3proxy.log D
logformat "L%d-%m-%Y %H:%M:%S %U %C:%c %R:%r %O %I %T"
rotate 30
auth strong
users $/etc/3proxy/passwd
deny *
proxy -p3128 -a
socks -p1080 -a
EOF
touch /etc/3proxy/passwd

# 3proxy systemd service
cat > /etc/systemd/system/3proxy.service << 'EOF'
[Unit]
Description=3proxy Proxy Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/3proxy /etc/3proxy/3proxy.cfg
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable 3proxy
systemctl start 3proxy

# 8. Setup Python backend
echo "[8/10] Setting up Python backend..."
mkdir -p /opt/proxygate
cd /opt/proxygate
python3 -m venv venv

# 9. Setup certbot renewal hook (автоматическое обновление ключей для strongSwan)
echo "[9/10] Configuring certbot hooks..."
mkdir -p /etc/letsencrypt/renewal-hooks/post
cat > /etc/letsencrypt/renewal-hooks/post/strongswan.sh << 'EOF'
#!/bin/bash
# Автоматическое обновление ключей strongSwan после обновления сертификата

# Определяем домен из конфига strongSwan
DOMAIN=""
if [ -f /etc/swanctl/conf.d/connections.conf ]; then
    DOMAIN=$(grep "id = " /etc/swanctl/conf.d/connections.conf | head -1 | sed 's/.*id = //' | tr -d ' ')
fi

if [ -n "$DOMAIN" ] && [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    # Копируем приватный ключ (symlink не работает из-за прав)
    cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" /etc/swanctl/private/privkey.pem
    chmod 600 /etc/swanctl/private/privkey.pem

    # Обновляем symlinks для сертификатов (они работают)
    ln -sf "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" /etc/swanctl/x509/fullchain.pem
    ln -sf "/etc/letsencrypt/live/$DOMAIN/chain.pem" /etc/swanctl/x509ca/chain.pem

    echo "Updated strongSwan certificates for $DOMAIN"
fi

# Перезагружаем конфиг strongSwan
swanctl --load-creds
systemctl reload strongswan
EOF
chmod +x /etc/letsencrypt/renewal-hooks/post/strongswan.sh

# 10. Create backend systemd service
echo "[10/10] Creating backend service..."
cat > /etc/systemd/system/proxygate.service << 'EOF'
[Unit]
Description=ProxyGate Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/proxygate/backend
Environment="PATH=/opt/proxygate/venv/bin"
ExecStart=/opt/proxygate/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Server IP: $(curl -s ifconfig.me)"
echo ""
echo "=== NEXT STEPS ==="
echo ""
echo "1. Configure DNS (replace YOUR_DOMAIN with actual domain):"
echo "   Point YOUR_DOMAIN -> $(curl -s ifconfig.me)"
echo ""
echo "2. Get SSL certificate:"
echo "   certbot --nginx -d YOUR_DOMAIN"
echo ""
echo "3. Copy/link strongSwan certificates (CRITICAL!):"
echo "   # Сертификаты - symlink работает"
echo "   ln -sf /etc/letsencrypt/live/YOUR_DOMAIN/fullchain.pem /etc/swanctl/x509/fullchain.pem"
echo "   ln -sf /etc/letsencrypt/live/YOUR_DOMAIN/chain.pem /etc/swanctl/x509ca/chain.pem"
echo "   # Приватный ключ - КОПИРОВАТЬ (symlink не работает из-за прав)"
echo "   cp /etc/letsencrypt/live/YOUR_DOMAIN/privkey.pem /etc/swanctl/private/privkey.pem"
echo "   chmod 600 /etc/swanctl/private/privkey.pem"
echo ""
echo "4. Deploy application:"
echo "   cd /opt/proxygate"
echo "   git clone YOUR_REPO ."
echo "   source venv/bin/activate"
echo "   pip install -r requirements.txt"
echo ""
echo "5. Configure backend (create .env file):"
echo "   cat > /opt/proxygate/backend/.env << EOF"
echo "   VPN_DOMAIN=YOUR_DOMAIN"
echo "   EOF"
echo ""
echo "6. Initialize database:"
echo "   cd /opt/proxygate/backend"
echo "   python scripts/init_db.py"
echo ""
echo "7. Build frontend:"
echo "   cd /opt/proxygate/frontend"
echo "   npm install && npm run build"
echo ""
echo "8. Setup nginx:"
echo "   # Edit nginx config - replace vpn.yourdomain.com with YOUR_DOMAIN:"
echo "   sed -i 's/vpn.yourdomain.com/YOUR_DOMAIN/g' /opt/proxygate/nginx/proxygate.conf"
echo "   cp /opt/proxygate/nginx/proxygate.conf /etc/nginx/sites-available/"
echo "   ln -sf /etc/nginx/sites-available/proxygate.conf /etc/nginx/sites-enabled/"
echo "   nginx -t && systemctl restart nginx"
echo ""
echo "9. Start services:"
echo "   swanctl --load-all"
echo "   systemctl restart strongswan"
echo "   systemctl start proxygate"
echo ""
echo "10. Verify VPN is working:"
echo "    bash /opt/proxygate/backend/scripts/diagnose_vpn.sh"
echo ""
echo "=== TROUBLESHOOTING ==="
echo "- View strongSwan logs: journalctl -u strongswan -f"
echo "- Reload VPN config: swanctl --load-all"
echo "- Check open ports: ss -uln | grep -E '500|4500'"
echo ""
