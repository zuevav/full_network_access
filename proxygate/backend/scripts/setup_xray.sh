#!/bin/bash
# XRay + VLESS + REALITY Setup Script
# Обход блокировок с маскировкой под обычный HTTPS трафик

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}  XRay + VLESS + REALITY Setup  ${NC}"
echo -e "${BLUE}================================${NC}"

# Проверка root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Запустите скрипт с правами root (sudo)${NC}"
    exit 1
fi

# Определение архитектуры
ARCH=$(uname -m)
case $ARCH in
    x86_64) XRAY_ARCH="64" ;;
    aarch64) XRAY_ARCH="arm64-v8a" ;;
    armv7l) XRAY_ARCH="arm32-v7a" ;;
    *) echo -e "${RED}Неподдерживаемая архитектура: $ARCH${NC}"; exit 1 ;;
esac

# Получение внешнего IP
SERVER_IP=$(curl -s4 ifconfig.me || curl -s4 icanhazip.com)
if [ -z "$SERVER_IP" ]; then
    echo -e "${RED}Не удалось определить внешний IP${NC}"
    exit 1
fi
echo -e "${GREEN}Внешний IP: $SERVER_IP${NC}"

# Установка XRay
echo -e "${YELLOW}Установка XRay...${NC}"
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# Генерация ключей для REALITY
echo -e "${YELLOW}Генерация ключей REALITY...${NC}"
KEYS=$(/usr/local/bin/xray x25519)
PRIVATE_KEY=$(echo "$KEYS" | grep "Private key:" | cut -d' ' -f3)
PUBLIC_KEY=$(echo "$KEYS" | grep "Public key:" | cut -d' ' -f3)

# Генерация UUID
UUID=$(/usr/local/bin/xray uuid)

# Генерация Short ID (16 hex символов)
SHORT_ID=$(openssl rand -hex 8)

# Сайт для маскировки (должен поддерживать TLS 1.3 и HTTP/2)
DEST_SERVER="www.microsoft.com"
DEST_PORT="443"
SERVER_NAME="www.microsoft.com"

# Порт для XRay
XRAY_PORT="443"

# Проверка занятости порта 443
if ss -tlnp | grep -q ":443 "; then
    echo -e "${YELLOW}Порт 443 занят, используем 8443${NC}"
    XRAY_PORT="8443"
fi

# Создание конфигурации сервера
echo -e "${YELLOW}Создание конфигурации...${NC}"
mkdir -p /usr/local/etc/xray

cat > /usr/local/etc/xray/config.json << EOF
{
    "log": {
        "loglevel": "warning"
    },
    "inbounds": [
        {
            "listen": "0.0.0.0",
            "port": ${XRAY_PORT},
            "protocol": "vless",
            "settings": {
                "clients": [
                    {
                        "id": "${UUID}",
                        "flow": "xtls-rprx-vision"
                    }
                ],
                "decryption": "none"
            },
            "streamSettings": {
                "network": "tcp",
                "security": "reality",
                "realitySettings": {
                    "show": false,
                    "dest": "${DEST_SERVER}:${DEST_PORT}",
                    "xver": 0,
                    "serverNames": [
                        "${SERVER_NAME}",
                        "www.microsoft.com",
                        "microsoft.com"
                    ],
                    "privateKey": "${PRIVATE_KEY}",
                    "shortIds": [
                        "${SHORT_ID}",
                        ""
                    ]
                }
            },
            "sniffing": {
                "enabled": true,
                "destOverride": [
                    "http",
                    "tls",
                    "quic"
                ]
            }
        }
    ],
    "outbounds": [
        {
            "protocol": "freedom",
            "tag": "direct"
        },
        {
            "protocol": "blackhole",
            "tag": "block"
        }
    ],
    "routing": {
        "domainStrategy": "IPIfNonMatch",
        "rules": [
            {
                "type": "field",
                "ip": [
                    "geoip:private"
                ],
                "outboundTag": "block"
            }
        ]
    }
}
EOF

# Открытие порта в firewall
echo -e "${YELLOW}Настройка firewall...${NC}"
if command -v ufw &> /dev/null; then
    ufw allow ${XRAY_PORT}/tcp
fi
iptables -I INPUT -p tcp --dport ${XRAY_PORT} -j ACCEPT 2>/dev/null || true

# Запуск XRay
echo -e "${YELLOW}Запуск XRay...${NC}"
systemctl enable xray
systemctl restart xray

# Проверка статуса
sleep 2
if systemctl is-active --quiet xray; then
    echo -e "${GREEN}XRay успешно запущен!${NC}"
else
    echo -e "${RED}Ошибка запуска XRay${NC}"
    journalctl -u xray -n 20 --no-pager
    exit 1
fi

# Сохранение конфигурации клиента
CLIENT_CONFIG_DIR="/root/xray-client"
mkdir -p "$CLIENT_CONFIG_DIR"

