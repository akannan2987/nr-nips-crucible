#!/bin/bash

# Crucible: Pandora Toolbox Enhancement (v2.0) - Python Backend Container Management
#
# Runtime-agnostic: works with BOTH podman and docker using identical
# subcommands. Selection order:
#   1. CONTAINER_RUNTIME=podman|docker  (explicit override)
#   2. podman, if installed
#   3. docker, if installed
#
# All settings are env-overridable:
#   CRUCIBLE_PORT=<n>   host+container HTTP port (default 49160; a generic
#                       PORT env var is ignored to avoid shared-VM clashes)
#   HOST_BIND=<ip>      published-port interface (see below)
#   PLATFORM=linux/amd64  cross-build target (e.g. building amd64 on a Mac)

IMAGE_NAME="crucible-py"
CONTAINER_NAME="crucible-py"
DATA_DIR="$(pwd)/data"
BACKUP_DIR="${BACKUP_DIR:-$(pwd)/backups}"
CERTS_DIR="$(pwd)/certs"

# ── PostgreSQL (optional) ───────────────────────────────────────────
# SQLite (data/crucible.db) is the DEFAULT and needs nothing extra. Set
# USE_POSTGRES=true to run the app against a managed Postgres container:
#   ./container-py.sh db-start          # bring up Postgres (once)
#   USE_POSTGRES=true ./container-py.sh start        # app → Postgres
# The app container joins DB_NETWORK and reaches the database at
# <DB_CONTAINER_NAME>:5432; schema is created/upgraded on boot by
# backend/scripts/db_bootstrap.py (Alembic).
USE_POSTGRES="${USE_POSTGRES:-false}"
DB_CONTAINER_NAME="${DB_CONTAINER_NAME:-crucible-db}"
DB_NETWORK="${DB_NETWORK:-crucible-net}"
DB_VOLUME="${DB_VOLUME:-crucible-pgdata}"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-docker.io/library/postgres:16-alpine}"
POSTGRES_USER="${POSTGRES_USER:-crucible}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-crucible}"
POSTGRES_DB="${POSTGRES_DB:-crucible}"
# Host port for external psql access (container-to-container uses 5432 on
# the shared network directly, regardless of this value).
DB_HOST_PORT="${DB_HOST_PORT:-5432}"
# Connection string the app uses when USE_POSTGRES=true. Override with
# DATABASE_URL to point at an external/managed Postgres instead.
APP_DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${DB_CONTAINER_NAME}:5432/${POSTGRES_DB}}"

# ── Port selection ──────────────────────────────────────────────────
# Use CRUCIBLE_PORT to override the port. A generic PORT variable from the
# environment is deliberately IGNORED: shared dev machines often export
# PORT for unrelated apps (observed on the RHEL8 VM, where PORT=3000 made
# the container bind the wrong port).
if [ -n "$CRUCIBLE_PORT" ]; then
    PORT="$CRUCIBLE_PORT"
else
    if [ -n "$PORT" ] && [ "$PORT" != "49160" ]; then
        echo "ℹ  Ignoring PORT=$PORT from the environment (use CRUCIBLE_PORT=<n> to override); using 49160."
    fi
    PORT=49160
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ── Container runtime detection ─────────────────────────────────────
# Note: on macOS the podman VM also exposes a docker-compatible socket at
# /var/run/docker.sock. Detection is by CLI presence (not by socket), so
# that socket cannot confuse the choice.
if [ -n "$CONTAINER_RUNTIME" ]; then
    RUNTIME="$CONTAINER_RUNTIME"
    if ! command -v "$RUNTIME" >/dev/null 2>&1; then
        echo -e "${RED}✗ CONTAINER_RUNTIME=$RUNTIME but '$RUNTIME' is not installed${NC}"
        exit 1
    fi
elif command -v podman >/dev/null 2>&1; then
    RUNTIME="podman"
