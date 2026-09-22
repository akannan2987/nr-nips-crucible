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
#   CRUCIBLE_INSTANCE=<name>  run a second, separate instance from another
#                       checkout on the same machine: every resource this
#                       script owns is named crucible-py-<name>
#                       (docs/14-beta-instance.md)
#   HOST_BIND=<ip>      published-port interface (see below)
#   PLATFORM=linux/amd64  cross-build target (e.g. building amd64 on an arm64 laptop)
#   AUTH_MODE=off|token|local  the login (docs/13-authentication.md); token
#   needs CRUCIBLE_TOKEN=<secret>, local needs SESSION_SECRET=<secret>; the
#   accounts of the local mode are managed with `users`. All live in .env.local.

DATA_DIR="$(pwd)/data"
BACKUP_DIR="${BACKUP_DIR:-$(pwd)/backups}"
CERTS_DIR="$(pwd)/certs"

# ── Site defaults from .env.local (untracked, gitignored) ───────────
# A machine can declare its standing configuration here so plain
# `start`/`rebuild` do the right thing — e.g. the HTTPS production VM sets:
#   USE_HTTPS=true
# and the beta checkout beside it (docs/14-beta-instance.md) sets:
#   CRUCIBLE_INSTANCE=beta
#   CRUCIBLE_PORT=49161
# and an instance with the login on (docs/13-authentication.md) sets:
#   AUTH_MODE=token                       # rung 1, one shared token, or
#   CRUCIBLE_TOKEN=<a long random secret>
#   AUTH_MODE=local                       # rung 2, accounts with passwords and roles
#   SESSION_SECRET=<a long random secret>
# Environment variables always override .env.local. Same mechanism as
# setup-after-clone-py.sh (which reads CERT_SOURCE/CERT_HOSTNAME from it).
if [ -f "$(pwd)/.env.local" ]; then
    _env_use_https="${USE_HTTPS:-}"
    _env_use_postgres="${USE_POSTGRES:-}"
    _env_instance="${CRUCIBLE_INSTANCE:-}"
    _env_label="${CRUCIBLE_INSTANCE_LABEL:-}"
    _env_port="${CRUCIBLE_PORT:-}"
    _env_auth_mode="${AUTH_MODE:-}"
    _env_token="${CRUCIBLE_TOKEN:-}"
    _env_session_secret="${SESSION_SECRET:-}"
    # shellcheck disable=SC1091
    . "$(pwd)/.env.local"
    USE_HTTPS="${_env_use_https:-${USE_HTTPS:-}}"
    USE_POSTGRES="${_env_use_postgres:-${USE_POSTGRES:-}}"
    CRUCIBLE_INSTANCE="${_env_instance:-${CRUCIBLE_INSTANCE:-}}"
    CRUCIBLE_INSTANCE_LABEL="${_env_label:-${CRUCIBLE_INSTANCE_LABEL:-}}"
    CRUCIBLE_PORT="${_env_port:-${CRUCIBLE_PORT:-}}"
    AUTH_MODE="${_env_auth_mode:-${AUTH_MODE:-}}"
    CRUCIBLE_TOKEN="${_env_token:-${CRUCIBLE_TOKEN:-}}"
    SESSION_SECRET="${_env_session_secret:-${SESSION_SECRET:-}}"
fi

# ── Instance name ───────────────────────────────────────────────────
# One checkout is one instance. Unset — the default, and every machine that
# ran this script before v2.20.0 — the image and container are named
# crucible-py and nothing below changes. Set (CRUCIBLE_INSTANCE=beta in the
# beta folder's .env.local), the name is appended to every resource this
# script creates: the image, the container, and the optional Postgres
# container, network and volume. A second checkout on the same machine can
# therefore never touch the first one's: `rebuild` in the beta folder
# replaces crucible-py-beta and leaves crucible-py running. The folder's own
# data/, backups/ and certs/ were already per checkout.
CRUCIBLE_INSTANCE="${CRUCIBLE_INSTANCE:-}"
INSTANCE_SUFFIX=""
if [ -n "$CRUCIBLE_INSTANCE" ]; then
    case "$CRUCIBLE_INSTANCE" in
        *[!a-z0-9-]*|-*|*-)
            echo "✗ CRUCIBLE_INSTANCE='$CRUCIBLE_INSTANCE' must be lowercase letters, digits and hyphens, e.g. beta"
            exit 1 ;;
    esac
    INSTANCE_SUFFIX="-${CRUCIBLE_INSTANCE}"
