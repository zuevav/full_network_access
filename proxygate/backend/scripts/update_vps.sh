#!/bin/bash
# ProxyGate VPS Update Script
# Применяет исправления на уже установленных серверах
# Run: sudo bash update_vps.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=== ProxyGate VPS Update ==="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Запустите от root (sudo)${NC}"
    exit 1
fi

# 1. Fix IP forwarding
echo "[1/5] Исправление IP forwarding..."

# Check current status
CURRENT_IP_FWD=$(cat /proc/sys/net/ipv4/ip_forward)
if [ "$CURRENT_IP_FWD" = "1" ]; then
    echo -e "${GREEN}[OK]${NC} IP forwarding уже включен"
else
    echo -e "${YELLOW}[FIX]${NC} Включаем IP forwarding..."

    # Remove old settings
    sed -i '/net.ipv4.ip_forward/d' /etc/sysctl.conf
    sed -i '/net.ipv6.conf.all.forwarding/d' /etc/sysctl.conf
    sed -i '/net.ipv4.conf.all.accept_redirects/d' /etc/sysctl.conf
    sed -i '/net.ipv4.conf.all.send_redirects/d' /etc/sysctl.conf

    # Add new settings
    cat >> /etc/sysctl.conf << 'EOF'

# ProxyGate VPN - IP Forwarding
net.ipv4.ip_forward=1
net.ipv6.conf.all.forwarding=1
net.ipv4.conf.all.accept_redirects=0
net.ipv4.conf.all.send_redirects=0
EOF

    # Apply
    sysctl -p >/dev/null 2>&1
    sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1

    # Verify
    if [ "$(cat /proc/sys/net/ipv4/ip_forward)" = "1" ]; then
        echo -e "${GREEN}[OK]${NC} IP forwarding включен"
    else
        echo -e "${RED}[FAIL]${NC} Не удалось включить IP forwarding!"
    fi
fi

# 2. Fix swanctl directories
echo "[2/5] Проверка директорий swanctl..."
mkdir -p /etc/swanctl/x509
mkdir -p /etc/swanctl/private
mkdir -p /etc/swanctl/x509ca
echo -e "${GREEN}[OK]${NC} Директории созданы"

# 3. Check and fix certificate symlinks
echo "[3/5] Проверка сертификатов..."

# Try to find the domain from existing config
DOMAIN=""
if [ -f /etc/swanctl/conf.d/connections.conf ]; then
    DOMAIN=$(grep "id = " /etc/swanctl/conf.d/connections.conf | head -1 | sed 's/.*id = //' | tr -d ' ')
fi

if [ -n "$DOMAIN" ] && [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    # Create symlinks if missing
    if [ ! -f /etc/swanctl/x509/fullchain.pem ]; then
        ln -sf "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" /etc/swanctl/x509/fullchain.pem
        echo -e "${YELLOW}[FIX]${NC} Создан symlink для fullchain.pem"
    else
        echo -e "${GREEN}[OK]${NC} fullchain.pem существует"
    fi

    if [ ! -f /etc/swanctl/private/privkey.pem ]; then
        ln -sf "/etc/letsencrypt/live/$DOMAIN/privkey.pem" /etc/swanctl/private/privkey.pem
        echo -e "${YELLOW}[FIX]${NC} Создан symlink для privkey.pem"
    else
        echo -e "${GREEN}[OK]${NC} privkey.pem существует"
    fi

    if [ ! -f /etc/swanctl/x509ca/chain.pem ]; then
        ln -sf "/etc/letsencrypt/live/$DOMAIN/chain.pem" /etc/swanctl/x509ca/chain.pem
        echo -e "${YELLOW}[FIX]${NC} Создан symlink для chain.pem"
    else
        echo -e "${GREEN}[OK]${NC} chain.pem существует"
    fi
else
    echo -e "${YELLOW}[SKIP]${NC} Домен не определён или сертификаты отсутствуют"
    echo "       Создайте symlinks вручную:"
    echo "       ln -sf /etc/letsencrypt/live/YOUR_DOMAIN/fullchain.pem /etc/swanctl/x509/fullchain.pem"
    echo "       ln -sf /etc/letsencrypt/live/YOUR_DOMAIN/privkey.pem /etc/swanctl/private/privkey.pem"
    echo "       ln -sf /etc/letsencrypt/live/YOUR_DOMAIN/chain.pem /etc/swanctl/x509ca/chain.pem"
fi

# 4. Fix NAT rules
echo "[4/5] Проверка NAT правил..."

NAT_EXISTS=$(iptables -t nat -L POSTROUTING -n 2>/dev/null | grep -c "10.0.0.0/24" || echo "0")
if [ "$NAT_EXISTS" -gt 0 ]; then
    echo -e "${GREEN}[OK]${NC} NAT правила существуют"
else
    echo -e "${YELLOW}[FIX]${NC} Добавляем NAT правила..."
    IFACE=$(ip route | grep default | awk '{print $5}' | head -1)
    iptables -t nat -A POSTROUTING -s 10.0.0.0/24 -o $IFACE -j MASQUERADE
    iptables -A FORWARD -s 10.0.0.0/24 -j ACCEPT
    iptables -A FORWARD -d 10.0.0.0/24 -j ACCEPT

    # Save rules
    if command -v netfilter-persistent &> /dev/null; then
        netfilter-persistent save >/dev/null 2>&1
    fi
    echo -e "${GREEN}[OK]${NC} NAT правила добавлены"
fi

# 5. Fix strongSwan service
echo "[5/5] Проверка strongSwan..."

# Make sure we're using charon-systemd, not strongswan-starter
if systemctl is-active --quiet strongswan-starter 2>/dev/null; then
    echo -e "${YELLOW}[FIX]${NC} Отключаем strongswan-starter..."
    systemctl disable strongswan-starter 2>/dev/null || true
    systemctl stop strongswan-starter 2>/dev/null || true
fi

# Enable and reload strongswan
systemctl enable strongswan 2>/dev/null || true
swanctl --load-all 2>/dev/null || true
systemctl restart strongswan

if systemctl is-active --quiet strongswan; then
    echo -e "${GREEN}[OK]${NC} strongSwan работает"
else
    echo -e "${RED}[FAIL]${NC} strongSwan не запустился!"
fi

echo ""
echo "=== Обновление завершено ==="
echo ""
echo "Проверьте статус:"
echo "  bash /opt/proxygate/backend/scripts/diagnose_vpn.sh"
echo ""
echo "Просмотр логов при подключении:"
echo "  journalctl -u strongswan -f"
echo ""
