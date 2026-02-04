#!/bin/bash
# ProxyGate VPN Diagnostic Script
# Run: sudo bash diagnose_vpn.sh
# This script checks all VPN-related configurations

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== ProxyGate VPN Diagnostic ==="
echo ""

# Function to check and report
check() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}[OK]${NC} $2"
        return 0
    else
        echo -e "${RED}[FAIL]${NC} $2"
        return 1
    fi
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

info() {
    echo -e "      $1"
}

# 1. Check if running as root
echo "[1/10] Checking permissions..."
if [ "$EUID" -eq 0 ]; then
    check 0 "Running as root"
else
    check 1 "Not running as root - some checks may fail"
fi

# 2. Check strongSwan service
echo ""
echo "[2/10] Checking strongSwan service..."
if systemctl is-active --quiet strongswan; then
    check 0 "strongswan service is running"
else
    check 1 "strongswan service is NOT running"
    info "Try: systemctl start strongswan"
fi

# Check if charon-systemd is being used (not strongswan-starter)
if systemctl is-active --quiet strongswan-starter 2>/dev/null; then
    warn "strongswan-starter is running (old service)"
    info "For swanctl configs, disable it: systemctl disable --now strongswan-starter"
fi

# 3. Check swanctl configuration
echo ""
echo "[3/10] Checking swanctl configuration..."
if [ -f /etc/swanctl/conf.d/connections.conf ]; then
    check 0 "connections.conf exists"

    # Check if config is loaded
    if swanctl --list-conns 2>/dev/null | grep -q "proxygate"; then
        check 0 "proxygate connection is loaded"
    else
        check 1 "proxygate connection NOT loaded"
        info "Try: swanctl --load-all"
    fi
else
    check 1 "connections.conf missing"
    info "Run the backend to generate config, or copy from setup"
fi

if [ -f /etc/swanctl/conf.d/secrets.conf ]; then
    check 0 "secrets.conf exists"

    # Check if EAP secrets exist
    if grep -q "eap-" /etc/swanctl/conf.d/secrets.conf 2>/dev/null; then
        check 0 "EAP secrets configured"
        EAP_COUNT=$(grep -c "eap-" /etc/swanctl/conf.d/secrets.conf 2>/dev/null || echo "0")
        info "Found $EAP_COUNT EAP user(s)"
    else
        warn "No EAP users in secrets.conf"
        info "Add clients via admin panel and sync VPN"
    fi
else
    check 1 "secrets.conf missing"
fi

# 4. Check certificates
echo ""
echo "[4/10] Checking certificates..."

CERT_DIR="/etc/swanctl/x509"
KEY_DIR="/etc/swanctl/private"
CA_DIR="/etc/swanctl/x509ca"

# Create dirs if needed
mkdir -p $CERT_DIR $KEY_DIR $CA_DIR 2>/dev/null || true

if [ -f "$CERT_DIR/fullchain.pem" ]; then
    check 0 "Server certificate exists ($CERT_DIR/fullchain.pem)"

    # Check if it's a symlink and valid
    if [ -L "$CERT_DIR/fullchain.pem" ]; then
        TARGET=$(readlink -f "$CERT_DIR/fullchain.pem")
        if [ -f "$TARGET" ]; then
            info "Symlink -> $TARGET"
        else
            check 1 "Symlink target doesn't exist: $TARGET"
        fi
    fi

    # Check certificate expiry
    EXPIRY=$(openssl x509 -enddate -noout -in "$CERT_DIR/fullchain.pem" 2>/dev/null | cut -d= -f2)
    if [ -n "$EXPIRY" ]; then
        info "Expires: $EXPIRY"

        # Check if expired
        if openssl x509 -checkend 0 -noout -in "$CERT_DIR/fullchain.pem" 2>/dev/null; then
            check 0 "Certificate is valid (not expired)"
        else
            check 1 "Certificate has EXPIRED!"
        fi
    fi

    # Check certificate CN/SAN
    CN=$(openssl x509 -subject -noout -in "$CERT_DIR/fullchain.pem" 2>/dev/null | sed 's/.*CN = //' | sed 's/,.*//')
    if [ -n "$CN" ]; then
        info "Common Name: $CN"
    fi

    SAN=$(openssl x509 -text -noout -in "$CERT_DIR/fullchain.pem" 2>/dev/null | grep -A1 "Subject Alternative Name" | tail -1 | tr ',' '\n' | grep DNS | head -3)
    if [ -n "$SAN" ]; then
        info "SANs: $(echo $SAN | tr '\n' ' ')"
    fi
else
    check 1 "Server certificate missing"
    info "Create symlink: ln -sf /etc/letsencrypt/live/YOUR_DOMAIN/fullchain.pem $CERT_DIR/fullchain.pem"
fi

if [ -f "$KEY_DIR/privkey.pem" ]; then
    check 0 "Private key exists ($KEY_DIR/privkey.pem)"
else
    check 1 "Private key missing"
    info "Create symlink: ln -sf /etc/letsencrypt/live/YOUR_DOMAIN/privkey.pem $KEY_DIR/privkey.pem"