elif command -v docker >/dev/null 2>&1; then
    RUNTIME="docker"
else
    echo -e "${RED}✗ Neither podman nor docker found. Install one, or set CONTAINER_RUNTIME.${NC}"
    exit 1
fi

# ── macOS podman: the client talks to a Linux VM that does NOT auto-start
# on login. Check it before any command, so the user gets a clear message
# instead of a cryptic socket error.
check_podman_machine() {
    if [ "$RUNTIME" = "podman" ] && [ "$(uname -s)" = "Darwin" ]; then
        local state
        state=$(podman machine inspect --format '{{.State}}' 2>/dev/null)
        if [ "$state" != "running" ]; then
            echo -e "${RED}✗ The podman machine VM is not running (state: ${state:-not created}).${NC}"
            echo ""
            echo "  Start it with:   podman machine start"
            echo "  (create first with 'podman machine init' if it does not exist)"
            exit 1
        fi
    fi
}

# ── Host interface for published ports ──
# Linux (RHEL8 VM): 0.0.0.0 so the app is reachable from other machines.
# macOS: Apple's remoted daemon occupies ports 49152+ on a link-local IPv6
# address, which makes a wildcard bind of 49160 fail — 127.0.0.1 avoids
# that and is all local development needs. Override with HOST_BIND=<ip>.
if [ -z "$HOST_BIND" ]; then
    if [ "$(uname -s)" = "Darwin" ]; then
        HOST_BIND="127.0.0.1"
    else
        HOST_BIND="0.0.0.0"
    fi
fi

show_help() {
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║   🧪 Crucible: Pandora Toolbox Enhancement (v2.0)        ║"
    echo "║      Python Backend Container Management                  ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo ""
    echo "Usage: $0 [command]        (runtime: $RUNTIME)"
    echo ""
    echo "Commands:"
    echo "  build       Build the Python backend image"
    echo "  start       Start the container (HTTP, port ${PORT})"
    echo "  start-ssl   Start with HTTPS (needs certs/server.crt + server.key)"
    echo "  stop        Stop the container"
    echo "  restart     Restart the container"
    echo "  rebuild     Rebuild image and restart container"
    echo "  backup      Consistent database backup → backups/ (safe while running)"
    echo "  restore <f> Restore a backup file (stops app, swaps db, restarts)"
    echo "  logs        Show container logs (follow)"
    echo "  status      Show container status + /api/stats healthcheck"
    echo "  shell       Open a shell in the container"
    echo "  clean       Remove container and image"
    echo "  db-start    Start the PostgreSQL container (for USE_POSTGRES=true)"
    echo "  db-stop     Stop the PostgreSQL container"
    echo "  db-shell    Open a psql shell in the PostgreSQL container"
    echo "  help        Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  CONTAINER_RUNTIME=podman|docker   force a runtime (default: auto-detect)"
    echo "  CRUCIBLE_PORT=<n>                 port (default 49160; generic PORT is ignored)"
    echo "  HOST_BIND=<ip>                    published-port interface"
    echo "  PLATFORM=linux/amd64              cross-build target platform"
    echo "  USE_POSTGRES=true                 run the app against PostgreSQL (default: SQLite)"
    echo "  DATABASE_URL=<url>                external Postgres URL (overrides the managed db)"
    echo ""
}

build_image() {
    check_podman_machine
    echo -e "${YELLOW}Building ${IMAGE_NAME} image with ${RUNTIME}...${NC}"

    local build_args=(-f backend/Dockerfile -t "${IMAGE_NAME}:latest")
    # podman's native OCI format silently drops the Dockerfile HEALTHCHECK;
    # --format docker preserves it. Docker needs (and accepts) no such flag.
    if [ "$RUNTIME" = "podman" ]; then
        build_args=(--format docker "${build_args[@]}")
    fi
    # Optional cross-build, e.g. PLATFORM=linux/amd64 on an arm64 Mac.
    if [ -n "$PLATFORM" ]; then
        build_args=(--platform "$PLATFORM" "${build_args[@]}")
    fi

    if $RUNTIME build "${build_args[@]}" .; then
        echo -e "${GREEN}✓ Image built successfully${NC}"
    else
        echo -e "${RED}✗ Failed to build image${NC}"
        exit 1
    fi
}

