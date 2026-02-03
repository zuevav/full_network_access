# ProxyGate — Система управления VPN/Proxy доступом
## Техническая спецификация v2 (для Claude Code)

---

## 1. ОБЗОР ПРОЕКТА

### Что это
Веб-платформа для управления VPN и Proxy доступом клиентов из России к европейским сервисам. Администратор управляет клиентами, у каждого клиента — свой персональный список доменов, через которые идёт трафик. Остальной трафик клиента идёт напрямую (split tunneling).

### Ключевые требования
- **Встроенный VPN**: IKEv2/IPsec — встроен в Windows 10/11, iOS, macOS (без установки софта)
- **Селективный роутинг**: только указанные домены идут через VPS, остальное — напрямую
- **Per-client списки**: у каждого клиента свой набор доменов → свои маршруты
- **Мобильные профили**: .mobileconfig (iOS/macOS), PowerShell-скрипт (Windows), .sswan (Android)
- **Личный кабинет клиента**: клиент логинится → видит свой статус, скачивает профили, видит домены
- **Админ-панель**: управление клиентами, доменами, оплатой, статусами
- **Масштабируемость**: от 5 до 200+ клиентов

### Два веб-интерфейса

**1. Админ-панель** (`/admin/...`)
- Полное управление: создание клиентов, домены, платежи, шаблоны
- JWT авторизация + опциональный TOTP
- Только для администратора

**2. Личный кабинет клиента** (`/my/...`)
- Клиент логинится по своему username + password (тот же что для VPN)
- Скачивает профили для всех своих устройств
- Видит свой список разрешённых доменов/сайтов
- Видит статус подписки и историю платежей
- Может отправить запрос администратору на добавление доменов
- Может сам сбросить пароль VPN/Proxy

### Почему IKEv2/IPsec
| Свойство | IKEv2 | WireGuard |
|----------|-------|-----------|
| Встроен в Windows | ✅ Да, нативно | ❌ Нужен клиент |
| Встроен в iOS | ✅ Да, нативно | ❌ Нужен App Store |
| Встроен в macOS | ✅ Да, нативно | ❌ Нужен клиент |
| Android | strongSwan (бесплатный) | WireGuard App |
| Авторизация | Логин + пароль (EAP) | Ключи (сложнее) |
| Split tunnel Windows | PowerShell маршруты | AllowedIPs |
| Сертификат сервера | Let's Encrypt (бесплатно) | Не нужен |
| Блокировка DPI | Сложнее блокировать | Легко детектится |
| Переподключение | MOBIKE (мгновенное) | Keepalive |
| Шифрование | AES-256 + SHA-256 | ChaCha20 |

### Два режима доступа для клиентов

**Режим 1 — VPN (IKEv2/IPsec, split tunnel)**
- Windows: Настройки → VPN → подключить (логин/пароль)
- iOS/macOS: установить профиль .mobileconfig
- Android: strongSwan App
- Только трафик к указанным доменам идёт через VPN
- Остальной трафик — напрямую (экономия скорости)

**Режим 2 — Proxy (HTTP/SOCKS5)**
- Клиент настраивает прокси в браузере/системе
- Или использует PAC-файл (автоматически выбирает какие домены через прокси)
- Аутентификация по логину/паролю

---

## 2. СТЕК ТЕХНОЛОГИЙ

```
Сервер:         Ubuntu 24.04 LTS (OVHcloud VPS-3, Франция, 6 vCPU / 12 GB / 100 GB)
VPN:            strongSwan 5.9+ (IKEv2/IPsec)
Proxy:          3proxy 0.9.x
Backend:        Python 3.12 + FastAPI + Uvicorn
ORM:            SQLAlchemy 2.0 + Alembic (миграции)
БД:             SQLite (начало, легко мигрировать на PostgreSQL)
Frontend:       React 18 + Tailwind CSS + shadcn/ui
Сборка:         Vite
Web-сервер:     Nginx (reverse proxy + SSL + раздача PAC/профилей)
SSL:            Let's Encrypt (certbot) — также используется для IKEv2
Уведомления:    Telegram Bot API (aiogram 3)
```

---

## 3. СТРУКТУРА ПРОЕКТА

```
proxygate/
├── .env.example
├── README.md
│
├── backend/
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app, lifespan, CORS
│   │   ├── config.py               # Settings from .env
│   │   ├── database.py             # SQLAlchemy engine, session
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── client.py           # Client model
│   │   │   ├── domain.py           # ClientDomain, DomainTemplate
│   │   │   ├── vpn.py              # VpnConfig model (IKEv2)
│   │   │   ├── proxy.py            # ProxyAccount model
│   │   │   ├── payment.py          # Payment model
│   │   │   └── domain_request.py   # DomainRequest model (запросы клиентов)
│   │   │
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── client.py           # Pydantic schemas
│   │   │   ├── domain.py
│   │   │   ├── vpn.py
│   │   │   ├── proxy.py
│   │   │   ├── payment.py
│   │   │   └── portal.py           # Schemas for client portal
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py           # Main API router (admin + portal)
│   │   │   │
│   │   │   ├── # === ADMIN API (/api/admin/...) ===
│   │   │   ├── auth.py             # Admin JWT auth
│   │   │   ├── clients.py          # CRUD clients
│   │   │   ├── domains.py          # Domain management
│   │   │   ├── vpn.py              # VPN config generation
│   │   │   ├── proxy.py            # Proxy account management
│   │   │   ├── payments.py         # Payment tracking
│   │   │   ├── profiles.py         # Platform-specific profile generation
│   │   │   ├── templates.py        # Domain templates
│   │   │   ├── dashboard.py        # Stats & monitoring
│   │   │   │
│   │   │   └── # === CLIENT PORTAL API (/api/portal/...) ===
│   │   │   ├── portal_auth.py      # Client login (username+password → JWT)
│   │   │   ├── portal_profile.py   # Client self-service: profile downloads
│   │   │   ├── portal_domains.py   # Client: view domains, request additions
│   │   │   └── portal_account.py   # Client: status, payments, password reset
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── ikev2_manager.py    # strongSwan management (swanctl)
│   │   │   ├── proxy_manager.py    # 3proxy config generation & reload
│   │   │   ├── pac_generator.py    # PAC file generation per client
│   │   │   ├── profile_generator.py # iOS .mobileconfig, Windows .ps1, Android .sswan
│   │   │   ├── domain_resolver.py  # Resolve domains → IPs for routes
│   │   │   ├── route_manager.py    # Generate per-client route lists
│   │   │   ├── payment_checker.py  # Auto-block expired clients
│   │   │   └── telegram_bot.py     # Telegram notifications
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── security.py         # Password hashing, JWT (admin + client tokens)
│   │       └── helpers.py
│   │
│   └── scripts/
│       ├── init_db.py              # Create initial admin + seed templates
│       ├── setup_strongswan.sh     # strongSwan initial setup
│       ├── setup_3proxy.sh         # 3proxy initial setup
│       ├── setup_vps.sh            # Full VPS bootstrap
│       └── cron_tasks.py           # Periodic tasks
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── index.html
│   │
│   └── src/
│       ├── main.jsx
│       ├── App.jsx                 # Routes: /admin/* и /my/*
│       ├── api.js                  # API client (fetch wrapper, два типа JWT)
│       │
│       ├── # === ADMIN PANEL ===
│       ├── admin/
│       │   ├── Layout.jsx          # Admin layout with sidebar
│       │   ├── Sidebar.jsx
│       │   ├── pages/
│       │   │   ├── Dashboard.jsx
│       │   │   ├── Clients.jsx
│       │   │   ├── ClientDetail.jsx
│       │   │   ├── Templates.jsx
│       │   │   ├── Settings.jsx
│       │   │   └── Login.jsx
│       │   └── components/
│       │       ├── DashboardStats.jsx
│       │       ├── ClientTable.jsx
│       │       ├── ClientCard.jsx
│       │       ├── DomainManager.jsx
│       │       ├── PaymentHistory.jsx
│       │       ├── ProfileDownload.jsx
│       │       ├── TemplateManager.jsx
│       │       └── DomainRequests.jsx  # Запросы от клиентов на домены
│       │
│       ├── # === CLIENT PORTAL ===
│       ├── portal/
│       │   ├── PortalLayout.jsx    # Portal layout (header + content)
│       │   ├── pages/
│       │   │   ├── PortalLogin.jsx     # Вход клиента
│       │   │   ├── PortalHome.jsx      # Главная: статус + быстрые действия
│       │   │   ├── PortalDevices.jsx   # Скачивание профилей для устройств
│       │   │   ├── PortalDomains.jsx   # Мои сайты + запрос на добавление
│       │   │   └── PortalPayments.jsx  # История платежей
│       │   └── components/
│       │       ├── StatusCard.jsx      # Статус подписки
│       │       ├── DeviceCard.jsx      # Карточка устройства + кнопка скачать
│       │       ├── DomainList.jsx      # Список доменов (read-only)
│       │       ├── DomainRequestForm.jsx # Форма запроса нового домена
│       │       └── SetupGuide.jsx      # Пошаговая инструкция настройки
│       │
│       └── shared/
│           ├── LoadingSpinner.jsx
│           ├── ErrorMessage.jsx
│           └── ConfirmDialog.jsx
│
└── nginx/
    └── proxygate.conf
```

---

## 4. БАЗА ДАННЫХ (SQLAlchemy models)

