#!/bin/bash
set -e

#===============================================================================
# ProxyGate Auto-Installer v1.2
# Полная автоматическая установка VPN/Proxy системы
# Поддержка: Ubuntu 22.04 LTS, 24.04 LTS
#
# Исправления v1.2:
# - Фикс pydantic версии (2.9.2 для совместимости с aiogram)
# - Фикс bcrypt версии (4.0.1 для совместимости с passlib)
# - Добавлен asyncpg для PostgreSQL
# - Улучшен поиск директории проекта
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
SYSTEM_PYTHON=""  # Системный Python (3.10 или 3.11)

#===============================================================================
# Функция для чтения ввода (работает даже при curl | bash)
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

    # Отключаем needrestart если установлен
    if [[ -f /etc/needrestart/needrestart.conf ]]; then
        sed -i "s/#\$nrconf{restart} = 'i';/\$nrconf{restart} = 'a';/" /etc/needrestart/needrestart.conf 2>/dev/null || true
    fi

    # Отключаем интерактивные диалоги dpkg
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
    # Находим системный Python (не из deadsnakes)
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
# Определение IP сервера (предпочитаем IPv4)
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
# Интерактивная настройка
#===============================================================================
interactive_setup() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          ProxyGate Installer v1.0                            ║${NC}"
    echo -e "${GREEN}║          VPN/Proxy Management System                         ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    detect_server_ip
    generate_secrets

    echo ""
    echo -e "${BLUE}=== Основные настройки ===${NC}"
    echo ""

    # IP сервера
    SERVER_IP=$(read_input "IP адрес сервера (IPv4)" "$SERVER_IP")

    # Домен
    echo ""
    local input_domain
    input_domain=$(read_input "Домен для VPN/панели (Enter = использовать IP)" "")
    if [[ -n "$input_domain" ]]; then
        DOMAIN="$input_domain"
    else
        DOMAIN="$SERVER_IP"
    fi

    # Admin пароль
    echo ""
    local input_pass
    input_pass=$(read_input "Пароль администратора (Enter = автогенерация)" "$ADMIN_PASSWORD")
    ADMIN_PASSWORD="$input_pass"

    # Admin email
    echo ""
    ADMIN_EMAIL=$(read_input "Email администратора" "admin@${DOMAIN}")

    echo ""
    echo -e "${BLUE}=== Telegram уведомления (опционально) ===${NC}"
    echo ""

    # Telegram
    TELEGRAM_TOKEN=$(read_input "Telegram Bot Token (Enter = пропустить)" "")

    if [[ -n "$TELEGRAM_TOKEN" ]]; then
        echo ""
        TELEGRAM_CHAT_ID=$(read_input "Telegram Chat ID" "")
    fi

    echo ""
    echo -e "${BLUE}=== Дополнительные настройки ===${NC}"
    echo ""

    # Порты прокси
    HTTP_PROXY_PORT=$(read_input "HTTP Proxy порт" "3128")
    echo ""
    SOCKS_PROXY_PORT=$(read_input "SOCKS5 Proxy порт" "1080")

    # SSL сертификат
    echo ""
    if read_confirm "Установить Let's Encrypt SSL?"; then
        INSTALL_SSL="y"
    else
        INSTALL_SSL="n"
    fi

    # Показываем итоговую конфигурацию
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
# Исправление репозиториев (для проблемных версий Ubuntu)
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

    # Обновляем без интерактивных запросов
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
        cron

    log_success "Базовые пакеты установлены"
}

#===============================================================================
# Установка Python 3.12
#===============================================================================
install_python() {
    log_info "Установка Python 3.12..."

    # Определяем системный Python ДО изменений
    detect_system_python

    # Устанавливаем python3-apt для системного Python (нужен для apt)
    apt-get install -y python3-apt 2>/dev/null || true

    # Добавляем PPA
    add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
    apt-get update -y || true

    # Устанавливаем Python 3.12
    apt-get install -y python3.12 python3.12-venv python3.12-dev

    # Устанавливаем pip для Python 3.12
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12 || {
        apt-get install -y python3-pip
    }

    # ВАЖНО: НЕ меняем системный python3, это ломает apt!
    # Вместо этого создаём симлинк python3.12 и используем его явно
    # update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

    # Убеждаемся что системный Python работает для apt
    if [[ -n "$SYSTEM_PYTHON" ]] && [[ -x "$SYSTEM_PYTHON" ]]; then
        # Восстанавливаем системный Python как default если он был изменён
        update-alternatives --install /usr/bin/python3 python3 "$SYSTEM_PYTHON" 2 2>/dev/null || true
    fi

    log_success "Python 3.12 установлен"
    python3.12 --version

    # Проверяем что apt работает
    log_info "Проверка работы apt..."
    apt-get update -y > /dev/null 2>&1 || {
        log_warn "apt update выдал ошибку, пробуем исправить..."
        # Если apt сломан - восстанавливаем системный Python
        if [[ -x /usr/bin/python3.10 ]]; then
            update-alternatives --set python3 /usr/bin/python3.10 2>/dev/null || true
        elif [[ -x /usr/bin/python3.11 ]]; then
            update-alternatives --set python3 /usr/bin/python3.11 2>/dev/null || true
        fi
        apt-get update -y || true
    }
}