# Конфигурация для v2rayN/v2rayNG (Windows/Android)
cat > "$CLIENT_CONFIG_DIR/config.json" << EOF
{
    "log": {
        "loglevel": "warning"
    },
    "inbounds": [
        {
            "listen": "127.0.0.1",
            "port": 10808,
            "protocol": "socks",
            "settings": {
                "udp": true
            }
        },
        {
            "listen": "127.0.0.1",
            "port": 10809,
            "protocol": "http"
        }
    ],
    "outbounds": [
        {
            "protocol": "vless",
            "settings": {
                "vnext": [
                    {
                        "address": "${SERVER_IP}",
                        "port": ${XRAY_PORT},
                        "users": [
                            {
                                "id": "${UUID}",
                                "encryption": "none",
                                "flow": "xtls-rprx-vision"
                            }
                        ]
                    }
                ]
            },
            "streamSettings": {
                "network": "tcp",
                "security": "reality",
                "realitySettings": {
                    "fingerprint": "chrome",
                    "serverName": "${SERVER_NAME}",
                    "publicKey": "${PUBLIC_KEY}",
                    "shortId": "${SHORT_ID}"
                }
            },
            "tag": "proxy"
        },
        {
            "protocol": "freedom",
            "tag": "direct"
        }
    ],
    "routing": {
        "domainStrategy": "IPIfNonMatch",
        "rules": [
            {
                "type": "field",
                "domain": [
                    "geosite:private"
                ],
                "outboundTag": "direct"
            }
        ]
    }
}
EOF

# VLESS URL для импорта (Shadowrocket, v2rayN, v2rayNG)
VLESS_URL="vless://${UUID}@${SERVER_IP}:${XRAY_PORT}?encryption=none&flow=xtls-rprx-vision&security=reality&sni=${SERVER_NAME}&fp=chrome&pbk=${PUBLIC_KEY}&sid=${SHORT_ID}&type=tcp#ProxyGate-REALITY"

echo "$VLESS_URL" > "$CLIENT_CONFIG_DIR/vless-url.txt"

# Сохранение параметров
cat > "$CLIENT_CONFIG_DIR/connection-info.txt" << EOF
===========================================
    XRay VLESS + REALITY - Данные для подключения
===========================================

Сервер: ${SERVER_IP}
Порт: ${XRAY_PORT}
UUID: ${UUID}
Flow: xtls-rprx-vision
Security: reality
SNI: ${SERVER_NAME}
Fingerprint: chrome
Public Key: ${PUBLIC_KEY}
Short ID: ${SHORT_ID}

===========================================
    VLESS URL (для импорта в приложения)
===========================================

${VLESS_URL}

===========================================
    Приложения для подключения
===========================================

iOS:
  - Shadowrocket (рекомендуется) - App Store
  - Streisand
  - V2Box

Mac:
  - V2RayXS
  - V2BOX
  - Shadowrocket (Mac App Store)

Android:
  - v2rayNG (Google Play / GitHub)
  - Matsuri

Windows:
  - v2rayN (GitHub)
  - Nekoray

===========================================
    Инструкция для Shadowrocket (iOS)
===========================================

1. Откройте Shadowrocket
2. Нажмите + в правом верхнем углу
3. Выберите "Scan QR Code" или "Type"
4. Если Type - выберите VLESS и введите:
   - Address: ${SERVER_IP}
   - Port: ${XRAY_PORT}
   - UUID: ${UUID}
   - Flow: xtls-rprx-vision
   - TLS: reality
   - SNI: ${SERVER_NAME}
   - Public Key: ${PUBLIC_KEY}
   - Short ID: ${SHORT_ID}
5. Сохраните и подключайтесь!

Или просто скопируйте VLESS URL и вставьте в приложение.

EOF

# Генерация QR-кода если qrencode установлен
if command -v qrencode &> /dev/null; then
    qrencode -t UTF8 "$VLESS_URL" > "$CLIENT_CONFIG_DIR/qrcode.txt"
    echo -e "${GREEN}QR-код сохранён в $CLIENT_CONFIG_DIR/qrcode.txt${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  XRay VLESS + REALITY успешно установлен!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Сервер:${NC} ${SERVER_IP}"
echo -e "${BLUE}Порт:${NC} ${XRAY_PORT}"
echo -e "${BLUE}UUID:${NC} ${UUID}"
echo -e "${BLUE}Public Key:${NC} ${PUBLIC_KEY}"
echo -e "${BLUE}Short ID:${NC} ${SHORT_ID}"
echo ""
echo -e "${YELLOW}VLESS URL для импорта:${NC}"
echo -e "${GREEN}${VLESS_URL}${NC}"
echo ""
echo -e "${BLUE}Файлы конфигурации:${NC} ${CLIENT_CONFIG_DIR}/"
echo ""
echo -e "${YELLOW}Для подключения с iOS используйте Shadowrocket:${NC}"
echo -e "1. Скопируйте VLESS URL выше"
echo -e "2. В Shadowrocket нажмите + и вставьте URL"
echo ""