start_container() {
    check_podman_machine
    # Set when we reuse an existing container: its published port is whatever
    # it was created with, NOT the current $PORT.
    local running_port=""
    if $RUNTIME ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        echo -e "${YELLOW}Container already exists. Starting...${NC}"
        $RUNTIME start ${CONTAINER_NAME}
        # An existing container keeps its original port/env — a changed
        # CRUCIBLE_PORT/HOST_BIND/USE_POSTGRES only takes effect after
        # `rebuild` (or stop + rm + start). Report the real port, not the
        # requested one, so the printed URL is never wrong.
        running_port=$($RUNTIME port ${CONTAINER_NAME} 2>/dev/null \
            | sed -n 's/.*:\([0-9]\{1,\}\)$/\1/p' | head -1)
        if [ -n "$running_port" ] && [ "$running_port" != "${PORT}" ]; then
            echo -e "${YELLOW}⚠ Existing container is published on ${running_port}, not ${PORT}."
            echo -e "  Env changes need: ./container-py.sh rebuild${NC}"
        fi
    else
        echo -e "${YELLOW}Creating and starting container (runtime: ${RUNTIME}, port: ${PORT})...${NC}"
        mkdir -p "${DATA_DIR}"

        local pg_args=()
        if [ "$USE_POSTGRES" = "true" ]; then
            db_start || { echo -e "${RED}✗ Postgres not ready${NC}"; exit 1; }
            pg_args=(--network "${DB_NETWORK}" -e DATABASE_URL="${APP_DATABASE_URL}" -e AUTO_INIT_DB=false)
            echo -e "${BLUE}Using PostgreSQL: ${DB_CONTAINER_NAME}:5432/${POSTGRES_DB}${NC}"
        fi

        # :Z relabels the volume for SELinux (required on RHEL8; harmless
        # no-op on macOS and non-SELinux hosts, for both runtimes).
        $RUNTIME run -d \
            --name ${CONTAINER_NAME} \
            -p ${HOST_BIND}:${PORT}:${PORT} \
            -v "${DATA_DIR}:/app/data:Z" \
            -e PORT=${PORT} \
            "${pg_args[@]}" \
            --restart unless-stopped \
            ${IMAGE_NAME}:latest
    fi

    if [ $? -eq 0 ]; then
        local shown_port="${running_port:-${PORT}}"
        echo -e "${GREEN}✓ Container started successfully${NC}"
        echo ""
        echo "Access the application at:"
        echo "  http://localhost:${shown_port}"
        echo "  http://$(hostname):${shown_port}   (from another machine)"
    else
        echo -e "${RED}✗ Failed to start container${NC}"
        exit 1
    fi
}

stop_container() {
    check_podman_machine
    echo -e "${YELLOW}Stopping container '${CONTAINER_NAME}' (Python backend)...${NC}"
    if $RUNTIME stop ${CONTAINER_NAME} 2>/dev/null; then
        echo -e "${GREEN}✓ Container '${CONTAINER_NAME}' stopped${NC}"
    else
        echo -e "${YELLOW}Container '${CONTAINER_NAME}' was not running${NC}"
    fi
}

restart_container() {
    stop_container
    sleep 2
    start_container
}

rebuild() {
    build_image
    check_podman_machine
    # Preserve the protocol mode across the rebuild: an HTTPS deployment
    # (start-ssl) must come back as HTTPS, not silently drop to HTTP.
    local was_https="false"
    if $RUNTIME inspect ${CONTAINER_NAME} --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null \
        | grep -q '^USE_HTTPS=true$'; then
        was_https="true"
    fi
    $RUNTIME stop ${CONTAINER_NAME} 2>/dev/null
    $RUNTIME rm ${CONTAINER_NAME} 2>/dev/null
    if [ "$was_https" = "true" ]; then
        start_container_ssl
    else
        start_container
    fi
}

