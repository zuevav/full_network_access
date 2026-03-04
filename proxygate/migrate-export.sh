#!/bin/bash
set -e

#===============================================================================
# ProxyGate Migration Export Script v1.0
# Создаёт полный бэкап для переноса на новый сервер
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
DATE=$(date +%Y%m%d)
BACKUP_DIR="/tmp/proxygate-backup"
BACKUP_FILE="/tmp/proxygate-backup-${DATE}.tar.gz"

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
# Подготовка
#===============================================================================
prepare() {
    log_info "Подготовка к экспорту..."
    rm -rf "$BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"/{env,etc/{3proxy,nginx,letsencrypt,swanctl,wireguard,xray,sysctl.d,systemd},profiles,go-src/{tls-proxy-go,proxygate-connect}}
    log_success "Директории созданы"
}

#===============================================================================
# PostgreSQL dump
#===============================================================================
export_database() {
    log_info "Экспорт базы данных PostgreSQL..."
    sudo -u postgres pg_dump proxygate > "$BACKUP_DIR/db.sql"
    local size=$(du -h "$BACKUP_DIR/db.sql" | cut -f1)
    log_success "БД экспортирована ($size)"
}

#===============================================================================
# ENV и настройки
#===============================================================================
export_env() {
    log_info "Экспорт конфигурационных файлов..."

    for f in .env .ssl_settings.json .system_settings.json .update_settings.json; do
        if [[ -f "$INSTALL_DIR/$f" ]]; then
            cp "$INSTALL_DIR/$f" "$BACKUP_DIR/env/"
            log_success "  $f"
        else
            log_warn "  $f — не найден, пропускаю"
        fi
    done
}