fi
IMAGE_NAME="crucible-py${INSTANCE_SUFFIX}"
CONTAINER_NAME="crucible-py${INSTANCE_SUFFIX}"
# The page shows which instance it is (SH-13): the name goes into the
# container as an environment variable, and an optional label spells it
# the way you want ("Production" instead of "Prod").
CRUCIBLE_INSTANCE_LABEL="${CRUCIBLE_INSTANCE_LABEL:-}"

# ── The login (phases SH-3a and SH-3b; docs/13-authentication.md) ────
# AUTH_MODE=off (the default) leaves every route open, as before v2.22.0.
# AUTH_MODE=token with CRUCIBLE_TOKEN=<a long random secret> makes every
# /api route except health, instance and the login answer 401 without it.
# AUTH_MODE=local with SESSION_SECRET=<a long random secret> asks for a
# username and a password instead (accounts made with `users add`), gives
# each account a role, and lets scripts in with a personal token.
# All of it travels into the container as environment variables. This
# script never prints a secret, and the file that holds one is kept
# owner-only.
AUTH_MODE="${AUTH_MODE:-off}"
CRUCIBLE_TOKEN="${CRUCIBLE_TOKEN:-}"
SESSION_SECRET="${SESSION_SECRET:-}"
case "$AUTH_MODE" in
    off|token|local) ;;
    *)  echo "✗ AUTH_MODE='$AUTH_MODE' must be off, token or local (docs/13-authentication.md)"
        exit 1 ;;
esac
if [ "$AUTH_MODE" = "token" ] && [ "${#CRUCIBLE_TOKEN}" -lt 32 ]; then
    echo "✗ AUTH_MODE=token needs CRUCIBLE_TOKEN of at least 32 characters (in .env.local, or the environment)."
    echo "  Generate one:  python3 -c 'import secrets; print(secrets.token_urlsafe(48))'"
    exit 1
fi
if [ "$AUTH_MODE" = "local" ] && [ "${#SESSION_SECRET}" -lt 32 ]; then
    echo "✗ AUTH_MODE=local needs SESSION_SECRET of at least 32 characters (in .env.local, or the environment)."
    echo "  Generate one:  python3 -c 'import secrets; print(secrets.token_urlsafe(48))'"
    exit 1
fi
if [ "$AUTH_MODE" != "off" ] && [ -f "$(pwd)/.env.local" ] \
    && grep -qE '^(CRUCIBLE_TOKEN|SESSION_SECRET)=' "$(pwd)/.env.local" 2>/dev/null; then
    _perm="$(stat -c %a "$(pwd)/.env.local" 2>/dev/null || stat -f %Lp "$(pwd)/.env.local" 2>/dev/null)"
    if [ -n "$_perm" ] && [ "$_perm" != "600" ]; then
        chmod 600 "$(pwd)/.env.local" 2>/dev/null \
            && echo "ℹ  .env.local holds a login secret: its permissions are now 600 (owner only)"
    fi
fi

# ── PostgreSQL (optional) ───────────────────────────────────────────
# SQLite (data/crucible.db) is the DEFAULT and needs nothing extra. Set
# USE_POSTGRES=true to run the app against a managed Postgres container:
#   ./container-py.sh db-start          # bring up Postgres (once)
#   USE_POSTGRES=true ./container-py.sh start        # app → Postgres
# The app container joins DB_NETWORK and reaches the database at
# <DB_CONTAINER_NAME>:5432; schema is created/upgraded on boot by
# backend/scripts/db_bootstrap.py (Alembic).
# A named instance gets its own database container, network and volume;
# give it its own DB_HOST_PORT too if both instances use Postgres.
USE_POSTGRES="${USE_POSTGRES:-false}"
DB_CONTAINER_NAME="${DB_CONTAINER_NAME:-crucible-db${INSTANCE_SUFFIX}}"
DB_NETWORK="${DB_NETWORK:-crucible-net${INSTANCE_SUFFIX}}"
DB_VOLUME="${DB_VOLUME:-crucible-pgdata${INSTANCE_SUFFIX}}"
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