fi

if [ -f "$CA_DIR/chain.pem" ]; then
    check 0 "CA chain exists ($CA_DIR/chain.pem)"
else
    warn "CA chain missing (optional but recommended)"
    info "Create symlink: ln -sf /etc/letsencrypt/live/YOUR_DOMAIN/chain.pem $CA_DIR/chain.pem"
fi

# 5. Check server identity match
echo ""
echo "[5/10] Checking server identity..."
if [ -f /etc/swanctl/conf.d/connections.conf ]; then
    SERVER_ID=$(grep "id = " /etc/swanctl/conf.d/connections.conf 2>/dev/null | head -1 | sed 's/.*id = //' | tr -d ' ')
    if [ -n "$SERVER_ID" ]; then
        info "Server ID in config: $SERVER_ID"

        if [ -f "$CERT_DIR/fullchain.pem" ]; then
            # Check if server ID matches certificate
            if openssl x509 -text -noout -in "$CERT_DIR/fullchain.pem" 2>/dev/null | grep -q "$SERVER_ID"; then
                check 0 "Server ID matches certificate"
            else
                check 1 "Server ID ($SERVER_ID) may not match certificate!"
                info "The server ID must match the certificate's CN or SAN"
            fi
        fi
    fi
fi

# 6. Check firewall
echo ""
echo "[6/10] Checking firewall..."
if command -v ufw &> /dev/null; then
    UFW_STATUS=$(ufw status 2>/dev/null)
    if echo "$UFW_STATUS" | grep -q "Status: active"; then
        check 0 "UFW is active"

        if echo "$UFW_STATUS" | grep -q "500/udp"; then
            check 0 "UDP 500 (IKE) is allowed"
        else
            check 1 "UDP 500 (IKE) NOT allowed"
            info "Run: ufw allow 500/udp"
        fi

        if echo "$UFW_STATUS" | grep -q "4500/udp"; then
            check 0 "UDP 4500 (NAT-T) is allowed"
        else
            check 1 "UDP 4500 (NAT-T) NOT allowed"
            info "Run: ufw allow 4500/udp"
        fi
    else
        warn "UFW is not active"
    fi
else
    info "UFW not installed, check your firewall manually"
fi

# 7. Check IP forwarding
echo ""
echo "[7/10] Checking IP forwarding..."
IP_FORWARD=$(cat /proc/sys/net/ipv4/ip_forward 2>/dev/null)
if [ "$IP_FORWARD" = "1" ]; then
    check 0 "IPv4 forwarding enabled"
else
    check 1 "IPv4 forwarding DISABLED"
    info "Run: sysctl -w net.ipv4.ip_forward=1"
fi

# 8. Check NAT rules
echo ""
echo "[8/10] Checking NAT rules..."
NAT_RULES=$(iptables -t nat -L POSTROUTING -n 2>/dev/null | grep -c MASQUERADE || echo "0")
if [ "$NAT_RULES" -gt 0 ]; then
    check 0 "MASQUERADE rules found ($NAT_RULES)"
else
    check 1 "No MASQUERADE rules"
    info "VPN clients won't be able to access the internet"
fi

# 9. Check listening ports
echo ""
echo "[9/10] Checking listening ports..."
if ss -uln | grep -q ":500 "; then
    check 0 "UDP 500 is listening"
else
    check 1 "UDP 500 NOT listening"
    info "strongSwan may not be running properly"
fi

if ss -uln | grep -q ":4500 "; then
    check 0 "UDP 4500 is listening"
else
    check 1 "UDP 4500 NOT listening"
fi

# 10. Check swanctl credentials
echo ""
echo "[10/10] Checking swanctl credentials..."
CREDS_OUTPUT=$(swanctl --list-creds 2>&1)
if echo "$CREDS_OUTPUT" | grep -q "fullchain.pem"; then
    check 0 "Server certificate loaded in swanctl"
else
    check 1 "Server certificate NOT loaded"
    info "Run: swanctl --load-creds"
fi

if echo "$CREDS_OUTPUT" | grep -q "privkey.pem"; then
    check 0 "Private key loaded in swanctl"
else
    check 1 "Private key NOT loaded"
fi

# Summary
echo ""
echo "=== Summary ==="
echo ""
echo "Quick fixes:"
echo "  1. Reload all configs: swanctl --load-all"
echo "  2. Restart strongSwan: systemctl restart strongswan"
echo "  3. Check logs: journalctl -u strongswan -f"
echo ""
echo "If VPN still doesn't connect:"
echo "  1. Verify DNS resolves to this server"
echo "  2. Check certificate matches domain"
echo "  3. Ensure client credentials are in secrets.conf"
echo "  4. Check server logs during connection attempt:"
echo "     journalctl -u strongswan -f"
echo ""

# Show recent strongSwan logs
echo "=== Recent strongSwan logs ==="
journalctl -u strongswan --no-pager -n 20 2>/dev/null || echo "Unable to read logs"
