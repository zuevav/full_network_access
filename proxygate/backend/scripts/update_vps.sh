#!/bin/bash
# ProxyGate VPS Update Script
# Применяет исправления и обновления на уже установленных серверах
# Run: sudo bash update_vps.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== ProxyGate VPS Update ===${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Запустите от root (sudo)${NC}"
    exit 1
fi

# Get current version
CURRENT_VERSION="unknown"
if [ -f /opt/proxygate/VERSION ]; then
    CURRENT_VERSION=$(cat /opt/proxygate/VERSION)
fi
echo "Текущая версия: $CURRENT_VERSION"
echo ""

# 0. Sync files from git repository to working directory
echo "[0/12] Синхронизация файлов из git..."

# Check if git repo structure exists (proxygate/proxygate/backend)
if [ -d /opt/proxygate/proxygate/backend ]; then
    echo -e "${YELLOW}[SYNC]${NC} Обнаружена структура git репозитория"

    # Sync backend files
    rsync -a --delete \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude '.env' \
        --exclude 'alembic.ini' \
        /opt/proxygate/proxygate/backend/ /opt/proxygate/backend/

    # Sync frontend if exists
    if [ -d /opt/proxygate/proxygate/frontend/dist ]; then
        rsync -a --delete /opt/proxygate/proxygate/frontend/dist/ /opt/proxygate/frontend/dist/
    fi

    # Sync scripts
    if [ -d /opt/proxygate/proxygate/backend/scripts ]; then
        rsync -a /opt/proxygate/proxygate/backend/scripts/ /opt/proxygate/backend/scripts/
    fi

    echo -e "${GREEN}[OK]${NC} Файлы синхронизированы"
else
    echo -e "${GREEN}[OK]${NC} Стандартная структура, синхронизация не требуется"
fi

# 1. Fix IP forwarding
echo "[1/12] Исправление IP forwarding..."

CURRENT_IP_FWD=$(cat /proc/sys/net/ipv4/ip_forward)
if [ "$CURRENT_IP_FWD" = "1" ]; then
    echo -e "${GREEN}[OK]${NC} IP forwarding уже включен"
else
    echo -e "${YELLOW}[FIX]${NC} Включаем IP forwarding..."

    sed -i '/net.ipv4.ip_forward/d' /etc/sysctl.conf
    sed -i '/net.ipv6.conf.all.forwarding/d' /etc/sysctl.conf
    sed -i '/net.ipv4.conf.all.accept_redirects/d' /etc/sysctl.conf
    sed -i '/net.ipv4.conf.all.send_redirects/d' /etc/sysctl.conf

    cat >> /etc/sysctl.conf << 'EOF'

# ProxyGate VPN - IP Forwarding
net.ipv4.ip_forward=1
net.ipv6.conf.all.forwarding=1
net.ipv4.conf.all.accept_redirects=0
net.ipv4.conf.all.send_redirects=0
EOF

    sysctl -p >/dev/null 2>&1
    sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1

    if [ "$(cat /proc/sys/net/ipv4/ip_forward)" = "1" ]; then
        echo -e "${GREEN}[OK]${NC} IP forwarding включен"
    else
        echo -e "${RED}[FAIL]${NC} Не удалось включить IP forwarding!"
    fi
fi

# 2. Fix swanctl directories
echo "[2/12] Проверка директорий swanctl..."
mkdir -p /etc/swanctl/x509
mkdir -p /etc/swanctl/private
mkdir -p /etc/swanctl/x509ca
echo -e "${GREEN}[OK]${NC} Директории созданы"

# 3. Check and fix certificate symlinks
echo "[3/12] Проверка сертификатов..."

DOMAIN=""
if [ -f /etc/swanctl/conf.d/connections.conf ]; then
    DOMAIN=$(grep "id = " /etc/swanctl/conf.d/connections.conf | head -1 | sed 's/.*id = //' | tr -d ' ')
fi