# ── The systemd service (Linux servers) ─────────────────────────────
# On the RHEL 8 server a systemd user unit made by `podman generate systemd
# --new` (docs/07-operations.md → Auto-start on boot) is THE thing that runs
# the application: it starts the container at boot, restarts it if it
# dies, and owns it. This script builds and updates, and then hands the
# container to the service, so `systemctl --user status|stop|start|restart`
# and this script's status|stop|start|restart always agree. The rules,
# learned the hard way (lessons 36 and 37, docs/15-run-stop-status.md):
#   1. before this script stops or recreates the container, it stops the
#      service if it is active (an active service would otherwise recreate
#      its own, older copy of the container underneath us);
#   2. after this script creates a container, it rewrites the unit from
#      it (the unit records the exact run command) and then starts the
#      service, which takes the container over.
# No unit file, no systemctl, or Docker: every step is a silent no-op, so
# macOS and Windows behave as before, with this script as the only tool.
UNIT_DIR="${CRUCIBLE_UNIT_DIR:-$HOME/.config/systemd/user}"
UNIT_NAME="container-${CONTAINER_NAME}.service"

have_unit() {
    [ "$RUNTIME" = "podman" ] && [ -f "${UNIT_DIR}/${UNIT_NAME}" ] && command -v systemctl >/dev/null 2>&1
}

unit_active() {
    have_unit && systemctl --user is-active --quiet "${UNIT_NAME}" 2>/dev/null
}

stop_unit_if_active() {
    if unit_active; then
        echo -e "${YELLOW}Stopping the service ${UNIT_NAME} first (it would otherwise recreate the old container)...${NC}"
        systemctl --user stop "${UNIT_NAME}"
    fi
}

regenerate_unit() {
    have_unit || return 0
    echo -e "${YELLOW}Rewriting ${UNIT_NAME} from the container just created (the unit records the exact run command)...${NC}"
    # `generate systemd --files` writes into the current directory: run it
    # in the unit folder so the file lands in place, replacing the old one.
    # The unit records the exact run command, the token included, so the
    # file is made owner-only: your own systemd reads it, nobody else needs to.
    if (cd "${UNIT_DIR}" && $RUNTIME generate systemd --new --name "${CONTAINER_NAME}" --files >/dev/null 2>&1) \
        && chmod 600 "${UNIT_DIR}/${UNIT_NAME}" \
        && systemctl --user daemon-reload; then
        echo -e "${GREEN}✓ ${UNIT_NAME} rewritten (enabled: $(systemctl --user is-enabled "${UNIT_NAME}" 2>/dev/null || echo unknown))${NC}"
    else
        echo -e "${RED}✗ Could not rewrite ${UNIT_NAME} — do it by hand: docs/07-operations.md → Auto-start on boot${NC}"
    fi
}

handover_to_unit() {
    have_unit || return 0
    echo -e "${YELLOW}Handing the container to the service ${UNIT_NAME}, which runs it from now on...${NC}"
    if systemctl --user start "${UNIT_NAME}"; then
        echo -e "${GREEN}✓ ${UNIT_NAME} is active: the service runs the application (systemctl --user status ${UNIT_NAME})${NC}"
    else
        echo -e "${RED}✗ systemctl --user start ${UNIT_NAME} failed; the container this script started keeps running (podman ps). See docs/15-run-stop-status.md${NC}"
    fi
}