### 4.1 clients
```python
class Client(Base):
    __tablename__ = "clients"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    telegram_id: Mapped[Optional[str]] = mapped_column(String(100))
    service_type: Mapped[str] = mapped_column(String(20), default="both")  # vpn / proxy / both
    is_active: Mapped[bool] = mapped_column(default=True)
    access_token: Mapped[str] = mapped_column(String(64), unique=True)     # Секретный токен для страницы клиента
    portal_password_hash: Mapped[Optional[str]] = mapped_column(String(255)) # Хеш пароля для личного кабинета
    # При создании клиента portal password = VPN password (можно сменить отдельно)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
    
    # Relationships
    vpn_config: Mapped[Optional["VpnConfig"]] = relationship(back_populates="client", uselist=False, cascade="all, delete-orphan")
    proxy_account: Mapped[Optional["ProxyAccount"]] = relationship(back_populates="client", uselist=False, cascade="all, delete-orphan")
    domains: Mapped[List["ClientDomain"]] = relationship(back_populates="client", cascade="all, delete-orphan")
    payments: Mapped[List["Payment"]] = relationship(back_populates="client", cascade="all, delete-orphan")
    domain_requests: Mapped[List["DomainRequest"]] = relationship(back_populates="client", cascade="all, delete-orphan")
```

### 4.2 vpn_configs (IKEv2)
```python
class VpnConfig(Base):
    __tablename__ = "vpn_configs"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), unique=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)    # EAP username: client_001
    password: Mapped[str] = mapped_column(String(64))                 # EAP password (plaintext для strongSwan)
    assigned_ip: Mapped[Optional[str]] = mapped_column(String(20))    # Фиксированный IP из пула (опционально)
    is_active: Mapped[bool] = mapped_column(default=True)
    # Кэш resolved IPs для маршрутов
    resolved_routes: Mapped[Optional[str]] = mapped_column(Text)      # JSON список CIDR для маршрутов
    last_resolved: Mapped[Optional[datetime]] = mapped_column()
    
    client: Mapped["Client"] = relationship(back_populates="vpn_config")
```

### 4.3 proxy_accounts
```python
class ProxyAccount(Base):
    __tablename__ = "proxy_accounts"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), unique=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    password_plain: Mapped[str] = mapped_column(String(64))           # Для отображения админу
    is_active: Mapped[bool] = mapped_column(default=True)
    
    client: Mapped["Client"] = relationship(back_populates="proxy_account")
```

### 4.4 client_domains
```python
class ClientDomain(Base):
    __tablename__ = "client_domains"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    domain: Mapped[str] = mapped_column(String(255))
    include_subdomains: Mapped[bool] = mapped_column(default=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    added_at: Mapped[datetime] = mapped_column(default=func.now())
    
    client: Mapped["Client"] = relationship(back_populates="domains")
    __table_args__ = (UniqueConstraint("client_id", "domain"),)
```

### 4.5 domain_templates
```python
class DomainTemplate(Base):
    __tablename__ = "domain_templates"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(500))
    icon: Mapped[Optional[str]] = mapped_column(String(10))
    domains_json: Mapped[str] = mapped_column(Text)                   # JSON array
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
```

### 4.6 payments
```python
class Payment(Base):
    __tablename__ = "payments"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    amount: Mapped[float] = mapped_column()
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    paid_at: Mapped[datetime] = mapped_column(default=func.now())
    valid_from: Mapped[date] = mapped_column()
    valid_until: Mapped[date] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), default="paid")
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    client: Mapped["Client"] = relationship(back_populates="payments")
```

### 4.7 domain_requests (запросы клиентов на добавление доменов)
```python
class DomainRequest(Base):
    __tablename__ = "domain_requests"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    domain: Mapped[str] = mapped_column(String(255))                  # Запрошенный домен
    reason: Mapped[Optional[str]] = mapped_column(String(500))        # Зачем нужен (от клиента)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending / approved / rejected
    admin_comment: Mapped[Optional[str]] = mapped_column(String(500)) # Комментарий админа
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column()
    
    client: Mapped["Client"] = relationship(back_populates="domain_requests")
```

### 4.8 admin_users
```python
class AdminUser(Base):
    __tablename__ = "admin_users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    totp_secret: Mapped[Optional[str]] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(default=True)
```

### Начальные шаблоны доменов (seed data)
```python
INITIAL_TEMPLATES = [
    {
        "name": "AI Сервисы",
        "icon": "🤖",
        "description": "ChatGPT, Claude, Gemini, Midjourney и другие AI-платформы",
        "domains": [
            "openai.com", "chat.openai.com", "api.openai.com", "platform.openai.com",
            "chatgpt.com", "oaiusercontent.com",
            "claude.ai", "anthropic.com",
            "gemini.google.com", "bard.google.com", "aistudio.google.com",
            "midjourney.com", "discord.com", "discord.gg",
            "perplexity.ai",
            "poe.com",
            "huggingface.co",
            "replicate.com",
            "stability.ai",
            "copilot.microsoft.com"
        ]
    },
    {
        "name": "Стриминг",
        "icon": "🎬",
        "description": "Netflix, YouTube Premium, Spotify, Disney+ и др.",
        "domains": [
            "netflix.com", "nflxvideo.net", "nflxext.com", "nflximg.net",
            "youtube.com", "googlevideo.com", "ytimg.com", "ggpht.com",
            "spotify.com", "spotifycdn.com", "scdn.co",
            "disneyplus.com", "disney-plus.net", "bamgrid.com", "dssott.com",
            "hbomax.com", "max.com",
            "primevideo.com", "amazonvideo.com"
        ]
    },
    {
        "name": "Соцсети",
        "icon": "📱",
        "description": "Instagram, Twitter/X, Facebook, LinkedIn и др.",
        "domains": [
            "instagram.com", "cdninstagram.com",
            "twitter.com", "x.com", "twimg.com", "t.co",
            "facebook.com", "fbcdn.net", "fb.com", "fb.me",
            "linkedin.com", "licdn.com",
            "threads.net",
            "tiktok.com", "tiktokcdn.com"
        ]
    },
    {
        "name": "Разработка",
        "icon": "💻",
        "description": "GitHub, npm, Docker Hub, StackOverflow и др.",
        "domains": [
            "github.com", "github.io", "githubusercontent.com", "githubassets.com",
            "npmjs.com", "npmjs.org",
            "docker.com", "docker.io",
            "stackoverflow.com", "stackexchange.com",
            "gitlab.com",
            "bitbucket.org",
            "pypi.org", "pythonhosted.org", "files.pythonhosted.org",
            "crates.io",
            "vercel.com", "netlify.com"
        ]
    },
    {
        "name": "Google Сервисы",
        "icon": "🔍",
        "description": "Google Search, Maps, Drive, Gmail и др.",
        "domains": [
            "google.com", "googleapis.com", "gstatic.com", "googleusercontent.com",
            "google.co.uk", "google.de", "google.fr",
            "gmail.com", "mail.google.com",
            "drive.google.com", "docs.google.com",
            "maps.google.com", "maps.googleapis.com",
            "translate.google.com",
            "play.google.com",
            "accounts.google.com"
        ]
    },
    {
        "name": "Облачные хранилища",
        "icon": "☁️",
        "description": "Dropbox, OneDrive, iCloud, Notion и др.",
        "domains": [
            "dropbox.com", "dropboxstatic.com",
            "onedrive.com", "onedrive.live.com", "sharepoint.com",
            "icloud.com", "apple.com",
            "box.com", "boxcdn.net",
            "notion.so", "notion.site",
            "mega.nz", "mega.io"
        ]
    }
]
```

---

## 5. API ENDPOINTS

### ═══ ADMIN API (prefix: /api/admin) ═══
### Требует JWT-токен администратора

### Аутентификация админа
```
POST /api/admin/auth/login    — { username, password, totp_code? } → { access_token, token_type: "admin" }
POST /api/admin/auth/refresh  — Обновить токен
GET  /api/admin/auth/me       — Текущий админ
```

### Клиенты
```
GET    /api/admin/clients                    — Список клиентов (с пагинацией, фильтрами)
       Query: ?search=&status=active|inactive|expired&service_type=vpn|proxy|both&page=1&per_page=20
       Response: { items: [...], total, page, pages }

POST   /api/admin/clients                    — Создать клиента
       Body: { name, email?, phone?, telegram_id?, service_type, notes? }
       Бизнес-логика:
         1. Создать запись clients + access_token (UUID4)
         2. Сгенерировать portal_password (= VPN password по умолчанию)
         3. Если VPN: создать vpn_configs (username, password), обновить swanctl
         4. Если Proxy: создать proxy_accounts (username, password)
         5. Перегенерировать 3proxy конфиг
         6. Отправить клиенту ссылку на личный кабинет (Telegram / email)
         7. Вернуть полные данные клиента

GET    /api/admin/clients/{id}               — Детали клиента (со всеми связями)
PUT    /api/admin/clients/{id}               — Обновить данные клиента
DELETE /api/admin/clients/{id}               — Удалить клиента (+ удалить из strongSwan, 3proxy)

POST   /api/admin/clients/{id}/activate      — Активировать
POST   /api/admin/clients/{id}/deactivate    — Деактивировать (удалить из swanctl, 3proxy)
```

### Домены клиента (админ)
```
GET    /api/admin/clients/{id}/domains       — Список доменов клиента
POST   /api/admin/clients/{id}/domains       — Добавить домен(ы)
       Body: { domains: ["example.com", "test.org"], include_subdomains: true }
       Бизнес-логика:
         1. Добавить в client_domains
         2. Резолвить домены → CIDR для маршрутов
         3. Обновить resolved_routes в vpn_configs
         4. Перегенерировать 3proxy ACL
         5. Перегенерировать PAC-файл клиента

DELETE /api/admin/clients/{id}/domains/{domain_id}
POST   /api/admin/clients/{id}/domains/template      — Применить шаблон { template_id }
POST   /api/admin/clients/{id}/domains/sync          — Перерезолвить DNS → обновить маршруты
```

