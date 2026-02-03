#!/bin/bash
set -e

#===============================================================================
# ProxyGate Auto-Installer
# Полная автоматическая установка VPN/Proxy системы
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
TELEGRAM_TOKEN=""
TELEGRAM_CHAT_ID=""

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
# Определение IP сервера
#===============================================================================
detect_server_ip() {
    SERVER_IP=$(curl -s ifconfig.me || curl -s icanhazip.com || hostname -I | awk '{print $1}')
    log_info "Определён IP сервера: $SERVER_IP"
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

    # Домен
    echo -e "${YELLOW}Введите домен (или Enter для использования IP):${NC}"
    read -r input_domain
    if [[ -n "$input_domain" ]]; then
        DOMAIN="$input_domain"
    else
        DOMAIN="$SERVER_IP"
    fi

    # Telegram (опционально)
    echo -e "${YELLOW}Telegram Bot Token (Enter для пропуска):${NC}"
    read -r TELEGRAM_TOKEN

    if [[ -n "$TELEGRAM_TOKEN" ]]; then
        echo -e "${YELLOW}Telegram Chat ID:${NC}"
        read -r TELEGRAM_CHAT_ID
    fi

    echo ""
    log_info "=== Конфигурация ==="
    echo "  Домен/IP: $DOMAIN"
    echo "  Server IP: $SERVER_IP"
    echo "  Admin пароль: $ADMIN_PASSWORD"
    echo "  Telegram: $([ -n "$TELEGRAM_TOKEN" ] && echo "Да" || echo "Нет")"
    echo ""

    echo -e "${YELLOW}Начать установку? (y/n):${NC}"
    read -r confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        log_warn "Установка отменена"
        exit 0
    fi
}

#===============================================================================
# Обновление системы
#===============================================================================
update_system() {
    log_info "Обновление системы..."

    export DEBIAN_FRONTEND=noninteractive

    apt-get update -y
    apt-get upgrade -y
    apt-get dist-upgrade -y
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

    add-apt-repository -y ppa:deadsnakes/ppa
    apt-get update -y
    apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip

    # Установка как default
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

    log_success "Python 3.12 установлен"
    python3.12 --version
}

#===============================================================================
# Установка PostgreSQL
#===============================================================================
install_postgresql() {
    log_info "Установка PostgreSQL..."

    apt-get install -y postgresql postgresql-contrib

    systemctl start postgresql
    systemctl enable postgresql

    # Создание пользователя и БД
    sudo -u postgres psql -c "DROP DATABASE IF EXISTS proxygate;"
    sudo -u postgres psql -c "DROP USER IF EXISTS proxygate;"
    sudo -u postgres psql -c "CREATE USER proxygate WITH PASSWORD '$DB_PASSWORD';"
    sudo -u postgres psql -c "CREATE DATABASE proxygate OWNER proxygate;"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE proxygate TO proxygate;"

    log_success "PostgreSQL установлен и настроен"
}

