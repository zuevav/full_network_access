#!/bin/bash
set -e

#===============================================================================
# ProxyGate Auto-Installer v2.0
# Полная автоматическая установка VPN/Proxy системы
# Поддержка: Ubuntu 22.04 LTS, 24.04 LTS
#
# Использование:
#   install.sh                           — чистая установка
#   install.sh --restore backup.tar.gz   — установка + восстановление из бэкапа
#===============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

INSTALL_DIR="/opt/proxygate"
DOMAIN=""
SERVER_IP=""
DB_PASSWORD=""
SECRET_KEY=""
ADMIN_PASSWORD=""
ADMIN_EMAIL=""
TELEGRAM_TOKEN=""
TELEGRAM_CHAT_ID=""
HTTP_PROXY_PORT="3128"
SOCKS_PROXY_PORT="1080"
INSTALL_SSL="n"
SYSTEM_PYTHON=""

# Restore mode vars
RESTORE_MODE=false
RESTORE_FILE=""
RESTORE_DIR=""
OLD_IP=""

#===============================================================================
# Парсинг аргументов
#===============================================================================
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --restore)
                RESTORE_MODE=true
                RESTORE_FILE="$2"
                if [[ -z "$RESTORE_FILE" ]] || [[ ! -f "$RESTORE_FILE" ]]; then
                    log_error "Файл бэкапа не найден: $RESTORE_FILE"
                    echo "Использование: install.sh --restore /path/to/backup.tar.gz"
                    exit 1
                fi
                shift 2
                ;;
            -h|--help)
                echo "ProxyGate Installer v2.0"
                echo ""
                echo "Использование:"
                echo "  install.sh                           — чистая установка"
                echo "  install.sh --restore backup.tar.gz   — установка из бэкапа"
                exit 0
                ;;
            *)
                log_error "Неизвестный аргумент: $1"
                exit 1
                ;;
        esac
    done
}

#===============================================================================
# Утилиты
#===============================================================================
read_input() {
    local prompt="$1"
    local default="$2"
    local result=""

    if [[ -n "$default" ]]; then
        echo -en "${YELLOW}${prompt} [${default}]:${NC} " > /dev/tty
    else
        echo -en "${YELLOW}${prompt}:${NC} " > /dev/tty
    fi

    read -r result < /dev/tty

    if [[ -z "$result" ]]; then
        echo "$default"
    else
        echo "$result"
    fi
}

read_confirm() {
    local prompt="$1"
    local result=""

    echo -en "${YELLOW}${prompt} (y/n):${NC} " > /dev/tty
    read -r result < /dev/tty

    [[ "$result" == "y" || "$result" == "Y" ]]
}

#===============================================================================
# Отключение интерактивных диалогов
#===============================================================================
disable_interactive() {
    export DEBIAN_FRONTEND=noninteractive
    export NEEDRESTART_MODE=a
    export NEEDRESTART_SUSPEND=1

    if [[ -f /etc/needrestart/needrestart.conf ]]; then
        sed -i "s/#\$nrconf{restart} = 'i';/\$nrconf{restart} = 'a';/" /etc/needrestart/needrestart.conf 2>/dev/null || true
    fi

    echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections 2>/dev/null || true
}

#===============================================================================
# Проверка root
#===============================================================================
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "Скрипт должен быть запущен от root (sudo)"
        exit 1
    fi
}

#===============================================================================
# Определение системного Python
#===============================================================================
detect_system_python() {
    if [[ -x /usr/bin/python3.11 ]]; then
        SYSTEM_PYTHON="/usr/bin/python3.11"
    elif [[ -x /usr/bin/python3.10 ]]; then
        SYSTEM_PYTHON="/usr/bin/python3.10"
    elif [[ -x /usr/bin/python3.12 ]] && dpkg -l | grep -q "^ii  python3.12 "; then
        SYSTEM_PYTHON="/usr/bin/python3.12"
    else
        SYSTEM_PYTHON=$(which python3 2>/dev/null || echo "/usr/bin/python3")
    fi
    log_info "Системный Python: $SYSTEM_PYTHON"
}

#===============================================================================
# Определение IP сервера
#===============================================================================
detect_server_ip() {
    SERVER_IP=$(curl -4 -s --connect-timeout 5 ifconfig.me 2>/dev/null || \
                curl -4 -s --connect-timeout 5 icanhazip.com 2>/dev/null || \
                curl -4 -s --connect-timeout 5 ipv4.icanhazip.com 2>/dev/null || \
                hostname -I | awk '{print $1}')
    log_info "Автоопределённый IP: $SERVER_IP"
}

#===============================================================================
# Генерация паролей
#===============================================================================
generate_secrets() {
    DB_PASSWORD=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
    SECRET_KEY=$(openssl rand -hex 32)
    ADMIN_PASSWORD=$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 12)
    log_success "Секреты сгенерированы"
}

#===============================================================================
# Распаковка бэкапа и чтение настроек
#===============================================================================
unpack_restore() {
    log_info "Распаковка бэкапа: $RESTORE_FILE"

    RESTORE_DIR="/tmp/proxygate-restore"
    rm -rf "$RESTORE_DIR"
    mkdir -p "$RESTORE_DIR"

    tar xzf "$RESTORE_FILE" -C "$RESTORE_DIR" --strip-components=1

    if [[ ! -f "$RESTORE_DIR/manifest.json" ]]; then
        log_error "manifest.json не найден в архиве! Неверный формат бэкапа."
        exit 1
    fi

    log_success "Бэкап распакован"

    # Читаем manifest
    OLD_IP=$(python3 -c "import json; print(json.load(open('$RESTORE_DIR/manifest.json'))['old_ip'])" 2>/dev/null || \
             grep -oP '"old_ip"\s*:\s*"\K[^"]+' "$RESTORE_DIR/manifest.json")
    DOMAIN=$(python3 -c "import json; print(json.load(open('$RESTORE_DIR/manifest.json'))['domain'])" 2>/dev/null || \
             grep -oP '"domain"\s*:\s*"\K[^"]+' "$RESTORE_DIR/manifest.json")
    local backup_version=$(python3 -c "import json; print(json.load(open('$RESTORE_DIR/manifest.json'))['version'])" 2>/dev/null || \
                          grep -oP '"version"\s*:\s*"\K[^"]+' "$RESTORE_DIR/manifest.json")

    detect_server_ip

    echo ""
    log_info "Manifest бэкапа:"
    echo -e "  Версия:    ${BLUE}$backup_version${NC}"
    echo -e "  Домен:     ${BLUE}$DOMAIN${NC}"
    echo -e "  Старый IP: ${BLUE}$OLD_IP${NC}"
    echo -e "  Новый IP:  ${BLUE}$SERVER_IP${NC}"
    echo ""

    # Читаем настройки из .env бэкапа
    if [[ -f "$RESTORE_DIR/env/.env" ]]; then
        DB_PASSWORD=$(grep -oP 'postgresql\+asyncpg://proxygate:\K[^@]+' "$RESTORE_DIR/env/.env" 2>/dev/null || true)
        SECRET_KEY=$(grep -oP 'SECRET_KEY=\K.*' "$RESTORE_DIR/env/.env" 2>/dev/null || true)
        ADMIN_EMAIL=$(grep -oP 'ADMIN_EMAIL=\K.*' "$RESTORE_DIR/env/.env" 2>/dev/null || true)
        ADMIN_PASSWORD=$(grep -oP 'ADMIN_PASSWORD=\K.*' "$RESTORE_DIR/env/.env" 2>/dev/null || true)
        TELEGRAM_TOKEN=$(grep -oP 'TELEGRAM_BOT_TOKEN=\K.*' "$RESTORE_DIR/env/.env" 2>/dev/null || true)
        TELEGRAM_CHAT_ID=$(grep -oP 'TELEGRAM_CHAT_ID=\K.*' "$RESTORE_DIR/env/.env" 2>/dev/null || true)
        HTTP_PROXY_PORT=$(grep -oP 'HTTP_PROXY_PORT=\K.*' "$RESTORE_DIR/env/.env" 2>/dev/null || echo "3128")
        SOCKS_PROXY_PORT=$(grep -oP 'SOCKS_PROXY_PORT=\K.*' "$RESTORE_DIR/env/.env" 2>/dev/null || echo "1080")
        log_success "Настройки прочитаны из .env бэкапа"
    fi

    # Генерируем новый пароль БД (восстановим dump в новую БД)
    DB_PASSWORD=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
}