### Запросы на домены (от клиентов → одобрение админом)
```
GET    /api/admin/domain-requests              — Все запросы (?status=pending|approved|rejected)
PUT    /api/admin/domain-requests/{id}/approve — Одобрить { admin_comment? }
       Действия: создать ClientDomain + перегенерация конфигов + уведомить клиента
PUT    /api/admin/domain-requests/{id}/reject  — Отклонить { admin_comment }
       Действия: уведомить клиента
```

### VPN (IKEv2)
```
GET    /api/admin/clients/{id}/vpn/credentials   — Получить username/password
POST   /api/admin/clients/{id}/vpn/reset-password — Новый пароль → обновить swanctl
GET    /api/admin/clients/{id}/vpn/routes         — Список CIDR-маршрутов клиента
```

### Proxy
```
GET    /api/admin/clients/{id}/proxy/credentials     — Получить логин/пароль
POST   /api/admin/clients/{id}/proxy/reset-password  — Новый пароль
GET    /api/admin/clients/{id}/proxy/pac             — Скачать PAC-файл
```

### Профили (скачивание конфигов — из админки)
```
GET    /api/admin/clients/{id}/profiles/windows      — PowerShell скрипт (.ps1)
GET    /api/admin/clients/{id}/profiles/ios          — .mobileconfig (IKEv2)
GET    /api/admin/clients/{id}/profiles/macos        — .mobileconfig (IKEv2)
GET    /api/admin/clients/{id}/profiles/android      — .sswan профиль
```

### Шаблоны доменов
```
GET    /api/admin/templates                  — Список шаблонов
POST   /api/admin/templates                  — Создать шаблон
PUT    /api/admin/templates/{id}             — Обновить
DELETE /api/admin/templates/{id}             — Удалить
```

### Платежи
```
GET    /api/admin/clients/{id}/payments              — История
POST   /api/admin/clients/{id}/payments              — Добавить платёж { amount, valid_from, valid_until }
PUT    /api/admin/payments/{id}                      — Обновить
DELETE /api/admin/payments/{id}                      — Удалить
```

### Dashboard (админ)
```
GET    /api/admin/dashboard
       Response: {
         total_clients, active_clients, inactive_clients,
         expiring_soon: [...],  // Оплата истекает ≤ 7 дней
         expired: [...],
         pending_domain_requests: int,  // Непросмотренные запросы на домены
         total_domains,
         recent_clients: [...]  // Последние 5 созданных
       }
```

---

### ═══ CLIENT PORTAL API (prefix: /api/portal) ═══
### Требует JWT-токен клиента. Клиент видит ТОЛЬКО свои данные.

### Аутентификация клиента
```
POST /api/portal/auth/login    — { username, password } → { access_token, token_type: "client" }
       username = VPN-логин (client_001)
       password = portal-пароль (по умолчанию = VPN-пароль, можно сменить)
       
POST /api/portal/auth/refresh  — Обновить токен
```

### Главная клиента — статус и обзор
```
GET  /api/portal/me
     Response: {
       name: "Иванов Иван",
       username: "client_001",
       is_active: true,
       service_type: "both",
       subscription: {
         status: "active",          // active / expiring / expired / none
         valid_until: "2026-03-15",
         days_left: 40
       },
       domains_count: 12,
       pending_requests: 1
     }
```

### Скачивание профилей (из личного кабинета)
```
GET  /api/portal/profiles/windows     — PowerShell скрипт (.ps1)
GET  /api/portal/profiles/ios         — .mobileconfig для iPhone
GET  /api/portal/profiles/macos       — .mobileconfig для macOS
GET  /api/portal/profiles/android     — .sswan для Android
GET  /api/portal/profiles/pac         — PAC-файл для прокси
GET  /api/portal/profiles/info        — Все данные подключения (JSON)
     Response: {
       vpn: { server: "vpn.domain.com", username: "client_001", password: "xxx" },
       proxy: { host: "51.xx.xx.xx", http_port: 3128, socks_port: 1080, 
                username: "client_001", password: "xxx" },
       pac_url: "https://vpn.domain.com/pac/client_001"
     }
```

### Мои домены (read-only + запросы)
```
GET  /api/portal/domains
     Response: {
       domains: [
         { domain: "openai.com", include_subdomains: true, added_at: "..." },
         { domain: "google.com", include_subdomains: true, added_at: "..." },
         ...
       ],
       grouped_by_template: {
         "AI Сервисы": ["openai.com", "claude.ai", ...],
         "Google": ["google.com", "youtube.com", ...],
         "Другое": ["custom-site.com"]
       }
     }

POST /api/portal/domains/request
     Body: { domain: "newsite.com", reason: "Нужен для работы с клиентами" }
     Действия:
       1. Создать DomainRequest (status=pending)
       2. Уведомить админа в Telegram
     Response: { id, domain, status: "pending", message: "Запрос отправлен администратору" }

GET  /api/portal/domains/requests
     Response: [
       { id: 1, domain: "newsite.com", status: "pending", created_at: "..." },
       { id: 2, domain: "oldsite.com", status: "approved", resolved_at: "..." },
       { id: 3, domain: "badsite.com", status: "rejected", admin_comment: "...", resolved_at: "..." }
     ]
```

### Мои платежи (read-only)
```
GET  /api/portal/payments
     Response: {
       current_subscription: {
         valid_until: "2026-03-15",
         days_left: 40,
         status: "active"
       },
       history: [
         { paid_at: "2026-02-01", amount: 500, currency: "RUB", period: "01.02-15.03.2026" },
         ...
       ]
     }
```

### Управление аккаунтом
```
POST /api/portal/account/change-password
     Body: { old_password, new_password }
     Действия: обновить portal_password_hash
     (VPN-пароль НЕ меняется — его меняет только админ)
     
GET  /api/portal/account/setup-guides
     Response: {
       windows: { steps: [...], video_url?: "..." },
       ios: { steps: [...] },
       macos: { steps: [...] },
       android: { steps: [...] }
     }
```

---

### ═══ ПУБЛИЧНЫЕ ENDPOINTS (без авторизации) ═══
```
GET    /connect/{access_token}                 — Персональная страница клиента (HTML)
       Альтернативный быстрый вход без логина/пароля
       Содержит ссылку «Войти в личный кабинет»

GET    /download/{access_token}/windows        — Скачать PowerShell скрипт
GET    /download/{access_token}/ios            — Скачать .mobileconfig
GET    /download/{access_token}/macos          — Скачать .mobileconfig
GET    /download/{access_token}/android        — Скачать .sswan
GET    /download/{access_token}/pac            — Скачать PAC-файл
```

---

## 6. СЕРВИСЫ (backend/app/services/)

### 6.1 ikev2_manager.py — Управление strongSwan IKEv2

```python
class IKEv2Manager:
    """
    Управление strongSwan IKEv2/IPsec VPN сервером.
    
    strongSwan использует swanctl (новый интерфейс) вместо устаревшего ipsec.
    Конфигурация: /etc/swanctl/conf.d/ — по файлу на каждую connection.
    Секреты (EAP): /etc/swanctl/conf.d/secrets.conf
    
    Сертификат сервера: Let's Encrypt (тот же что для Nginx).
    Клиенты доверяют Let's Encrypt CA по умолчанию → НОЛЬ ручной настройки сертификатов.
    """
    
    SWANCTL_DIR = "/etc/swanctl"
    CONF_DIR = "/etc/swanctl/conf.d"
    CONNECTIONS_FILE = f"{CONF_DIR}/connections.conf"
    SECRETS_FILE = f"{CONF_DIR}/secrets.conf"
    
    def generate_connections_conf(self, active_clients: list) -> str:
        """
        Генерирует /etc/swanctl/conf.d/connections.conf
        
        Одно общее подключение для всех клиентов:
        
        connections {
            proxygate {
                version = 2
                proposals = aes256-sha256-modp2048,aes256-sha384-ecp384
                rekey_time = 0s
                pools = client_pool
                fragmentation = yes
                dpd_delay = 30s
                send_certreq = no
                
                local {
                    auth = pubkey
                    certs = fullchain.pem
                    id = vpn.yourdomain.com
                }
                
                remote {
                    auth = eap-mschapv2
                    eap_id = %any
                }
                
                children {
                    proxygate-child {
                        local_ts = 0.0.0.0/0
                        esp_proposals = aes256-sha256,aes256-sha384
                        dpd_action = clear
                        rekey_time = 0s
                    }
                }
            }
        }
        
        pools {
            client_pool {
                addrs = 10.0.0.0/24
                dns = 1.1.1.1, 8.8.8.8
            }
        }
        """
        
    def generate_secrets_conf(self, active_clients: list) -> str:
        """
        Генерирует /etc/swanctl/conf.d/secrets.conf
        
        secrets {
            private-server {
                file = privkey.pem
            }
            
            eap-client_001 {
                id = client_001
                secret = "сгенерированный_пароль_1"
            }
            
            eap-client_002 {
                id = client_002
                secret = "сгенерированный_пароль_2"
            }
            
            # ... для каждого активного клиента
        }
        """
    
    def reload(self) -> None:
        """
        Перезагрузка конфигурации strongSwan:
        
        subprocess.run(["swanctl", "--load-all"], check=True)
        
        Это подхватывает изменения без разрыва существующих соединений.
        """
        
    def terminate_client(self, username: str) -> None:
        """
        Принудительное отключение клиента:
        
        swanctl --terminate --ike <sa-name> 
        (находим SA по identity = username)
        """
        
    def get_active_sessions(self) -> list[dict]:
        """
        Текущие подключения:
        
        swanctl --list-sas → парсинг
        Возвращает: [{username, remote_ip, connected_since, bytes_in, bytes_out}]
        """
    
    def add_client(self, username: str, password: str) -> None:
        """Добавить клиента: обновить secrets.conf + reload"""
        
    def remove_client(self, username: str) -> None:
        """Удалить клиента: terminate + обновить secrets.conf + reload"""
        
    def change_password(self, username: str, new_password: str) -> None:
        """Сменить пароль: обновить secrets.conf + reload"""
```

