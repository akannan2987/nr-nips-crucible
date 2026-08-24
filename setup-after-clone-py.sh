#!/bin/bash

# Crucible: Pandora Toolbox Enhancement (v2.0) - Python Backend Bootstrap
#
# One-shot setup after cloning, for BOTH macOS and the RHEL8 VM. It:
#   1. (optional) copies SSL certificates into certs/  (VM: from the corporate cert store)
#   2. builds the crucible-py image        (podman or docker, auto-detected)
#   3. starts the container                (HTTPS when certs exist, else HTTP)
#   4. verifies the API answers
#   5. (optional) installs the health-monitoring cron job
#
# Non-interactive use (e.g. from another script):
#   SETUP_MONITOR=y ./setup-after-clone-py.sh      # or SETUP_MONITOR=n

set -e
cd "$(dirname "$0")"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   🧪 Crucible: Pandora Toolbox Enhancement (v2.0)        ║"
echo "║      Python Backend — Setup After Clone                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: SSL certificates (optional — skipped gracefully) ────────
# Site-specific values (corporate cert-store path, VM hostname) are NOT
# hardcoded here: put them in an untracked .env.local file next to this
# script (it is gitignored), or pass them as environment variables.
# Environment variables win over .env.local. Example .env.local:
#   CERT_SOURCE=/path/to/corporate/cert/store
#   CERT_HOSTNAME=your-vm.example.com   # optional; defaults to `hostname -f`
# On a Mac neither is usually set → the app starts in HTTP mode.
if [ -f ".env.local" ]; then
    _env_cert_source="$CERT_SOURCE"; _env_cert_hostname="$CERT_HOSTNAME"
    # shellcheck disable=SC1091
    . ./.env.local
    # values already set in the environment take precedence over .env.local
    CERT_SOURCE="${_env_cert_source:-$CERT_SOURCE}"
    CERT_HOSTNAME="${_env_cert_hostname:-$CERT_HOSTNAME}"
fi
CERT_SOURCE="${CERT_SOURCE:-}"
CERT_HOSTNAME="${CERT_HOSTNAME:-$(hostname -f 2>/dev/null || hostname)}"

echo "Step 1: SSL certificates"
if [ -f "certs/server.crt" ] && [ -f "certs/server.key" ]; then
    echo -e "  ${GREEN}✓ certs/ already populated — keeping existing certificates${NC}"
elif [ -d "$CERT_SOURCE" ]; then
    mkdir -p certs
    cp "$CERT_SOURCE/${CERT_HOSTNAME}.cer" certs/server.crt
    cp "$CERT_SOURCE/${CERT_HOSTNAME}.key" certs/server.key
    chmod 600 certs/server.key
    # The cert and key must be a matching pair — verify via modulus hash.
    CERT_HASH=$(openssl x509 -noout -modulus -in certs/server.crt | openssl md5 | cut -d'=' -f2)
    KEY_HASH=$(openssl rsa -noout -modulus -in certs/server.key 2>/dev/null | openssl md5 | cut -d'=' -f2)
    if [ "$CERT_HASH" = "$KEY_HASH" ]; then
        echo -e "  ${GREEN}✓ Nestlé certificates copied and verified${NC}"
    else
        echo -e "  ${RED}✗ Certificate and key do not match — removing them; continuing with HTTP${NC}"
        rm -f certs/server.crt certs/server.key
    fi
else
    if [ -z "$CERT_SOURCE" ]; then
        echo -e "  ${YELLOW}– No certificate store configured (normal on macOS)${NC}"
    else
        echo -e "  ${YELLOW}– No certificate store at ${CERT_SOURCE}${NC}"
    fi
    echo "    → will start in HTTP mode. For HTTPS later: ./setup-ssl.sh (self-signed)"
    echo "      or CERT_SOURCE=/path ./setup-after-clone-py.sh, then ./container-py.sh start-ssl"
    echo "      (persist site values in .env.local — see the comment at Step 1)"
fi
echo ""

# ── Step 2: build the image ─────────────────────────────────────────
echo "Step 2: Building the crucible-py image (first build takes a few minutes)..."
./container-py.sh build
echo ""