start_container_ssl() {
    check_podman_machine
    if [ ! -f "${CERTS_DIR}/server.crt" ] || [ ! -f "${CERTS_DIR}/server.key" ]; then
        echo -e "${RED}✗ SSL certificates not found in ${CERTS_DIR}/${NC}"
        echo ""
        echo "  Self-signed (dev):    ./setup-ssl.sh"
        echo "  Nestlé certs (VM):    ./setup-after-clone-py.sh   (copies from the corporate cert store)"
        exit 1
    fi

    # Recreate the container: TLS mode changes its env + mounts.
    if $RUNTIME ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        echo -e "${YELLOW}Recreating container '${CONTAINER_NAME}' with HTTPS...${NC}"
        $RUNTIME stop ${CONTAINER_NAME} 2>/dev/null
        $RUNTIME rm ${CONTAINER_NAME} 2>/dev/null
    fi
    mkdir -p "${DATA_DIR}"

    local pg_args=()
    if [ "$USE_POSTGRES" = "true" ]; then
        db_start || { echo -e "${RED}✗ Postgres not ready${NC}"; exit 1; }
        pg_args=(--network "${DB_NETWORK}" -e DATABASE_URL="${APP_DATABASE_URL}" -e AUTO_INIT_DB=false)
        echo -e "${BLUE}Using PostgreSQL: ${DB_CONTAINER_NAME}:5432/${POSTGRES_DB}${NC}"
    fi

    $RUNTIME run -d \
        --name ${CONTAINER_NAME} \
        -p ${HOST_BIND}:${PORT}:${PORT} \
        -v "${DATA_DIR}:/app/data:Z" \
        -v "${CERTS_DIR}:/app/certs:Z,ro" \
        -e PORT=${PORT} \
        -e USE_HTTPS=true \
        -e SSL_CERT_PATH=/app/certs/server.crt \
        -e SSL_KEY_PATH=/app/certs/server.key \
        "${pg_args[@]}" \
        --restart unless-stopped \
        ${IMAGE_NAME}:latest

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Container started with HTTPS${NC}"
        echo ""
        echo -e "${BLUE}🔒 Access the application at:${NC}"
        echo "  https://localhost:${PORT}"
        echo "  https://$(hostname):${PORT}   (from another machine)"
        echo ""
        echo -e "${YELLOW}Note: self-signed certificates trigger a browser warning"
        echo -e "(Advanced → Proceed). Nestlé-signed certificates do not.${NC}"
    else
        echo -e "${RED}✗ Failed to start container with HTTPS${NC}"
        exit 1
    fi
}

backup_data() {
    check_podman_machine
    mkdir -p "${BACKUP_DIR}"
    local stamp
    stamp=$(date +%Y%m%d-%H%M%S)
    local dest="${BACKUP_DIR}/crucible-${stamp}.db"

    if [ ! -f "${DATA_DIR}/crucible.db" ]; then
        echo -e "${RED}✗ No database found at ${DATA_DIR}/crucible.db${NC}"
        exit 1
    fi

    if $RUNTIME ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        # Container running: a plain `cp` could catch SQLite mid-write and
        # produce a corrupt file. Use SQLite's online-backup API instead
        # (runs inside the container, so no sqlite3 needed on the host).
        echo -e "${YELLOW}Creating consistent online backup (app keeps running)...${NC}"
        $RUNTIME exec ${CONTAINER_NAME} python -c "
import sqlite3
src = sqlite3.connect('/app/data/crucible.db')
dst = sqlite3.connect('/app/data/.backup-tmp.db')
src.backup(dst)
dst.close(); src.close()
"
        mv "${DATA_DIR}/.backup-tmp.db" "${dest}"
    else
        # Container stopped: nothing is writing, a plain copy is safe.
        echo -e "${YELLOW}Container not running — plain file copy is safe...${NC}"
        cp "${DATA_DIR}/crucible.db" "${dest}"
    fi

    echo -e "${GREEN}✓ Backup complete:${NC}"
    ls -lh "${BACKUP_DIR}" | grep "${stamp}"
}

