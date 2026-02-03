# ProxyGate

VPN/Proxy Access Management System with IKEv2/IPsec and HTTP/SOCKS5 proxy support.

## Features

- **IKEv2/IPsec VPN** - Native support in Windows, iOS, macOS (no client installation required)
- **HTTP/SOCKS5 Proxy** - 3proxy with per-client ACL
- **Split Tunneling** - Only configured domains go through VPN, rest goes directly
- **Per-client domain lists** - Each client has their own set of allowed domains
- **Admin Panel** - Full client management, payments, domain templates
- **Client Portal** - Self-service profile downloads, domain requests

## Tech Stack

- **Backend**: Python 3.12 + FastAPI + SQLAlchemy 2.0
- **Frontend**: React 18 + Vite + Tailwind CSS
- **VPN**: strongSwan 5.9+ (IKEv2/IPsec with EAP-MSCHAPv2)
- **Proxy**: 3proxy 0.9.x
- **Database**: SQLite (easily migrated to PostgreSQL)
- **Web Server**: Nginx (reverse proxy + SSL)
- **SSL**: Let's Encrypt (also used for IKEv2 server certificate)

## Quick Start

### Development

1. Backend:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python scripts/init_db.py
uvicorn app.main:app --reload
```

2. Frontend:
```bash
cd frontend
npm install
npm run dev
```

### Production Deployment

1. Prepare VPS (Ubuntu 24.04):
```bash
sudo bash backend/scripts/setup_vps.sh
```

2. Configure DNS A record: `vpn.yourdomain.com` -> VPS IP

3. Get SSL certificate:
```bash
certbot --nginx -d vpn.yourdomain.com
```

4. Create certificate symlinks for strongSwan:
```bash
ln -sf /etc/letsencrypt/live/vpn.yourdomain.com/fullchain.pem /etc/swanctl/x509/fullchain.pem
ln -sf /etc/letsencrypt/live/vpn.yourdomain.com/privkey.pem /etc/swanctl/private/privkey.pem
ln -sf /etc/letsencrypt/live/vpn.yourdomain.com/chain.pem /etc/swanctl/x509ca/chain.pem
```

5. Deploy application:
```bash
# Clone/upload to /opt/proxygate/
cd /opt/proxygate/backend
source ../venv/bin/activate
pip install -r requirements.txt
python scripts/init_db.py

cd /opt/proxygate/frontend
npm install
npm run build
```

6. Configure and start services:
```bash
# Nginx
cp nginx/proxygate.conf /etc/nginx/sites-available/
ln -s /etc/nginx/sites-available/proxygate.conf /etc/nginx/sites-enabled/
nginx -t && systemctl restart nginx

# strongSwan
systemctl restart strongswan-starter
swanctl --load-all

# Backend
systemctl enable proxygate
systemctl start proxygate
```

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Server
VPS_PUBLIC_IP=51.xx.xx.xx
VPS_DOMAIN=vpn.yourdomain.com

# Admin credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_strong_password

# Secret key for JWT
SECRET_KEY=your_random_64_char_string

# Telegram notifications (optional)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
ADMIN_TELEGRAM_ID=123456789
```

## API Documentation

- Admin API: `/api/admin/...` (requires admin JWT)
- Portal API: `/api/portal/...` (requires client JWT)
- Public: `/connect/{token}`, `/download/{token}/*`, `/pac/{token}`

Interactive docs: `https://vpn.yourdomain.com/docs`

## Cron Tasks

Add to crontab:
```bash
# Check payments every 15 minutes
*/15 * * * * /opt/proxygate/venv/bin/python /opt/proxygate/backend/scripts/cron_tasks.py check_payments

# Update DNS routes every 30 minutes
*/30 * * * * /opt/proxygate/venv/bin/python /opt/proxygate/backend/scripts/cron_tasks.py resolve_domains

# Daily backup at 3 AM
0 3 * * * /opt/proxygate/venv/bin/python /opt/proxygate/backend/scripts/cron_tasks.py backup
```

## Client Profiles

- **Windows**: PowerShell script (.ps1) - creates VPN connection with routes
- **iOS/macOS**: .mobileconfig - IKEv2 profile with On-Demand and split tunneling
- **Android**: .sswan - strongSwan app profile

## License

MIT