### 6.2 domain_resolver.py — Резолвинг доменов в IP

```python
class DomainResolver:
    """
    Резолвит домены клиента в CIDR-блоки для маршрутов.
    
    Маршруты используются в:
    - Windows: Add-VpnConnectionRoute (PowerShell скрипт)
    - iOS/macOS: .mobileconfig → IPv4 → IncludedRoutes
    - Android: strongSwan App → Split tunneling routes
    - PAC-файлы: по доменам (не IP)
    """
    
    async def resolve_domain(self, domain: str, include_subdomains: bool = True) -> list[str]:
        """
        Стратегия резолвинга:
        1. Проверить KNOWN_CIDRS — предзаготовленные подсети крупных сервисов
        2. DNS A/AAAA записи → расширить до /24 (чтобы покрыть CDN)
        3. Если include_subdomains — также www., cdn., api. + wildcard
        4. Дедупликация и объединение перекрывающихся CIDR
        
        Возвращает: ["104.18.0.0/16", "172.64.0.0/13", ...]
        """
        
    async def resolve_client_domains(self, client_id: int) -> list[str]:
        """Резолвит ВСЕ домены клиента → единый список CIDR"""
        
    async def update_all_clients(self) -> dict:
        """
        Cron-задача (каждые 30 мин):
        Обновить resolved_routes для всех клиентов.
        Возвращает: {client_id: [new_routes_count, changed: bool]}
        """
    
    # Предзаготовленные CIDR для популярных сервисов
    # (резолвить DNS для них ненадёжно — CDN меняет IP)
    KNOWN_CIDRS = {
        "openai.com":       ["104.18.0.0/16", "172.64.0.0/13"],
        "chatgpt.com":      ["104.18.0.0/16", "172.64.0.0/13"],
        "claude.ai":        ["104.18.0.0/16", "172.64.0.0/13"],
        "anthropic.com":    ["104.18.0.0/16", "172.64.0.0/13"],
        "netflix.com":      ["23.246.0.0/18", "37.77.184.0/21", "45.57.0.0/17",
                             "64.120.128.0/17", "108.175.32.0/20", "185.2.220.0/22",
                             "185.9.188.0/22", "192.173.64.0/18", "198.38.96.0/19",
                             "198.45.48.0/20"],
        "google.com":       ["142.250.0.0/15", "172.217.0.0/16", "216.58.192.0/19",
                             "172.253.0.0/16", "74.125.0.0/16", "173.194.0.0/16"],
        "youtube.com":      ["142.250.0.0/15", "172.217.0.0/16", "216.58.192.0/19",
                             "172.253.0.0/16", "74.125.0.0/16", "173.194.0.0/16"],
        "googlevideo.com":  ["142.250.0.0/15", "172.217.0.0/16", "172.253.0.0/16"],
        "facebook.com":     ["157.240.0.0/16", "31.13.24.0/21", "31.13.64.0/18",
                             "179.60.192.0/22", "185.60.216.0/22"],
        "instagram.com":    ["157.240.0.0/16", "31.13.24.0/21", "31.13.64.0/18"],
        "twitter.com":      ["104.244.42.0/24", "104.244.46.0/24", "199.16.156.0/22",
                             "199.59.148.0/22"],
        "x.com":            ["104.244.42.0/24", "104.244.46.0/24", "199.16.156.0/22"],
        "linkedin.com":     ["108.174.0.0/20", "144.2.0.0/16"],
        "github.com":       ["140.82.112.0/20", "185.199.108.0/22", "192.30.252.0/22",
                             "143.55.64.0/20"],
        "spotify.com":      ["35.186.224.0/20", "78.31.8.0/21", "194.132.196.0/22"],
        "discord.com":      ["162.159.0.0/16"],
        "discord.gg":       ["162.159.0.0/16"],
        "tiktok.com":       ["16.0.0.0/8", "34.0.0.0/8", "99.0.0.0/8"],
        # CDN провайдеры (покрывают множество сервисов через Cloudflare/Fastly)
        "cloudflare":       ["104.16.0.0/12", "172.64.0.0/13", "131.0.72.0/22"],
    }
```

### 6.3 route_manager.py — Управление маршрутами

```python
class RouteManager:
    """
    Генерирует per-client списки маршрутов для split tunneling.
    Маршруты = CIDR-блоки IP-адресов доменов клиента.
    
    Один и тот же список маршрутов используется:
    - PowerShell (Add-VpnConnectionRoute)
    - .mobileconfig (IncludedRoutes)
    - .sswan (split tunneling)
    """
    
    def get_client_routes(self, client_id: int) -> list[str]:
        """
        Возвращает актуальный список CIDR для клиента.
        Читает из vpn_configs.resolved_routes (кэш).
        """
    
    def optimize_routes(self, cidrs: list[str]) -> list[str]:
        """
        Оптимизация списка маршрутов:
        1. Удалить дубликаты
        2. Объединить перекрывающиеся CIDR (10.0.0.0/24 + 10.0.1.0/24 → 10.0.0.0/23)
        3. Удалить подсети, которые уже покрыты более широкой (10.0.0.5/32 внутри 10.0.0.0/24)
        4. Сортировка
        
        Использовать ipaddress.collapse_addresses() из stdlib.
        """
```

### 6.4 profile_generator.py — Генерация профилей для всех платформ

```python
class ProfileGenerator:
    """Генерация конфигов для каждой платформы"""
    
    def generate_windows_ps1(self, client: Client, routes: list[str]) -> str:
        """
        PowerShell скрипт (.ps1) для Windows 10/11.
        
        Клиент скачивает → запускает от имени администратора → VPN настроен.
        
        Скрипт:
        1. Создаёт VPN-подключение (Add-VpnConnection IKEv2)
        2. Настраивает шифрование (Set-VpnConnectionIPsecConfiguration)
        3. Включает split tunneling
        4. Добавляет маршруты для доменов клиента
        5. Сохраняет логин (пароль вводится при первом подключении)
        """
        # Шаблон ниже в разделе 7
        
    def generate_ios_mobileconfig(self, client: Client, routes: list[str]) -> bytes:
        """
        .mobileconfig для iOS (iPhone/iPad).
        
        Клиент скачивает → Настройки → Профиль → Установить → VPN готов.
        
        Профиль содержит:
        1. IKEv2 VPN конфигурацию
        2. Логин/пароль (EAP)
        3. On-Demand правила (автоподключение)
        4. Split tunneling маршруты
        """
        
    def generate_macos_mobileconfig(self, client: Client, routes: list[str]) -> bytes:
        """
        .mobileconfig для macOS.
        Аналогично iOS, но с другим PayloadType для маршрутов.
        """
        
    def generate_android_sswan(self, client: Client, routes: list[str]) -> bytes:
        """
        .sswan профиль для strongSwan Android App.
        
        Формат: JSON, zip-архив с расширением .sswan
        
        {
            "uuid": "...",
            "name": "ProxyGate VPN",
            "type": "ikev2-eap",
            "remote": {
                "addr": "vpn.yourdomain.com",
                "id": "vpn.yourdomain.com"
            },
            "local": {
                "eap_id": "client_001"
            },
            "split-tunneling": {
                "subnets": ["104.18.0.0/16", "142.250.0.0/15", ...]
            }
        }
        """
    
    def generate_client_page_html(self, client: Client) -> str:
        """
        HTML-страница клиента (по секретному access_token).
        Содержит кнопки скачивания для всех платформ + инструкции.
        """
```

### 6.5 proxy_manager.py — Управление 3proxy

```python
class ProxyManager:
    """Генерация конфигов 3proxy и управление сервисом"""
    
    CONFIG_PATH = "/etc/3proxy/3proxy.cfg"
    PASSWD_PATH = "/etc/3proxy/passwd"
    
    def generate_config(self, active_clients: list) -> str:
        """
        Генерирует полный конфиг 3proxy.
        Per-client ACL с whitelist доменов.
        """
        
    def generate_passwd(self, accounts: list) -> str:
        """username:CL:password"""
        
    def reload(self) -> None:
        """kill -HUP $(pidof 3proxy)"""
        
    def apply_changes(self) -> None:
        """Полный цикл: генерация + reload"""
```

### 6.6 pac_generator.py — PAC-файлы

```python
class PacGenerator:
    """Per-client PAC файлы для автоматической прокси-конфигурации"""
    
    def generate(self, client_id: int, domains: list[str]) -> str:
        """JavaScript PAC файл с доменами клиента"""
```

### 6.7 payment_checker.py — Проверка оплаты

```python
class PaymentChecker:
    """Cron каждые 15 минут"""
    
    async def check_all(self) -> None:
        """
        1. Найти клиентов без действующей оплаты → деактивировать
        2. Найти клиентов с оплатой ≤ 3 дня → предупреждение в Telegram
        """
```

### 6.8 telegram_bot.py — Уведомления

```python
class TelegramNotifier:
    """aiogram 3 для отправки уведомлений"""
    
    async def notify_admin(self, message: str) -> None: ...
    async def notify_client(self, client: Client, message: str) -> None: ...
    async def send_payment_reminder(self, client: Client, days_left: int) -> None: ...
    async def send_profile_file(self, client: Client, file_data: bytes, filename: str) -> None: ...
```

---

## 7. ГЕНЕРАЦИЯ КОНФИГОВ (полные примеры)

### 7.1 Windows PowerShell скрипт (генерируется per-client)

