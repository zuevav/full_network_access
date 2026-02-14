import hmac
import hashlib
import time
from html import escape

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession
from app.config import settings
from app.models import Client, IpWhitelistLog, XrayConfig, XrayServerConfig, WireguardConfig, WireguardServerConfig
from app.services.profile_generator import ProfileGenerator
from app.services.proxy_manager import rebuild_proxy_config
from app.services.xray_manager import XRayManager, XrayServerSettings
from app.services.wireguard_manager import WireGuardManager, WgServerSettings
from app.api.system import get_configured_domain, get_configured_ports, get_configured_web_port
from app.utils.security import is_access_token_expired


def _generate_csrf_token(access_token: str) -> str:
    """Generate HMAC-based CSRF token: timestamp:hmac_hex."""
    ts = str(int(time.time()))
    sig = hmac.new(
        settings.secret_key.encode(),
        f"{access_token}:{ts}".encode(),
        hashlib.sha256
    ).hexdigest()
    return f"{ts}:{sig}"


def _validate_csrf_token(access_token: str, token: str, max_age: int = 300) -> bool:
    """Validate CSRF token: check timestamp window and HMAC signature."""
    if not token or ":" not in token:
        return False
    parts = token.split(":", 1)
    if len(parts) != 2:
        return False
    ts_str, sig = parts
    try:
        ts = int(ts_str)
    except ValueError:
        return False
    if abs(time.time() - ts) > max_age:
        return False
    expected = hmac.new(
        settings.secret_key.encode(),
        f"{access_token}:{ts_str}".encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(sig, expected)


router = APIRouter()
profile_generator = ProfileGenerator()
xray_manager = XRayManager()
wg_manager = WireGuardManager()


def get_client_ip(request: Request) -> str:
    """Get client IP from X-Real-IP, X-Forwarded-For, or request.client.host."""
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _build_connect_html(client, access_token, status_emoji, valid_until_str,
                        proxy_host, http_port, client_ip, csrf_token,
                        ip_already_whitelisted,
                        vless_url=None, xray_available=False,
                        wg_available=False, wg_server_ip=None,
                        wg_server_port=None, wg_client_ip=None):
    """Build the full HTML page for client connect."""

    name = escape(client.name or "")
    initial = escape((client.name or "?")[0].upper())

    # IP whitelist button or status
    if ip_already_whitelisted:
        ip_status_html = (
            '<div class="ip-ok">'
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2">'
            '<path d="M22 11.08V12a10 10 0 11-5.93-9.14"/>'
            '<polyline points="22 4 12 14.01 9 11.01"/></svg>'
            ' Ваш IP добавлен</div>'
        )
    else:
        ip_status_html = (
            '<button onclick="addMyIp()" id="add-ip-btn" class="ip-btn">'
            'Добавить мой IP (работа без пароля)</button>'
        )

    # Badge class
    badge_cls = "badge-green" if status_emoji == "\U0001f7e2" else "badge-red"
    badge_text = "Активен" if status_emoji == "\U0001f7e2" else "Не оплачено"

    # VPN card
    vpn_html = ""
    if client.vpn_config:
        vpn_html = f"""
        <div class="card">
            <div class="card-header" style="background: linear-gradient(135deg, #059669 0%, #047857 100%);">
                <div class="card-icon">\U0001f6e1</div>
                <div>
                    <div class="card-title" style="color: white;">VPN (IKEv2)</div>
                    <div class="card-desc" style="color: rgba(255,255,255,0.8);">Защита всего трафика</div>
                </div>
            </div>
            <div class="card-body">
                <div class="dl-grid">
                    <button onclick="showModal('ios')" class="dl-btn">
                        <span class="icon">\U0001f4f1</span>
                        <span class="name">iPhone</span>
                        <span class="hint">Выбор режима</span>
                    </button>
                    <a href="/api/download/{access_token}/android" class="dl-btn">
                        <span class="icon">\U0001f916</span>
                        <span class="name">Android</span>
                        <span class="hint">.sswan профиль</span>
                    </a>
                    <a href="/api/download/{access_token}/windows" class="dl-btn">
                        <span class="icon">\U0001fa9f</span>
                        <span class="name">Windows</span>
                        <span class="hint">PowerShell скрипт</span>
                    </a>
                    <button onclick="showModal('macos')" class="dl-btn">
                        <span class="icon">\U0001f34f</span>
                        <span class="name">macOS</span>
                        <span class="hint">Выбор режима</span>
                    </button>
                </div>
            </div>
            <div class="acc-item">
                <button class="acc-head" onclick="toggleAcc(this)">
                    <span>\U0001f4f1</span> iPhone / iPad <span class="arr">\u25bc</span>
                </button>
                <div class="acc-body">
                    <ol>
                        <li>Нажмите \u00abiPhone\u00bb выше \u2014 откроется выбор режима VPN</li>
                        <li>Выберите режим (рекомендуем \u00abАвто\u00bb)</li>
                        <li>В появившемся окне нажмите \u00abРазрешить\u00bb</li>
                        <li>Откройте <strong>Настройки \u2192 Основные \u2192 VPN и управление устройством</strong></li>
                        <li>Нажмите на загруженный профиль \u2192 \u00abУстановить\u00bb</li>
                        <li>VPN появится в <strong>Настройки \u2192 VPN</strong> \u2014 включите его!</li>
                    </ol>
                </div>
            </div>
            <div class="acc-item">
                <button class="acc-head" onclick="toggleAcc(this)">
                    <span>\U0001f916</span> Android <span class="arr">\u25bc</span>
                </button>
                <div class="acc-body">
                    <ol>
                        <li>Установите <strong>strongSwan VPN Client</strong> из Google Play</li>
                        <li>Нажмите \u00abAndroid\u00bb выше \u2014 скачается .sswan файл</li>
                        <li>Откройте скачанный файл</li>
                        <li>Нажмите \u00abИмпортировать\u00bb и подтвердите</li>
                        <li>Подключитесь в приложении strongSwan</li>
                    </ol>
                    <a href="https://play.google.com/store/apps/details?id=org.strongswan.android"
                       target="_blank" rel="noopener noreferrer" class="ext-link">\u2197 strongSwan в Google Play</a>
                </div>
            </div>
            <div class="acc-item">
                <button class="acc-head" onclick="toggleAcc(this)">
                    <span>\U0001fa9f</span> Windows <span class="arr">\u25bc</span>
                </button>
                <div class="acc-body">
                    <ol>
                        <li>Нажмите \u00abWindows\u00bb выше \u2014 скачается скрипт .ps1</li>
                        <li>Правой кнопкой \u2192 \u00abВыполнить с помощью PowerShell\u00bb (от имени админа)</li>
                        <li>Скрипт автоматически настроит VPN-подключение</li>
                    </ol>
                </div>
            </div>
            <div class="acc-item">
                <button class="acc-head" onclick="toggleAcc(this)">
                    <span>\U0001f34f</span> macOS <span class="arr">\u25bc</span>
                </button>
                <div class="acc-body">
                    <ol>
                        <li>Нажмите \u00abmacOS\u00bb выше \u2014 откроется выбор режима</li>
                        <li>Выберите режим (рекомендуем \u00abАвто\u00bb)</li>
                        <li>Откройте скачанный файл .mobileconfig</li>
                        <li><strong>Системные настройки \u2192 Профили</strong> \u2192 Установить</li>
                        <li>VPN появится в <strong>Системные настройки \u2192 VPN</strong></li>
                    </ol>
                </div>
            </div>
        </div>
        """

    # Proxy card
    proxy_html = ""
    if client.proxy_account:
        proxy_password = escape(client.proxy_account.password_plain or "")
        proxy_username = escape(client.proxy_account.username or "")
        proxy_html = f"""
        <div class="card proxy-card">
            <div class="card-header" style="background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);">
                <div class="card-icon">\U0001f310</div>
                <div>
                    <div class="card-title" style="color: white;">Прокси</div>
                    <div class="card-desc" style="color: rgba(255,255,255,0.8);">Для браузера и приложений</div>
                </div>
            </div>
            <div class="card-body">
                <div class="cred-row">
                    <span class="cred-label">HTTP</span>
                    <div class="cred-value-wrap">
                        <code class="cred-value" id="proxy-http">{escape(proxy_host)}:{http_port}</code>
                        <button class="copy-btn" onclick="copyText('proxy-http')" title="Копировать">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                        </button>
                    </div>
                </div>
                <div class="cred-row">
                    <span class="cred-label">Логин</span>
                    <div class="cred-value-wrap">
                        <code class="cred-value" id="proxy-user">{proxy_username}</code>
                        <button class="copy-btn" onclick="copyText('proxy-user')" title="Копировать">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                        </button>
                    </div>
                </div>
                <div class="cred-row">
                    <span class="cred-label">Пароль</span>
                    <div class="cred-value-wrap">
                        <code class="cred-value" id="proxy-pass">\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022</code>
                        <button class="copy-btn" onclick="revealAndCopy()" title="Показать и скопировать" id="reveal-btn">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                        </button>
                    </div>
                </div>
                <div style="display:flex;gap:8px;margin-top:16px;flex-wrap:wrap;">
                    <a href="/api/download/{access_token}/pac" class="action-btn" style="background:#fff7ed;color:#c2410c;border:1px solid #fed7aa;">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        PAC-файл
                    </a>
                    <a href="/api/download/{access_token}/proxy-setup" class="action-btn" style="background:#fff7ed;color:#c2410c;border:1px solid #fed7aa;">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                        Скрипт Windows
                    </a>
                </div>
            </div>
        </div>

        <div class="card" style="border:1px solid #e5e7eb;">
            <div class="card-body" style="padding:16px;">
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
                    <div style="width:36px;height:36px;background:#eff6ff;border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                    </div>
                    <div>
                        <div style="font-weight:600;font-size:14px;color:#111;">Доступ по IP</div>
                        <div style="font-size:13px;color:#6b7280;">Ваш IP: <code style="background:#f3f4f6;padding:1px 6px;border-radius:4px;font-size:12px;">{escape(client_ip)}</code></div>
                    </div>
                </div>
                <div id="ip-whitelist-status">{ip_status_html}</div>
                <div id="ip-whitelist-result"></div>
            </div>
        </div>
        """

    # XRay card
    xray_html = ""
    if xray_available and vless_url:
        escaped_vless = escape(vless_url)
        xray_html = f"""
        <div class="card">
            <div class="card-header" style="background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);">
                <div class="card-icon">\u26a1</div>
                <div>
                    <div class="card-title" style="color: white;">XRay (VLESS + REALITY)</div>
                    <div class="card-desc" style="color: rgba(255,255,255,0.8);">Современный протокол с маскировкой</div>
                </div>
            </div>
            <div class="card-body">
                <div style="background:#f5f3ff;border:1px solid #e9d5ff;border-radius:10px;padding:12px;margin-bottom:12px;">
                    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
                        <span style="font-size:12px;font-weight:600;color:#7c3aed;">VLESS URL</span>
                        <button class="copy-btn" onclick="copyText('vless-url')" title="Копировать">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                        </button>
                    </div>
                    <code id="vless-url" style="display:block;font-size:11px;word-break:break-all;color:#581c87;background:white;padding:8px;border-radius:6px;border:1px solid #e9d5ff;max-height:60px;overflow-y:auto;">{escaped_vless}</code>
                </div>
                <button onclick="toggleQr('xray')" class="action-btn" style="background:#f5f3ff;color:#7c3aed;border:1px solid #e9d5ff;width:100%;justify-content:center;">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
                    <span id="xray-qr-label">Показать QR-код</span>
                </button>
                <div id="xray-qr-box" style="display:none;margin-top:12px;text-align:center;">
                    <div id="xray-qr-content" style="color:#7c3aed;font-size:13px;">Загрузка...</div>
                </div>

                <div style="margin-top:16px;">
                    <div style="font-size:13px;font-weight:600;color:#374151;margin-bottom:8px;">Windows (v2rayN) \u2014 быстрый старт</div>
                    <a href="/downloads/v2rayN.zip" class="action-btn" style="background:#7c3aed;color:white;border:none;width:100%;justify-content:center;padding:12px;font-size:14px;margin-bottom:8px;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        \U0001fa9f \u0421\u043a\u0430\u0447\u0430\u0442\u044c v2rayN (Windows, portable)
                    </a>
                    <div style="background:#faf5ff;border:1px solid #e9d5ff;border-radius:8px;padding:12px;font-size:12px;color:#581c87;line-height:1.8;">
                        <strong>\u0418\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f:</strong><br>
                        1. \u0421\u043a\u0430\u0447\u0430\u0439\u0442\u0435 \u0438 \u0440\u0430\u0441\u043f\u0430\u043a\u0443\u0439\u0442\u0435 \u0430\u0440\u0445\u0438\u0432 \u0432 \u043b\u044e\u0431\u0443\u044e \u043f\u0430\u043f\u043a\u0443<br>
                        2. \u0417\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u0435 <strong>v2rayN.exe</strong> (\u043f\u0440\u0430\u0432\u0430 \u0430\u0434\u043c\u0438\u043d\u0430 \u043d\u0435 \u043d\u0443\u0436\u043d\u044b)<br>
                        3. \u041d\u0430\u0436\u043c\u0438\u0442\u0435 \u043a\u043d\u043e\u043f\u043a\u0443 \u00ab\u041a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c\u00bb \u0440\u044f\u0434\u043e\u043c \u0441 VLESS URL \u0432\u044b\u0448\u0435<br>
                        4. \u0412 v2rayN: <strong>Servers \u2192 Import from clipboard</strong><br>
                        5. \u041d\u0430\u0436\u043c\u0438\u0442\u0435 \u25b6 \u0434\u043b\u044f \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f
                    </div>
                </div>
                <div style="margin-top:12px;">
                    <div style="font-size:13px;font-weight:600;color:#374151;margin-bottom:8px;">\u0414\u0440\u0443\u0433\u0438\u0435 \u043f\u043b\u0430\u0442\u0444\u043e\u0440\u043c\u044b</div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                        <a href="https://apps.apple.com/app/shadowrocket/id932747118" target="_blank" rel="noopener" class="action-btn" style="background:#f5f3ff;color:#7c3aed;border:1px solid #e9d5ff;justify-content:center;">\U0001f4f1 Shadowrocket</a>
                        <a href="https://play.google.com/store/apps/details?id=com.v2ray.ang" target="_blank" rel="noopener" class="action-btn" style="background:#f5f3ff;color:#7c3aed;border:1px solid #e9d5ff;justify-content:center;">\U0001f916 v2rayNG</a>
                        <a href="https://github.com/tzmax/V2RayXS/releases" target="_blank" rel="noopener" class="action-btn" style="background:#f5f3ff;color:#7c3aed;border:1px solid #e9d5ff;justify-content:center;">\U0001f34f V2RayXS</a>
                    </div>
                </div>
            </div>
        </div>
        """

    # WireGuard card
    wg_html = ""
    if wg_available:
        wg_html = f"""
        <div class="card">
            <div class="card-header" style="background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);">
                <div class="card-icon">\U0001f4e1</div>
                <div>
                    <div class="card-title" style="color: white;">WireGuard</div>
                    <div class="card-desc" style="color: rgba(255,255,255,0.8);">Быстрый VPN-протокол</div>
                </div>
            </div>
            <div class="card-body">
                <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;">
                    <button onclick="downloadWgConf()" class="action-btn" style="background:#2563eb;color:white;border:none;flex:1;justify-content:center;">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        Скачать .conf
                    </button>
                    <button onclick="toggleQr('wg')" class="action-btn" style="background:#eff6ff;color:#2563eb;border:1px solid #bfdbfe;flex:1;justify-content:center;">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
                        <span id="wg-qr-label">QR-код</span>
                    </button>
                </div>
                <div id="wg-qr-box" style="display:none;margin-bottom:16px;text-align:center;">
                    <div id="wg-qr-content" style="color:#2563eb;font-size:13px;">Загрузка...</div>
                </div>
                <div class="cred-row">
                    <span class="cred-label">Сервер</span>
                    <div class="cred-value-wrap">
                        <code class="cred-value" id="wg-server">{escape(wg_server_ip or '')}:{wg_server_port or ''}</code>
                        <button class="copy-btn" onclick="copyText('wg-server')" title="Копировать">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                        </button>
                    </div>
                </div>
                <div class="cred-row">
                    <span class="cred-label">Ваш IP</span>
                    <code class="cred-value">{escape(wg_client_ip or '')}</code>
                </div>

                <div style="margin-top:16px;">
                    <div style="font-size:13px;font-weight:600;color:#374151;margin-bottom:8px;">Приложение WireGuard</div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                        <a href="https://apps.apple.com/app/wireguard/id1441195209" target="_blank" rel="noopener" class="action-btn" style="background:#eff6ff;color:#2563eb;border:1px solid #bfdbfe;justify-content:center;">\U0001f4f1 iPhone</a>
                        <a href="https://play.google.com/store/apps/details?id=com.wireguard.android" target="_blank" rel="noopener" class="action-btn" style="background:#eff6ff;color:#2563eb;border:1px solid #bfdbfe;justify-content:center;">\U0001f916 Android</a>
                        <a href="https://www.wireguard.com/install/" target="_blank" rel="noopener" class="action-btn" style="background:#eff6ff;color:#2563eb;border:1px solid #bfdbfe;justify-content:center;">\U0001fa9f Windows</a>
                        <a href="https://apps.apple.com/app/wireguard/id1451685025" target="_blank" rel="noopener" class="action-btn" style="background:#eff6ff;color:#2563eb;border:1px solid #bfdbfe;justify-content:center;">\U0001f34f macOS</a>
                    </div>
                    <p style="font-size:11px;color:#9ca3af;margin-top:8px;text-align:center;">Скачайте .conf файл или отсканируйте QR-код в приложении</p>
                </div>
            </div>
        </div>
        """

    # JavaScript — password stored separately to avoid HTML injection
    js_password = proxy_password if client.proxy_account else ""

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZETIT FNA \u2014 {name}</title>
    <style>
        *{{margin:0;padding:0;box-sizing:border-box}}
        body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f0f2f5;min-height:100vh;color:#111}}
        .top-bar{{background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);padding:24px 20px 48px;text-align:center;color:white}}
        .top-bar h1{{font-size:22px;font-weight:700;letter-spacing:-0.3px}}
        .top-bar .sub{{font-size:13px;opacity:0.8;margin-top:4px}}
        .page{{max-width:480px;margin:-32px auto 0;padding:0 16px 32px;position:relative}}
        .card{{background:white;border-radius:16px;box-shadow:0 1px 3px rgba(0,0,0,0.06),0 1px 2px rgba(0,0,0,0.04);margin-bottom:16px;overflow:hidden}}
        .card-header{{padding:16px 20px;display:flex;align-items:center;gap:14px}}
        .card-icon{{font-size:28px;width:44px;height:44px;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,0.2);border-radius:12px;flex-shrink:0}}
        .card-title{{font-size:16px;font-weight:700}}
        .card-desc{{font-size:13px;margin-top:2px}}
        .card-body{{padding:20px}}
        .status-card{{display:flex;align-items:center;gap:14px;padding:16px 20px}}
        .status-avatar{{width:48px;height:48px;background:linear-gradient(135deg,#4f46e5,#7c3aed);border-radius:14px;display:flex;align-items:center;justify-content:center;color:white;font-size:20px;font-weight:700;flex-shrink:0}}
        .status-name{{font-size:17px;font-weight:700;color:#111}}
        .status-sub{{font-size:13px;color:#6b7280;margin-top:2px}}
        .badge{{display:inline-flex;align-items:center;gap:4px;font-size:12px;font-weight:600;padding:3px 10px;border-radius:20px}}
        .badge-green{{background:#dcfce7;color:#15803d}}
        .badge-red{{background:#fee2e2;color:#dc2626}}
        .portal-link{{display:flex;align-items:center;justify-content:center;gap:8px;padding:12px;border-top:1px solid #f3f4f6;color:#4f46e5;font-weight:600;font-size:14px;text-decoration:none;transition:background 0.15s}}
        .portal-link:hover{{background:#f5f3ff}}
        .dl-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
        .dl-btn{{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:18px 12px;background:#f9fafb;border-radius:14px;border:2px solid transparent;cursor:pointer;font-family:inherit;text-decoration:none;color:#111;transition:all 0.15s}}
        .dl-btn:hover{{border-color:#4f46e5;background:#f5f3ff}}
        .dl-btn .icon{{font-size:28px;margin-bottom:6px}}
        .dl-btn .name{{font-size:14px;font-weight:600}}
        .dl-btn .hint{{font-size:11px;color:#9ca3af;margin-top:2px}}
        .cred-row{{display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid #f3f4f6}}
        .cred-row:last-of-type{{border-bottom:none}}
        .cred-label{{font-size:13px;color:#6b7280;font-weight:500}}
        .cred-value-wrap{{display:flex;align-items:center;gap:8px}}
        .cred-value{{font-family:'SF Mono',SFMono-Regular,Consolas,monospace;font-size:13px;color:#111;background:#f3f4f6;padding:4px 10px;border-radius:6px}}
        .copy-btn{{background:none;border:none;cursor:pointer;color:#9ca3af;padding:4px;border-radius:6px;transition:all 0.15s;display:flex;align-items:center}}
        .copy-btn:hover{{color:#4f46e5;background:#f5f3ff}}
        .copy-btn.copied{{color:#16a34a}}
        .action-btn{{display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:10px;font-size:13px;font-weight:600;text-decoration:none;transition:opacity 0.15s}}
        .action-btn:hover{{opacity:0.85}}
        .acc-item{{border-bottom:1px solid #f3f4f6}}
        .acc-item:last-child{{border-bottom:none}}
        .acc-head{{display:flex;align-items:center;gap:10px;width:100%;padding:14px 20px;background:none;border:none;cursor:pointer;font-family:inherit;font-size:14px;font-weight:600;color:#111;text-align:left}}
        .acc-head:hover{{background:#f9fafb}}
        .acc-head .arr{{margin-left:auto;font-size:12px;color:#9ca3af;transition:transform 0.2s}}
        .acc-head.open .arr{{transform:rotate(180deg)}}
        .acc-body{{display:none;padding:0 20px 16px 48px}}
        .acc-body.open{{display:block}}
        .acc-body ol{{padding-left:16px;margin:0}}
        .acc-body li{{margin-bottom:8px;font-size:13px;color:#374151;line-height:1.6}}
        .ext-link{{display:inline-flex;align-items:center;gap:4px;margin-top:6px;color:#4f46e5;text-decoration:none;font-weight:600;font-size:13px}}
        .ext-link:hover{{text-decoration:underline}}
        .overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.4);backdrop-filter:blur(4px);z-index:1000;justify-content:center;align-items:flex-end;padding:0}}
        @media(min-width:480px){{.overlay{{align-items:center;padding:20px}}.modal{{border-radius:20px!important;max-height:85vh}}}}
        .overlay.open{{display:flex}}
        .modal{{background:white;border-radius:20px 20px 0 0;width:100%;max-width:420px;overflow:auto;animation:slideUp 0.25s ease-out}}
        @keyframes slideUp{{from{{transform:translateY(40px);opacity:0}}to{{transform:translateY(0);opacity:1}}}}
        .modal-head{{padding:20px;border-bottom:1px solid #f3f4f6;display:flex;justify-content:space-between;align-items:center}}
        .modal-head h2{{font-size:18px;font-weight:700}}
        .modal-head p{{font-size:13px;color:#6b7280;margin-top:2px}}
        .modal-x{{width:32px;height:32px;border-radius:10px;background:#f3f4f6;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;color:#6b7280;font-size:18px}}
        .modal-x:hover{{background:#e5e7eb}}
        .modal-opts{{padding:16px}}
        .opt{{display:block;padding:16px;border:2px solid #e5e7eb;border-radius:14px;margin-bottom:10px;text-decoration:none;color:#111;position:relative;transition:all 0.15s}}
        .opt:hover{{border-color:#4f46e5;background:#f5f3ff}}
        .opt-icon{{font-size:22px;margin-bottom:6px}}
        .opt-title{{font-weight:700;font-size:15px;margin-bottom:2px}}
        .opt-desc{{font-size:13px;color:#6b7280}}
        .opt-badge{{position:absolute;top:-8px;right:14px;background:linear-gradient(135deg,#fbbf24,#f59e0b);color:#78350f;font-size:11px;font-weight:700;padding:2px 10px;border-radius:10px}}
        .modal-tip{{padding:14px 20px;background:#fffbeb;border-top:1px solid #fef3c7;font-size:12px;color:#92400e;line-height:1.6}}
        .ip-btn{{padding:10px 20px;background:linear-gradient(135deg,#4f46e5,#7c3aed);color:white;border:none;border-radius:10px;font-weight:600;cursor:pointer;font-size:13px;font-family:inherit;transition:opacity 0.15s;width:100%}}
        .ip-btn:hover{{opacity:0.9}}
        .ip-btn:disabled{{opacity:0.6;cursor:not-allowed}}
        .ip-ok{{display:flex;align-items:center;gap:8px;color:#16a34a;font-weight:600;font-size:14px;padding:8px 0}}
    </style>
</head>
<body>
    <div class="top-bar">
        <h1>ZETIT FNA</h1>
        <div class="sub">Full Network Access</div>
    </div>

    <div class="page">
        <div class="card">
            <div class="status-card">
                <div class="status-avatar">{initial}</div>
                <div style="flex:1;min-width:0;">
                    <div class="status-name">{name}</div>
                    <div class="status-sub">
                        <span class="badge {badge_cls}">
                            {status_emoji} {badge_text} до {valid_until_str}
                        </span>
                    </div>
                </div>
            </div>
            <a href="/my/link/{access_token}" class="portal-link">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg>
                Личный кабинет
            </a>
        </div>

        {proxy_html}

        {vpn_html}

        {xray_html}

        {wg_html}

        <div style="text-align:center;padding:16px 0;color:#9ca3af;font-size:13px;">
            Вопросы? Обратитесь к администратору
        </div>
    </div>

    <div id="vpnModal" class="overlay" onclick="hideModal(event)">
        <div class="modal" onclick="event.stopPropagation()">
            <div class="modal-head">
                <div>
                    <h2>Режим VPN</h2>
                    <p>Как должен работать VPN?</p>
                </div>
                <button class="modal-x" onclick="hideModal()">\u2715</button>
            </div>
            <div class="modal-opts">
                <a id="opt-ondemand" class="opt">
                    <span class="opt-badge">Рекомендуем</span>
                    <div class="opt-icon">\u26a1</div>
                    <div class="opt-title">Авто (по доменам)</div>
                    <div class="opt-desc">VPN включается только при открытии нужных сайтов</div>
                </a>
                <a id="opt-always" class="opt">
                    <div class="opt-icon">\U0001f6e1\ufe0f</div>
                    <div class="opt-title">Всегда (Split-туннель)</div>
                    <div class="opt-desc">VPN всегда включён, но только рабочий трафик через VPN</div>
                </a>
                <a id="opt-full" class="opt">
                    <div class="opt-icon">\U0001f310</div>
                    <div class="opt-title">Всегда (Весь трафик)</div>
                    <div class="opt-desc">Весь трафик через VPN. Максимальная защита</div>
                </a>
            </div>
            <div class="modal-tip">
                <strong>Инструкция:</strong> нажмите на режим \u2192 разрешите загрузку \u2192 откройте <strong>Настройки \u2192 Профили</strong> \u2192 Установить
            </div>
        </div>
    </div>

    <script>
        var _at='{access_token}';
        var _pw='{js_password}';
        function showModal(p){{var b='/api/download/'+_at+'/'+p;document.getElementById('opt-ondemand').href=b+'?mode=ondemand';document.getElementById('opt-always').href=b+'?mode=always';document.getElementById('opt-full').href=b+'?mode=full';document.getElementById('vpnModal').classList.add('open')}}
        function hideModal(e){{if(!e||e.target===e.currentTarget)document.getElementById('vpnModal').classList.remove('open')}}
        function toggleAcc(b){{var d=b.nextElementSibling,w=b.classList.contains('open');document.querySelectorAll('.acc-head').forEach(function(h){{h.classList.remove('open')}});document.querySelectorAll('.acc-body').forEach(function(x){{x.classList.remove('open')}});if(!w){{b.classList.add('open');d.classList.add('open')}}}}
        function copyText(id){{var el=document.getElementById(id);if(!el)return;navigator.clipboard.writeText(el.textContent).then(function(){{var btn=el.parentElement.querySelector('.copy-btn');if(btn){{btn.classList.add('copied');setTimeout(function(){{btn.classList.remove('copied')}},1500)}}}})}};
        function revealAndCopy(){{var el=document.getElementById('proxy-pass');el.textContent=_pw;copyText('proxy-pass')}}
        var _qrLoaded={{}};
        function toggleQr(type){{
            var box=document.getElementById(type+'-qr-box');
            var label=document.getElementById(type+'-qr-label');
            if(box.style.display==='none'){{
                box.style.display='block';
                label.textContent='Скрыть QR-код';
                if(!_qrLoaded[type]){{
                    _qrLoaded[type]=true;
                    fetch('/api/connect/'+_at+'/'+type+'-qr').then(function(r){{return r.json()}}).then(function(d){{
                        if(d.qrcode){{document.getElementById(type+'-qr-content').innerHTML='<img src="'+d.qrcode+'" style="width:200px;height:200px;border-radius:12px;border:1px solid #e5e7eb;" alt="QR">'}}
                        else{{document.getElementById(type+'-qr-content').textContent='QR-код недоступен'}}
                    }}).catch(function(){{document.getElementById(type+'-qr-content').textContent='Ошибка загрузки'}})
                }}
            }}else{{
                box.style.display='none';
                label.textContent=type==='wg'?'QR-код':'Показать QR-код';
            }}
        }}
        function downloadWgConf(){{
            fetch('/api/connect/'+_at+'/wg-conf').then(function(r){{return r.blob()}}).then(function(b){{
                var u=URL.createObjectURL(b);var a=document.createElement('a');a.href=u;a.download='wireguard.conf';a.click();URL.revokeObjectURL(u);
            }})
        }}
        function addMyIp(){{var btn=document.getElementById('add-ip-btn');var res=document.getElementById('ip-whitelist-result');if(btn)btn.disabled=true;fetch('/api/connect/'+_at+'/whitelist-ip',{{method:'POST',headers:{{'Content-Type':'application/json','X-CSRF-Token':'{csrf_token}'}}}}).then(function(r){{return r.json()}}).then(function(d){{if(d.success){{document.getElementById('ip-whitelist-status').innerHTML='<div class="ip-ok"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg> Ваш IP добавлен</div>';res.innerHTML=''}}else{{res.innerHTML='<p style="color:#dc2626;font-size:13px;margin-top:8px;">'+(d.detail||'Ошибка')+'</p>';if(btn)btn.disabled=false}}}}).catch(function(e){{res.innerHTML='<p style="color:#dc2626;font-size:13px;margin-top:8px;">Ошибка: '+e.message+'</p>';if(btn)btn.disabled=false}})}};
    </script>
</body>
</html>"""


@router.get("/connect/{access_token}", response_class=HTMLResponse)
async def client_connect_page(
    access_token: str,
    request: Request,
    db: DBSession
):
    """Public client connection page (no auth required)."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.proxy_account),
            selectinload(Client.payments),
            selectinload(Client.xray_config),
            selectinload(Client.wireguard_config),
        )
        .where(Client.access_token == access_token)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Not found")
    if is_access_token_expired(client):
        raise HTTPException(status_code=410, detail="Link expired")

    # Get subscription status
    valid_until_str = "Не оплачено"
    status_emoji = "\U0001f534"
    if client.payments:
        latest = max(client.payments, key=lambda p: p.valid_until)
        valid_until_str = latest.valid_until.strftime("%d.%m.%Y")
        from datetime import date
        if latest.valid_until >= date.today():
            status_emoji = "\U0001f7e2"

    # Get proxy settings
    domain = get_configured_domain()
    proxy_host = domain if domain and domain != "localhost" else "127.0.0.1"
    http_port, _ = get_configured_ports()

    # Get client IP for whitelist feature
    client_ip = get_client_ip(request)
    csrf_token = _generate_csrf_token(access_token)
    ip_already_whitelisted = False
    if client.proxy_account and client.proxy_account.allowed_ips:
        whitelisted = [ip.strip() for ip in client.proxy_account.allowed_ips.split(",") if ip.strip()]
        ip_already_whitelisted = client_ip in whitelisted

    # XRay data
    vless_url = None
    xray_available = False
    if client.xray_config and client.xray_config.is_active:
        xray_srv_result = await db.execute(select(XrayServerConfig).limit(1))
        xray_srv = xray_srv_result.scalar_one_or_none()
        if xray_srv and xray_srv.is_enabled:
            xray_available = True
            server_ip = xray_manager.get_server_ip()
            xray_settings = XrayServerSettings(
                port=xray_srv.port, private_key=xray_srv.private_key,
                public_key=xray_srv.public_key, short_id=xray_srv.short_id,
                dest_server=xray_srv.dest_server, dest_port=xray_srv.dest_port,
                server_name=xray_srv.server_name
            )
            vless_url = xray_manager.generate_vless_url(
                server_ip, xray_settings, client.xray_config.uuid,
                client.xray_config.short_id, client.name
            )

    # WireGuard data
    wg_available = False
    wg_server_ip = wg_server_port = wg_client_ip = None
    if client.wireguard_config and client.wireguard_config.is_active:
        wg_srv_result = await db.execute(select(WireguardServerConfig).limit(1))
        wg_srv = wg_srv_result.scalar_one_or_none()
        if wg_srv and wg_srv.is_enabled:
            wg_available = True
            wg_server_ip = wg_manager.get_server_ip()
            wg_server_port = wg_srv.wstunnel_port if wg_srv.wstunnel_enabled else wg_srv.listen_port
            wg_client_ip = client.wireguard_config.assigned_ip

    html = _build_connect_html(
        client, access_token, status_emoji, valid_until_str,
        proxy_host, http_port, client_ip, csrf_token, ip_already_whitelisted,
        vless_url=vless_url, xray_available=xray_available,
        wg_available=wg_available, wg_server_ip=wg_server_ip,
        wg_server_port=wg_server_port, wg_client_ip=wg_client_ip
    )
    return HTMLResponse(content=html)


@router.post("/connect/{access_token}/whitelist-ip")
async def whitelist_ip(
    access_token: str,
    request: Request,
    db: DBSession
):
    """Add client's current IP to proxy whitelist (no auth required)."""
    csrf_token = request.headers.get("X-CSRF-Token", "")
    if not _validate_csrf_token(access_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or expired CSRF token")

    result = await db.execute(
        select(Client)
        .options(selectinload(Client.proxy_account))
        .where(Client.access_token == access_token)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Not found")
    if is_access_token_expired(client):
        raise HTTPException(status_code=410, detail="Link expired")

    if client.proxy_account is None:
        raise HTTPException(status_code=400, detail="Proxy not configured")

    ip = get_client_ip(request)

    # Deduplicate
    existing_ips = []
    if client.proxy_account.allowed_ips:
        existing_ips = [i.strip() for i in client.proxy_account.allowed_ips.split(",") if i.strip()]

    if ip in existing_ips:
        return {"success": True, "ip": ip, "message": "already_added"}

    existing_ips.append(ip)
    client.proxy_account.allowed_ips = ",".join(existing_ips)

    # Log
    log_entry = IpWhitelistLog(
        client_id=client.id,
        ip_address=ip,
        action="added"
    )
    db.add(log_entry)
    await db.flush()

    # Rebuild 3proxy config
    await rebuild_proxy_config(db)

    return {"success": True, "ip": ip}


async def _load_client_by_token(db, access_token: str):
    """Helper: load client by access_token, raise if not found or expired."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.xray_config),
            selectinload(Client.wireguard_config),
        )
        .where(Client.access_token == access_token)
    )
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Not found")
    if is_access_token_expired(client):
        raise HTTPException(status_code=410, detail="Link expired")
    return client


@router.get("/connect/{access_token}/xray-qr")
async def public_xray_qr(access_token: str, db: DBSession):
    """Public XRay QR code endpoint."""
    import base64, io
    try:
        import qrcode
    except ImportError:
        raise HTTPException(status_code=501, detail="QR not available")

    client = await _load_client_by_token(db, access_token)
    if not client.xray_config or not client.xray_config.is_active:
        raise HTTPException(status_code=404, detail="XRay not enabled")

    xray_srv_result = await db.execute(select(XrayServerConfig).limit(1))
    xray_srv = xray_srv_result.scalar_one_or_none()
    if not xray_srv or not xray_srv.is_enabled:
        raise HTTPException(status_code=404, detail="XRay server not configured")

    server_ip = xray_manager.get_server_ip()
    xray_settings = XrayServerSettings(
        port=xray_srv.port, private_key=xray_srv.private_key,
        public_key=xray_srv.public_key, short_id=xray_srv.short_id,
        dest_server=xray_srv.dest_server, dest_port=xray_srv.dest_port,
        server_name=xray_srv.server_name
    )
    vless_url = xray_manager.generate_vless_url(
        server_ip, xray_settings, client.xray_config.uuid,
        client.xray_config.short_id, client.name
    )

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(vless_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return {"qrcode": f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"}


@router.get("/connect/{access_token}/wg-qr")
async def public_wg_qr(access_token: str, db: DBSession):
    """Public WireGuard QR code endpoint."""
    import base64, io
    try:
        import qrcode
    except ImportError:
        raise HTTPException(status_code=501, detail="QR not available")

    client = await _load_client_by_token(db, access_token)
    if not client.wireguard_config or not client.wireguard_config.is_active:
        raise HTTPException(status_code=404, detail="WireGuard not enabled")

    wg_srv_result = await db.execute(select(WireguardServerConfig).limit(1))
    wg_srv = wg_srv_result.scalar_one_or_none()
    if not wg_srv or not wg_srv.is_enabled:
        raise HTTPException(status_code=404, detail="WireGuard not configured")

    server_ip = wg_manager.get_server_ip()
    wg_settings = WgServerSettings(
        private_key=wg_srv.private_key, public_key=wg_srv.public_key,
        interface=wg_srv.interface, listen_port=wg_srv.listen_port,
        server_ip=wg_srv.server_ip, subnet=wg_srv.subnet,
        dns=wg_srv.dns, mtu=wg_srv.mtu,
        wstunnel_enabled=wg_srv.wstunnel_enabled,
        wstunnel_port=wg_srv.wstunnel_port, wstunnel_path=wg_srv.wstunnel_path
    )
    config_text = wg_manager.generate_client_config(
        server_ip, wg_settings, client.wireguard_config.private_key,
        client.wireguard_config.assigned_ip, client.wireguard_config.preshared_key
    )

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(config_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return {"qrcode": f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"}


@router.get("/connect/{access_token}/wg-conf")
async def public_wg_conf_download(access_token: str, db: DBSession):
    """Public WireGuard .conf download."""
    client = await _load_client_by_token(db, access_token)
    if not client.wireguard_config or not client.wireguard_config.is_active:
        raise HTTPException(status_code=404, detail="WireGuard not enabled")

    wg_srv_result = await db.execute(select(WireguardServerConfig).limit(1))
    wg_srv = wg_srv_result.scalar_one_or_none()
    if not wg_srv or not wg_srv.is_enabled:
        raise HTTPException(status_code=404, detail="WireGuard not configured")

    server_ip = wg_manager.get_server_ip()
    wg_settings = WgServerSettings(
        private_key=wg_srv.private_key, public_key=wg_srv.public_key,
        interface=wg_srv.interface, listen_port=wg_srv.listen_port,
        server_ip=wg_srv.server_ip, subnet=wg_srv.subnet,
        dns=wg_srv.dns, mtu=wg_srv.mtu,
        wstunnel_enabled=wg_srv.wstunnel_enabled,
        wstunnel_port=wg_srv.wstunnel_port, wstunnel_path=wg_srv.wstunnel_path
    )
    config_text = wg_manager.generate_client_config(
        server_ip, wg_settings, client.wireguard_config.private_key,
        client.wireguard_config.assigned_ip, client.wireguard_config.preshared_key
    )

    return Response(
        content=config_text,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="wireguard.conf"'}
    )


@router.get("/download/{access_token}/windows")
async def download_windows_public(
    access_token: str,
    db: DBSession
):
    """Download Windows profile by access token."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.domains)
        )
        .where(Client.access_token == access_token)
    )
    client = result.scalar_one_or_none()

    if client is None or client.vpn_config is None:
        raise HTTPException(status_code=404, detail="Not found")
    if is_access_token_expired(client):
        raise HTTPException(status_code=410, detail="Link expired")

    content = profile_generator.generate_windows_ps1(client)

    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna-{client.vpn_config.username}.ps1"'
        }
    )


@router.get("/download/{access_token}/ios")
async def download_ios_public(
    access_token: str,
    db: DBSession,
    mode: str = "ondemand"
):
    """Download iOS profile by access token with VPN mode selection."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.domains)
        )
        .where(Client.access_token == access_token)
    )
    client = result.scalar_one_or_none()

    if client is None or client.vpn_config is None:
        raise HTTPException(status_code=404, detail="Not found")
    if is_access_token_expired(client):
        raise HTTPException(status_code=410, detail="Link expired")

    # Validate mode
    if mode not in ("ondemand", "always", "full"):
        mode = "ondemand"

    content = profile_generator.generate_ios_mobileconfig(client, mode=mode)
    mode_suffix = f"-{mode}" if mode != "ondemand" else ""

    # Explicit Content-Length required for iOS Safari with large files
    return Response(
        content=content,
        media_type="application/x-apple-aspen-config",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna-{client.vpn_config.username}{mode_suffix}.mobileconfig"',
            "Content-Length": str(len(content))
        }
    )


@router.get("/download/{access_token}/macos")
async def download_macos_public(
    access_token: str,
    db: DBSession,
    mode: str = "ondemand"
):
    """Download macOS profile by access token with VPN mode selection."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.domains)
        )
        .where(Client.access_token == access_token)
    )
    client = result.scalar_one_or_none()

    if client is None or client.vpn_config is None:
        raise HTTPException(status_code=404, detail="Not found")
    if is_access_token_expired(client):
        raise HTTPException(status_code=410, detail="Link expired")

    # Validate mode
    if mode not in ("ondemand", "always", "full"):
        mode = "ondemand"

    content = profile_generator.generate_macos_mobileconfig(client, mode=mode)
    mode_suffix = f"-{mode}" if mode != "ondemand" else ""

    return Response(
        content=content,
        media_type="application/x-apple-aspen-config",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna-{client.vpn_config.username}-macos{mode_suffix}.mobileconfig"'
        }
    )


@router.get("/download/{access_token}/android")
async def download_android_public(
    access_token: str,
    db: DBSession
):
    """Download Android profile by access token."""
    result = await db.execute(
        select(Client)
        .options(
            selectinload(Client.vpn_config),
            selectinload(Client.domains)
        )
        .where(Client.access_token == access_token)
    )
    client = result.scalar_one_or_none()

    if client is None or client.vpn_config is None:
        raise HTTPException(status_code=404, detail="Not found")
    if is_access_token_expired(client):
        raise HTTPException(status_code=410, detail="Link expired")

    content = profile_generator.generate_android_sswan(client)

    return Response(
        content=content,
        media_type="application/vnd.strongswan.profile",
        headers={
            "Content-Disposition": f'attachment; filename="zetit-fna-{client.vpn_config.username}.sswan"'
        }
    )


@router.get("/download/{access_token}/pac")
async def download_pac_public(
    access_token: str,
    db: DBSession
):
    """Download PAC file by access token."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.domains), selectinload(Client.vpn_config))
        .where(Client.access_token == access_token)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Not found")
    if is_access_token_expired(client):
        raise HTTPException(status_code=410, detail="Link expired")

    content = profile_generator.generate_pac_file(client)

    return Response(
        content=content,
        media_type="application/x-ns-proxy-autoconfig",
        headers={
            "Content-Disposition": 'attachment; filename="zetit-fna.pac"',
            "Cache-Control": "public, max-age=300",
        }
    )


@router.get("/pac/{access_token}")
async def get_pac_file(
    access_token: str,
    db: DBSession
):
    """Get PAC file for proxy auto-configuration."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.domains), selectinload(Client.vpn_config))
        .where(Client.access_token == access_token)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Not found")
    if is_access_token_expired(client):
        raise HTTPException(status_code=410, detail="Link expired")

    content = profile_generator.generate_pac_file(client)

    return Response(
        content=content,
        media_type="application/x-ns-proxy-autoconfig",
        headers={
            "Cache-Control": "public, max-age=300",
        }
    )


@router.get("/download/{access_token}/proxy-setup")
async def download_proxy_setup_public(
    access_token: str,
    db: DBSession
):
    """Download Windows proxy setup PowerShell script by access token."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.proxy_account))
        .where(Client.access_token == access_token)
    )
    client = result.scalar_one_or_none()

    if client is None or client.proxy_account is None:
        raise HTTPException(status_code=404, detail="Not found")
    if is_access_token_expired(client):
        raise HTTPException(status_code=410, detail="Link expired")

    domain = get_configured_domain()
    http_port, _ = get_configured_ports()
    web_port = get_configured_web_port()
    pac_url = f"https://{domain}:{web_port}/api/pac/{client.access_token}"

    script = f'''# ZETIT FNA - Windows Proxy Setup Script
# Run as Administrator

param(
    [switch]$UsePAC,
    [switch]$UseManual,
    [switch]$Disable
)

$ErrorActionPreference = "Stop"

# Proxy settings
$ProxyServer = "{domain}:{http_port}"
$PacUrl = "{pac_url}"
$Username = "{client.proxy_account.username}"

Write-Host "ZETIT FNA - Proxy Setup" -ForegroundColor Cyan
Write-Host "========================" -ForegroundColor Cyan
Write-Host ""

if ($Disable) {{
    Write-Host "Disabling proxy..." -ForegroundColor Yellow

    # Disable proxy in registry
    Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name ProxyEnable -Value 0
    Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name AutoConfigURL -Value ""

    # Refresh Internet settings
    $signature = @"
[DllImport("wininet.dll", SetLastError = true, CharSet=CharSet.Auto)]
public static extern bool InternetSetOption(IntPtr hInternet, int dwOption, IntPtr lpBuffer, int dwBufferLength);
"@
    $type = Add-Type -MemberDefinition $signature -Name WinInet -Namespace Win32API -PassThru
    $INTERNET_OPTION_SETTINGS_CHANGED = 39
    $INTERNET_OPTION_REFRESH = 37
    [Win32API.WinInet]::InternetSetOption([IntPtr]::Zero, $INTERNET_OPTION_SETTINGS_CHANGED, [IntPtr]::Zero, 0) | Out-Null
    [Win32API.WinInet]::InternetSetOption([IntPtr]::Zero, $INTERNET_OPTION_REFRESH, [IntPtr]::Zero, 0) | Out-Null

    Write-Host "Proxy disabled successfully!" -ForegroundColor Green
    exit 0
}}

if ($UsePAC -or (-not $UseManual)) {{
    Write-Host "Configuring PAC (Automatic Configuration)..." -ForegroundColor Yellow
    Write-Host "PAC URL: $PacUrl" -ForegroundColor Gray

    # Set PAC URL and disable manual proxy
    Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name AutoConfigURL -Value $PacUrl
    Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name ProxyEnable -Value 0

    # Disable auto-detect (WPAD) and enable PAC only via DefaultConnectionSettings
    $regPath = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings\\Connections"
    $settings = (Get-ItemProperty -Path $regPath -Name DefaultConnectionSettings -ErrorAction SilentlyContinue).DefaultConnectionSettings
    if ($settings -and $settings.Length -gt 8) {{
        # Byte 8: 1=direct, 2=proxy, 4=PAC, 8=auto-detect. Set to 5 (direct+PAC)
        $settings[8] = 5
        Set-ItemProperty -Path $regPath -Name DefaultConnectionSettings -Value $settings
    }}

    Write-Host ""
    Write-Host "PAC configured successfully!" -ForegroundColor Green
    Write-Host "Auto-detect (WPAD) disabled." -ForegroundColor Gray
    Write-Host "Only sites from your domain list will use proxy." -ForegroundColor Gray
}}

if ($UseManual) {{
    Write-Host "Configuring manual proxy..." -ForegroundColor Yellow
    Write-Host "Proxy Server: $ProxyServer" -ForegroundColor Gray

    # Set manual proxy
    Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name ProxyServer -Value $ProxyServer
    Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name ProxyEnable -Value 1
    Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name AutoConfigURL -Value ""

    Write-Host ""
    Write-Host "Manual proxy configured!" -ForegroundColor Green
    Write-Host "ALL traffic will go through proxy." -ForegroundColor Yellow
}}

# Refresh Internet settings
$signature = @"
[DllImport("wininet.dll", SetLastError = true, CharSet=CharSet.Auto)]
public static extern bool InternetSetOption(IntPtr hInternet, int dwOption, IntPtr lpBuffer, int dwBufferLength);
"@
$type = Add-Type -MemberDefinition $signature -Name WinInet -Namespace Win32API -PassThru
$INTERNET_OPTION_SETTINGS_CHANGED = 39
$INTERNET_OPTION_REFRESH = 37
[Win32API.WinInet]::InternetSetOption([IntPtr]::Zero, $INTERNET_OPTION_SETTINGS_CHANGED, [IntPtr]::Zero, 0) | Out-Null
[Win32API.WinInet]::InternetSetOption([IntPtr]::Zero, $INTERNET_OPTION_REFRESH, [IntPtr]::Zero, 0) | Out-Null

Write-Host ""
Write-Host "Your credentials:" -ForegroundColor Cyan
Write-Host "  Username: $Username" -ForegroundColor White
Write-Host "  Password: (same as VPN)" -ForegroundColor White
Write-Host ""
Write-Host "Note: Browser will ask for credentials on first connection." -ForegroundColor Gray
Write-Host ""
Write-Host "Usage:" -ForegroundColor Cyan
Write-Host "  .\\proxy-setup.ps1           - Configure PAC (recommended)" -ForegroundColor Gray
Write-Host "  .\\proxy-setup.ps1 -UseManual - Configure manual proxy for ALL traffic" -ForegroundColor Gray
Write-Host "  .\\proxy-setup.ps1 -Disable   - Disable proxy" -ForegroundColor Gray
'''

    return Response(
        content=script,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="zetit-fna-proxy-setup.ps1"'
        }
    )