if [ -n "$DOMAIN" ] && [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    # Сертификат - копируем вместо symlink для надёжности
    if [ -L /etc/swanctl/x509/fullchain.pem ] || [ ! -f /etc/swanctl/x509/fullchain.pem ]; then
        rm -f /etc/swanctl/x509/fullchain.pem 2>/dev/null || true
        cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" /etc/swanctl/x509/fullchain.pem
        chmod 644 /etc/swanctl/x509/fullchain.pem
        echo -e "${YELLOW}[FIX]${NC} Скопирован fullchain.pem"
    else
        echo -e "${GREEN}[OK]${NC} fullchain.pem существует"
    fi

    # Приватный ключ - всегда копируем
    if [ -L /etc/swanctl/private/privkey.pem ] || [ ! -f /etc/swanctl/private/privkey.pem ]; then
        rm -f /etc/swanctl/private/privkey.pem 2>/dev/null || true
        cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" /etc/swanctl/private/privkey.pem
        chmod 600 /etc/swanctl/private/privkey.pem
        echo -e "${YELLOW}[FIX]${NC} Скопирован privkey.pem"
    else
        echo -e "${GREEN}[OK]${NC} privkey.pem существует"
    fi

    # Chain для CA
    if [ ! -f /etc/swanctl/x509ca/chain.pem ]; then
        ln -sf "/etc/letsencrypt/live/$DOMAIN/chain.pem" /etc/swanctl/x509ca/chain.pem
        echo -e "${YELLOW}[FIX]${NC} Создан symlink для chain.pem"
    else
        echo -e "${GREEN}[OK]${NC} chain.pem существует"
    fi

    # Удаляем старые самоподписанные сертификаты если есть
    rm -f /etc/swanctl/x509/server-cert.pem 2>/dev/null || true
    rm -f /etc/swanctl/x509ca/ca-cert.pem 2>/dev/null || true
    rm -f /etc/swanctl/private/ca-key.pem 2>/dev/null || true
    rm -f /etc/swanctl/private/server-key.pem 2>/dev/null || true
else
    echo -e "${YELLOW}[SKIP]${NC} Домен не определён или сертификаты отсутствуют"
fi

# 4. Fix strongSwan proposals for Apple devices
echo "[4/12] Обновление конфигурации strongSwan..."

if [ -f /etc/swanctl/conf.d/connections.conf ]; then
    # Проверяем есть ли ecp256 в proposals
    if ! grep -q "ecp256" /etc/swanctl/conf.d/connections.conf; then
        echo -e "${YELLOW}[FIX]${NC} Добавляем поддержку ECP_256 для Apple устройств..."
        sed -i 's/proposals = aes256-sha256-modp2048,aes128-sha256-modp2048/proposals = aes256-sha256-ecp256,aes256-sha256-modp2048,aes128-sha256-ecp256,aes128-sha256-modp2048/g' /etc/swanctl/conf.d/connections.conf
        sed -i 's/esp_proposals = aes256-sha256,aes128-sha256/esp_proposals = aes256-sha256-ecp256,aes256-sha256-modp2048,aes128-sha256-ecp256,aes128-sha256-modp2048/g' /etc/swanctl/conf.d/connections.conf
        echo -e "${GREEN}[OK]${NC} ECP_256 добавлен"
    else
        echo -e "${GREEN}[OK]${NC} ECP_256 уже поддерживается"
    fi

    # Обновляем certs если старый формат
    if grep -q "certs = fullchain.pem" /etc/swanctl/conf.d/connections.conf; then
        # Проверяем что файл существует
        if [ -f /etc/swanctl/x509/server.pem ]; then
            sed -i 's/certs = fullchain.pem/certs = server.pem/g' /etc/swanctl/conf.d/connections.conf
            echo -e "${YELLOW}[FIX]${NC} Обновлён путь к сертификату"
        fi
    fi
fi

# 5. Fix NAT rules
echo "[5/12] Проверка NAT правил..."

NAT_EXISTS=$(iptables -t nat -L POSTROUTING -n 2>/dev/null | grep -c "10.0.0.0/24" || echo "0")
if [ "$NAT_EXISTS" -gt 0 ]; then
    echo -e "${GREEN}[OK]${NC} NAT правила существуют"
else
    echo -e "${YELLOW}[FIX]${NC} Добавляем NAT правила..."
    IFACE=$(ip route | grep default | awk '{print $5}' | head -1)
    iptables -t nat -A POSTROUTING -s 10.0.0.0/24 -o $IFACE -j MASQUERADE
    iptables -A FORWARD -s 10.0.0.0/24 -j ACCEPT
    iptables -A FORWARD -d 10.0.0.0/24 -j ACCEPT

    if command -v netfilter-persistent &> /dev/null; then
        netfilter-persistent save >/dev/null 2>&1
    fi
    echo -e "${GREEN}[OK]${NC} NAT правила добавлены"
fi

# 6. Fix certbot renewal hook
echo "[6/12] Обновление certbot hook..."

mkdir -p /etc/letsencrypt/renewal-hooks/post
cat > /etc/letsencrypt/renewal-hooks/post/strongswan.sh << 'EOF'
#!/bin/bash
# Автоматическое обновление ключей strongSwan после обновления сертификата

DOMAIN=""
if [ -f /etc/swanctl/conf.d/connections.conf ]; then
    DOMAIN=$(grep "id = " /etc/swanctl/conf.d/connections.conf | head -1 | sed 's/.*id = //' | tr -d ' ')
fi

if [ -n "$DOMAIN" ] && [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" /etc/swanctl/private/privkey.pem
    chmod 600 /etc/swanctl/private/privkey.pem
    cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" /etc/swanctl/x509/fullchain.pem
    chmod 644 /etc/swanctl/x509/fullchain.pem
    ln -sf "/etc/letsencrypt/live/$DOMAIN/chain.pem" /etc/swanctl/x509ca/chain.pem
    echo "Updated strongSwan certificates for $DOMAIN"
fi

swanctl --load-creds 2>/dev/null || true
systemctl reload strongswan 2>/dev/null || true
EOF
chmod +x /etc/letsencrypt/renewal-hooks/post/strongswan.sh
echo -e "${GREEN}[OK]${NC} Certbot hook обновлён"

# 7. Install/Update XRay
echo "[7/12] Установка XRay (VLESS + REALITY)..."

if [ -f /usr/local/bin/xray ]; then
    echo -e "${GREEN}[OK]${NC} XRay уже установлен"
    # Update to latest version
    bash -c "$(curl -sL https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install >/dev/null 2>&1 || true
else
    echo -e "${YELLOW}[INSTALL]${NC} Устанавливаем XRay..."
    bash -c "$(curl -sL https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install >/dev/null 2>&1
    if [ -f /usr/local/bin/xray ]; then
        echo -e "${GREEN}[OK]${NC} XRay установлен"
        systemctl enable xray 2>/dev/null || true
    else
        echo -e "${RED}[FAIL]${NC} Не удалось установить XRay"
    fi
fi

# 8. Install/Update WireGuard
echo "[8/12] Установка WireGuard..."

if command -v wg &> /dev/null; then
    echo -e "${GREEN}[OK]${NC} WireGuard уже установлен"
else
    echo -e "${YELLOW}[INSTALL]${NC} Устанавливаем WireGuard..."
    apt-get update -qq
    apt-get install -y wireguard wireguard-tools >/dev/null 2>&1
    if command -v wg &> /dev/null; then
        echo -e "${GREEN}[OK]${NC} WireGuard установлен"
    else
        echo -e "${RED}[FAIL]${NC} Не удалось установить WireGuard"
    fi
fi

# Add NAT rules for WireGuard subnet if not exists
WG_NAT_EXISTS=$(iptables -t nat -L POSTROUTING -n 2>/dev/null | grep -c "10.10.0.0/24" || echo "0")
if [ "$WG_NAT_EXISTS" -eq 0 ]; then
    IFACE=$(ip route | grep default | awk '{print $5}' | head -1)
    iptables -t nat -A POSTROUTING -s 10.10.0.0/24 -o $IFACE -j MASQUERADE 2>/dev/null || true
    iptables -A FORWARD -s 10.10.0.0/24 -j ACCEPT 2>/dev/null || true
    iptables -A FORWARD -d 10.10.0.0/24 -j ACCEPT 2>/dev/null || true
fi

# 9. Install wstunnel for WireGuard obfuscation
echo "[9/12] Установка wstunnel..."

if [ -f /usr/local/bin/wstunnel ]; then
    echo -e "${GREEN}[OK]${NC} wstunnel уже установлен"
else
    echo -e "${YELLOW}[INSTALL]${NC} Устанавливаем wstunnel..."
    ARCH=$(uname -m)
    case $ARCH in
        x86_64) WSTUNNEL_ARCH="x86_64-unknown-linux-musl" ;;
        aarch64) WSTUNNEL_ARCH="aarch64-unknown-linux-musl" ;;
        *) WSTUNNEL_ARCH="" ;;
    esac

    if [ -n "$WSTUNNEL_ARCH" ]; then
        # Get latest version
        WSTUNNEL_VERSION=$(curl -sI https://github.com/erebe/wstunnel/releases/latest | grep -i location | sed 's/.*tag\/v//' | tr -d '\r\n')
        if [ -n "$WSTUNNEL_VERSION" ]; then
            curl -sL "https://github.com/erebe/wstunnel/releases/download/v${WSTUNNEL_VERSION}/wstunnel_${WSTUNNEL_VERSION}_linux_${ARCH}.tar.gz" -o /tmp/wstunnel.tar.gz
            tar -xzf /tmp/wstunnel.tar.gz -C /usr/local/bin/ wstunnel 2>/dev/null || true
            chmod +x /usr/local/bin/wstunnel 2>/dev/null || true
            rm -f /tmp/wstunnel.tar.gz
        fi
    fi

    if [ -f /usr/local/bin/wstunnel ]; then
        echo -e "${GREEN}[OK]${NC} wstunnel установлен"
    else
        echo -e "${YELLOW}[SKIP]${NC} wstunnel не установлен (опционально)"
    fi
fi

# 10. Install Python dependencies
echo "[10/12] Обновление Python зависимостей..."

# Install qrcode for QR code generation
pip3 install -q qrcode[pil] 2>/dev/null || pip3 install -q qrcode 2>/dev/null || true
echo -e "${GREEN}[OK]${NC} Python зависимости обновлены"

# 11. Run database migrations
echo "[11/12] Выполнение миграций базы данных..."

if [ -d /opt/proxygate/backend ]; then
    cd /opt/proxygate/backend
    if [ -f alembic.ini ]; then
        source /opt/proxygate/venv/bin/activate 2>/dev/null || true
        alembic upgrade head 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[OK]${NC} Миграции выполнены"
        else
            echo -e "${YELLOW}[SKIP]${NC} Миграции уже применены или ошибка"
        fi
        deactivate 2>/dev/null || true
    else
        echo -e "${YELLOW}[SKIP]${NC} alembic.ini не найден"
    fi
else
    echo -e "${YELLOW}[SKIP]${NC} /opt/proxygate/backend не найден"
fi

# 12. Restart backend service
echo "[12/12] Перезапуск backend сервиса..."

if systemctl list-units --type=service | grep -q "proxygate"; then
    systemctl restart proxygate 2>/dev/null || systemctl restart proxygate-backend 2>/dev/null || true
    if systemctl is-active --quiet proxygate 2>/dev/null || systemctl is-active --quiet proxygate-backend 2>/dev/null; then
        echo -e "${GREEN}[OK]${NC} Backend перезапущен"
    else
        echo -e "${RED}[FAIL]${NC} Backend не запустился!"
        echo "Проверьте логи: journalctl -u proxygate -n 50"
    fi
else
    echo -e "${YELLOW}[SKIP]${NC} Сервис proxygate не найден"
fi

# Reload strongSwan
echo ""
echo "Перезагрузка strongSwan..."

if systemctl is-active --quiet strongswan-starter 2>/dev/null; then
    systemctl disable strongswan-starter 2>/dev/null || true
    systemctl stop strongswan-starter 2>/dev/null || true
fi

systemctl enable strongswan 2>/dev/null || true
swanctl --load-all 2>/dev/null || true
systemctl restart strongswan

if systemctl is-active --quiet strongswan; then
    echo -e "${GREEN}[OK]${NC} strongSwan работает"
else
    echo -e "${RED}[FAIL]${NC} strongSwan не запустился!"
fi

# Save iptables rules
if command -v netfilter-persistent &> /dev/null; then
    netfilter-persistent save >/dev/null 2>&1 || true
fi

echo ""
echo -e "${BLUE}=== Обновление завершено ===${NC}"
echo ""
echo "Установленные компоненты:"
echo "  - strongSwan (IKEv2/IPsec) ✓"
[ -f /usr/local/bin/xray ] && echo "  - XRay (VLESS + REALITY) ✓"
command -v wg &> /dev/null && echo "  - WireGuard ✓"
[ -f /usr/local/bin/wstunnel ] && echo "  - wstunnel (WebSocket туннель) ✓"
echo ""
echo "Проверьте статус:"
echo "  bash /opt/proxygate/backend/scripts/diagnose_vpn.sh"
echo ""
echo "Просмотр логов:"
echo "  journalctl -u strongswan -f  # IKEv2"
echo "  journalctl -u xray -f        # XRay"
echo ""