#===============================================================================
# 3proxy конфиги
#===============================================================================
export_3proxy() {
    log_info "Экспорт конфигов 3proxy..."

    if [[ -d /etc/3proxy ]]; then
        cp -a /etc/3proxy/* "$BACKUP_DIR/etc/3proxy/" 2>/dev/null || true
        log_success "  /etc/3proxy/ скопирован"
    else
        log_warn "  /etc/3proxy/ не найден"
    fi
}

#===============================================================================
# Nginx конфиги
#===============================================================================
export_nginx() {
    log_info "Экспорт конфигов nginx..."

    if [[ -f /etc/nginx/sites-available/proxygate ]]; then
        cp /etc/nginx/sites-available/proxygate "$BACKUP_DIR/etc/nginx/proxygate-site"
        log_success "  sites-available/proxygate"
    fi

    if [[ -d "$INSTALL_DIR/nginx" ]]; then
        cp -a "$INSTALL_DIR/nginx/"* "$BACKUP_DIR/etc/nginx/" 2>/dev/null || true
        log_success "  $INSTALL_DIR/nginx/"
    fi

    # nginx.conf (main)
    if [[ -f /etc/nginx/nginx.conf ]]; then
        cp /etc/nginx/nginx.conf "$BACKUP_DIR/etc/nginx/nginx.conf.main"
        log_success "  nginx.conf (main)"
    fi
}

#===============================================================================
# SSL сертификаты (Let's Encrypt)
#===============================================================================
export_letsencrypt() {
    log_info "Экспорт SSL сертификатов..."

    if [[ -d /etc/letsencrypt ]]; then
        cp -a /etc/letsencrypt/* "$BACKUP_DIR/etc/letsencrypt/" 2>/dev/null || true
        log_success "  /etc/letsencrypt/ скопирован"
    else
        log_warn "  /etc/letsencrypt/ не найден"
    fi
}

#===============================================================================
# VPN сертификаты (swanctl)
#===============================================================================
export_swanctl() {
    log_info "Экспорт VPN сертификатов (swanctl)..."

    if [[ -d /etc/swanctl ]]; then
        cp -a /etc/swanctl/* "$BACKUP_DIR/etc/swanctl/" 2>/dev/null || true
        log_success "  /etc/swanctl/ скопирован"
    else
        log_warn "  /etc/swanctl/ не найден"
    fi
}

#===============================================================================
# WireGuard
#===============================================================================
export_wireguard() {
    log_info "Экспорт WireGuard конфигов..."

    if [[ -d /etc/wireguard ]] && [[ -n "$(ls -A /etc/wireguard 2>/dev/null)" ]]; then
        cp -a /etc/wireguard/* "$BACKUP_DIR/etc/wireguard/" 2>/dev/null || true
        log_success "  /etc/wireguard/ скопирован"
    else
        log_warn "  /etc/wireguard/ пуст или не найден"
    fi
}

#===============================================================================
# XRay
#===============================================================================
export_xray() {
    log_info "Экспорт XRay конфигов..."

    if [[ -f /usr/local/etc/xray/config.json ]]; then
        cp /usr/local/etc/xray/config.json "$BACKUP_DIR/etc/xray/"
        log_success "  /usr/local/etc/xray/config.json"
    else
        log_warn "  XRay config не найден"
    fi
}

#===============================================================================
# Systemd сервисы
#===============================================================================
export_systemd() {
    log_info "Экспорт systemd сервисов..."

    for svc in proxygate tls-proxy 3proxy xray; do
        if [[ -f "/etc/systemd/system/${svc}.service" ]]; then
            cp "/etc/systemd/system/${svc}.service" "$BACKUP_DIR/etc/systemd/"
            log_success "  ${svc}.service"
        fi

        # Overrides
        local override_dir="/etc/systemd/system/${svc}.service.d"
        if [[ -d "$override_dir" ]]; then
            mkdir -p "$BACKUP_DIR/etc/systemd/${svc}.service.d"
            cp -a "$override_dir/"* "$BACKUP_DIR/etc/systemd/${svc}.service.d/" 2>/dev/null || true
            log_success "  ${svc}.service.d/ (overrides)"
        fi
    done
}

#===============================================================================
# Sysctl
#===============================================================================
export_sysctl() {
    log_info "Экспорт sysctl конфигов..."

    if [[ -f /etc/sysctl.d/99-proxygate.conf ]]; then
        cp /etc/sysctl.d/99-proxygate.conf "$BACKUP_DIR/etc/sysctl.d/"
        log_success "  99-proxygate.conf"
    fi
}

#===============================================================================
# Crontab
#===============================================================================
export_crontab() {
    log_info "Экспорт crontab..."

    crontab -l > "$BACKUP_DIR/crontab.txt" 2>/dev/null || {
        echo "# No crontab" > "$BACKUP_DIR/crontab.txt"
        log_warn "  Crontab пуст"
    }
    log_success "  crontab.txt"
}

#===============================================================================
# Profiles
#===============================================================================
export_profiles() {
    log_info "Экспорт профилей..."

    if [[ -d /var/lib/proxygate/profiles ]] && [[ -n "$(ls -A /var/lib/proxygate/profiles 2>/dev/null)" ]]; then
        cp -a /var/lib/proxygate/profiles/* "$BACKUP_DIR/profiles/" 2>/dev/null || true
        log_success "  /var/lib/proxygate/profiles/"
    else
        log_warn "  Профили не найдены или пусты"
    fi
}

#===============================================================================
# Go исходники
#===============================================================================
export_go_sources() {
    log_info "Экспорт Go исходников..."

    if [[ -d "$INSTALL_DIR/backend/scripts/tls-proxy-go" ]]; then
        cp -a "$INSTALL_DIR/backend/scripts/tls-proxy-go/"* "$BACKUP_DIR/go-src/tls-proxy-go/" 2>/dev/null || true
        log_success "  tls-proxy-go/"
    fi

    if [[ -d "$INSTALL_DIR/backend/scripts/proxygate-connect" ]]; then
        cp -a "$INSTALL_DIR/backend/scripts/proxygate-connect/"* "$BACKUP_DIR/go-src/proxygate-connect/" 2>/dev/null || true
        log_success "  proxygate-connect/"
    fi
}

#===============================================================================
# VERSION
#===============================================================================
export_version() {
    log_info "Экспорт VERSION..."

    if [[ -f "$INSTALL_DIR/VERSION" ]]; then
        cp "$INSTALL_DIR/VERSION" "$BACKUP_DIR/"
        log_success "  VERSION: $(cat $INSTALL_DIR/VERSION)"
    elif [[ -f "$INSTALL_DIR/proxygate/VERSION" ]]; then
        cp "$INSTALL_DIR/proxygate/VERSION" "$BACKUP_DIR/VERSION"
        log_success "  VERSION: $(cat $INSTALL_DIR/proxygate/VERSION)"
    fi
}

#===============================================================================
# Manifest (метаданные бэкапа)
#===============================================================================
create_manifest() {
    log_info "Создание manifest.json..."

    local version=$(cat "$INSTALL_DIR/VERSION" 2>/dev/null || cat "$INSTALL_DIR/proxygate/VERSION" 2>/dev/null || echo "unknown")
    local server_ip=$(curl -4 -s --connect-timeout 5 ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
    local domain=$(grep -oP 'VPN_DOMAIN=\K.*' "$INSTALL_DIR/.env" 2>/dev/null || echo "unknown")

    cat > "$BACKUP_DIR/manifest.json" << EOF
{
    "version": "$version",
    "date": "$(date -Iseconds)",
    "old_ip": "$server_ip",
    "domain": "$domain",
    "hostname": "$(hostname)",
    "ubuntu_version": "$(lsb_release -ds 2>/dev/null || cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"')",
    "backup_file": "proxygate-backup-${DATE}.tar.gz"
}
EOF
    log_success "  manifest.json создан"
    echo ""
    log_info "Manifest:"
    cat "$BACKUP_DIR/manifest.json"
    echo ""
}

#===============================================================================
# Создание архива
#===============================================================================
create_archive() {
    log_info "Создание архива..."

    cd /tmp
    tar czf "$BACKUP_FILE" -C /tmp proxygate-backup/

    local size=$(du -h "$BACKUP_FILE" | cut -f1)
    log_success "Архив создан: $BACKUP_FILE ($size)"
}

#===============================================================================
# Очистка
#===============================================================================
cleanup() {
    rm -rf "$BACKUP_DIR"
    log_success "Временные файлы очищены"
}

#===============================================================================
# Main
#===============================================================================
main() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║       ProxyGate Migration Export v1.0                        ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    check_root

    prepare
    export_database
    export_env
    export_3proxy
    export_nginx
    export_letsencrypt
    export_swanctl
    export_wireguard
    export_xray
    export_systemd
    export_sysctl
    export_crontab
    export_profiles
    export_go_sources
    export_version
    create_manifest
    create_archive
    cleanup

    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  Экспорт завершён!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  Архив: ${BLUE}$BACKUP_FILE${NC}"
    echo ""
    echo -e "  Следующий шаг:"
    echo -e "  ${YELLOW}scp $BACKUP_FILE newserver:/tmp/${NC}"
    echo -e "  На новом сервере:"
    echo -e "  ${YELLOW}git clone <repo> /opt/proxygate${NC}"
    echo -e "  ${YELLOW}sudo bash /opt/proxygate/install.sh --restore /tmp/proxygate-backup-${DATE}.tar.gz${NC}"
    echo ""
}

main "$@"
