#!/bin/bash

# Crucible Health Monitor
# This script checks if the application is responding and restarts if needed

# ── Which instance? ─────────────────────────────────────────────────
# The cron line written by setup-after-clone-py.sh names the container and
# the address explicitly (CONTAINER_NAME=… API_URL=…), and those always win.
# Run by hand from a checkout, the script reads that folder's .env.local so
# that `./monitor.sh` in the beta folder probes — and, if need be, restarts —
# beta, never production (docs/14-beta-instance.md).
_here="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$_here/.env.local" ]; then
    _inst="${CRUCIBLE_INSTANCE:-}"; _cport="${CRUCIBLE_PORT:-}"; _https="${USE_HTTPS:-}"
    # shellcheck disable=SC1091
    . "$_here/.env.local"
    CRUCIBLE_INSTANCE="${_inst:-${CRUCIBLE_INSTANCE:-}}"
    CRUCIBLE_PORT="${_cport:-${CRUCIBLE_PORT:-}}"
    USE_HTTPS="${_https:-${USE_HTTPS:-}}"
fi
CRUCIBLE_INSTANCE="${CRUCIBLE_INSTANCE:-}"
CONTAINER_NAME="${CONTAINER_NAME:-crucible-py${CRUCIBLE_INSTANCE:+-$CRUCIBLE_INSTANCE}}"
# The port: CRUCIBLE_PORT from .env.local or the environment, else 49160. A
# generic PORT in the shell is IGNORED, exactly as container-py.sh ignores
# it. Until v2.22.1 it was honoured, and on a server whose shell exports
# PORT=3000 for something else this monitor, run by hand in a folder with
# no CRUCIBLE_PORT, probed port 3000, found nothing, and restarted a healthy
# production application (2026-09-22, lesson 39). The cron line names
# API_URL outright and never depended on this.
if [ -n "${PORT:-}" ] && [ -z "${CRUCIBLE_PORT:-}" ] && [ "${PORT}" != "49160" ]; then
    echo "ℹ  Ignoring PORT=${PORT} from the environment (use CRUCIBLE_PORT=<n> to override); using 49160."
fi
PORT="${CRUCIBLE_PORT:-49160}"

# Runtime detection (same convention as container*.sh)
if [ -n "$CONTAINER_RUNTIME" ]; then RUNTIME="$CONTAINER_RUNTIME"
elif command -v podman >/dev/null 2>&1; then RUNTIME="podman"
elif command -v docker >/dev/null 2>&1; then RUNTIME="docker"
else echo "Neither podman nor docker found"; exit 1; fi
# Default: plain HTTP (./container-py.sh start), or HTTPS when the folder's
# .env.local says USE_HTTPS=true. The cron line sets API_URL explicitly.
if [ "${USE_HTTPS:-false}" = "true" ]; then _scheme="https"; else _scheme="http"; fi
API_URL="${API_URL:-${_scheme}://localhost:${PORT}/api/health}"
# One log per instance, so two monitors on one machine never interleave.
LOG_FILE="${LOG_FILE:-/tmp/crucible-monitor${CRUCIBLE_INSTANCE:+-$CRUCIBLE_INSTANCE}.log}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

check_health() {
    # Since v2.22.0 the probe is /api/health: the one route that stays open
    # when the login is on, answering 200 with no data. An older cron line
    # may still name /api/stats, which answers 401 once the login is on and
    # would have this monitor restart a healthy application every five
    # minutes. So the probe always tries /api/health at the same address
    # first, and falls back to the named URL only when /api/health does not
    # exist there (a container older than v2.22.0 answers 404).
    local base code
    base="${API_URL%/api/*}"
    code=$(curl --noproxy '*' -k -s -w "%{http_code}" -o /dev/null "${base}/api/health" --max-time 10)
    if [ "$code" = "200" ]; then
        return 0  # Healthy
    fi
    if [ "$code" = "404" ]; then
        code=$(curl --noproxy '*' -k -s -w "%{http_code}" -o /dev/null "$API_URL" --max-time 10)
        [ "$code" = "200" ] && return 0
    fi
    return 1  # Unhealthy
}

# A second line of defence against the same mistake: never restart a
# container for not answering at a port it does not publish. If the probe's
# port and the container's published port disagree, the probe is wrong, not
# the application, and the only right move is to say so and stop.
probe_port_matches_container() {
    local probe_port published
    probe_port=$(printf '%s' "$API_URL" | sed -n 's|^[a-z]*://[^:/]*:\([0-9]\{1,\}\).*|\1|p')
    published=$($RUNTIME port "$CONTAINER_NAME" 2>/dev/null | sed -n 's/.*:\([0-9]\{1,\}\)$/\1/p' | head -1)
    [ -z "$probe_port" ] || [ -z "$published" ] || [ "$probe_port" = "$published" ]
}

restart_container() {
    if ! probe_port_matches_container; then
        log "✗ Not restarting ${CONTAINER_NAME}: the probe asked ${API_URL}, but the container publishes port $($RUNTIME port "$CONTAINER_NAME" 2>/dev/null | sed -n 's/.*:\([0-9]\{1,\}\)$/\1/p' | head -1). Fix API_URL or CRUCIBLE_PORT; the application was not touched."
        return 1
    fi
    log "⚠️  Container ${CONTAINER_NAME} unhealthy, restarting..."
    # On the server the systemd service owns the container (v2.21.2):
    # restart through it, or systemd and podman fight over one container.
    local unit="container-${CONTAINER_NAME}.service"
    if command -v systemctl >/dev/null 2>&1 && systemctl --user is-active --quiet "$unit" 2>/dev/null; then
        log "   through the service ${unit}"
        systemctl --user restart "$unit"
    else
        $RUNTIME restart "$CONTAINER_NAME"
    fi
    sleep 5
    
    if check_health; then
        log "✓ Container restarted successfully"
    else
        log "✗ Container restart failed"
    fi
}

# Main monitoring loop
log "Starting health check of ${CONTAINER_NAME} at ${API_URL}..."

if ! check_health; then
    log "⚠️  Health check failed for ${CONTAINER_NAME}!"
    restart_container
else
    log "✓ ${CONTAINER_NAME} is healthy"
fi