```powershell
# ============================================
# ProxyGate VPN — Настройка для Windows
# Клиент: Иванов Иван Иванович
# Дата: 2026-02-03
# ============================================
# Запустите этот скрипт от имени Администратора!
# Правый клик → "Запуск от имени администратора"
# ============================================

$ErrorActionPreference = "Stop"
$VpnName = "ProxyGate VPN"
$ServerAddress = "vpn.yourdomain.com"
$Username = "client_001"

Write-Host "=== ProxyGate VPN Setup ===" -ForegroundColor Cyan
Write-Host ""

# Удалить существующее подключение
try {
    Remove-VpnConnection -Name $VpnName -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Старое подключение удалено" -ForegroundColor Yellow
} catch {}

# Создать VPN подключение IKEv2
Write-Host "[1/4] Создание VPN подключения..." -ForegroundColor Green
Add-VpnConnection `
    -Name $VpnName `
    -ServerAddress $ServerAddress `
    -TunnelType Ikev2 `
    -AuthenticationMethod Eap `
    -EncryptionLevel Required `
    -SplitTunneling `
    -RememberCredential `
    -DnsSuffix ""

# Настройка параметров безопасности IKEv2
Write-Host "[2/4] Настройка шифрования..." -ForegroundColor Green
Set-VpnConnectionIPsecConfiguration -ConnectionName $VpnName `
    -AuthenticationTransformConstants SHA256128 `
    -CipherTransformConstants AES256 `
    -DHGroup Group14 `
    -IntegrityCheckMethod SHA256 `
    -PfsGroup PFS2048 `
    -EncryptionMethod AES256 `
    -Force

# Добавить маршруты для ваших сервисов
Write-Host "[3/4] Добавление маршрутов..." -ForegroundColor Green

# --- AI Сервисы (OpenAI, Claude, Anthropic) ---
Add-VpnConnectionRoute -ConnectionName $VpnName -DestinationPrefix "104.18.0.0/16" -PassThru | Out-Null
Add-VpnConnectionRoute -ConnectionName $VpnName -DestinationPrefix "172.64.0.0/13" -PassThru | Out-Null

# --- Google (Search, YouTube, Gmail, Drive) ---
Add-VpnConnectionRoute -ConnectionName $VpnName -DestinationPrefix "142.250.0.0/15" -PassThru | Out-Null
Add-VpnConnectionRoute -ConnectionName $VpnName -DestinationPrefix "172.217.0.0/16" -PassThru | Out-Null
Add-VpnConnectionRoute -ConnectionName $VpnName -DestinationPrefix "172.253.0.0/16" -PassThru | Out-Null
Add-VpnConnectionRoute -ConnectionName $VpnName -DestinationPrefix "216.58.192.0/19" -PassThru | Out-Null
Add-VpnConnectionRoute -ConnectionName $VpnName -DestinationPrefix "74.125.0.0/16" -PassThru | Out-Null
Add-VpnConnectionRoute -ConnectionName $VpnName -DestinationPrefix "173.194.0.0/16" -PassThru | Out-Null

# === МАРШРУТЫ ГЕНЕРИРУЮТСЯ ДИНАМИЧЕСКИ ДЛЯ КАЖДОГО КЛИЕНТА ===

# Сохранить учётные данные
Write-Host "[4/4] Настройка учётных данных..." -ForegroundColor Green
# Логин сохраняется в системе, пароль — при первом подключении
cmdkey /generic:$ServerAddress /user:$Username

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " VPN успешно настроен!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host " Подключение: Настройки > Сеть > VPN > $VpnName"
Write-Host " Логин: $Username"
Write-Host " Пароль: (введите при первом подключении)"
Write-Host ""
Write-Host " Через VPN работают:"
Write-Host "   - openai.com, claude.ai (AI)"
Write-Host "   - google.com, youtube.com (Google)"
Write-Host " Остальные сайты — напрямую."
Write-Host ""
Read-Host "Нажмите Enter для выхода"
```

### 7.2 iOS .mobileconfig (IKEv2 + On-Demand + Split Tunnel)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadContent</key>
    <array>
        <dict>
            <!-- VPN Payload -->
            <key>PayloadType</key>
            <string>com.apple.vpn.managed</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
            <key>PayloadIdentifier</key>
            <string>com.proxygate.vpn.{{CLIENT_ID}}</string>
            <key>PayloadUUID</key>
            <string>{{VPN_UUID}}</string>
            <key>PayloadDisplayName</key>
            <string>ProxyGate VPN</string>
            
            <key>UserDefinedName</key>
            <string>ProxyGate VPN</string>
            <key>VPNType</key>
            <string>IKEv2</string>
            
            <key>IKEv2</key>
            <dict>
                <key>RemoteAddress</key>
                <string>vpn.yourdomain.com</string>
                <key>RemoteIdentifier</key>
                <string>vpn.yourdomain.com</string>
                <key>LocalIdentifier</key>
                <string>{{USERNAME}}</string>
                
                <!-- EAP аутентификация -->
                <key>AuthenticationMethod</key>
                <string>None</string>
                <key>ExtendedAuthEnabled</key>
                <true/>
                <key>AuthName</key>
                <string>{{USERNAME}}</string>
                <key>AuthPassword</key>
                <string>{{PASSWORD}}</string>
                
                <!-- Шифрование -->
                <key>IKESecurityAssociationParameters</key>
                <dict>
                    <key>EncryptionAlgorithm</key>
                    <string>AES-256</string>
                    <key>IntegrityAlgorithm</key>
                    <string>SHA2-256</string>
                    <key>DiffieHellmanGroup</key>
                    <integer>14</integer>
                </dict>
                <key>ChildSecurityAssociationParameters</key>
                <dict>
                    <key>EncryptionAlgorithm</key>
                    <string>AES-256</string>
                    <key>IntegrityAlgorithm</key>
                    <string>SHA2-256</string>
                    <key>DiffieHellmanGroup</key>
                    <integer>14</integer>
                </dict>
                
                <!-- Split Tunnel: указываем КАКИЕ маршруты через VPN -->
                <key>EnablePFS</key>
                <true/>
                
                <!-- IMPORTANT: This disables default route through VPN -->
                <key>NETunnelIPv4</key>
                <dict>
                    <key>IncludedRoutes</key>
                    <array>
                        <!-- Маршруты генерируются динамически -->
                        <dict>
                            <key>Address</key>
                            <string>104.18.0.0</string>
                            <key>SubnetMask</key>
                            <string>255.255.0.0</string>
                        </dict>
                        <dict>
                            <key>Address</key>
                            <string>142.250.0.0</string>
                            <key>SubnetMask</key>
                            <string>255.254.0.0</string>
                        </dict>
                        <!-- ... ещё маршруты ... -->
                    </array>
                </dict>
            </dict>
            
            <!-- On Demand: автоподключение -->
            <key>OnDemandEnabled</key>
            <integer>1</integer>
            <key>OnDemandRules</key>
            <array>
                <dict>
                    <key>Action</key>
                    <string>Connect</string>
                </dict>
            </array>
        </dict>
    </array>
    
    <!-- Profile Metadata -->
    <key>PayloadDisplayName</key>
    <string>ProxyGate VPN — {{CLIENT_NAME}}</string>
    <key>PayloadIdentifier</key>
    <string>com.proxygate.profile.{{CLIENT_ID}}</string>
    <key>PayloadOrganization</key>
    <string>ProxyGate</string>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>{{PROFILE_UUID}}</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
    <key>PayloadRemovalDisallowed</key>
    <false/>
</dict>
</plist>
```

### 7.3 strongSwan серверный конфиг

```
# /etc/swanctl/conf.d/connections.conf
# Автогенерация ProxyGate — не редактировать вручную!

connections {
    proxygate {
        version = 2
        proposals = aes256-sha256-modp2048,aes128-sha256-modp2048
        rekey_time = 0s
        unique = replace
        pools = client_pool
        fragmentation = yes
        dpd_delay = 30s
        send_certreq = no
        
        local {
            auth = pubkey
            certs = fullchain.pem
            id = vpn.yourdomain.com
        }
        
        remote {
            auth = eap-mschapv2
            eap_id = %any
        }
        
        children {
            proxygate-net {
                local_ts = 0.0.0.0/0
                esp_proposals = aes256-sha256,aes128-sha256
                dpd_action = clear
                rekey_time = 0s
            }
        }
    }
}

pools {
    client_pool {
        addrs = 10.0.0.0/24
        dns = 1.1.1.1, 8.8.8.8
    }
}
```

```
# /etc/swanctl/conf.d/secrets.conf
# Автогенерация ProxyGate — не редактировать вручную!

secrets {
    private-server {
        file = privkey.pem
    }
    
    eap-client_001 {
        id = client_001
        secret = "xK9mP2vL8nQ5wR3j"
    }
    
    eap-client_002 {
        id = client_002
        secret = "hT6yN4bF1cZ7dA9s"
    }
    
    # Добавляются/удаляются автоматически при управлении клиентами
}
```

### 7.4 3proxy конфиг (генерируется автоматически)

```
# === 3proxy config — автогенерация ProxyGate ===

nserver 1.1.1.1
nserver 8.8.8.8
nscache 65536
timeouts 1 5 30 60 180 1800 15 60

log /var/log/3proxy/3proxy.log D
logformat "L%d-%m-%Y %H:%M:%S %U %C:%c %R:%r %O %I %T"
rotate 30

auth strong
users $/etc/3proxy/passwd

# === Per-client ACL ===

# client_001 (Иванов) — AI + Google
allow client_001 * * openai.com,chat.openai.com,chatgpt.com *
allow client_001 * * claude.ai,anthropic.com *
allow client_001 * * google.com,googleapis.com,gstatic.com *
allow client_001 * * youtube.com,googlevideo.com,ytimg.com *

# client_002 (Петров) — Стриминг + Соцсети
allow client_002 * * netflix.com,nflxvideo.net,nflximg.net *
allow client_002 * * instagram.com,cdninstagram.com *

# === ЗАПРЕТ ОСТАЛЬНОГО ===
deny *

# === Серверы ===
proxy -p3128 -a
socks -p1080 -a
```