# Wait until the application answers, so a command returns only when the
# app is really up (a curl in the first seconds after a start used to fail
# with "Connection reset by peer"; SH-9).
wait_for_api() {
    local url i
    url="$(api_url)"
    for i in $(seq 1 30); do
        if api_answers; then
            echo -e "${GREEN}✓ The application answers at ${url}${NC}"
            return 0
        fi
        sleep 2
    done
    echo -e "${YELLOW}⚠ The application did not answer within 60 s at ${url} — check: ./container-py.sh logs${NC}"
    return 1
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
    echo "Usage: $0 [command]        (runtime: $RUNTIME · instance: ${CRUCIBLE_INSTANCE:-default} → ${CONTAINER_NAME}, port ${PORT} · login: ${AUTH_MODE})"
    echo ""
    echo "Commands:"
    echo "  build       Build the Python backend image"
    echo "  start       Start the application (HTTPS when .env.local says USE_HTTPS=true, else HTTP on port ${PORT});"
    echo "              on a server with a systemd unit, the service takes the container over"
    echo "  start-ssl   Start with HTTPS (needs certs/server.crt + server.key)"
    echo "  stop        Stop the application (through its service when the service runs it)"
    echo "  restart     Restart the application (through its service when the service runs it)"
    echo "  rebuild     Rebuild image and restart container"
    echo "  backup      Consistent database backup → backups/ (safe while running)"
    echo "  restore <f> Restore a backup file (stops app, swaps db, restarts);"
    echo "              given a FOLDER, restores the newest crucible-*.db in it"
    echo "  lock        Regenerate backend/requirements.lock inside the base image"
    echo "  logs        Show container logs (follow)"
    echo "  status      Show container status, the service, the /api/health probe and the counts"
    echo "  script <name> [args]  Run a maintenance script inside the container"
    echo "  users <verb> [args]   The login's accounts (AUTH_MODE=local): add, list, reset, role, enable,"
    echo "              disable, unlock, token, remove; e.g. ./container-py.sh users add alice --role editor"
    echo "  import chemicals <file>   Load a .json/.csv/.tsv/.xlsx/.xls/.sdf file into the registry"
    echo "  export chemicals <file>   Write every registry entry to a JSON file (reviewable, re-importable)"
    echo "              e.g. ./container-py.sh script remove_chemicals.py CHEM-000042 --apply"
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
    echo "  CRUCIBLE_INSTANCE=<name>          a second instance from another checkout: image, container"
    echo "                                    and db resources named crucible-py-<name> (docs/14-beta-instance.md)"
    echo "  CRUCIBLE_INSTANCE_LABEL=<word>    what the page's corner says (default: Prod, or the name capitalised)"
    echo "  AUTH_MODE=off|token|local         the login (default off); token needs CRUCIBLE_TOKEN, local needs SESSION_SECRET"
    echo "  CRUCIBLE_TOKEN=<secret>           the shared secret of the token mode; keep it in .env.local, never printed"
    echo "  SESSION_SECRET=<secret>           signs the local mode's session cookie; keep it in .env.local, never printed"
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
    # Optional cross-build, e.g. PLATFORM=linux/amd64 on an arm64 laptop.
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
    local running_port="" created=""
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
        # Rule 2 of docs/13-authentication.md: a credential over plain HTTP is
        # a credential on a postcard. Loopback (127.0.0.1) is the development
        # exception; anything wider needs HTTPS, or an explicit override.
        if [ "$AUTH_MODE" != "off" ] && [ "$HOST_BIND" != "127.0.0.1" ] && [ "${CRUCIBLE_ALLOW_HTTP_LOGIN:-}" != "true" ]; then
            echo -e "${RED}✗ AUTH_MODE=${AUTH_MODE} over plain HTTP on ${HOST_BIND}: the credentials would cross the network unencrypted.${NC}"
            echo "  Use HTTPS (USE_HTTPS=true in .env.local, certificates in certs/), or, on a machine only you can reach:"
            echo "  CRUCIBLE_ALLOW_HTTP_LOGIN=true ./container-py.sh start"
            exit 1
        fi
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
            -e CRUCIBLE_INSTANCE="${CRUCIBLE_INSTANCE}" \
            -e CRUCIBLE_INSTANCE_LABEL="${CRUCIBLE_INSTANCE_LABEL}" \
            -e AUTH_MODE="${AUTH_MODE}" \
            -e CRUCIBLE_TOKEN="${CRUCIBLE_TOKEN}" \
            -e SESSION_SECRET="${SESSION_SECRET}" \
            "${pg_args[@]}" \
            --restart unless-stopped \
            ${IMAGE_NAME}:latest && created="yes"
    fi

    if [ $? -eq 0 ]; then
        [ -n "$created" ] && regenerate_unit
        handover_to_unit
        wait_for_api
        local shown_port="${running_port:-${PORT}}"
        # An existing container keeps the mode it was created with: say
        # https:// when that is what it serves, or the line is a lie.
        local scheme="http"
        if $RUNTIME inspect ${CONTAINER_NAME} --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null \
            | grep -q '^USE_HTTPS=true$'; then
            scheme="https"
        fi
        echo -e "${GREEN}✓ Container started successfully${NC}"
        echo "  instance: ${CRUCIBLE_INSTANCE:-default} · container: ${CONTAINER_NAME} · image: ${IMAGE_NAME}:latest"
        echo ""
        echo "Access the application at:"
        echo "  ${scheme}://localhost:${shown_port}"
        echo "  ${scheme}://$(hostname):${shown_port}   (from another machine)"
    else
        echo -e "${RED}✗ Failed to start container${NC}"
        exit 1
    fi
}