#===============================================================================
# Установка PostgreSQL
#===============================================================================
install_postgresql() {
    log_info "Установка PostgreSQL..."

    apt-get install -y postgresql postgresql-contrib

    systemctl start postgresql
    systemctl enable postgresql

    sudo -u postgres psql -c "DROP DATABASE IF EXISTS proxygate;"
    sudo -u postgres psql -c "DROP USER IF EXISTS proxygate;"
    sudo -u postgres psql -c "CREATE USER proxygate WITH PASSWORD '$DB_PASSWORD';"
    sudo -u postgres psql -c "CREATE DATABASE proxygate OWNER proxygate;"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE proxygate TO proxygate;"

    log_success "PostgreSQL установлен и настроен"
}

#===============================================================================
# Установка Node.js 20
#===============================================================================
install_nodejs() {
    log_info "Установка Node.js 20..."

    # Удаляем старые версии Node.js если есть
    apt-get remove -y nodejs npm 2>/dev/null || true
    rm -f /etc/apt/sources.list.d/nodesource*.list 2>/dev/null || true
    rm -f /etc/apt/keyrings/nodesource.gpg 2>/dev/null || true

    # Устанавливаем зависимости
    apt-get install -y ca-certificates curl gnupg

    # Создаём директорию для ключей
    mkdir -p /etc/apt/keyrings

    # Скачиваем и добавляем GPG ключ NodeSource
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg

    # Добавляем репозиторий NodeSource
    NODE_MAJOR=20
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list

    # Обновляем и устанавливаем
    apt-get update -y
    apt-get install -y nodejs

    # Проверяем установку
    if ! command -v node &> /dev/null || ! command -v npm &> /dev/null; then
        log_error "Node.js не установился корректно. Пробуем альтернативный метод..."

        # Альтернативный метод через NVM
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        nvm install 20
        nvm use 20
        nvm alias default 20

        # Создаём симлинки
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
# Установка strongSwan (IKEv2 VPN)
#===============================================================================
install_strongswan() {
    log_info "Установка strongSwan..."

    apt-get install -y strongswan strongswan-pki libcharon-extra-plugins libcharon-extauth-plugins

    mkdir -p /etc/swanctl/conf.d
    mkdir -p /etc/swanctl/x509
    mkdir -p /etc/swanctl/x509ca
    mkdir -p /etc/swanctl/private

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

    cat > /etc/3proxy/3proxy.cfg << EOFPROXY
daemon
pidfile /var/run/3proxy.pid
nserver 8.8.8.8
nserver 8.8.4.4
nscache 65536
timeouts 1 5 30 60 180 1800 15 60
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

    systemctl daemon-reload
    systemctl enable 3proxy

    log_success "3proxy установлен"
}

#===============================================================================
# Копирование файлов проекта
#===============================================================================
setup_project_files() {
    log_info "Настройка файлов проекта..."

    # Определяем директорию с исходниками проекта
    PROJECT_SOURCE=""

    # Метод 1: Используем BASH_SOURCE если доступен
    if [[ -n "${BASH_SOURCE[0]}" ]] && [[ "${BASH_SOURCE[0]}" != "bash" ]]; then
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
        if [[ -n "$SCRIPT_DIR" ]] && [[ -d "$SCRIPT_DIR/backend" ]]; then
            PROJECT_SOURCE="$SCRIPT_DIR"
            log_info "Источник проекта (BASH_SOURCE): $PROJECT_SOURCE"
        fi
    fi

    # Метод 2: Проверяем текущую директорию
    if [[ -z "$PROJECT_SOURCE" ]] && [[ -d "./backend" ]]; then
        PROJECT_SOURCE="$(pwd)"
        log_info "Источник проекта (pwd): $PROJECT_SOURCE"
    fi

    # Метод 3: Ищем в типичных местах после клонирования
    if [[ -z "$PROJECT_SOURCE" ]]; then
        for candidate in \
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

    # Метод 4: Поиск через find (последний вариант)
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

    # Проверяем что нашли
    if [[ -z "$PROJECT_SOURCE" ]] || [[ ! -d "$PROJECT_SOURCE/backend" ]]; then
        log_error "Не удалось найти файлы проекта!"
        log_error "Убедитесь что backend/ и frontend/ находятся в директории со скриптом"
        log_error "Или запустите скрипт из директории proxygate/"
        exit 1
    fi

    mkdir -p $INSTALL_DIR

    log_info "Копирование файлов из $PROJECT_SOURCE..."
    cp -r "$PROJECT_SOURCE/backend" "$INSTALL_DIR/"
    cp -r "$PROJECT_SOURCE/frontend" "$INSTALL_DIR/"
    cp -r "$PROJECT_SOURCE/nginx" "$INSTALL_DIR/" 2>/dev/null || true
    cp "$PROJECT_SOURCE/.env.example" "$INSTALL_DIR/.env.example" 2>/dev/null || true

    log_success "Файлы проекта скопированы в $INSTALL_DIR"
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
# Исправление requirements.txt для совместимости версий
#===============================================================================
fix_requirements() {
    log_info "Проверка и исправление requirements.txt..."

    local req_file="$INSTALL_DIR/backend/requirements.txt"

    # Исправляем pydantic: aiogram требует <2.10
    if grep -q "pydantic==2.10" "$req_file" 2>/dev/null; then
        sed -i 's/pydantic==2.10.0/pydantic==2.9.2/' "$req_file"
        sed -i 's/pydantic==2.10/pydantic==2.9.2/' "$req_file"
        log_info "Исправлена версия pydantic -> 2.9.2"
    fi

    # Добавляем asyncpg если отсутствует
    if ! grep -q "asyncpg" "$req_file" 2>/dev/null; then
        # Добавляем после alembic
        sed -i '/alembic/a asyncpg==0.30.0' "$req_file"
        log_info "Добавлен asyncpg==0.30.0"
    fi

    # Добавляем bcrypt с правильной версией (4.0.1 совместим с passlib)
    if ! grep -q "bcrypt==" "$req_file" 2>/dev/null; then
        echo "bcrypt==4.0.1" >> "$req_file"
        log_info "Добавлен bcrypt==4.0.1"
    fi

    log_success "requirements.txt проверен"
}

#===============================================================================
# Настройка Python окружения
#===============================================================================
setup_python_env() {
    log_info "Настройка Python окружения..."

    cd $INSTALL_DIR/backend

    # Исправляем requirements.txt перед установкой
    fix_requirements

    # Создаём виртуальное окружение
    python3.12 -m venv venv
    source venv/bin/activate

    # Обновляем pip
    pip install --upgrade pip wheel setuptools

    # Устанавливаем зависимости
    pip install -r requirements.txt

    # Принудительно устанавливаем правильную версию bcrypt
    # (passlib 1.7.4 несовместим с bcrypt 5.x)
    pip install bcrypt==4.0.1

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
VITE_API_URL=https://${DOMAIN}/api
EOF

    npm install
    npm run build

    mkdir -p /var/www/proxygate
    cp -r dist/* /var/www/proxygate/

    log_success "Фронтенд собран"
}

#===============================================================================
# Настройка Nginx
#===============================================================================
configure_nginx() {
    log_info "Настройка Nginx..."

    cat > /etc/nginx/sites-available/proxygate << EOF
server {
    listen 80;
    server_name ${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://\$server_name\$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name ${DOMAIN};

    ssl_certificate /etc/nginx/ssl/selfsigned.crt;
    ssl_certificate_key /etc/nginx/ssl/selfsigned.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    root /var/www/proxygate;
    index index.html;

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
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

    mkdir -p /etc/nginx/ssl
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/nginx/ssl/selfsigned.key \
        -out /etc/nginx/ssl/selfsigned.crt \
        -subj "/CN=${DOMAIN}"

    ln -sf /etc/nginx/sites-available/proxygate /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default

    nginx -t && systemctl reload nginx

    log_success "Nginx настроен"
}

#===============================================================================
# Создание systemd сервиса
#===============================================================================
create_systemd_service() {
    log_info "Создание systemd сервиса..."

    cat > /etc/systemd/system/proxygate.service << EOF
[Unit]
Description=ProxyGate API Server
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=${INSTALL_DIR}/backend
Environment="PATH=${INSTALL_DIR}/backend/venv/bin"
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable proxygate

    log_success "Systemd сервис создан"
}

#===============================================================================
# Инициализация базы данных
#===============================================================================
init_database() {
    log_info "Инициализация базы данных..."

    cd $INSTALL_DIR/backend
    source venv/bin/activate

    alembic upgrade head
    python scripts/init_db.py

    deactivate

    log_success "База данных инициализирована"
}

#===============================================================================
# Настройка файрвола
#===============================================================================
configure_firewall() {
    log_info "Настройка файрвола..."

    ufw --force reset
    ufw default deny incoming
    ufw default allow outgoing

    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
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
    mkdir -p /var/www/certbot

    chmod 755 /var/lib/proxygate
    chmod 755 /var/lib/proxygate/profiles

    log_success "Директории созданы"
}

#===============================================================================
# Установка Let's Encrypt SSL
#===============================================================================
install_letsencrypt() {
    if [[ "$INSTALL_SSL" != "y" ]]; then
        return
    fi

    if [[ "$DOMAIN" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        log_warn "Let's Encrypt требует доменное имя, не IP. Пропускаем SSL."
        return
    fi

    log_info "Установка Let's Encrypt SSL..."

    apt-get install -y certbot python3-certbot-nginx

    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "$ADMIN_EMAIL" --redirect || {
        log_warn "Не удалось получить SSL сертификат. Проверьте DNS записи."
        return
    }

    sed -i "s|/etc/nginx/ssl/selfsigned.crt|/etc/letsencrypt/live/${DOMAIN}/fullchain.pem|g" /etc/nginx/sites-available/proxygate
    sed -i "s|/etc/nginx/ssl/selfsigned.key|/etc/letsencrypt/live/${DOMAIN}/privkey.pem|g" /etc/nginx/sites-available/proxygate

    (crontab -l 2>/dev/null | grep -v certbot; echo "0 3 * * * certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -

    nginx -t && systemctl reload nginx

    log_success "Let's Encrypt SSL установлен"
}

#===============================================================================
# Запуск сервисов
#===============================================================================
start_services() {
    log_info "Запуск сервисов..."

    systemctl start postgresql
    systemctl start nginx
    systemctl start strongswan-starter || systemctl start strongswan
    systemctl start 3proxy || true
    systemctl start proxygate

    log_success "Сервисы запущены"
}

#===============================================================================
# Вывод информации об установке
#===============================================================================
print_installation_info() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО!                        ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Данные для входа:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "  Админ-панель:  ${GREEN}https://${DOMAIN}/admin${NC}"
    echo -e "  Логин:         ${GREEN}admin${NC}"
    echo -e "  Пароль:        ${GREEN}${ADMIN_PASSWORD}${NC}"
    echo ""
    echo -e "  Клиент-портал: ${GREEN}https://${DOMAIN}/portal${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo -e "${BLUE}Полезные команды:${NC}"
    echo "  systemctl status proxygate    - статус API"
    echo "  systemctl restart proxygate   - перезапуск API"
    echo "  journalctl -u proxygate -f    - логи API"
    echo ""
    echo -e "${BLUE}Файлы конфигурации:${NC}"
    echo "  $INSTALL_DIR/.env"
    echo "  $INSTALL_DIR/credentials.txt"
    echo ""

    if [[ "$INSTALL_SSL" != "y" ]]; then
        echo -e "${YELLOW}Для SSL сертификата Let's Encrypt выполните:${NC}"
        echo "  apt install certbot python3-certbot-nginx"
        echo "  certbot --nginx -d ${DOMAIN}"
        echo ""
    fi

    # Сохраняем credentials
    cat > $INSTALL_DIR/credentials.txt << EOF
ProxyGate Installation Credentials
===================================
Generated: $(date)

Admin Panel: https://${DOMAIN}/admin
Username: admin
Password: ${ADMIN_PASSWORD}

Database Password: ${DB_PASSWORD}
Secret Key: ${SECRET_KEY}

Server IP: ${SERVER_IP}
Domain: ${DOMAIN}

HTTP Proxy Port: ${HTTP_PROXY_PORT}
SOCKS5 Proxy Port: ${SOCKS_PROXY_PORT}
EOF
    chmod 600 $INSTALL_DIR/credentials.txt

    echo -e "${GREEN}Credentials сохранены в: $INSTALL_DIR/credentials.txt${NC}"
    echo ""
}

#===============================================================================
# Основная функция
#===============================================================================
main() {
    check_root
    interactive_setup

    echo ""
    log_info "Начинаем установку..."
    echo ""

    update_system
    install_base_packages
    install_python
    install_postgresql
    install_nodejs
    install_nginx
    install_strongswan
    install_3proxy
    create_directories
    setup_project_files
    create_env_file
    setup_python_env
    build_frontend
    configure_nginx
    create_systemd_service
    init_database
    configure_firewall
    setup_cron
    start_services
    install_letsencrypt

    print_installation_info
}

# Запуск
main "$@"
