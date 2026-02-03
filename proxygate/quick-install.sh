#!/bin/bash
#===============================================================================
# ProxyGate Quick Installer
# Запуск: curl -sSL https://raw.githubusercontent.com/.../quick-install.sh | sudo bash
#===============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          ProxyGate Quick Installer                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Проверка root
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}Запустите с sudo: sudo bash quick-install.sh${NC}"
    exit 1
fi

# Исправляем репозитории если нужно (для oracular и др.)
echo -e "${BLUE}[INFO]${NC} Проверка репозиториев..."
if grep -q "oracular" /etc/apt/sources.list 2>/dev/null; then
    echo -e "${BLUE}[INFO]${NC} Исправление репозиториев..."
    rm -f /etc/apt/sources.list.d/*.list 2>/dev/null || true
    rm -f /etc/apt/sources.list.d/*.sources 2>/dev/null || true
    cat > /etc/apt/sources.list << 'EOFSOURCES'
deb http://archive.ubuntu.com/ubuntu noble main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu noble-updates main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu noble-backports main restricted universe multiverse
deb http://security.ubuntu.com/ubuntu noble-security main restricted universe multiverse
EOFSOURCES
fi

# Установка git если нет
apt-get update -y
apt-get install -y git curl

# Клонирование
TEMP_DIR=$(mktemp -d)
cd $TEMP_DIR

echo -e "${BLUE}[INFO]${NC} Клонирование репозитория..."

# Попытка клонировать (публичный или с токеном)
if [[ -n "$GH_TOKEN" ]]; then
    git clone https://${GH_TOKEN}@github.com/zuevav/full_network_access.git
else
    git clone https://github.com/zuevav/full_network_access.git
fi

PROXYGATE_DIR="$TEMP_DIR/full_network_access/proxygate"
cd "$PROXYGATE_DIR"

echo -e "${BLUE}[INFO]${NC} Директория проекта: $PROXYGATE_DIR"

# Проверяем что файлы на месте
if [[ ! -d "backend" ]] || [[ ! -d "frontend" ]]; then
    echo -e "${RED}[ERROR]${NC} Файлы проекта не найдены!"
    ls -la
    exit 1
fi

# Запуск основного установщика
chmod +x install.sh
bash install.sh

# Очистка
cd /
rm -rf $TEMP_DIR

echo -e "${GREEN}Готово!${NC}"