stop_container() {
    check_podman_machine
    if unit_active; then
        echo -e "${YELLOW}Stopping the application through its service ${UNIT_NAME}...${NC}"
        if systemctl --user stop "${UNIT_NAME}"; then
            echo -e "${GREEN}✓ ${UNIT_NAME} stopped; the container is removed (start, or the next boot, recreates it)${NC}"
        else
            echo -e "${RED}✗ systemctl --user stop ${UNIT_NAME} failed${NC}"
        fi
        return
    fi
    echo -e "${YELLOW}Stopping container '${CONTAINER_NAME}' (Python backend)...${NC}"
    if $RUNTIME stop ${CONTAINER_NAME} 2>/dev/null; then
        echo -e "${GREEN}✓ Container '${CONTAINER_NAME}' stopped${NC}"
    else
        echo -e "${YELLOW}Container '${CONTAINER_NAME}' was not running${NC}"
    fi
}

# Plain `start`: HTTPS when .env.local or the environment says so.
start_dispatch() {
    if [ "${USE_HTTPS:-false}" = "true" ]; then
        start_container_ssl
    else
        start_container
    fi
}

restart_container() {
    check_podman_machine
    if unit_active; then
        echo -e "${YELLOW}Restarting the application through its service ${UNIT_NAME}...${NC}"
        systemctl --user restart "${UNIT_NAME}" && wait_for_api
        return
    fi
    stop_container
    sleep 2
    start_dispatch
}