#===============================================================================
# Замена OLD_IP → NEW_IP в файле
#===============================================================================
replace_ip_in_file() {
    local file="$1"
    if [[ -f "$file" ]] && [[ -n "$OLD_IP" ]] && [[ -n "$SERVER_IP" ]] && [[ "$OLD_IP" != "$SERVER_IP" ]]; then
        sed -i "s/${OLD_IP}/${SERVER_IP}/g" "$file" 2>/dev/null || true
    fi
}

#===============================================================================
# Интерактивная настройка (чистая установка)
#===============================================================================
interactive_setup() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          ProxyGate Installer v2.0                            ║${NC}"
    echo -e "${GREEN}║          VPN/Proxy Management System                         ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    detect_server_ip
    generate_secrets

    echo ""
    echo -e "${BLUE}=== Основные настройки ===${NC}"
    echo ""

    SERVER_IP=$(read_input "IP адрес сервера (IPv4)" "$SERVER_IP")

    echo ""
    local input_domain
    input_domain=$(read_input "Домен для VPN/панели (Enter = использовать IP)" "")
    if [[ -n "$input_domain" ]]; then
        DOMAIN="$input_domain"
    else
        DOMAIN="$SERVER_IP"
    fi

    echo ""
    local input_pass
    input_pass=$(read_input "Пароль администратора (Enter = автогенерация)" "$ADMIN_PASSWORD")
    ADMIN_PASSWORD="$input_pass"

    echo ""
    ADMIN_EMAIL=$(read_input "Email администратора" "admin@${DOMAIN}")

    echo ""
    echo -e "${BLUE}=== Telegram уведомления (опционально) ===${NC}"
    echo ""

    TELEGRAM_TOKEN=$(read_input "Telegram Bot Token (Enter = пропустить)" "")
    if [[ -n "$TELEGRAM_TOKEN" ]]; then
        echo ""
        TELEGRAM_CHAT_ID=$(read_input "Telegram Chat ID" "")
    fi

    echo ""
    echo -e "${BLUE}=== Дополнительные настройки ===${NC}"
    echo ""

    HTTP_PROXY_PORT=$(read_input "HTTP Proxy порт" "3128")
    echo ""
    SOCKS_PROXY_PORT=$(read_input "SOCKS5 Proxy порт" "1080")

    echo ""
    if read_confirm "Установить Let's Encrypt SSL?"; then
        INSTALL_SSL="y"
    else
        INSTALL_SSL="n"
    fi

    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}                    КОНФИГУРАЦИЯ                              ${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  ${BLUE}Server IP:${NC}        $SERVER_IP"
    echo -e "  ${BLUE}Домен:${NC}            $DOMAIN"
    echo -e "  ${BLUE}Admin email:${NC}      $ADMIN_EMAIL"
    echo -e "  ${BLUE}Admin пароль:${NC}     $ADMIN_PASSWORD"
    echo -e "  ${BLUE}HTTP Proxy:${NC}       $HTTP_PROXY_PORT"
    echo -e "  ${BLUE}SOCKS5 Proxy:${NC}     $SOCKS_PROXY_PORT"
    echo -e "  ${BLUE}Telegram:${NC}         $([ -n "$TELEGRAM_TOKEN" ] && echo "Да (Chat: $TELEGRAM_CHAT_ID)" || echo "Нет")"
    echo -e "  ${BLUE}Let's Encrypt:${NC}    $([ "$INSTALL_SSL" = "y" ] && echo "Да" || echo "Нет")"
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    if ! read_confirm "Всё верно? Начать установку?"; then
        log_warn "Установка отменена"
        exit 0
    fi
}