### 7.5 PAC-файл клиента

```javascript
// PAC: client_001 (Иванов) — Generated by ProxyGate
function FindProxyForURL(url, host) {
    var domains = [
        ".openai.com", ".chatgpt.com", ".oaiusercontent.com",
        ".claude.ai", ".anthropic.com",
        ".google.com", ".googleapis.com", ".gstatic.com", ".googleusercontent.com",
        ".youtube.com", ".googlevideo.com", ".ytimg.com"
    ];
    for (var i = 0; i < domains.length; i++) {
        if (dnsDomainIs(host, domains[i]) || host === domains[i].substring(1)) {
            return "PROXY 51.xx.xx.xx:3128; DIRECT";
        }
    }
    return "DIRECT";
}
```

---

## 8. FRONTEND — СТРАНИЦЫ

### ═══ ADMIN PANEL (`/admin/...`) ═══

### 8.1 Admin Login (`/admin/login`)
- username + password + optional TOTP
- JWT (type=admin) → localStorage

### 8.2 Dashboard (`/admin/`)
- Карточки: всего / активных / неоплаченных / онлайн
- Карточка «Запросы на домены» — кол-во pending запросов от клиентов
- Список «Скоро истекает оплата» (≤ 7 дней)
- Список «Просроченные»
- Последние 5 клиентов

### 8.3 Клиенты (`/admin/clients`)
- Таблица: имя, статус 🟢/🔴, тип (VPN/Proxy/Оба), оплата до, доменов
- Фильтры: статус, тип, поиск
- Кнопка «+ Новый клиент» → модалка
- «Быстрое создание» (имя → всё автоматически)

### 8.4 Карточка клиента (`/admin/clients/:id`)

**Заголовок:** имя, статус, кнопки активации/деактивации, ссылка на ЛК клиента (копировать)

**Таб «Профили»:**
- 4 кнопки: 🪟 Windows (.ps1), 🍎 iPhone (.mobileconfig), 🍏 macOS (.mobileconfig), 🤖 Android (.sswan)
- Ссылка на личный кабинет клиента (копирование)
- Кнопка «Отправить в Telegram»
- Proxy-данные: хост:порт, логин, пароль, PAC-ссылка

**Таб «Домены»:**
- Таблица: домен, с поддоменами?, дата добавления, ✕
- Input «Добавить домен» (autocomplete + Enter)
- Dropdown «Применить шаблон» (чекбоксы: AI, Стриминг, Соцсети...)
- Кнопка «Перерезолвить DNS»
- Счётчик маршрутов: «12 CIDR-маршрутов для 8 доменов»

**Таб «Платежи»:**
- Таблица: дата, сумма, период, статус (🟢 оплачен / 🔴 просрочен)
- Текущий статус: «Оплачено до 15.03.2026» или «Не оплачено!»
- Кнопка «+ Новый платёж»

**Таб «Настройки»:**
- Редактирование полей (имя, email, телефон, telegram)
- Тип сервиса (select: VPN / Proxy / Оба)
- Сброс VPN-пароля / Proxy-пароля / Пароля ЛК
- Удаление клиента (confirm dialog)

### 8.5 Запросы на домены (`/admin/domain-requests`)
- Таблица: клиент, домен, причина, дата, статус (pending/approved/rejected)
- Фильтр по статусу (по умолчанию — pending)
- Кнопки «✅ Одобрить» / «❌ Отклонить» (с модалкой для комментария)
- При одобрении → домен автоматически добавляется клиенту

### 8.6 Шаблоны (`/admin/templates`)
- Карточки шаблонов (иконка + название + кол-во доменов)
- Создание/редактирование шаблона (имя, иконка, список доменов)

### 8.7 Настройки (`/admin/settings`)
- VPS IP, домен
- Telegram bot token, admin chat ID
- Порты (IKEv2, proxy)
- Смена пароля админа

---

### ═══ ЛИЧНЫЙ КАБИНЕТ КЛИЕНТА (`/my/...`) ═══

Отдельный интерфейс — лаконичный, мобильно-адаптивный, на русском языке.
Клиент логинится по VPN-логину + паролю личного кабинета.

### 8.8 Вход клиента (`/my/login`)
- Поле «Логин» (= VPN-username, например client_001)
- Поле «Пароль» (по умолчанию = VPN-пароль, можно сменить)
- JWT (type=client) → localStorage
- Ссылка «Забыли пароль? Обратитесь к администратору»
- Минимальный дизайн, логотип ProxyGate

### 8.9 Главная кабинета (`/my/`)
Первое что видит клиент после входа — статус и быстрые действия.

```
╔═══════════════════════════════════════════════════╗
║                                                   ║
║  🔐 ProxyGate                          [Выйти]   ║
║                                                   ║
║  Привет, Иван!                                    ║
║                                                   ║
║  ┌─────────────────────────────────────────────┐  ║
║  │  ✅ Подписка активна                        │  ║
║  │  Действует до: 15 марта 2026                │  ║
║  │  Осталось: 40 дней                          │  ║
║  └─────────────────────────────────────────────┘  ║
║                                                   ║
║  ── Быстрые действия ──                          ║
║                                                   ║
║  📱 Настроить устройство    →                     ║
║  🌐 Мои сайты (12)         →                     ║
║  💳 История платежей        →                     ║
║  ⚙️  Сменить пароль          →                     ║
║                                                   ║
║  ── Нужна помощь? ──                              ║
║  📖 Инструкции по настройке                       ║
║  💬 Написать администратору: @admin               ║
║                                                   ║
╚═══════════════════════════════════════════════════╝
```

Компоненты:
- **StatusCard** — большая карточка со статусом подписки (🟢 активна / 🟡 истекает через N дней / 🔴 не оплачена)
- **QuickActions** — 4 кнопки-ссылки на основные разделы
- **HelpSection** — контакт администратора

### 8.10 Мои устройства (`/my/devices`)
Главная страница для клиента — скачивание профилей VPN/Proxy для каждого устройства.

```
╔═══════════════════════════════════════════════════╗
║  ← Назад         Мои устройства                  ║
║                                                   ║
║  Выберите ваше устройство и скачайте профиль      ║
║  для автоматической настройки VPN.                ║
║                                                   ║
║  ┌─────────────────────────────────────────────┐  ║
║  │  📱 iPhone / iPad                            │  ║
║  │                                              │  ║
║  │  Автоматическая настройка — ничего            │  ║
║  │  устанавливать не нужно!                      │  ║
║  │                                              │  ║
║  │  [  ⬇ Скачать профиль .mobileconfig  ]       │  ║
║  │                                              │  ║
║  │  ▸ Как установить (развернуть)               │  ║
║  │    1. Нажмите кнопку скачать (в Safari)       │  ║
║  │    2. Откройте «Настройки»                    │  ║
║  │    3. Вверху появится «Профиль загружен»      │  ║
║  │    4. Нажмите «Установить»                    │  ║
║  │    5. Готово! VPN включится автоматически      │  ║
║  └─────────────────────────────────────────────┘  ║
║                                                   ║
║  ┌─────────────────────────────────────────────┐  ║
║  │  🤖 Android                                   │  ║
║  │                                              │  ║
║  │  Нужно приложение strongSwan (бесплатное)     │  ║
║  │                                              │  ║
║  │  [ ⬇ Скачать профиль .sswan ]                │  ║
║  │  [ 📥 Установить strongSwan (Play Store) ]    │  ║
║  │                                              │  ║
║  │  ▸ Как установить (развернуть)               │  ║
║  └─────────────────────────────────────────────┘  ║
║                                                   ║
║  ┌─────────────────────────────────────────────┐  ║
║  │  🪟 Windows 10/11                             │  ║
║  │                                              │  ║
║  │  Автоматическая настройка — запустите скрипт  │  ║
║  │                                              │  ║
║  │  [ ⬇ Скачать скрипт настройки .ps1 ]         │  ║
║  │                                              │  ║
║  │  ▸ Как установить (развернуть)               │  ║
║  │    1. Скачайте файл                           │  ║
║  │    2. Правый клик → Запуск от имени админа    │  ║
║  │    3. Дождитесь завершения скрипта             │  ║
║  │    4. Откройте Настройки → Сеть → VPN          │  ║
║  │    5. Нажмите «ProxyGate VPN» → Подключить    │  ║
║  │    6. Введите пароль (только при первом разе)  │  ║
║  └─────────────────────────────────────────────┘  ║
║                                                   ║
║  ┌─────────────────────────────────────────────┐  ║
║  │  🍏 macOS                                     │  ║
║  │  [ ⬇ Скачать профиль .mobileconfig ]         │  ║
║  │  ▸ Как установить (развернуть)               │  ║
║  └─────────────────────────────────────────────┘  ║
║                                                   ║
║  ── Альтернатива: Прокси (для браузера) ──       ║
║                                                   ║
║  Если VPN не подходит, настройте прокси:          ║
║  Адрес: 51.xx.xx.xx                              ║
║  HTTP-порт: 3128  |  SOCKS5-порт: 1080           ║
║  Логин: client_001                               ║
║  Пароль: xxxxxxxx  [👁 показать] [📋 копировать]  ║
║                                                   ║
║  [ ⬇ Скачать PAC-файл ]                          ║
║  PAC — автоматически направляет нужные сайты      ║
║  через прокси, остальное — напрямую.              ║
║                                                   ║
╚═══════════════════════════════════════════════════╝
```

Компоненты:
- **DeviceCard** — карточка устройства (иконка, название, описание, кнопка скачивания, разворачиваемая инструкция)
- **SetupGuide** — пошаговые инструкции (accordion, разворачиваются по клику)
- **ProxyCredentials** — блок с данными прокси (с кнопками «Показать пароль» и «Копировать»)