rebuild() {
    build_image
    check_podman_machine
    # Choose the protocol mode for the recreated container. HTTPS wins when
    # EITHER source says so:
    #   1. the existing container runs HTTPS (preserve-mode: a live HTTPS
    #      deployment must never silently drop to HTTP), or
    #   2. USE_HTTPS=true from the environment or .env.local (so a fresh
    #      machine with no container yet — e.g. right after an uninstall —
    #      still comes up HTTPS).
    local was_https="${USE_HTTPS:-false}"
    if $RUNTIME inspect ${CONTAINER_NAME} --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null \
        | grep -q '^USE_HTTPS=true$'; then
        was_https="true"
    fi
    stop_unit_if_active
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
    stop_unit_if_active
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
        -e CRUCIBLE_INSTANCE="${CRUCIBLE_INSTANCE}" \
        -e CRUCIBLE_INSTANCE_LABEL="${CRUCIBLE_INSTANCE_LABEL}" \
        -e AUTH_MODE="${AUTH_MODE}" \
        -e CRUCIBLE_TOKEN="${CRUCIBLE_TOKEN}" \
        -e SESSION_SECRET="${SESSION_SECRET}" \
        -e USE_HTTPS=true \
        -e SSL_CERT_PATH=/app/certs/server.crt \
        -e SSL_KEY_PATH=/app/certs/server.key \
        "${pg_args[@]}" \
        --restart unless-stopped \
        ${IMAGE_NAME}:latest

    if [ $? -eq 0 ]; then
        regenerate_unit
        handover_to_unit
        wait_for_api
        echo -e "${GREEN}✓ Container started with HTTPS${NC}"
        echo "  instance: ${CRUCIBLE_INSTANCE:-default} · container: ${CONTAINER_NAME} · image: ${IMAGE_NAME}:latest"
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

lock_requirements() {
    # Resolve backend/requirements.txt (ranges, the intent) into exact versions
    # inside the SAME base image the Dockerfile builds from, and write them to
    # backend/requirements.lock (what a real build gets). The Dockerfile, CI and
    # the test virtualenv all install from the lock, so every build is the same.
    check_podman_machine
    local base
    base=$(grep -E '^FROM .*python:' "$(pwd)/backend/Dockerfile" | head -1 | awk '{print $2}')
    local lock="$(pwd)/backend/requirements.lock"
    echo -e "${YELLOW}Resolving backend/requirements.txt inside ${base} ...${NC}"
    local pins
    pins=$($RUNTIME run --rm \
        -v "$(pwd)/backend/requirements.txt:/w/requirements.txt:ro,Z" \
        "${base}" sh -c 'pip install -q --no-cache-dir --root-user-action=ignore -r /w/requirements.txt >/dev/null 2>&1 && python -V && pip freeze --exclude-editable') || {
        echo -e "${RED}✗ pip could not resolve requirements.txt — the lock was not changed${NC}"; exit 1; }
    local pyver
    pyver=$(printf '%s\n' "${pins}" | head -1)
    {
        echo "# backend/requirements.lock — the exact versions the container image runs."
        echo "#"
        echo "# GENERATED, do not edit by hand. Regenerate whenever backend/requirements.txt"
        echo "# changes, from the repository root, inside the same base image the Dockerfile"
        echo "# uses (so the versions are the ones a real build would resolve):"
        echo "#"
        echo "#   ./container-py.sh lock"
        echo "#"
        echo "# requirements.txt says what the project ASKS for (ranges, the intent);"
        echo "# this file says what it GOT (every package, every dependency of a dependency,"
        echo "# one exact version each). The Dockerfile, the CI workflow and the test"
        echo "# virtual environment all install from THIS file, so a build a year from now"
        echo "# installs what a build today installs."
        echo "#"
        echo "# Resolved with ${pyver} on $(date +%Y-%m-%d)."
        printf '%s\n' "${pins}" | tail -n +2 | grep -vE '^(pip|setuptools|wheel)=='
    } > "${lock}"
    echo -e "${GREEN}✓ Wrote ${lock} ($(grep -c '==' "${lock}") pinned packages)${NC}"
    echo "  Review with: git diff backend/requirements.lock   then rebuild: ./container-py.sh rebuild"
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
    if [ -d "$src" ]; then
        # A folder: take the newest backup in it. This is how the beta
        # instance is refreshed from production without copying a timestamp
        # by hand:  ./container-py.sh restore ../nr-nips-crucible/backups
        # (docs/14-beta-instance.md). Nothing is ever written to that folder.
        local newest
        newest=$(ls -t "$src"/crucible-*.db 2>/dev/null | head -1)
        if [ -z "$newest" ]; then
            echo -e "${RED}✗ No crucible-*.db backup found in folder $src${NC}"
            exit 1
        fi
        echo "Newest backup in ${src}: $(basename "$newest")"
        src="$newest"
    fi
    if [ ! -f "$src" ]; then
        echo -e "${RED}✗ Backup file not found: $src${NC}"
        exit 1
    fi

    check_podman_machine
    stop_unit_if_active
    echo -e "${YELLOW}Stopping container '${CONTAINER_NAME}' before restore...${NC}"
    $RUNTIME stop ${CONTAINER_NAME} 2>/dev/null

    # Keep the current database as a safety net — restore is destructive.
    if [ -f "${DATA_DIR}/crucible.db" ]; then
        mv "${DATA_DIR}/crucible.db" "${DATA_DIR}/crucible.db.pre-restore"
        echo "  (current database kept as data/crucible.db.pre-restore)"
    fi

    cp "$src" "${DATA_DIR}/crucible.db"
    echo -e "${GREEN}✓ Restored $(basename "$src") → data/crucible.db  (instance: ${CRUCIBLE_INSTANCE:-default})${NC}"

    # An existing container is simply started again and keeps its mode. If
    # there is none (the service removed it, or after `clean`), honour
    # USE_HTTPS as plain `start` does.
    if $RUNTIME ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        start_container
    else
        start_dispatch
    fi
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
api_base() {
    if $RUNTIME inspect ${CONTAINER_NAME} --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null \
        | grep -q '^USE_HTTPS=true$'; then
        echo "https://localhost:${PORT}"
    else
        echo "http://localhost:${PORT}"
    fi
}

# The probe is /api/health: the one route that stays open when the login
# is on (docs/13-authentication.md). It says {"status":"ok"} and nothing
# else. /api/stats, the probe before v2.22.0, answers 401 without a token.
api_url() {
    echo "$(api_base)/api/health"
}

# True when the application answers: 200 at /api/health, or, for a
# container built from an image older than v2.22.0 (no /api/health, so 404),
# the counts at /api/stats.
api_answers() {
    local base code
    base="$(api_base)"
    code=$(curl --noproxy '*' -sk -m 5 -o /dev/null -w '%{http_code}' "${base}/api/health" 2>/dev/null)
    [ "$code" = "200" ] && return 0
    if [ "$code" = "404" ]; then
        curl --noproxy '*' -sk -m 5 "${base}/api/stats" 2>/dev/null | grep -q '"chemicals"' && return 0
    fi
    return 1
}

show_status() {
    check_podman_machine
    echo -e "${YELLOW}Container status (runtime: ${RUNTIME} · instance: ${CRUCIBLE_INSTANCE:-default} · folder: $(pwd)):${NC}"
    # Exact match on the name: a filter would also match crucible-py-beta
    # from the production folder.
    $RUNTIME ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | awk -v n="${CONTAINER_NAME}" 'NR==1 || $1==n'
    if have_unit; then
        if unit_active; then
            echo "service ${UNIT_NAME}: active ($(systemctl --user is-enabled "${UNIT_NAME}" 2>/dev/null)) — the service runs the application"
        else
            echo "service ${UNIT_NAME}: inactive ($(systemctl --user is-enabled "${UNIT_NAME}" 2>/dev/null)) — the application is stopped, or runs outside the service; ./container-py.sh start hands it over"
        fi
    fi
    echo ""
    if $RUNTIME ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        echo -e "${GREEN}✓ Container is running${NC}"
        echo ""
        # -k so a self-signed dev certificate doesn't fail the check.
        echo "Testing API endpoint ($(api_url))..."
        curl --noproxy '*' -sk "$(api_url)"; echo ""
        # The counts, with the token when the login is on (this script has
        # it; the token itself is never printed). In the local mode the
        # script holds no credential, so the counts come from the database
        # itself, through the container's Python, and the accounts are listed.
        if [ "$AUTH_MODE" = "token" ]; then
            echo "login: token — the page asks for it once; scripts send it as Authorization: Bearer (docs/13-authentication.md)"
            curl --noproxy '*' -sk -H "Authorization: Bearer ${CRUCIBLE_TOKEN}" "$(api_base)/api/stats" | head -c 300; echo ""
        elif [ "$AUTH_MODE" = "local" ]; then
            echo "login: local — usernames and passwords; scripts send a personal token as Authorization: Bearer (docs/13-authentication.md)"
            $RUNTIME exec ${CONTAINER_NAME} python -c '
from sqlalchemy import func, select
from app.database import SessionLocal
from app.models import Chemical, Sample, Screening, Toxicology, User
db = SessionLocal()
counts = {m.__tablename__: db.scalar(select(func.count()).select_from(m)) for m in (Chemical, Sample, Screening, Toxicology)}
users = db.scalars(select(User)).all()
print("counts, from the database:", counts)
print("accounts:", len(users), "(" + ", ".join(sorted(f"{u.username} {u.doc.get(chr(114)+chr(111)+chr(108)+chr(101))}" for u in users)) + ")" if users else "accounts: none yet (./container-py.sh users add <name> --role admin)")
' 2>/dev/null || echo "  (the container could not report the counts)"
        else
            echo "login: off — every route answers anyone"
            curl --noproxy '*' -sk "$(api_base)/api/stats" | head -c 300; echo ""
        fi
        echo ""
    else
        echo -e "${RED}✗ Container is not running${NC}"
    fi
}

run_script() {
    # The maintenance scripts need the application's Python and packages,
    # which live only inside the image — so this is the one-line form of
    # `$RUNTIME exec ${CONTAINER_NAME} python /app/backend/scripts/<name> …`.
    check_podman_machine
    local name="$1"
    if [ -z "$name" ]; then
        echo "Usage: $0 script <name.py> [args...]   (scripts in backend/scripts/)"
        echo "Available:"
        ls backend/scripts/*.py 2>/dev/null | sed 's|.*/|  |'
        return 1
    fi
    shift
    case "$name" in */*) ;; *) name="/app/backend/scripts/${name}" ;; esac
    $RUNTIME exec ${CONTAINER_NAME} python "$name" "$@"
}

manage_users() {
    # The login's accounts (AUTH_MODE=local, docs/13-authentication.md):
    # backend/scripts/manage_users.py, inside the container, against the
    # database directly, so it works whatever the mode says and can never
    # lock the operator out. -i keeps stdin open for --password-stdin; -t
    # only when this terminal is one, so --prompt can hide what is typed.
    check_podman_machine
    if ! $RUNTIME ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        echo -e "${RED}✗ ${CONTAINER_NAME} is not running: the accounts live in its database (./container-py.sh start)${NC}"
        return 1
    fi
    local tty=()
    [ -t 0 ] && tty=(-t)
    $RUNTIME exec -i "${tty[@]}" ${CONTAINER_NAME} python /app/backend/scripts/manage_users.py "$@"
}

import_file() {
    # Put the host file where the container can see it — data/ is the one
    # mounted folder — run the import script on it, then tidy up. No
    # runtime `cp` involved, so it behaves the same with podman and Docker
    # on every platform.
    check_podman_machine
    local module="$1" src="$2"
    if [ -z "$module" ] || [ -z "$src" ]; then
        echo "Usage: $0 import chemicals <file>   (.json .csv .tsv .xlsx .xls .sdf)"; return 1
    fi
    if [ ! -f "$src" ]; then echo "No such file: $src"; return 1; fi
    local base; base="$(basename "$src")"
    mkdir -p "${DATA_DIR}/.import"
    cp "$src" "${DATA_DIR}/.import/${base}"
    $RUNTIME exec ${CONTAINER_NAME} python /app/backend/scripts/import_file.py "$module" "/app/data/.import/${base}"
    local rc=$?
    rm -f "${DATA_DIR}/.import/${base}"
    return $rc
}

export_file() {
    # The export script writes into the mounted data/ folder; the file is
    # then moved to the path given. Same reasoning as import_file.
    check_podman_machine
    local module="$1" dest="$2"
    if [ "$module" != "chemicals" ] || [ -z "$dest" ]; then
        echo "Usage: $0 export chemicals <file.json>"; return 1
    fi
    $RUNTIME exec ${CONTAINER_NAME} python /app/backend/scripts/export_chemicals.py -o /app/data/.export.json || return 1
    mv "${DATA_DIR}/.export.json" "$dest" && echo "Copied to $dest"
}

open_shell() {
    check_podman_machine
    echo -e "${YELLOW}Opening shell in container...${NC}"
    $RUNTIME exec -it ${CONTAINER_NAME} /bin/bash
}

clean_up() {
    check_podman_machine
    echo -e "${YELLOW}Cleaning up container '${CONTAINER_NAME}' and image '${IMAGE_NAME}:latest'...${NC}"
    stop_unit_if_active
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
    start)
        # USE_HTTPS=true (env or .env.local) makes plain `start` an HTTPS
        # start — the standing config for the production VM.
        start_dispatch
        ;;
    start-ssl) start_container_ssl ;;
    stop)     stop_container ;;
    restart)  restart_container ;;
    rebuild)  rebuild ;;
    backup)   backup_data ;;
    lock)     lock_requirements ;;
    restore)  restore_data "$2" ;;
    logs)     show_logs ;;
    status)   show_status ;;
    shell)    open_shell ;;
    script)   shift; run_script "$@" ;;
    users)    shift; manage_users "$@" ;;
    import)   import_file "$2" "$3" ;;
    export)   export_file "$2" "$3" ;;
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