#===============================================================================
# Исправление репозиториев
#===============================================================================
fix_repositories() {
    log_info "Проверка репозиториев..."

    UBUNTU_CODENAME=$(lsb_release -cs 2>/dev/null || echo "unknown")
    log_info "Версия Ubuntu: $UBUNTU_CODENAME"

    if [[ "$UBUNTU_CODENAME" == "oracular" ]] || grep -q "oracular" /etc/apt/sources.list 2>/dev/null; then
        log_warn "Обнаружена проблемная версия Ubuntu. Переключаем на noble (24.04 LTS)..."

        rm -f /etc/apt/sources.list.d/*.list 2>/dev/null || true
        rm -f /etc/apt/sources.list.d/*.sources 2>/dev/null || true

        cat > /etc/apt/sources.list << 'EOFSOURCES'
deb http://archive.ubuntu.com/ubuntu noble main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu noble-updates main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu noble-backports main restricted universe multiverse
deb http://security.ubuntu.com/ubuntu noble-security main restricted universe multiverse
EOFSOURCES

        log_success "Репозитории исправлены на noble"
    fi
}

#===============================================================================
# Обновление системы
#===============================================================================
update_system() {
    log_info "Обновление системы..."

    disable_interactive
    fix_repositories

    apt-get update -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"
    apt-get upgrade -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"
    apt-get dist-upgrade -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"
    apt-get autoremove -y
    apt-get autoclean -y

    log_success "Система обновлена"
}

#===============================================================================
# Установка базовых пакетов
#===============================================================================
install_base_packages() {
    log_info "Установка базовых пакетов..."

    apt-get install -y \
        curl \
        wget \
        git \
        nano \
        vim \
        htop \
        ufw \
        fail2ban \
        software-properties-common \
        apt-transport-https \
        ca-certificates \
        gnupg \
        lsb-release \
        unzip \
        zip \
        build-essential \
        libssl-dev \
        libffi-dev \
        openssl \
        cron \
        iptables \
        jq

    log_success "Базовые пакеты установлены"
}

#===============================================================================
# Установка Python 3.12
#===============================================================================
install_python() {
    log_info "Установка Python 3.12..."

    detect_system_python

    apt-get install -y python3-apt 2>/dev/null || true

    add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
    apt-get update -y || true

    apt-get install -y python3.12 python3.12-venv python3.12-dev

    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12 || {
        apt-get install -y python3-pip
    }

    if [[ -n "$SYSTEM_PYTHON" ]] && [[ -x "$SYSTEM_PYTHON" ]]; then
        update-alternatives --install /usr/bin/python3 python3 "$SYSTEM_PYTHON" 2 2>/dev/null || true
    fi

    log_success "Python 3.12 установлен"
    python3.12 --version

    log_info "Проверка работы apt..."
    apt-get update -y > /dev/null 2>&1 || {
        log_warn "apt update выдал ошибку, пробуем исправить..."
        if [[ -x /usr/bin/python3.10 ]]; then
            update-alternatives --set python3 /usr/bin/python3.10 2>/dev/null || true
        elif [[ -x /usr/bin/python3.11 ]]; then
            update-alternatives --set python3 /usr/bin/python3.11 2>/dev/null || true
        fi
        apt-get update -y || true
    }
}

#===============================================================================
# Установка Go
#===============================================================================
install_go() {
    log_info "Установка Go..."

    local GO_VERSION="1.22.6"

    if command -v go &>/dev/null; then
        local current_go=$(go version 2>/dev/null | grep -oP 'go\K[0-9.]+')
        log_info "Go уже установлен: $current_go"
        return
    fi

    local ARCH=$(dpkg --print-architecture)
    local GO_ARCH="amd64"
    if [[ "$ARCH" == "arm64" ]] || [[ "$ARCH" == "aarch64" ]]; then
        GO_ARCH="arm64"
    fi

    cd /tmp
    wget -q "https://go.dev/dl/go${GO_VERSION}.linux-${GO_ARCH}.tar.gz" -O go.tar.gz
    rm -rf /usr/local/go
    tar -C /usr/local -xzf go.tar.gz
    rm go.tar.gz

    # Добавляем в PATH
    if ! grep -q '/usr/local/go/bin' /etc/profile.d/go.sh 2>/dev/null; then
        echo 'export PATH=$PATH:/usr/local/go/bin' > /etc/profile.d/go.sh
    fi
    export PATH=$PATH:/usr/local/go/bin

    log_success "Go ${GO_VERSION} установлен"
    go version
}

#===============================================================================
# Сборка Go бинарей
#===============================================================================
build_go_binaries() {
    log_info "Сборка Go бинарей..."

    export PATH=$PATH:/usr/local/go/bin

    # TLS Proxy
    if [[ -d "$INSTALL_DIR/backend/scripts/tls-proxy-go" ]]; then
        log_info "  Сборка proxygate-tls-proxy..."
        cd "$INSTALL_DIR/backend/scripts/tls-proxy-go"
        CGO_ENABLED=0 go build -ldflags="-s -w" -o /usr/local/bin/proxygate-tls-proxy .
        chmod +x /usr/local/bin/proxygate-tls-proxy
        log_success "  proxygate-tls-proxy собран"
    fi

    # ProxyGate Connect
    if [[ -d "$INSTALL_DIR/backend/scripts/proxygate-connect" ]]; then
        log_info "  Сборка proxygate-connect.exe (Windows)..."
        cd "$INSTALL_DIR/backend/scripts/proxygate-connect"
        GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -ldflags="-s -w" -o "$INSTALL_DIR/backend/static/proxygate-connect.exe" .
        log_success "  proxygate-connect.exe собран"
    fi

    cd "$INSTALL_DIR"
}

#===============================================================================
# Установка XRay
#===============================================================================
install_xray() {
    log_info "Установка XRay..."

    if command -v xray &>/dev/null || [[ -f /usr/local/bin/xray ]]; then
        log_info "XRay уже установлен"
        return
    fi

    bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

    mkdir -p /usr/local/etc/xray

    # Создаём systemd сервис если нет
    if [[ ! -f /etc/systemd/system/xray.service ]]; then
        cat > /etc/systemd/system/xray.service << 'EOF'
[Unit]
Description=Xray Service
Documentation=https://github.com/xtls
After=network.target nss-lookup.target

[Service]
Type=simple
ExecStart=/usr/local/bin/xray run -config /usr/local/etc/xray/config.json
Restart=on-failure
RestartPreventExitStatus=23
LimitNPROC=10000
LimitNOFILE=1000000

[Install]
WantedBy=multi-user.target
EOF
    fi

    systemctl daemon-reload
    systemctl enable xray

    log_success "XRay установлен"
}

#===============================================================================
# Установка PostgreSQL
#===============================================================================
install_postgresql() {
    log_info "Установка PostgreSQL..."

    apt-get install -y postgresql postgresql-contrib

    systemctl start postgresql
    systemctl enable postgresql

    # В режиме restore — создаём пользователя с новым паролем и восстанавливаем dump
    if [[ "$RESTORE_MODE" == true ]]; then
        sudo -u postgres psql -c "DROP DATABASE IF EXISTS proxygate;" 2>/dev/null || true
        sudo -u postgres psql -c "DROP USER IF EXISTS proxygate;" 2>/dev/null || true
        sudo -u postgres psql -c "CREATE USER proxygate WITH PASSWORD '$DB_PASSWORD';"
        sudo -u postgres psql -c "CREATE DATABASE proxygate OWNER proxygate;"
        sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE proxygate TO proxygate;"

        if [[ -f "$RESTORE_DIR/db.sql" ]]; then
            log_info "Восстановление БД из дампа..."
            sudo -u postgres psql proxygate < "$RESTORE_DIR/db.sql"
            log_success "БД восстановлена из дампа"
        fi
    else
        sudo -u postgres psql -c "DROP DATABASE IF EXISTS proxygate;"
        sudo -u postgres psql -c "DROP USER IF EXISTS proxygate;"
        sudo -u postgres psql -c "CREATE USER proxygate WITH PASSWORD '$DB_PASSWORD';"
        sudo -u postgres psql -c "CREATE DATABASE proxygate OWNER proxygate;"
        sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE proxygate TO proxygate;"
    fi

    log_success "PostgreSQL установлен и настроен"
}

#===============================================================================
# Установка Node.js 20
#===============================================================================
install_nodejs() {
    log_info "Установка Node.js 20..."

    apt-get remove -y nodejs npm 2>/dev/null || true
    rm -f /etc/apt/sources.list.d/nodesource*.list 2>/dev/null || true
    rm -f /etc/apt/keyrings/nodesource.gpg 2>/dev/null || true

    apt-get install -y ca-certificates curl gnupg

    mkdir -p /etc/apt/keyrings

    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg

    NODE_MAJOR=20
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list

    apt-get update -y
    apt-get install -y nodejs

    if ! command -v node &> /dev/null || ! command -v npm &> /dev/null; then
        log_error "Node.js не установился корректно. Пробуем альтернативный метод..."

        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        nvm install 20
        nvm use 20
        nvm alias default 20

        ln -sf "$NVM_DIR/versions/node/$(nvm current)/bin/node" /usr/local/bin/node
        ln -sf "$NVM_DIR/versions/node/$(nvm current)/bin/npm" /usr/local/bin/npm
        ln -sf "$NVM_DIR/versions/node/$(nvm current)/bin/npx" /usr/local/bin/npx
    fi

    log_success "Node.js установлен"
    node --version
    npm --version
}

#===============================================================================
# Установка Nginx
#===============================================================================
install_nginx() {
    log_info "Установка Nginx..."

    apt-get install -y nginx

    systemctl start nginx
    systemctl enable nginx

    log_success "Nginx установлен"
}

#===============================================================================
# Установка strongSwan
#===============================================================================
install_strongswan() {
    log_info "Установка strongSwan..."

    apt-get install -y strongswan strongswan-pki libcharon-extra-plugins libcharon-extauth-plugins

    mkdir -p /etc/swanctl/conf.d
    mkdir -p /etc/swanctl/x509
    mkdir -p /etc/swanctl/x509ca
    mkdir -p /etc/swanctl/private

    # В режиме restore — сертификаты восстанавливаются из бэкапа
    if [[ "$RESTORE_MODE" == true ]]; then
        log_info "Сертификаты swanctl будут восстановлены из бэкапа"
    else
        log_info "Генерация VPN сертификатов..."

        cd /etc/swanctl

        pki --gen --type rsa --size 4096 --outform pem > private/ca-key.pem
        pki --self --ca --lifetime 3650 --in private/ca-key.pem \
            --type rsa --dn "CN=ProxyGate VPN CA" --outform pem > x509ca/ca-cert.pem

        pki --gen --type rsa --size 4096 --outform pem > private/server-key.pem
        pki --pub --in private/server-key.pem --type rsa | \
            pki --issue --lifetime 1825 \
            --cacert x509ca/ca-cert.pem --cakey private/ca-key.pem \
            --dn "CN=$DOMAIN" --san="$DOMAIN" --san="$SERVER_IP" \
            --flag serverAuth --flag ikeIntermediate --outform pem > x509/server-cert.pem

        chmod 600 private/*
    fi

    log_success "strongSwan установлен"
}

#===============================================================================
# Установка 3proxy
#===============================================================================
install_3proxy() {
    log_info "Установка 3proxy..."

    apt-get install -y 3proxy || {
        cd /tmp
        git clone https://github.com/3proxy/3proxy.git
        cd 3proxy
        make -f Makefile.Linux
        make -f Makefile.Linux install
        cd /
        rm -rf /tmp/3proxy
    }

    mkdir -p /etc/3proxy
    mkdir -p /var/log/3proxy

    # В режиме restore — конфиги восстанавливаются из бэкапа
    if [[ "$RESTORE_MODE" != true ]]; then
        cat > /etc/3proxy/3proxy.cfg << EOFPROXY
daemon
pidfile /var/run/3proxy.pid
nserver 8.8.8.8
nserver 8.8.4.4
nscache 65536
timeouts 10 10 120 300 600 1800 5 60
stacksize 262144
log /var/log/3proxy/3proxy.log D
logformat "- +_L%t.%. %N.%p %E %U %C:%c %R:%r %O %I %h %T"
rotate 30

include /etc/3proxy/users.cfg
include /etc/3proxy/acl.cfg

auth strong
allow *
proxy -p${HTTP_PROXY_PORT}
socks -p${SOCKS_PROXY_PORT}
EOFPROXY

        touch /etc/3proxy/users.cfg
        touch /etc/3proxy/acl.cfg
    fi

    # Systemd service
    if [[ ! -f /etc/systemd/system/3proxy.service ]] || [[ "$RESTORE_MODE" != true ]]; then
        cat > /etc/systemd/system/3proxy.service << 'EOF'
[Unit]
Description=3proxy Proxy Server
After=network.target

[Service]
Type=forking
ExecStart=/usr/bin/3proxy /etc/3proxy/3proxy.cfg
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
    fi

    # 3proxy limits override
    mkdir -p /etc/systemd/system/3proxy.service.d
    cat > /etc/systemd/system/3proxy.service.d/limits.conf << 'EOF'
[Service]
LimitNOFILE=65536
EOF

    systemctl daemon-reload
    systemctl enable 3proxy

    log_success "3proxy установлен"
}

#===============================================================================
# Копирование файлов проекта
#===============================================================================
setup_project_files() {
    log_info "Настройка файлов проекта..."

    PROJECT_SOURCE=""

    if [[ -n "${BASH_SOURCE[0]}" ]] && [[ "${BASH_SOURCE[0]}" != "bash" ]]; then
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
        if [[ -n "$SCRIPT_DIR" ]] && [[ -d "$SCRIPT_DIR/backend" ]]; then
            PROJECT_SOURCE="$SCRIPT_DIR"
            log_info "Источник проекта (BASH_SOURCE): $PROJECT_SOURCE"
        fi
    fi

    if [[ -z "$PROJECT_SOURCE" ]] && [[ -d "./backend" ]]; then
        PROJECT_SOURCE="$(pwd)"
        log_info "Источник проекта (pwd): $PROJECT_SOURCE"
    fi

    if [[ -z "$PROJECT_SOURCE" ]]; then
        for candidate in \
            "/opt/proxygate" \
            "/tmp/"*"/full_network_access/proxygate" \
            "/tmp/proxygate" \
            "$HOME/proxygate" \
            "$HOME/full_network_access/proxygate"; do
            if [[ -d "$candidate/backend" ]]; then
                PROJECT_SOURCE="$candidate"
                log_info "Источник проекта (поиск): $PROJECT_SOURCE"
                break
            fi
        done
    fi

    if [[ -z "$PROJECT_SOURCE" ]]; then
        log_info "Поиск директории проекта..."
        PROJECT_SOURCE=$(find /tmp -maxdepth 4 -type d -name "proxygate" 2>/dev/null | while read dir; do
            if [[ -d "$dir/backend" ]] && [[ -d "$dir/frontend" ]]; then
                echo "$dir"
                break
            fi
        done | head -1)
        if [[ -n "$PROJECT_SOURCE" ]]; then
            log_info "Источник проекта (find): $PROJECT_SOURCE"
        fi
    fi

    if [[ -z "$PROJECT_SOURCE" ]] || [[ ! -d "$PROJECT_SOURCE/backend" ]]; then
        log_error "Не удалось найти файлы проекта!"
        log_error "Убедитесь что backend/ и frontend/ находятся в директории со скриптом"
        exit 1
    fi

    # Если источник != INSTALL_DIR, копируем
    if [[ "$PROJECT_SOURCE" != "$INSTALL_DIR" ]]; then
        mkdir -p "$INSTALL_DIR"
        log_info "Копирование файлов из $PROJECT_SOURCE..."
        cp -r "$PROJECT_SOURCE/backend" "$INSTALL_DIR/"
        cp -r "$PROJECT_SOURCE/frontend" "$INSTALL_DIR/"
        cp -r "$PROJECT_SOURCE/nginx" "$INSTALL_DIR/" 2>/dev/null || true
        cp "$PROJECT_SOURCE/.env.example" "$INSTALL_DIR/.env.example" 2>/dev/null || true
        cp "$PROJECT_SOURCE/VERSION" "$INSTALL_DIR/VERSION" 2>/dev/null || true
    fi

    # Создаём static директорию для Go бинарей
    mkdir -p "$INSTALL_DIR/backend/static"

    log_success "Файлы проекта настроены в $INSTALL_DIR"
}

#===============================================================================
# Создание .env файла
#===============================================================================
create_env_file() {
    log_info "Создание .env файла..."

    cat > $INSTALL_DIR/.env << EOF
# ProxyGate Configuration
# Generated by installer on $(date)

# Database
DATABASE_URL=postgresql+asyncpg://proxygate:${DB_PASSWORD}@localhost/proxygate

# Security
SECRET_KEY=${SECRET_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
PORTAL_TOKEN_EXPIRE_MINUTES=10080

# Server
VPN_SERVER_IP=${SERVER_IP}
VPN_DOMAIN=${DOMAIN}
API_HOST=0.0.0.0
API_PORT=8000

# Admin
ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_PASSWORD=${ADMIN_PASSWORD}

# Proxy ports
HTTP_PROXY_PORT=${HTTP_PROXY_PORT}
SOCKS_PROXY_PORT=${SOCKS_PROXY_PORT}

# Paths
PROFILES_DIR=/var/lib/proxygate/profiles
SWANCTL_DIR=/etc/swanctl
PROXY_CONFIG_DIR=/etc/3proxy

# Telegram (optional)
TELEGRAM_BOT_TOKEN=${TELEGRAM_TOKEN}
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}

# SSL
SSL_CERT_PATH=/etc/letsencrypt/live/${DOMAIN}/fullchain.pem
SSL_KEY_PATH=/etc/letsencrypt/live/${DOMAIN}/privkey.pem
EOF

    chmod 600 $INSTALL_DIR/.env
    cp $INSTALL_DIR/.env $INSTALL_DIR/backend/.env

    log_success ".env файл создан"
}

#===============================================================================
# Исправление requirements.txt
#===============================================================================
fix_requirements() {
    log_info "Проверка и исправление requirements.txt..."

    local req_file="$INSTALL_DIR/backend/requirements.txt"

    if grep -q "pydantic==2.10" "$req_file" 2>/dev/null; then
        sed -i 's/pydantic==2.10.0/pydantic==2.9.2/' "$req_file"
        sed -i 's/pydantic==2.10/pydantic==2.9.2/' "$req_file"
        log_info "Исправлена версия pydantic -> 2.9.2"
    fi

    if ! grep -q "asyncpg" "$req_file" 2>/dev/null; then
        sed -i '/alembic/a asyncpg==0.30.0' "$req_file"
        log_info "Добавлен asyncpg==0.30.0"
    fi

    if ! grep -q "bcrypt==" "$req_file" 2>/dev/null; then
        echo "bcrypt==4.0.1" >> "$req_file"
        log_info "Добавлен bcrypt==4.0.1"
    fi

    if ! grep -q "email-validator" "$req_file" 2>/dev/null; then
        echo "email-validator==2.1.0" >> "$req_file"
        log_info "Добавлен email-validator==2.1.0"
    fi

    log_success "requirements.txt проверен"
}

#===============================================================================
# Настройка Python окружения
#===============================================================================
setup_python_env() {
    log_info "Настройка Python окружения..."

    cd $INSTALL_DIR/backend

    fix_requirements

    python3.12 -m venv venv
    source venv/bin/activate

    pip install --upgrade pip wheel setuptools
    pip install -r requirements.txt
    pip install bcrypt==4.0.1
    pip install email-validator==2.1.0

    # Устанавливаем uvicorn глобально (для systemd)
    pip install uvicorn
    cp venv/bin/uvicorn /usr/local/bin/uvicorn 2>/dev/null || ln -sf "$INSTALL_DIR/backend/venv/bin/uvicorn" /usr/local/bin/uvicorn

    # Устанавливаем alembic глобально
    cp venv/bin/alembic /usr/local/bin/alembic 2>/dev/null || ln -sf "$INSTALL_DIR/backend/venv/bin/alembic" /usr/local/bin/alembic

    deactivate

    log_success "Python окружение настроено"
}

#===============================================================================
# Сборка фронтенда
#===============================================================================
build_frontend() {
    log_info "Сборка фронтенда..."

    cd $INSTALL_DIR/frontend

    cat > .env << EOF
VITE_API_URL=/api
EOF

    npm install
    npm run build

    log_success "Фронтенд собран"
}

#===============================================================================
# Настройка Nginx
#===============================================================================
configure_nginx() {
    log_info "Настройка Nginx..."

    if [[ "$RESTORE_MODE" == true ]]; then
        # Восстанавливаем nginx конфиги из бэкапа
        if [[ -f "$RESTORE_DIR/etc/nginx/proxygate-site" ]]; then
            cp "$RESTORE_DIR/etc/nginx/proxygate-site" /etc/nginx/sites-available/proxygate
            replace_ip_in_file /etc/nginx/sites-available/proxygate
            log_success "  sites-available/proxygate восстановлен"
        fi

        if [[ -f "$RESTORE_DIR/etc/nginx/proxygate.conf" ]]; then
            cp "$RESTORE_DIR/etc/nginx/proxygate.conf" /etc/nginx/sites-available/proxygate
            replace_ip_in_file /etc/nginx/sites-available/proxygate
            log_success "  proxygate.conf восстановлен как sites-available/proxygate"
        fi

        if [[ -f "$RESTORE_DIR/etc/nginx/nginx.conf" ]]; then
            cp "$RESTORE_DIR/etc/nginx/nginx.conf" "$INSTALL_DIR/nginx/nginx.conf"
            replace_ip_in_file "$INSTALL_DIR/nginx/nginx.conf"
        fi

        if [[ -f "$RESTORE_DIR/etc/nginx/nginx.conf.main" ]]; then
            cp "$RESTORE_DIR/etc/nginx/nginx.conf.main" /etc/nginx/nginx.conf
            replace_ip_in_file /etc/nginx/nginx.conf
            log_success "  nginx.conf (main) восстановлен"
        fi
    else
        # Чистая установка — базовый HTTP конфиг
        cat > /etc/nginx/sites-available/proxygate << EOF
# ProxyGate Nginx Configuration
# SSL настраивается позже через: certbot --nginx -d ${DOMAIN}

server {
    listen 80;
    server_name ${DOMAIN} ${SERVER_IP};

    root /opt/proxygate/frontend/dist;
    index index.html;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF
    fi

    mkdir -p /var/www/certbot

    ln -sf /etc/nginx/sites-available/proxygate /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default

    nginx -t && systemctl reload nginx

    log_success "Nginx настроен"
}

#===============================================================================
# Создание systemd сервисов
#===============================================================================
create_systemd_services() {
    log_info "Создание systemd сервисов..."

    # --- proxygate.service ---
    if [[ "$RESTORE_MODE" == true ]] && [[ -f "$RESTORE_DIR/etc/systemd/proxygate.service" ]]; then
        cp "$RESTORE_DIR/etc/systemd/proxygate.service" /etc/systemd/system/proxygate.service
        replace_ip_in_file /etc/systemd/system/proxygate.service
    else
        cat > /etc/systemd/system/proxygate.service << EOF
[Unit]
Description=ProxyGate API Server
After=network.target postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}/backend
ExecStart=/usr/local/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
Environment=PYTHONPATH=${INSTALL_DIR}/backend

[Install]
WantedBy=multi-user.target
EOF
    fi

    # proxygate.service override
    mkdir -p /etc/systemd/system/proxygate.service.d
    if [[ "$RESTORE_MODE" == true ]] && [[ -d "$RESTORE_DIR/etc/systemd/proxygate.service.d" ]]; then
        cp -a "$RESTORE_DIR/etc/systemd/proxygate.service.d/"* /etc/systemd/system/proxygate.service.d/ 2>/dev/null || true
    else
        cat > /etc/systemd/system/proxygate.service.d/override.conf << 'EOF'
[Service]
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Filesystem protection
ProtectHome=yes
PrivateTmp=yes
ProtectSystem=strict
ReadWritePaths=/opt/proxygate /etc/wireguard /etc/swanctl/conf.d /etc/swanctl/x509 /etc/swanctl/private /etc/3proxy /etc/nginx/sites-available /etc/nginx/sites-enabled /usr/local/etc/xray /etc/letsencrypt /var/www/proxygate /etc/systemd/system /var/log/3proxy /usr/local/bin

# Kernel protection
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
ProtectClock=yes

# Process restrictions
RestrictRealtime=yes
RestrictSUIDSGID=yes
LockPersonality=yes
EOF
    fi
    log_success "  proxygate.service"

    # --- tls-proxy.service ---
    if [[ "$RESTORE_MODE" == true ]] && [[ -f "$RESTORE_DIR/etc/systemd/tls-proxy.service" ]]; then
        cp "$RESTORE_DIR/etc/systemd/tls-proxy.service" /etc/systemd/system/tls-proxy.service
        replace_ip_in_file /etc/systemd/system/tls-proxy.service
    else
        cat > /etc/systemd/system/tls-proxy.service << EOF
[Unit]
Description=ProxyGate Go TLS Proxy (DPI bypass + web panel)
After=network.target 3proxy.service nginx.service

[Service]
Type=simple
ExecStart=/usr/local/bin/proxygate-tls-proxy
Environment=TLS_PROXY_LISTEN=:443
Environment=TLS_PROXY_BACKUP=:8443
Environment=TLS_PROXY_BACKEND=127.0.0.1:3128
Environment=TLS_PROXY_WEB=127.0.0.1:8445
Environment=TLS_PROXY_CERT=/etc/letsencrypt/live/${DOMAIN}/fullchain.pem
Environment=TLS_PROXY_KEY=/etc/letsencrypt/live/${DOMAIN}/privkey.pem
AmbientCapabilities=CAP_NET_BIND_SERVICE
Restart=always
RestartSec=3
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
    fi

    # tls-proxy overrides
    if [[ "$RESTORE_MODE" == true ]] && [[ -d "$RESTORE_DIR/etc/systemd/tls-proxy.service.d" ]]; then
        mkdir -p /etc/systemd/system/tls-proxy.service.d
        cp -a "$RESTORE_DIR/etc/systemd/tls-proxy.service.d/"* /etc/systemd/system/tls-proxy.service.d/ 2>/dev/null || true
    fi
    log_success "  tls-proxy.service"

    # --- xray.service (restore overrides) ---
    if [[ "$RESTORE_MODE" == true ]] && [[ -f "$RESTORE_DIR/etc/systemd/xray.service" ]]; then
        cp "$RESTORE_DIR/etc/systemd/xray.service" /etc/systemd/system/xray.service
    fi
    if [[ "$RESTORE_MODE" == true ]] && [[ -d "$RESTORE_DIR/etc/systemd/xray.service.d" ]]; then
        mkdir -p /etc/systemd/system/xray.service.d
        cp -a "$RESTORE_DIR/etc/systemd/xray.service.d/"* /etc/systemd/system/xray.service.d/ 2>/dev/null || true
    fi

    systemctl daemon-reload
    systemctl enable proxygate
    systemctl enable tls-proxy 2>/dev/null || true

    log_success "Systemd сервисы созданы"
}

#===============================================================================
# Инициализация базы данных (чистая установка)
#===============================================================================
init_database() {
    # В режиме restore БД уже восстановлена из дампа
    if [[ "$RESTORE_MODE" == true ]]; then
        log_info "БД восстановлена из бэкапа, пропускаем init_database"

        # Обновляем VPN_SERVER_IP в БД если IP изменился
        if [[ -n "$OLD_IP" ]] && [[ -n "$SERVER_IP" ]] && [[ "$OLD_IP" != "$SERVER_IP" ]]; then
            log_info "Обновление IP в БД: $OLD_IP → $SERVER_IP"
            sudo -u postgres psql proxygate -c "UPDATE system_settings SET value = '$SERVER_IP' WHERE key = 'server_ip';" 2>/dev/null || true
            sudo -u postgres psql proxygate -c "UPDATE system_settings SET value = '$SERVER_IP' WHERE key = 'vpn_server_ip';" 2>/dev/null || true
        fi
        return
    fi

    log_info "Инициализация базы данных..."

    cd $INSTALL_DIR/backend
    source venv/bin/activate

    alembic upgrade head
    python3.12 scripts/init_db.py

    deactivate

    log_success "База данных инициализирована"
}

#===============================================================================
# Восстановление конфигов из бэкапа
#===============================================================================
restore_configs() {
    if [[ "$RESTORE_MODE" != true ]]; then
        return
    fi

    log_info "Восстановление конфигов из бэкапа..."

    # 3proxy
    if [[ -d "$RESTORE_DIR/etc/3proxy" ]] && [[ -n "$(ls -A "$RESTORE_DIR/etc/3proxy" 2>/dev/null)" ]]; then
        cp -a "$RESTORE_DIR/etc/3proxy/"* /etc/3proxy/
        # Заменяем IP во всех конфигах
        for f in /etc/3proxy/*; do
            replace_ip_in_file "$f"
        done
        log_success "  3proxy конфиги восстановлены"
    fi

    # swanctl (VPN сертификаты)
    if [[ -d "$RESTORE_DIR/etc/swanctl" ]] && [[ -n "$(ls -A "$RESTORE_DIR/etc/swanctl" 2>/dev/null)" ]]; then
        cp -a "$RESTORE_DIR/etc/swanctl/"* /etc/swanctl/
        chmod 600 /etc/swanctl/private/* 2>/dev/null || true
        log_success "  swanctl сертификаты восстановлены"
    fi

    # WireGuard
    if [[ -d "$RESTORE_DIR/etc/wireguard" ]] && [[ -n "$(ls -A "$RESTORE_DIR/etc/wireguard" 2>/dev/null)" ]]; then
        mkdir -p /etc/wireguard
        cp -a "$RESTORE_DIR/etc/wireguard/"* /etc/wireguard/
        for f in /etc/wireguard/*; do
            replace_ip_in_file "$f"
        done
        chmod 600 /etc/wireguard/* 2>/dev/null || true
        log_success "  WireGuard конфиги восстановлены"
    fi

    # XRay
    if [[ -f "$RESTORE_DIR/etc/xray/config.json" ]]; then
        mkdir -p /usr/local/etc/xray
        cp "$RESTORE_DIR/etc/xray/config.json" /usr/local/etc/xray/
        replace_ip_in_file /usr/local/etc/xray/config.json
        log_success "  XRay config восстановлен"
    fi

    # Let's Encrypt (временно, до получения нового сертификата)
    if [[ -d "$RESTORE_DIR/etc/letsencrypt" ]] && [[ -n "$(ls -A "$RESTORE_DIR/etc/letsencrypt" 2>/dev/null)" ]]; then
        cp -a "$RESTORE_DIR/etc/letsencrypt/"* /etc/letsencrypt/ 2>/dev/null || true
        log_success "  Let's Encrypt сертификаты восстановлены (временно)"
        log_warn "  После переключения DNS выполните: certbot --nginx -d $DOMAIN"
    fi

    # Sysctl
    if [[ -f "$RESTORE_DIR/etc/sysctl.d/99-proxygate.conf" ]]; then
        cp "$RESTORE_DIR/etc/sysctl.d/99-proxygate.conf" /etc/sysctl.d/
        sysctl -p /etc/sysctl.d/99-proxygate.conf 2>/dev/null || true
        log_success "  sysctl конфиги восстановлены"
    fi

    # Profiles
    if [[ -d "$RESTORE_DIR/profiles" ]] && [[ -n "$(ls -A "$RESTORE_DIR/profiles" 2>/dev/null)" ]]; then
        mkdir -p /var/lib/proxygate/profiles
        cp -a "$RESTORE_DIR/profiles/"* /var/lib/proxygate/profiles/
        log_success "  Профили восстановлены"
    fi

    # Settings files (.ssl_settings.json, .system_settings.json, .update_settings.json)
    for f in .ssl_settings.json .system_settings.json .update_settings.json; do
        if [[ -f "$RESTORE_DIR/env/$f" ]]; then
            cp "$RESTORE_DIR/env/$f" "$INSTALL_DIR/"
            replace_ip_in_file "$INSTALL_DIR/$f"
            log_success "  $f восстановлен"
        fi
    done

    # Go sources (для пересборки)
    if [[ -d "$RESTORE_DIR/go-src/tls-proxy-go" ]] && [[ -n "$(ls -A "$RESTORE_DIR/go-src/tls-proxy-go" 2>/dev/null)" ]]; then
        mkdir -p "$INSTALL_DIR/backend/scripts/tls-proxy-go"
        cp -a "$RESTORE_DIR/go-src/tls-proxy-go/"* "$INSTALL_DIR/backend/scripts/tls-proxy-go/"
        log_success "  Go source: tls-proxy-go"
    fi

    if [[ -d "$RESTORE_DIR/go-src/proxygate-connect" ]] && [[ -n "$(ls -A "$RESTORE_DIR/go-src/proxygate-connect" 2>/dev/null)" ]]; then
        mkdir -p "$INSTALL_DIR/backend/scripts/proxygate-connect"
        cp -a "$RESTORE_DIR/go-src/proxygate-connect/"* "$INSTALL_DIR/backend/scripts/proxygate-connect/"
        log_success "  Go source: proxygate-connect"
    fi

    log_success "Конфиги восстановлены"
}

#===============================================================================
# Настройка iptables PROXYGATE chain
#===============================================================================
setup_iptables() {
    log_info "Настройка iptables PROXYGATE chain..."

    # Создаём chain если не существует
    iptables -N PROXYGATE 2>/dev/null || true

    # Очищаем chain
    iptables -F PROXYGATE

    # Localhost всегда разрешён
    iptables -A PROXYGATE -s 127.0.0.1 -j ACCEPT

    # DROP в конце
    iptables -A PROXYGATE -j DROP

    # Привязываем к INPUT для proxy-портов
    local ports="443 2053 8080 3128 1080 8443"
    for port in $ports; do
        # Удаляем старое правило если есть
        iptables -D INPUT -p tcp --dport "$port" -j PROXYGATE 2>/dev/null || true
        # Добавляем
        iptables -A INPUT -p tcp --dport "$port" -j PROXYGATE
    done

    # IPv6
    ip6tables -N PROXYGATE 2>/dev/null || true
    ip6tables -F PROXYGATE
    ip6tables -A PROXYGATE -s ::1 -j ACCEPT
    ip6tables -A PROXYGATE -j DROP

    for port in $ports; do
        ip6tables -D INPUT -p tcp --dport "$port" -j PROXYGATE 2>/dev/null || true
        ip6tables -A INPUT -p tcp --dport "$port" -j PROXYGATE
    done

    # Сохраняем правила
    if command -v iptables-save &>/dev/null; then
        mkdir -p /etc/iptables
        iptables-save > /etc/iptables/rules.v4
        ip6tables-save > /etc/iptables/rules.v6
    fi

    # Устанавливаем iptables-persistent для автозагрузки
    apt-get install -y iptables-persistent 2>/dev/null || true

    log_success "iptables PROXYGATE chain настроен"
}

#===============================================================================
# Настройка sysctl
#===============================================================================
setup_sysctl() {
    if [[ "$RESTORE_MODE" == true ]]; then
        # Уже восстановлено в restore_configs
        return
    fi

    log_info "Настройка sysctl..."

    cat > /etc/sysctl.d/99-proxygate.conf << 'EOF'
net.ipv4.tcp_fastopen = 3
EOF

    sysctl -p /etc/sysctl.d/99-proxygate.conf 2>/dev/null || true

    log_success "sysctl настроен"
}

#===============================================================================
# Настройка файрвола (UFW)
#===============================================================================
configure_firewall() {
    log_info "Настройка файрвола..."

    ufw --force reset
    ufw default deny incoming
    ufw default allow outgoing

    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow 8443/tcp
    ufw allow 2053/tcp
    ufw allow 500/udp
    ufw allow 4500/udp

    ufw --force enable

    log_success "Файрвол настроен"
}

#===============================================================================
# Настройка cron задач
#===============================================================================
setup_cron() {
    log_info "Настройка cron задач..."

    if [[ "$RESTORE_MODE" == true ]] && [[ -f "$RESTORE_DIR/crontab.txt" ]]; then
        # Восстанавливаем crontab из бэкапа
        local crontab_content=$(cat "$RESTORE_DIR/crontab.txt")
        if [[ -n "$crontab_content" ]] && [[ "$crontab_content" != "# No crontab" ]]; then
            # Заменяем OLD_IP если нужно
            if [[ -n "$OLD_IP" ]] && [[ -n "$SERVER_IP" ]] && [[ "$OLD_IP" != "$SERVER_IP" ]]; then
                echo "$crontab_content" | sed "s/${OLD_IP}/${SERVER_IP}/g" | crontab -
            else
                echo "$crontab_content" | crontab -
            fi
            log_success "Crontab восстановлен из бэкапа"
            return
        fi
    fi

    # Чистая установка — базовый cron
    cat > $INSTALL_DIR/update.sh << 'EOF'
#!/bin/bash
cd /opt/proxygate
source backend/venv/bin/activate
python backend/scripts/cron_tasks.py
deactivate
EOF
    chmod +x $INSTALL_DIR/update.sh

    (crontab -l 2>/dev/null | grep -v proxygate; echo "*/30 * * * * $INSTALL_DIR/update.sh >> /var/log/proxygate-cron.log 2>&1") | crontab -

    log_success "Cron задачи настроены"
}