### 8.11 Мои сайты (`/my/domains`)
Клиент видит свой список доменов (read-only) и может запросить добавление нового.

```
╔═══════════════════════════════════════════════════╗
║  ← Назад            Мои сайты                    ║
║                                                   ║
║  Через VPN/прокси доступны следующие сайты:       ║
║                                                   ║
║  🤖 AI Сервисы                                    ║
║  ├── openai.com       (+ поддомены)               ║
║  ├── chatgpt.com      (+ поддомены)               ║
║  ├── claude.ai        (+ поддомены)               ║
║  └── anthropic.com    (+ поддомены)               ║
║                                                   ║
║  🔍 Google Сервисы                                ║
║  ├── google.com       (+ поддомены)               ║
║  ├── youtube.com      (+ поддомены)               ║
║  ├── gmail.com        (+ поддомены)               ║
║  └── googleapis.com   (+ поддомены)               ║
║                                                   ║
║  📱 Соцсети                                       ║
║  ├── instagram.com    (+ поддомены)               ║
║  └── twitter.com      (+ поддомены)               ║
║                                                   ║
║  📦 Другое                                        ║
║  └── custom-site.com  (+ поддомены)               ║
║                                                   ║
║  ── Нужен ещё сайт? ──                           ║
║                                                   ║
║  ┌─────────────────────────────────────────────┐  ║
║  │  Домен: [ newsite.com                    ]   │  ║
║  │  Зачем: [ Нужен для работы с клиентами   ]   │  ║
║  │                                              │  ║
║  │  [ 📩 Отправить запрос ]                      │  ║
║  └─────────────────────────────────────────────┘  ║
║                                                   ║
║  ── Мои запросы ──                                ║
║  ✅ oldsite.com — одобрен 28.01.2026              ║
║  ⏳ newsite.com — на рассмотрении                 ║
║  ❌ badsite.com — отклонён (комментарий админа)   ║
║                                                   ║
╚═══════════════════════════════════════════════════╝
```

Компоненты:
- **DomainList** — список доменов, сгруппированных по шаблону (AI, Google, Соцсети, Другое)
- **DomainRequestForm** — форма запроса нового домена (поле домена + причина)
- **RequestHistory** — список прошлых запросов со статусами

### 8.12 Мои платежи (`/my/payments`)
Read-only история платежей.

```
╔═══════════════════════════════════════════════════╗
║  ← Назад           Мои платежи                   ║
║                                                   ║
║  ┌─────────────────────────────────────────────┐  ║
║  │  ✅ Подписка активна до 15 марта 2026       │  ║
║  │  Осталось: 40 дней                          │  ║
║  └─────────────────────────────────────────────┘  ║
║                                                   ║
║  ── История ──                                    ║
║                                                   ║
║  01.02.2026   500 ₽   01.02 — 15.03.2026  🟢     ║
║  01.01.2026   500 ₽   01.01 — 31.01.2026  ✅     ║
║  01.12.2025   500 ₽   01.12 — 31.12.2025  ✅     ║
║                                                   ║
║  По вопросам оплаты: @admin_telegram              ║
║                                                   ║
╚═══════════════════════════════════════════════════╝
```

### 8.13 Сменить пароль (`/my/settings`)
- Старый пароль
- Новый пароль (2 раза)
- Кнопка «Сохранить»
- Примечание: «Это пароль для входа в личный кабинет. VPN-пароль настраивается администратором.»

---

### ═══ ПУБЛИЧНАЯ СТРАНИЦА (`/connect/{token}`) ═══

### 8.14 Быстрый доступ без логина

Остаётся как альтернативный способ — по секретной ссылке без авторизации.
Добавляется кнопка «Войти в личный кабинет» для полного доступа.

```
╔═══════════════════════════════════════════════════╗
║  🔐 ProxyGate                                     ║
║  Ваш персональный VPN-доступ                      ║
║                                                   ║
║  Привет, Иван!                                    ║
║  Статус: 🟢 Активен до 15.03.2026                ║
║                                                   ║
║  [ 🔑 Войти в личный кабинет ]                    ║
║                                                   ║
║  ─── Быстрое скачивание ───                      ║
║  📱 iPhone    [ ⬇ .mobileconfig ]                 ║
║  🤖 Android   [ ⬇ .sswan ]                        ║
║  🪟 Windows   [ ⬇ .ps1 ]                          ║
║  🍏 macOS     [ ⬇ .mobileconfig ]                 ║
║                                                   ║
║  ─── Прокси ───                                   ║
║  Адрес: 51.xx.xx.xx:3128                          ║
║  Логин: client_001 / Пароль: xxxxxxxx             ║
║  [ ⬇ PAC-файл ]                                   ║
║                                                   ║
║  Вопросы? @admin_telegram                          ║
╚═══════════════════════════════════════════════════╝
```

---

## 9. РАЗВЁРТЫВАНИЕ VPS

### 9.1 setup_vps.sh — полная настройка

```bash
#!/bin/bash
# ProxyGate — Setup VPS (Ubuntu 24.04)
# Запуск: sudo bash setup_vps.sh

set -e

echo "=== ProxyGate VPS Setup ==="

# 1. Обновление системы
apt update && apt upgrade -y

# 2. Базовые пакеты
apt install -y \
    strongswan strongswan-pki libcharon-extra-plugins libstrongswan-extra-plugins \
    nginx certbot python3-certbot-nginx \
    python3-pip python3-venv \
    git curl ufw fail2ban \
    build-essential  # для сборки 3proxy

# 3. Firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 443/tcp         # HTTPS
ufw allow 80/tcp          # HTTP (для certbot)
ufw allow 500/udp         # IKEv2 (IKE)
ufw allow 4500/udp        # IKEv2 (NAT-T)
ufw allow 3128/tcp        # HTTP Proxy
ufw allow 1080/tcp        # SOCKS5
ufw --force enable

# 4. IP forwarding
cat >> /etc/sysctl.conf << 'EOF'
net.ipv4.ip_forward=1
net.ipv6.conf.all.forwarding=1
net.ipv4.conf.all.accept_redirects=0
net.ipv4.conf.all.send_redirects=0
EOF
sysctl -p

# 5. iptables для NAT (VPN клиенты → интернет)
# Определяем основной интерфейс
IFACE=$(ip route | grep default | awk '{print $5}' | head -1)
iptables -t nat -A POSTROUTING -s 10.0.0.0/24 -o $IFACE -j MASQUERADE
iptables -A FORWARD -s 10.0.0.0/24 -j ACCEPT
iptables -A FORWARD -d 10.0.0.0/24 -j ACCEPT

# Сохранить iptables
apt install -y iptables-persistent
netfilter-persistent save

# 6. Let's Encrypt сертификат
# ВАЖНО: сначала настроить DNS A-запись vpn.yourdomain.com → IP сервера
# certbot --nginx -d vpn.yourdomain.com

# 7. strongSwan — настройка
# Символические ссылки на Let's Encrypt сертификаты
ln -sf /etc/letsencrypt/live/vpn.yourdomain.com/fullchain.pem /etc/swanctl/x509/fullchain.pem
ln -sf /etc/letsencrypt/live/vpn.yourdomain.com/privkey.pem /etc/swanctl/private/privkey.pem
ln -sf /etc/letsencrypt/live/vpn.yourdomain.com/chain.pem /etc/swanctl/x509ca/chain.pem

# Создать директорию для конфигов
mkdir -p /etc/swanctl/conf.d

# Начальный конфиг strongSwan
cat > /etc/swanctl/conf.d/connections.conf << 'EOF'
connections {
    proxygate {
        version = 2
        proposals = aes256-sha256-modp2048,aes128-sha256-modp2048
        rekey_time = 0s
        unique = replace
        pools = client_pool
        fragmentation = yes
        dpd_delay = 30s
        send_certreq = no

        local {
            auth = pubkey
            certs = fullchain.pem
            id = vpn.yourdomain.com
        }

        remote {
            auth = eap-mschapv2
            eap_id = %any
        }

        children {
            proxygate-net {
                local_ts = 0.0.0.0/0
                esp_proposals = aes256-sha256,aes128-sha256
                dpd_action = clear
                rekey_time = 0s
            }
        }
    }
}

pools {
    client_pool {
        addrs = 10.0.0.0/24
        dns = 1.1.1.1, 8.8.8.8
    }
}
EOF

cat > /etc/swanctl/conf.d/secrets.conf << 'EOF'
secrets {
    private-server {
        file = privkey.pem
    }
}
EOF

# Включить необходимые плагины для EAP
# В /etc/strongswan.d/charon/ включаем eap-mschapv2
systemctl restart strongswan-starter
swanctl --load-all

# 8. 3proxy — установка из исходников
cd /tmp
git clone https://github.com/3proxy/3proxy.git
cd 3proxy
ln -s Makefile.Linux Makefile
make -f Makefile.Linux
make -f Makefile.Linux install
mkdir -p /etc/3proxy /var/log/3proxy

# Начальный конфиг (пустой, без клиентов)
cat > /etc/3proxy/3proxy.cfg << 'EOF'
nserver 1.1.1.1
nserver 8.8.8.8
nscache 65536
timeouts 1 5 30 60 180 1800 15 60
log /var/log/3proxy/3proxy.log D
logformat "L%d-%m-%Y %H:%M:%S %U %C:%c %R:%r %O %I %T"
rotate 30
auth strong
users $/etc/3proxy/passwd
deny *
proxy -p3128 -a
socks -p1080 -a
EOF
touch /etc/3proxy/passwd

# systemd сервис для 3proxy
cat > /etc/systemd/system/3proxy.service << 'EOF'
[Unit]
Description=3proxy Proxy Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/3proxy /etc/3proxy/3proxy.cfg
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable 3proxy
systemctl start 3proxy

# 9. Python backend
mkdir -p /opt/proxygate
cd /opt/proxygate
python3 -m venv venv
# Далее — деплой backend через git clone / scp

# 10. Certbot auto-renew хук (обновить симлинки strongSwan)
cat > /etc/letsencrypt/renewal-hooks/post/strongswan.sh << 'EOF'
#!/bin/bash
swanctl --load-creds
systemctl reload strongswan-starter
EOF
chmod +x /etc/letsencrypt/renewal-hooks/post/strongswan.sh

echo "=== Setup Complete ==="
echo "Следующие шаги:"
echo "1. Настроить DNS: vpn.yourdomain.com → $(curl -s ifconfig.me)"
echo "2. Получить SSL: certbot --nginx -d vpn.yourdomain.com"
echo "3. Задеплоить backend и frontend"
echo "4. Запустить: python init_db.py"
```