#===============================================================================
# Установка Node.js
#===============================================================================
install_nodejs() {
    log_info "Установка Node.js 20..."

    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs

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

    # Создание директорий
    mkdir -p /etc/swanctl/conf.d
    mkdir -p /etc/swanctl/x509
    mkdir -p /etc/swanctl/x509ca
    mkdir -p /etc/swanctl/private

    # Генерация CA сертификата
    log_info "Генерация VPN сертификатов..."

    cd /etc/swanctl

    # CA ключ и сертификат
    pki --gen --type rsa --size 4096 --outform pem > private/ca-key.pem
    pki --self --ca --lifetime 3650 --in private/ca-key.pem \
        --type rsa --dn "CN=ProxyGate VPN CA" --outform pem > x509ca/ca-cert.pem

    # Серверный ключ и сертификат
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
        # Сборка из исходников если нет в репозитории
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

    # Базовый конфиг
    cat > /etc/3proxy/3proxy.cfg << 'EOFPROXY'
daemon
pidfile /var/run/3proxy.pid
nserver 8.8.8.8
nserver 8.8.4.4
nscache 65536
timeouts 1 5 30 60 180 1800 15 60
log /var/log/3proxy/3proxy.log D
logformat "- +_L%t.%. %N.%p %E %U %C:%c %R:%r %O %I %h %T"
rotate 30

# Users (will be managed by ProxyGate)
include /etc/3proxy/users.cfg

# ACL
include /etc/3proxy/acl.cfg

# Services
auth strong
allow *
proxy -p3128
socks -p1080
EOFPROXY

    touch /etc/3proxy/users.cfg
    touch /etc/3proxy/acl.cfg

    # Systemd сервис для 3proxy
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

    # Определяем где находится скрипт
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_SOURCE="$(dirname "$SCRIPT_DIR")"

    # Создаём директорию установки
    mkdir -p $INSTALL_DIR

    # Копируем файлы
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
ADMIN_EMAIL=admin@${DOMAIN}
ADMIN_PASSWORD=${ADMIN_PASSWORD}

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

    # Также создаём в backend
    cp $INSTALL_DIR/.env $INSTALL_DIR/backend/.env

    log_success ".env файл создан"
}

#===============================================================================
# Настройка Python окружения
#===============================================================================
setup_python_env() {
    log_info "Настройка Python окружения..."

    cd $INSTALL_DIR/backend

    python3.12 -m venv venv
    source venv/bin/activate

    pip install --upgrade pip wheel setuptools
    pip install -r requirements.txt

    deactivate

    log_success "Python окружение настроено"
}

#===============================================================================
# Сборка фронтенда
#===============================================================================
build_frontend() {
    log_info "Сборка фронтенда..."

    cd $INSTALL_DIR/frontend

    # Создаём .env для фронтенда
    cat > .env << EOF
VITE_API_URL=https://${DOMAIN}/api
EOF

    npm install
    npm run build

    # Копируем в nginx
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

    # SSL (will be configured after certbot)
    ssl_certificate /etc/nginx/ssl/selfsigned.crt;
    ssl_certificate_key /etc/nginx/ssl/selfsigned.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    root /var/www/proxygate;
    index index.html;

    # API
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Frontend
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Static files
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

    # Самоподписанный сертификат (временный)
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

    # Применяем миграции
    alembic upgrade head

    # Создаём админа и начальные данные
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

    # SSH
    ufw allow 22/tcp

    # HTTP/HTTPS
    ufw allow 80/tcp
    ufw allow 443/tcp

    # IKEv2 VPN
    ufw allow 500/udp
    ufw allow 4500/udp

    # Proxy (только если нужен внешний доступ)
    # ufw allow 3128/tcp
    # ufw allow 1080/tcp

    ufw --force enable

    log_success "Файрвол настроен"
}

#===============================================================================
# Настройка cron задач
#===============================================================================
setup_cron() {
    log_info "Настройка cron задач..."

    # Создаём скрипт обновления
    cat > $INSTALL_DIR/update.sh << 'EOF'
#!/bin/bash
cd /opt/proxygate
source backend/venv/bin/activate
python backend/scripts/cron_tasks.py
deactivate
EOF
    chmod +x $INSTALL_DIR/update.sh

    # Добавляем в cron
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
    echo -e "${GREEN}║          Установка завершена успешно!                        ║${NC}"
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
    echo ""
    echo -e "${YELLOW}Для SSL сертификата Let's Encrypt выполните:${NC}"
    echo "  apt install certbot python3-certbot-nginx"
    echo "  certbot --nginx -d ${DOMAIN}"
    echo ""

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
EOF
    chmod 600 $INSTALL_DIR/credentials.txt

    echo -e "${YELLOW}Credentials сохранены в: $INSTALL_DIR/credentials.txt${NC}"
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

    print_installation_info
}

# Запуск
main "$@"