#===============================================================================
# Создание директорий
#===============================================================================
create_directories() {
    log_info "Создание директорий..."

    mkdir -p /var/lib/proxygate/profiles
    mkdir -p /var/log/proxygate
    mkdir -p /var/log/3proxy
    mkdir -p /var/www/certbot
    mkdir -p /etc/letsencrypt
    mkdir -p /usr/local/etc/xray

    chmod 755 /var/lib/proxygate
    chmod 755 /var/lib/proxygate/profiles

    log_success "Директории созданы"
}

#===============================================================================
# Установка Let's Encrypt SSL
#===============================================================================
install_letsencrypt() {
    if [[ "$RESTORE_MODE" == true ]]; then
        log_info "Режим restore: SSL сертификаты восстановлены из бэкапа"
        log_warn "После переключения DNS выполните: certbot renew --force-renewal"
        apt-get install -y certbot python3-certbot-nginx 2>/dev/null || true
        return
    fi

    if [[ "$INSTALL_SSL" != "y" ]]; then
        log_info "SSL не запрошен. Можно настроить позже:"
        log_info "  sudo certbot --nginx -d $DOMAIN"
        return
    fi

    if [[ "$DOMAIN" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        log_warn "Let's Encrypt требует доменное имя, не IP. Пропускаем SSL."
        return
    fi

    log_info "Установка Let's Encrypt SSL..."

    apt-get install -y certbot python3-certbot-nginx

    if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "$ADMIN_EMAIL" --redirect; then
        (crontab -l 2>/dev/null | grep -v certbot; echo "0 3 * * * certbot renew --quiet --post-hook 'systemctl reload nginx; kill -HUP \$(pidof proxygate-tls-proxy) 2>/dev/null || true'") | crontab -
        log_success "Let's Encrypt SSL установлен"
    else
        log_warn "Не удалось получить SSL сертификат."
        log_warn "Проверьте что DNS для $DOMAIN указывает на $SERVER_IP"
        log_info "Попробуйте позже: sudo certbot --nginx -d $DOMAIN"
    fi
}

#===============================================================================
# Запуск сервисов
#===============================================================================
start_services() {
    log_info "Запуск сервисов..."

    systemctl start postgresql
    systemctl start nginx
    systemctl start strongswan-starter 2>/dev/null || systemctl start strongswan 2>/dev/null || true
    systemctl start 3proxy || true
    systemctl start proxygate

    # TLS proxy — только если есть SSL сертификат
    if [[ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
        systemctl start tls-proxy || true
        log_success "  tls-proxy запущен"
    else
        log_warn "  tls-proxy не запущен (нет SSL сертификата для $DOMAIN)"
    fi

    # XRay — только если есть конфиг
    if [[ -f /usr/local/etc/xray/config.json ]]; then
        systemctl start xray || true
        log_success "  xray запущен"
    fi

    log_success "Сервисы запущены"
}

#===============================================================================
# Вывод информации
#===============================================================================
print_installation_info() {
    local protocol="http"
    if [[ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
        protocol="https"
    fi

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    if [[ "$RESTORE_MODE" == true ]]; then
        echo -e "${GREEN}║      ВОССТАНОВЛЕНИЕ ЗАВЕРШЕНО УСПЕШНО!                       ║${NC}"
    else
        echo -e "${GREEN}║      УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО!                            ║${NC}"
    fi
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Данные для входа:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "  Админ-панель:  ${GREEN}${protocol}://${DOMAIN}/admin${NC}"
    echo -e "  Логин:         ${GREEN}admin${NC}"
    echo -e "  Пароль:        ${GREEN}${ADMIN_PASSWORD}${NC}"
    echo ""
    echo -e "  Клиент-портал: ${GREEN}${protocol}://${DOMAIN}/portal${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo -e "${BLUE}Полезные команды:${NC}"
    echo "  systemctl status proxygate tls-proxy 3proxy xray nginx"
    echo "  journalctl -u proxygate -f"
    echo "  curl -k https://localhost:8445/api/health"
    echo ""

    if [[ "$RESTORE_MODE" == true ]]; then
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}  Следующие шаги после миграции:${NC}"
        echo ""
        echo -e "  1. Переключить DNS ${BLUE}${DOMAIN}${NC} → ${BLUE}${SERVER_IP}${NC}"
        echo -e "  2. Получить новый SSL: ${BLUE}certbot --nginx -d ${DOMAIN}${NC}"
        echo -e "  3. Перезапустить: ${BLUE}systemctl restart tls-proxy nginx proxygate${NC}"
        echo -e "  4. Проверить: ${BLUE}systemctl status proxygate tls-proxy 3proxy xray nginx${NC}"
        echo -e "  5. Проверить БД: ${BLUE}psql -U proxygate -d proxygate -c \"SELECT count(*) FROM clients\"${NC}"
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    else
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}Для включения HTTPS (Let's Encrypt):${NC}"
        echo "  sudo apt install -y certbot python3-certbot-nginx"
        echo "  sudo certbot --nginx -d ${DOMAIN}"
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    fi
    echo ""

    # Сохраняем credentials
    cat > $INSTALL_DIR/credentials.txt << EOF
ProxyGate Installation Credentials
===================================
Generated: $(date)
Mode: $([ "$RESTORE_MODE" == true ] && echo "Restore" || echo "Fresh install")

Admin Panel: ${protocol}://${DOMAIN}/admin
Client Portal: ${protocol}://${DOMAIN}/portal

Username: admin
Password: ${ADMIN_PASSWORD}

Database Password: ${DB_PASSWORD}
Secret Key: ${SECRET_KEY}

Server IP: ${SERVER_IP}
Domain: ${DOMAIN}
$([ -n "$OLD_IP" ] && echo "Old Server IP: ${OLD_IP}")

HTTP Proxy Port: ${HTTP_PROXY_PORT}
SOCKS5 Proxy Port: ${SOCKS_PROXY_PORT}
EOF
    chmod 600 $INSTALL_DIR/credentials.txt

    echo -e "${GREEN}Credentials сохранены в: $INSTALL_DIR/credentials.txt${NC}"
    echo ""
}

#===============================================================================
# Cleanup restore
#===============================================================================
cleanup_restore() {
    if [[ "$RESTORE_MODE" == true ]] && [[ -d "$RESTORE_DIR" ]]; then
        rm -rf "$RESTORE_DIR"
        log_success "Временные файлы восстановления очищены"
    fi
}

#===============================================================================
# Main
#===============================================================================
main() {
    parse_args "$@"
    check_root

    if [[ "$RESTORE_MODE" == true ]]; then
        echo ""
        echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║       ProxyGate Installer v2.0 — RESTORE MODE               ║${NC}"
        echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
        echo ""

        unpack_restore

        if ! read_confirm "Начать восстановление?"; then
            log_warn "Восстановление отменено"
            exit 0
        fi
    else
        interactive_setup
    fi

    echo ""
    log_info "Начинаем $([ "$RESTORE_MODE" == true ] && echo "восстановление" || echo "установку")..."
    echo ""

    update_system
    install_base_packages
    install_python
    install_go
    install_postgresql
    install_nodejs
    install_nginx
    install_strongswan
    install_3proxy
    install_xray
    create_directories
    setup_project_files
    create_env_file
    setup_python_env
    build_frontend
    restore_configs
    configure_nginx
    create_systemd_services
    init_database
    build_go_binaries
    setup_sysctl
    setup_iptables
    configure_firewall
    setup_cron
    start_services
    install_letsencrypt

    print_installation_info
    cleanup_restore
}

main "$@"
