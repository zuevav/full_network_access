import hmac
import hashlib
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession
from app.config import settings
from app.models import Client, IpWhitelistLog
from app.services.profile_generator import ProfileGenerator
from app.services.proxy_manager import rebuild_proxy_config
from app.api.system import get_configured_domain, get_configured_ports
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


def get_client_ip(request: Request) -> str:
    """Get client IP from X-Real-IP, X-Forwarded-For, or request.client.host."""
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


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
            selectinload(Client.payments)
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
    status_emoji = "🔴"
    if client.payments:
        latest = max(client.payments, key=lambda p: p.valid_until)
        valid_until_str = latest.valid_until.strftime("%d.%m.%Y")
        from datetime import date
        if latest.valid_until >= date.today():
            status_emoji = "🟢"

    # Get proxy settings - use domain if configured
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

    ip_status_html = (
        '<p style="color: #16a34a; font-weight: 600;">Ваш IP уже добавлен &#10003;</p>'
        if ip_already_whitelisted
        else '<button onclick="addMyIp()" id="add-ip-btn" style="padding: 10px 20px; background: #667eea; color: white; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 14px;">Добавить мой IP (работа без пароля)</button>'
    )

    html = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZETIT FNA</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 480px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            margin-bottom: 24px;
        }}
        .logo {{ font-size: 32px; margin-bottom: 8px; }}
        h1 {{ font-size: 24px; color: #333; }}
        .subtitle {{ font-size: 12px; color: #888; margin-top: 4px; }}
        .status {{
            background: #f5f5f5;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 24px;
            text-align: center;
        }}
        .status-text {{ font-size: 18px; color: #333; }}
        .portal-btn {{
            display: block;
            width: 100%;
            padding: 14px;
            background: #667eea;
            color: white;
            text-align: center;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            margin-bottom: 24px;
        }}
        .portal-btn:hover {{ background: #5a6fd6; }}
        .section-title {{
            font-size: 14px;
            color: #888;
            margin-bottom: 12px;
            text-transform: uppercase;
        }}
        .download-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-bottom: 24px;
        }}
        .download-btn {{
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 16px;
            background: #f5f5f5;
            border-radius: 12px;
            text-decoration: none;
            color: #333;
            border: none;
            cursor: pointer;
            font-family: inherit;
            font-size: inherit;
        }}
        .download-btn:hover {{ background: #e8e8e8; }}
        .download-icon {{ font-size: 24px; margin-bottom: 8px; }}
        /* Instructions accordion */
        .instructions-section {{
            margin-bottom: 24px;
        }}
        .instr-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            width: 100%;
            padding: 14px 16px;
            background: #f5f5f5;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            font-family: inherit;
            font-size: 15px;
            font-weight: 600;
            color: #333;
            text-align: left;
            margin-bottom: 4px;
        }}
        .instr-header:hover {{ background: #e8e8e8; }}
        .instr-header .arrow {{ margin-left: auto; transition: transform 0.2s; }}
        .instr-header.active .arrow {{ transform: rotate(180deg); }}
        .instr-body {{
            display: none;
            padding: 12px 16px;
            background: #fafafa;
            border-radius: 0 0 12px 12px;
            margin-top: -4px;
            margin-bottom: 4px;
        }}
        .instr-body.active {{ display: block; }}
        .instr-body ol {{
            padding-left: 20px;
            margin: 0;
        }}
        .instr-body li {{
            margin-bottom: 8px;
            font-size: 14px;
            color: #444;
            line-height: 1.5;
        }}
        .instr-body .instr-link {{
            display: inline-block;
            margin-top: 8px;
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
            font-size: 14px;
        }}
        .instr-body .instr-link:hover {{ text-decoration: underline; }}
        /* Modal styles */
        .modal-overlay {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }}
        .modal-overlay.active {{ display: flex; }}
        .modal {{
            background: white;
            border-radius: 16px;
            width: 100%;
            max-width: 400px;
            max-height: 90vh;
            overflow: auto;
        }}
        .modal-header {{
            padding: 16px;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }}
        .modal-title {{ font-size: 18px; font-weight: 600; color: #333; }}
        .modal-subtitle {{ font-size: 14px; color: #888; margin-top: 4px; }}
        .modal-close {{
            background: none;
            border: none;
            font-size: 24px;
            color: #888;
            cursor: pointer;
            padding: 0;
            line-height: 1;
        }}
        .modal-body {{ padding: 16px; }}
        .modal-option {{
            display: block;
            padding: 16px;
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            margin-bottom: 12px;
            text-decoration: none;
            color: #333;
            position: relative;
        }}
        .modal-option:hover {{ border-color: #667eea; background: #f8f9ff; }}
        .modal-option-icon {{ font-size: 24px; margin-bottom: 8px; }}
        .modal-option-title {{ font-weight: 600; margin-bottom: 4px; }}
        .modal-option-desc {{ font-size: 13px; color: #666; }}
        .modal-badge {{
            position: absolute;
            top: -8px;
            right: 12px;
            background: #fbbf24;
            color: #78350f;
            font-size: 11px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 10px;
        }}
        .modal-footer {{
            padding: 12px 16px;
            background: #f5f5f5;
            border-radius: 0 0 16px 16px;
            text-align: center;
            font-size: 12px;
            color: #888;
        }}
        .proxy-info {{
            background: #f5f5f5;
            border-radius: 12px;
            padding: 16px;
            font-size: 14px;
        }}
        .proxy-info p {{ margin-bottom: 8px; }}
        .proxy-info code {{
            background: #e0e0e0;
            padding: 2px 6px;
            border-radius: 4px;
        }}
        .footer {{
            text-align: center;
            margin-top: 24px;
            color: #888;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🔐</div>
            <h1>ZETIT FNA</h1>
            <div class="subtitle">Full Network Access</div>
        </div>

        <div class="status">
            <div class="status-text">
                Привет, <strong>{client.name}</strong>!<br>
                {status_emoji} Активен до: {valid_until_str}
            </div>
        </div>

        <a href="/my/link/{access_token}" class="portal-btn">🔑 Личный кабинет</a>

        <div class="section-title">Быстрое скачивание</div>
        <div class="download-grid">
            <button onclick="showModal()" class="download-btn">
                <span class="download-icon">📱</span>
                <span>iPhone</span>
            </button>
            <a href="/api/download/{access_token}/android" class="download-btn">
                <span class="download-icon">🤖</span>
                <span>Android</span>
            </a>
            <a href="/api/download/{access_token}/windows" class="download-btn">
                <span class="download-icon">🪟</span>
                <span>Windows</span>
            </a>
            <button onclick="showModal()" class="download-btn">
                <span class="download-icon">🍏</span>
                <span>macOS</span>
            </button>
        </div>

        <div class="section-title">Инструкции по настройке</div>
        <div class="instructions-section">
            <button class="instr-header" onclick="toggleInstr(this)">
                📱 iPhone / iPad <span class="arrow">▼</span>
            </button>
            <div class="instr-body">
                <ol>
                    <li>Нажмите кнопку «iPhone» выше — откроется выбор режима VPN</li>
                    <li>Выберите режим (рекомендуем «Авто»)</li>
                    <li>В появившемся окне нажмите «Разрешить»</li>
                    <li>Откройте <strong>Настройки → Основные → VPN и управление устройством</strong></li>
                    <li>Нажмите на загруженный профиль → «Установить»</li>
                    <li>VPN появится в <strong>Настройки → VPN</strong> — включите его!</li>
                </ol>
            </div>

            <button class="instr-header" onclick="toggleInstr(this)">
                🤖 Android <span class="arrow">▼</span>
            </button>
            <div class="instr-body">
                <ol>
                    <li>Установите приложение <strong>strongSwan VPN Client</strong> из Google Play</li>
                    <li>Нажмите кнопку «Android» выше — скачается файл .sswan</li>
                    <li>Откройте скачанный файл</li>
                    <li>Приложение strongSwan предложит импортировать профиль — нажмите «Импортировать»</li>
                    <li>Подключитесь к VPN в приложении strongSwan</li>
                </ol>
                <a href="https://play.google.com/store/apps/details?id=org.strongswan.android" target="_blank" rel="noopener noreferrer" class="instr-link">↗ strongSwan в Google Play</a>
            </div>

            <button class="instr-header" onclick="toggleInstr(this)">
                🪟 Windows <span class="arrow">▼</span>
            </button>
            <div class="instr-body">
                <ol>
                    <li><strong>VPN:</strong> нажмите кнопку «Windows» выше — скачается скрипт настройки VPN (.ps1)</li>
                    <li>Нажмите правой кнопкой → «Выполнить с помощью PowerShell» (от имени администратора)</li>
                    <li>Скрипт автоматически настроит VPN-подключение</li>
                </ol>
                {"" if not client.proxy_account else f'''<hr style="margin: 12px 0; border: none; border-top: 1px solid #ddd;">
                <ol start="4">
                    <li><strong>Proxy:</strong> скачайте скрипт авто-настройки прокси (ссылка ниже)</li>
                    <li>Нажмите правой кнопкой → «Выполнить с помощью PowerShell»</li>
                    <li>Скрипт автоматически настроит системный прокси для всех сайтов</li>
                </ol>
                <a href="/api/download/{access_token}/proxy-setup" class="instr-link">⬇ Скачать скрипт настройки прокси</a>'''}
            </div>

            <button class="instr-header" onclick="toggleInstr(this)">
                🍏 macOS <span class="arrow">▼</span>
            </button>
            <div class="instr-body">
                <ol>
                    <li>Нажмите кнопку «macOS» выше — откроется выбор режима VPN</li>
                    <li>Выберите режим (рекомендуем «Авто»)</li>
                    <li>Откройте скачанный файл .mobileconfig</li>
                    <li>Откройте <strong>Системные настройки → Профили</strong></li>
                    <li>Нажмите на загруженный профиль → «Установить»</li>
                    <li>VPN появится в <strong>Системные настройки → VPN</strong> — включите его!</li>
                </ol>
            </div>
        </div>

        {"" if not client.proxy_account else f'''
        <div class="section-title">Прокси</div>
        <div class="proxy-info">
            <p>Адрес: <code>{proxy_host}:{http_port}</code></p>
            <p>Логин: <code>{client.proxy_account.username}</code></p>
            <p>Пароль: <code style="user-select:all; cursor:pointer" title="Нажмите, чтобы выделить">{"•" * 8}</code>
               <button onclick="this.previousElementSibling.textContent='{client.proxy_account.password_plain}';this.remove()" style="background:#e0e0e0;border:none;border-radius:6px;padding:2px 10px;cursor:pointer;font-size:12px;">Показать</button></p>
            <p><a href="/api/download/{access_token}/pac">⬇ Скачать PAC-файл</a></p>
        </div>
        <div style="margin-top: 16px; background: #f5f5f5; border-radius: 12px; padding: 16px; font-size: 14px;">
            <p style="margin-bottom: 8px;">Ваш текущий IP: <code>{client_ip}</code></p>
            <div id="ip-whitelist-status">
                {ip_status_html}
            </div>
            <div id="ip-whitelist-result" style="margin-top: 8px;"></div>
        </div>
        '''}

        <div class="footer">
            Вопросы? Обратитесь к администратору
        </div>
    </div>

    <!-- iOS/macOS VPN Mode Selection Modal -->
    <div id="vpnModal" class="modal-overlay" onclick="hideModal(event)">
        <div class="modal" onclick="event.stopPropagation()">
            <div class="modal-header">
                <div>
                    <div class="modal-title">Выберите режим VPN</div>
                    <div class="modal-subtitle">Как должен работать VPN?</div>
                </div>
                <button class="modal-close" onclick="hideModal()">&times;</button>
            </div>
            <div class="modal-body">
                <a href="/api/download/{access_token}/ios?mode=ondemand" class="modal-option">
                    <span class="modal-badge">Рекомендуем</span>
                    <div class="modal-option-icon">⚡</div>
                    <div class="modal-option-title">Авто (по доменам)</div>
                    <div class="modal-option-desc">VPN включается только при открытии нужных сайтов.</div>
                </a>
                <a href="/api/download/{access_token}/ios?mode=always" class="modal-option">
                    <div class="modal-option-icon">🛡️</div>
                    <div class="modal-option-title">Всегда (Split-туннель)</div>
                    <div class="modal-option-desc">VPN всегда включён, но только рабочий трафик идёт через VPN.</div>
                </a>
                <a href="/api/download/{access_token}/ios?mode=full" class="modal-option">
                    <div class="modal-option-icon">🌐</div>
                    <div class="modal-option-title">Всегда (Весь трафик)</div>
                    <div class="modal-option-desc">Весь трафик через VPN. Максимальная защита.</div>
                </a>
            </div>
            <div class="modal-footer" style="background: #fff3cd; color: #856404;">
                <strong>📱 Инструкция для iPhone:</strong><br>
                1. Нажмите на режим выше<br>
                2. Разрешите загрузку профиля<br>
                3. Откройте: <strong>Настройки → Основные → VPN и управление устройством</strong><br>
                4. Нажмите на загруженный профиль → Установить
            </div>
        </div>
    </div>

    <script>
        function showModal() {{
            document.getElementById('vpnModal').classList.add('active');
        }}
        function hideModal(event) {{
            if (!event || event.target === event.currentTarget) {{
                document.getElementById('vpnModal').classList.remove('active');
            }}
        }}
        function toggleInstr(btn) {{
            var body = btn.nextElementSibling;
            var wasActive = btn.classList.contains('active');
            // Close all
            document.querySelectorAll('.instr-header').forEach(function(h) {{ h.classList.remove('active'); }});
            document.querySelectorAll('.instr-body').forEach(function(b) {{ b.classList.remove('active'); }});
            // Toggle clicked
            if (!wasActive) {{
                btn.classList.add('active');
                body.classList.add('active');
            }}
        }}
        function addMyIp() {{
            var btn = document.getElementById('add-ip-btn');
            var result = document.getElementById('ip-whitelist-result');
            if (btn) btn.disabled = true;
            fetch('/api/connect/{access_token}/whitelist-ip', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json', 'X-CSRF-Token': '{csrf_token}' }}
            }})
            .then(function(r) {{ return r.json(); }})
            .then(function(data) {{
                if (data.success) {{
                    document.getElementById('ip-whitelist-status').innerHTML =
                        '<p style="color: #16a34a; font-weight: 600;">Ваш IP уже добавлен ✓</p>';
                    result.innerHTML = '';
                }} else {{
                    result.innerHTML = '<p style="color: #dc2626;">' + (data.detail || 'Ошибка') + '</p>';
                    if (btn) btn.disabled = false;
                }}
            }})
            .catch(function(e) {{
                result.innerHTML = '<p style="color: #dc2626;">Ошибка: ' + e.message + '</p>';
                if (btn) btn.disabled = false;
            }});
        }}
    </script>
</body>
</html>
"""
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
        .options(selectinload(Client.domains))
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
            "Content-Disposition": 'attachment; filename="zetit-fna.pac"'
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
        .options(selectinload(Client.domains))
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
        media_type="application/x-ns-proxy-autoconfig"
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
    pac_url = f"https://{domain}/pac/{client.access_token}"

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

    # Set PAC URL
    Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name AutoConfigURL -Value $PacUrl
    Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name ProxyEnable -Value 0

    Write-Host ""
    Write-Host "PAC configured successfully!" -ForegroundColor Green
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
