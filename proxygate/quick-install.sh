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

cd full_network_access/proxygate

# Запуск основного установщика
chmod +x install.sh
./install.sh

# Очистка
rm -rf $TEMP_DIR

echo -e "${GREEN}Готово!${NC}"