# ── Step 3: start (HTTPS when certs exist, else HTTP) ───────────────
echo "Step 3: Starting the container..."
if [ -f "certs/server.crt" ] && [ -f "certs/server.key" ]; then
    PROTO="https"
    ./container-py.sh start-ssl
else
    PROTO="http"
    ./container-py.sh start
fi
echo ""

# ── Step 4: verify ─────────────────────────────────────────────
echo "Step 4: Verifying the API..."
ok=""
for i in $(seq 1 30); do
    if curl --noproxy '*' -ks "${PROTO}://localhost:49160/api/stats" | grep -q '"chemicals"'; then
        ok=1; break
    fi
    sleep 2
done
if [ -n "$ok" ]; then
    echo -e "  ${GREEN}✓ API is answering:${NC}"
    curl --noproxy '*' -ks "${PROTO}://localhost:49160/api/stats" | head -c 200; echo ""
else
    echo -e "  ${RED}✗ API did not answer within 60s — check: ./container-py.sh logs${NC}"
    exit 1
fi
echo ""

# ── Step 5: health-monitoring cron (optional) ───────────────────
echo "Step 5: Health monitoring (cron job, every 5 minutes)"
REPLY="${SETUP_MONITOR:-}"
if [ -z "$REPLY" ]; then
    read -p "  Install/refresh the monitoring cron job? (y/n) " -n 1 -r; echo
fi
if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    chmod +x monitor.sh
    # rootless podman needs USER + XDG_RUNTIME_DIR in cron's minimal env (on a
    # network-mounted home it otherwise resolves its storage to a bad path and
    # fails, so monitor.sh could not restart the container).
    # cron runs with a minimal PATH (/usr/bin:/bin), which on macOS does NOT
    # include podman (/opt/podman/bin) or Homebrew (/opt/homebrew/bin). Capture
    # the runtime's directory now and prepend it, or monitor.sh cannot find the
    # container runtime and could never restart anything.
    RUNTIME_BIN="$(command -v podman 2>/dev/null || command -v docker 2>/dev/null)"
    RUNTIME_DIR="$(dirname "${RUNTIME_BIN:-/usr/bin/true}")"
    CRON_LINE="*/5 * * * * cd $(pwd) && PATH=${RUNTIME_DIR}:/usr/local/bin:/usr/bin:/bin USER=$(id -un) XDG_RUNTIME_DIR=/run/user/$(id -u) CONTAINER_NAME=crucible-py API_URL=${PROTO}://localhost:49160/api/stats ./monitor.sh"
    # Replace any previous monitor.sh entry so re-runs don't stack duplicate
    # cron lines.
    { crontab -l 2>/dev/null | grep -v "monitor.sh" || true; printf '%s\n' "$CRON_LINE"; } | crontab -
    # Trust but verify — macOS cron can silently drop a first-time install.
    if crontab -l 2>/dev/null | grep -q "crucible-py.*monitor.sh"; then
        echo -e "  ${GREEN}✓ Monitoring cron installed (old monitor.sh entries replaced):${NC}"
        echo "    $CRON_LINE"
    else
        echo -e "  ${RED}✗ Cron entry did not persist. Install it manually:${NC}"
        echo "    (crontab -l 2>/dev/null; echo '$CRON_LINE') | crontab -"
    fi
else
    echo "  – Skipped. Install later by re-running with SETUP_MONITOR=y"
fi
echo ""

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   ✅ Python backend setup complete!                       ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Access the application at:"
echo "  ${PROTO}://localhost:49160"
echo "  ${PROTO}://$(hostname):49160   (from another machine)"
echo ""
echo "Useful commands:"
echo "  ./container-py.sh status    - container + API health"
echo "  ./container-py.sh logs      - view logs"
echo "  ./container-py.sh backup    - consistent database backup"
echo ""
echo "On the RHEL8 VM, also set up auto-start on boot (survives reboots):"
echo "  → DEPLOYMENT.md, 'Auto-start on boot (systemd)' / docs/INSTALL-RHEL8.md §4"