### 9.2 Nginx конфиг

```nginx
server {
    listen 443 ssl http2;
    server_name vpn.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/vpn.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/vpn.yourdomain.com/privkey.pem;

    # Admin Panel (SPA)
    location / {
        root /opt/proxygate/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Публичные страницы клиентов
    location /connect/ {
        proxy_pass http://127.0.0.1:8000;
    }

    # Скачивание профилей
    location /download/ {
        proxy_pass http://127.0.0.1:8000;
    }

    # PAC-файлы
    location /pac/ {
        proxy_pass http://127.0.0.1:8000;
        add_header Content-Type "application/x-ns-proxy-autoconfig";
    }
}

server {
    listen 80;
    server_name vpn.yourdomain.com;
    return 301 https://$host$request_uri;
}
```

### 9.3 .env

```bash
# Server
VPS_PUBLIC_IP=51.xx.xx.xx
VPS_DOMAIN=vpn.yourdomain.com

# Admin
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_strong_password_here
SECRET_KEY=your_random_64_char_string_here

# IKEv2
IKEV2_SERVER_ID=vpn.yourdomain.com
IKEV2_POOL_SUBNET=10.0.0.0/24
IKEV2_DNS=1.1.1.1,8.8.8.8

# 3proxy
PROXY_HTTP_PORT=3128
PROXY_SOCKS_PORT=1080

# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
ADMIN_TELEGRAM_ID=123456789

# Database
DATABASE_URL=sqlite:///data/proxygate.db
```

---

## 10. CRON-ЗАДАЧИ

```python
# cron_tasks.py

# Каждые 15 минут: проверка оплаты
# */15 * * * * /opt/proxygate/venv/bin/python scripts/cron_tasks.py check_payments

# Каждые 30 минут: обновление DNS → IP маршруты
# */30 * * * * /opt/proxygate/venv/bin/python scripts/cron_tasks.py resolve_domains

# Раз в день 3:00: бэкап БД
# 0 3 * * * /opt/proxygate/venv/bin/python scripts/cron_tasks.py backup

# Раз в день: очистка логов 3proxy старше 30 дней
# 0 4 * * * find /var/log/3proxy/ -name "*.log" -mtime +30 -delete
```

---

## 11. ПОРЯДОК РЕАЛИЗАЦИИ (для Claude Code)

### Фаза 1: Backend Core
1. Инициализировать FastAPI проект (`backend/`)
2. config.py — Pydantic Settings из .env
3. database.py — SQLAlchemy async engine + session
4. models/ — все 8 моделей (включая DomainRequest)
5. Alembic init + начальная миграция
6. schemas/ — Pydantic schemas для всех моделей (включая portal.py)
7. utils/security.py — JWT (два типа: admin + client), хеширование паролей
8. api/auth.py — admin login, refresh, middleware
9. scripts/init_db.py — создать admin user + seed domain templates
10. api/clients.py — полный CRUD (с генерацией portal_password)
11. api/domains.py — управление доменами клиента
12. api/templates.py — CRUD шаблонов
13. api/payments.py — CRUD платежей
14. api/dashboard.py — статистика (включая pending domain_requests)

### Фаза 2: VPN & Proxy Сервисы
15. services/ikev2_manager.py — генерация swanctl конфигов, reload, управление
16. services/domain_resolver.py — резолвинг доменов → CIDR
17. services/route_manager.py — оптимизация маршрутов
18. services/proxy_manager.py — генерация 3proxy конфигов, reload
19. services/pac_generator.py — PAC-файлы
20. Интеграция: при создании/изменении клиента → обновить все конфиги

### Фаза 3: Профили
21. services/profile_generator.py:
    - generate_windows_ps1() — PowerShell скрипт с маршрутами
    - generate_ios_mobileconfig() — XML plist с IKEv2 + routes
    - generate_macos_mobileconfig()
    - generate_android_sswan() — JSON для strongSwan App
22. api/profiles.py — admin endpoints скачивания профилей
23. Публичные endpoints: /connect/{token}, /download/{token}/*

### Фаза 4: Client Portal API
24. api/portal_auth.py — логин клиента (username + password → JWT type=client)
25. api/portal_profile.py — скачивание профилей из ЛК (/api/portal/profiles/*)
26. api/portal_domains.py — просмотр доменов + запрос на добавление
27. api/portal_account.py — /api/portal/me, смена пароля, история платежей
28. api/admin: domain-requests endpoints (approve/reject)

### Фаза 5: Frontend — Admin Panel
29. React + Vite + Tailwind проект (`frontend/`)
30. api.js — fetch wrapper с двумя типами JWT (admin / client)
31. Admin Login page (`/admin/login`)
32. Admin Layout + Sidebar + routing
33. Dashboard page
34. Clients list page (таблица + фильтры)
35. Client detail page (4 таба)
36. Domain manager component
37. Payment history component
38. Domain Requests page (`/admin/domain-requests`)
39. Templates page
40. Settings page

### Фаза 6: Frontend — Client Portal
41. Portal Login page (`/my/login`)
42. Portal Layout (простой header + content)
43. Portal Home — статус подписки + быстрые действия (`/my/`)
44. Portal Devices — карточки устройств + скачивание профилей (`/my/devices`)
45. Portal Domains — список сайтов + запрос на добавление (`/my/domains`)
46. Portal Payments — read-only история платежей (`/my/payments`)
47. Portal Settings — смена пароля (`/my/settings`)
48. Публичная страница /connect/{token} (HTML с кнопкой «Войти в ЛК»)

### Фаза 7: Автоматизация
49. services/payment_checker.py
50. scripts/cron_tasks.py — check_payments, resolve_domains, backup
51. services/telegram_bot.py — уведомления (включая уведомления о запросах на домены)
52. Systemd timer / crontab

### Фаза 8: Деплой
53. scripts/setup_vps.sh
54. nginx/proxygate.conf
55. Systemd units для backend
56. README.md — полная инструкция

---

## 12. ЗАВИСИМОСТИ

### Backend (requirements.txt)
```
fastapi==0.115.0
uvicorn[standard]==0.32.0
sqlalchemy==2.0.36
alembic==1.14.0
aiosqlite==0.20.0
pydantic==2.10.0
pydantic-settings==2.6.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.17
aiofiles==24.1.0
httpx==0.28.0
dnspython==2.7.0
aiogram==3.14.0
jinja2==3.1.4
apscheduler==3.10.4
```

### Frontend (package.json dependencies)
```json
{
  "react": "^18.3.0",
  "react-dom": "^18.3.0",
  "react-router-dom": "^6.28.0",
  "lucide-react": "^0.460.0",
  "@tanstack/react-query": "^5.60.0"
}
```

---

## 13. КЛЮЧЕВЫЕ ТЕХНИЧЕСКИЕ МОМЕНТЫ

### Почему IKEv2 + EAP-MSCHAPv2
- Windows 10/11 поддерживает из коробки (Настройки → VPN → Добавить)
- iOS/macOS — .mobileconfig с IKEv2 payload (установил и забыл)
- Сервер использует Let's Encrypt сертификат → клиенты доверяют автоматически
- Не нужно устанавливать НИКАКОЙ дополнительный софт на Windows/iOS/macOS
- Android — единственная платформа, где нужен strongSwan App (бесплатный)

### Split Tunneling — как работает
1. Клиент подключается к VPN (IKEv2)
2. В конфиге указаны КОНКРЕТНЫЕ маршруты (CIDR-блоки)
3. Только трафик к этим IP идёт через VPN-туннель
4. Весь остальной трафик — напрямую через провайдера клиента
5. Пример: openai.com (104.18.x.x) → через VPN, yandex.ru → напрямую

### Обновление маршрутов при изменении доменов
1. Админ добавляет/удаляет домены клиента
2. Backend резолвит домены → CIDR
3. Сохраняет в vpn_configs.resolved_routes
4. При следующем скачивании профиля — клиент получает актуальные маршруты
5. Для применения изменений клиенту нужно переустановить профиль
   (или перезапустить PowerShell скрипт на Windows)

### Безопасность strongSwan
- Let's Encrypt сертификат (автообновление через certbot)
- EAP-MSCHAPv2 внутри IKEv2 (пароль защищён TLS-туннелем)
- AES-256 шифрование
- Perfect Forward Secrecy (PFS)
- DPD (Dead Peer Detection) для обнаружения разрывов
- unique = replace — новое подключение вытесняет старое (один клиент = одна сессия)

### Ограничение: при изменении доменов клиента
- VPN-маршруты «вшиваются» в конфиг клиента (PowerShell/.mobileconfig)
- При изменении списка доменов → нужно заново скачать/запустить конфиг
- Proxy (PAC-файл) обновляется на лету — клиенту ничего делать не нужно
- Рекомендация клиентам: использовать VPN + PAC в комбинации