restore_data() {
    local src="$1"
    if [ -z "$src" ]; then
        echo "Usage: $0 restore <backup-file.db>"
        echo ""
        echo "Available backups in ${BACKUP_DIR}:"
        ls -lh "${BACKUP_DIR}"/*.db 2>/dev/null || echo "  (none found)"
        exit 1
    fi
    if [ ! -f "$src" ]; then
        echo -e "${RED}✗ Backup file not found: $src${NC}"
        exit 1
    fi

    check_podman_machine
    echo -e "${YELLOW}Stopping container '${CONTAINER_NAME}' before restore...${NC}"
    $RUNTIME stop ${CONTAINER_NAME} 2>/dev/null

    # Keep the current database as a safety net — restore is destructive.
    if [ -f "${DATA_DIR}/crucible.db" ]; then
        mv "${DATA_DIR}/crucible.db" "${DATA_DIR}/crucible.db.pre-restore"
        echo "  (current database kept as data/crucible.db.pre-restore)"
    fi

    cp "$src" "${DATA_DIR}/crucible.db"
    echo -e "${GREEN}✓ Restored $(basename "$src") → data/crucible.db${NC}"

    start_container
    echo ""
    echo "Verify with: curl --noproxy '*' -sk $(api_url)"
}

show_logs() {
    check_podman_machine
    echo -e "${YELLOW}Container logs:${NC}"
    $RUNTIME logs -f ${CONTAINER_NAME}
}

# Echo the URL the app is actually answering on. In TLS mode (start-ssl) the
# app serves HTTPS on the SAME port and refuses plain HTTP, so a hardcoded
# http:// probe silently returns nothing.
api_url() {
    if $RUNTIME inspect ${CONTAINER_NAME} --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null \
        | grep -q '^USE_HTTPS=true$'; then
        echo "https://localhost:${PORT}/api/stats"
    else
        echo "http://localhost:${PORT}/api/stats"
    fi
}

show_status() {
    check_podman_machine
    echo -e "${YELLOW}Container status (runtime: ${RUNTIME}):${NC}"
    $RUNTIME ps -a --filter name=${CONTAINER_NAME} --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    if $RUNTIME ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        echo -e "${GREEN}✓ Container is running${NC}"
        echo ""
        # -k so a self-signed dev certificate doesn't fail the check.
        echo "Testing API endpoint ($(api_url))..."
        curl --noproxy '*' -sk "$(api_url)" | head -100
        echo ""
    else
        echo -e "${RED}✗ Container is not running${NC}"
    fi
}

open_shell() {
    check_podman_machine
    echo -e "${YELLOW}Opening shell in container...${NC}"
    $RUNTIME exec -it ${CONTAINER_NAME} /bin/bash
}

clean_up() {
    check_podman_machine
    echo -e "${YELLOW}Cleaning up container and image...${NC}"
    $RUNTIME stop ${CONTAINER_NAME} 2>/dev/null
    $RUNTIME rm ${CONTAINER_NAME} 2>/dev/null
    $RUNTIME rmi ${IMAGE_NAME}:latest 2>/dev/null
    echo -e "${GREEN}✓ Cleanup complete${NC}"
}

# ── PostgreSQL container helpers ────────────────────────────────────
# Works with both podman and docker: `network inspect` / `volume inspect`
# exist on both (unlike `network exists`, which is podman-only).
ensure_network() {
    if ! $RUNTIME network inspect "${DB_NETWORK}" >/dev/null 2>&1; then
        echo -e "${YELLOW}Creating network '${DB_NETWORK}'...${NC}"
        $RUNTIME network create "${DB_NETWORK}" >/dev/null
    fi
}

db_start() {
    check_podman_machine
    ensure_network
    if ! $RUNTIME volume inspect "${DB_VOLUME}" >/dev/null 2>&1; then
        echo -e "${YELLOW}Creating volume '${DB_VOLUME}'...${NC}"
        $RUNTIME volume create "${DB_VOLUME}" >/dev/null
    fi

    if $RUNTIME ps --format "{{.Names}}" | grep -q "^${DB_CONTAINER_NAME}$"; then
        echo -e "${GREEN}✓ PostgreSQL '${DB_CONTAINER_NAME}' already running${NC}"
    elif $RUNTIME ps -a --format "{{.Names}}" | grep -q "^${DB_CONTAINER_NAME}$"; then
        echo -e "${YELLOW}Starting existing PostgreSQL container...${NC}"
        $RUNTIME start "${DB_CONTAINER_NAME}" >/dev/null
    else
        echo -e "${YELLOW}Creating PostgreSQL container (${POSTGRES_IMAGE})...${NC}"
        $RUNTIME run -d \
            --name "${DB_CONTAINER_NAME}" \
            --network "${DB_NETWORK}" \
            -e POSTGRES_USER="${POSTGRES_USER}" \
            -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
            -e POSTGRES_DB="${POSTGRES_DB}" \
            -p ${DB_HOST_PORT}:5432 \
            -v "${DB_VOLUME}:/var/lib/postgresql/data:Z" \
            --restart unless-stopped \
            "${POSTGRES_IMAGE}" >/dev/null || {
                echo -e "${RED}✗ Failed to create PostgreSQL container${NC}"; return 1;
            }
    fi

    # Wait until the server accepts connections before returning.
    echo -n "Waiting for PostgreSQL to accept connections"
    for _ in $(seq 1 30); do
        if $RUNTIME exec "${DB_CONTAINER_NAME}" pg_isready -U "${POSTGRES_USER}" -q 2>/dev/null; then
            echo -e " ${GREEN}ready${NC}"
            return 0
        fi
        echo -n "."
        sleep 1
    done
    echo -e " ${RED}timed out${NC}"
    return 1
}

db_stop() {
    check_podman_machine
    echo -e "${YELLOW}Stopping PostgreSQL container '${DB_CONTAINER_NAME}'...${NC}"
    if $RUNTIME stop "${DB_CONTAINER_NAME}" 2>/dev/null; then
        echo -e "${GREEN}✓ PostgreSQL '${DB_CONTAINER_NAME}' stopped${NC}"
    else
        echo -e "${YELLOW}PostgreSQL '${DB_CONTAINER_NAME}' was not running${NC}"
    fi
}

db_shell() {
    check_podman_machine
    echo -e "${YELLOW}Opening psql shell (${POSTGRES_DB})...${NC}"
    $RUNTIME exec -it "${DB_CONTAINER_NAME}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"
}

# Main script
case "$1" in
    build)    build_image ;;
    start)    start_container ;;
    start-ssl) start_container_ssl ;;
    stop)     stop_container ;;
    restart)  restart_container ;;
    rebuild)  rebuild ;;
    backup)   backup_data ;;
    restore)  restore_data "$2" ;;
    logs)     show_logs ;;
    status)   show_status ;;
    shell)    open_shell ;;
    clean)    clean_up ;;
    db-start) db_start ;;
    db-stop)  db_stop ;;
    db-shell) db_shell ;;
    help|--help|-h) show_help ;;
    *)
        show_help
        if [ -n "$1" ]; then
            echo -e "${RED}Unknown command: $1${NC}"
            exit 1
        fi
        ;;
esac
