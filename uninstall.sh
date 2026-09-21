#!/bin/bash

# Crucible: Pandora Toolbox Enhancement (v2.0) - Uninstall & Cleanup Script
# Safely removes all Crucible components from the system
# Run from the project root directory

set -euo pipefail

# ── Configuration ────────────────────────────────────────────
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Which instance does THIS checkout run? container-py.sh names the image and
# container after CRUCIBLE_INSTANCE in the folder's .env.local (unset →
# crucible-py). This script removes that instance's resources and no other:
# on a machine with a production and a beta checkout, `./uninstall.sh` in the
# beta folder must never stop production (docs/14-beta-instance.md).
if [ -f "${PROJECT_DIR}/.env.local" ]; then
    _env_instance="${CRUCIBLE_INSTANCE:-}"
    set +u
    # shellcheck disable=SC1091
    . "${PROJECT_DIR}/.env.local"
    set -u
    CRUCIBLE_INSTANCE="${_env_instance:-${CRUCIBLE_INSTANCE:-}}"
fi
CRUCIBLE_INSTANCE="${CRUCIBLE_INSTANCE:-}"
INSTANCE_SUFFIX="${CRUCIBLE_INSTANCE:+-$CRUCIBLE_INSTANCE}"
IMAGES="crucible-py${INSTANCE_SUFFIX}"
CONTAINERS="crucible-py${INSTANCE_SUFFIX}"
# The rootless systemd unit (podman generate systemd) and the Quadlet file,
# named after the container — docs/07-operations.md → Auto-start on boot.
USER_UNIT="container-crucible-py${INSTANCE_SUFFIX}.service"
QUADLET_FILE="crucible-py${INSTANCE_SUFFIX}.container"
QUADLET_UNIT="crucible-py${INSTANCE_SUFFIX}.service"
# Base images pulled by the multi-stage build; removed by --full (offered in
# interactive). Rootless podman/docker images are per-user, so this cannot
# affect other users of a shared machine.
BASE_IMAGES="python:3.12-slim node:18-alpine"
# Every cron entry the project's docs/scripts may have installed. Only the
# lines that name THIS folder are touched: each checkout's lines carry its
# own path (`cd <folder> && …`, `<folder>/cert-expiry-check.sh`), so the
# other instance's monitor, cert check and nightly backup stay installed.
# The path is matched WITH what follows it (" && " or "/"), because the beta
# folder's path begins with production's (…/nr-nips-crucible-beta) and a bare
# prefix match from the production folder would remove beta's lines too.
# [.] rather than \. so the same pattern works in grep -E and awk.
CRON_PATTERNS='monitor[.]sh|cert-expiry-check[.]sh|container-py[.]sh backup'
# The log files those cron entries write. The monitor log is per instance;
# the cert and backup logs are shared names and belong to the default
# instance only.
CRON_LOGS="/tmp/crucible-monitor${INSTANCE_SUFFIX}.log"
if [ -z "${CRUCIBLE_INSTANCE}" ]; then
    CRON_LOGS="${CRON_LOGS} ${HOME}/crucible-cert.log ${HOME}/crucible-backup.log"
fi

# Runtime detection (same convention as container*.sh)
if [ -n "${CONTAINER_RUNTIME:-}" ]; then RUNTIME="$CONTAINER_RUNTIME"
elif command -v podman >/dev/null 2>&1; then RUNTIME="podman"
elif command -v docker >/dev/null 2>&1; then RUNTIME="docker"
else RUNTIME=":"; fi   # ':' = no-op → container steps report "not found" gracefully

# ── Colors ───────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# ── Helpers ──────────────────────────────────────────────────
info()    { echo -e "${BLUE}ℹ ${NC}$1"; }
success() { echo -e "${GREEN}✓${NC} $1"; }
warn()    { echo -e "${YELLOW}⚠${NC} $1"; }
error()   { echo -e "${RED}✗${NC} $1"; }
skip()    { echo -e "  ${YELLOW}↳ Skipped${NC} (not found)"; }

confirm() {
    local msg="$1"
    read -p "$(echo -e "${YELLOW}? ${NC}${msg} (y/N) ")" -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

show_header() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║   🧪 Crucible: Pandora Toolbox Enhancement (v2.0)        ║"
    echo "║      Uninstall & Cleanup                                  ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo ""
    echo -e "Instance: ${BOLD}${CRUCIBLE_INSTANCE:-default}${NC} — container ${CONTAINERS}, folder ${PROJECT_DIR}"
    echo "(only this instance's container, image, cron lines and units are touched)"
    echo ""
}

show_help() {
    show_header
    echo "Usage: $0 [option]"
    echo ""
    echo "Options:"
    echo "  --partial     Remove container, image, cron jobs + logs, certs/,"
    echo "                node_modules/dist/.venv (keep source, data & base images)"
    echo "  --full        Remove everything: the above plus base images"
    echo "                (python:3.12-slim, node:18-alpine), data/ (after a"
    echo "                safety backup to ~/crucible-backups), backups/,"
    echo "                systemd units, and the project directory"
    echo "  --interactive Guided step-by-step cleanup (default)"
    echo "  --dry-run     Show what would be removed without deleting anything"
    echo "  --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                  # Interactive mode"
    echo "  $0 --partial        # Quick cleanup, keep source code"
    echo "  $0 --full           # Remove absolutely everything"
    echo "  $0 --dry-run        # Preview what would be removed"
    echo ""
}

# ── Cleanup Functions ────────────────────────────────────────

stop_container() {
    echo ""
    echo -e "${BOLD}Step 1: Stop Container${NC}"
    local name
    for name in ${CONTAINERS}; do
        if $RUNTIME ps --format '{{.Names}}' 2>/dev/null | grep "^${name}$" >/dev/null; then
            $RUNTIME stop "${name}" 2>/dev/null
            success "Container '${name}' stopped"
        else
            info "Container '${name}' is not running"
        fi
    done
}

remove_container() {
    echo ""
    echo -e "${BOLD}Step 2: Remove Container${NC}"
    local name found=0
    for name in ${CONTAINERS}; do
        if $RUNTIME ps -a --format '{{.Names}}' 2>/dev/null | grep "^${name}$" >/dev/null; then
            $RUNTIME rm -f "${name}" 2>/dev/null
            success "Container '${name}' removed"
            found=1
        fi
    done
    if [ "$found" -eq 0 ]; then info "No crucible containers exist"; skip; fi
}

remove_image() {
    echo ""
    echo -e "${BOLD}Step 3: Remove Container Images${NC}"
    local name found=0
    for name in ${IMAGES}; do
        if $RUNTIME images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep "${name}:latest$" >/dev/null; then
            $RUNTIME rmi "${name}:latest" 2>/dev/null || true
            success "Image '${name}:latest' removed"
            found=1
        fi
    done
    if [ "$found" -eq 0 ]; then info "No crucible images exist"; skip; fi

    # Prune dangling images
    local dangling
    dangling=$($RUNTIME images -f "dangling=true" -q 2>/dev/null | wc -l | tr -d " ")
    if [ "$dangling" -gt 0 ]; then
        $RUNTIME image prune -f >/dev/null 2>&1 || true
        success "Pruned ${dangling} dangling image(s)"
    fi
}

remove_base_images() {
    echo ""
    echo -e "${BOLD}Step 3b: Remove Base Images${NC}"
    local img found=0
    for img in ${BASE_IMAGES}; do
        if $RUNTIME image inspect "${img}" >/dev/null 2>&1; then
            if $RUNTIME rmi "${img}" >/dev/null 2>&1; then
                success "Base image '${img}' removed"
            else
                warn "Could not remove '${img}' — another container may still use it"
            fi
            found=1
        fi
    done
    if [ "$found" -eq 0 ]; then info "No base images present"; skip; fi
    info "They are re-downloaded automatically on the next ./container-py.sh build"
}

# The project's cron lines that belong to THIS checkout (they name its path),
# and the ones that belong to other checkouts (left alone).
cron_mine()   { crontab -l 2>/dev/null | grep -F  -e "${PROJECT_DIR} && " -e "${PROJECT_DIR}/" | grep -E "${CRON_PATTERNS}" || true; }
cron_others() { crontab -l 2>/dev/null | grep -vF -e "${PROJECT_DIR} && " -e "${PROJECT_DIR}/" | grep -E "${CRON_PATTERNS}" || true; }

remove_cron() {
    echo ""
    echo -e "${BOLD}Step 4: Remove Cron Jobs & Their Logs${NC}"
    # Covers every entry the project installs or documents for this folder:
    # the */5 health monitor, the weekly cert-expiry check, and the nightly
    # backup job.
    if [ -n "$(cron_mine)" ]; then
        { crontab -l 2>/dev/null | awk -v dir="${PROJECT_DIR}" -v pat="${CRON_PATTERNS}" \
            '(index($0, dir " && ") || index($0, dir "/")) && $0 ~ pat { next } { print }' || true; } | crontab -
        success "Cron job(s) for this folder removed (monitor.sh / cert-expiry-check.sh / backup)"
    else
        info "No crucible cron jobs for this folder found"
        skip
    fi
    local others
    others=$(cron_others | wc -l | tr -d ' ')
    if [ "${others}" -gt 0 ]; then
        info "${others} crucible cron entr(y/ies) for OTHER checkouts left in place (crontab -l to see them)"
    fi

    local log
    for log in ${CRON_LOGS}; do
        if [ -f "${log}" ]; then
            rm -f "${log}"
            success "Log removed (${log})"
        fi
    done
}

remove_certs() {
    echo ""
    echo -e "${BOLD}Step 5: Remove SSL Certificates${NC}"
    if [ -d "${PROJECT_DIR}/certs" ]; then
        rm -rf "${PROJECT_DIR}/certs"
        success "Local certificate copies removed (certs/)"
        info "Source certificates are untouched"
    else
        info "No local certificates found"
        skip
    fi
}

backup_data() {
    echo ""
    echo -e "${BOLD}Step 6a: Backup Application Data${NC}"
    local backup_dir="${HOME}/crucible-backups"
    local stamp
    stamp=$(date +%Y%m%d-%H%M%S)
    local found=0
    mkdir -p "${backup_dir}"
    # Containers are already stopped at this point, so plain copies are safe
    # (never copy a RUNNING SQLite database — see docs/07-operations.md → Backup and restore).
    if [ -f "${PROJECT_DIR}/data/crucible.db" ]; then
        cp "${PROJECT_DIR}/data/crucible.db" "${backup_dir}/crucible${INSTANCE_SUFFIX}-final-${stamp}.db"
        success "SQLite database backed up to ${backup_dir}/crucible${INSTANCE_SUFFIX}-final-${stamp}.db"
        found=1
    fi
    if [ "$found" -eq 0 ]; then info "No database files found to back up"; fi
}

remove_data() {
    echo ""
    echo -e "${BOLD}Step 6b: Remove Application Data${NC}"
    if [ -d "${PROJECT_DIR}/data" ]; then
        rm -rf "${PROJECT_DIR}/data"
        success "Data directory removed (crucible.db)"
    else
        info "No data directory found"
        skip
    fi

    if [ -d "${PROJECT_DIR}/backups" ]; then
        rm -rf "${PROJECT_DIR}/backups"
        success "Local backups directory removed (backups/)"
        info "Final safety copies remain in ~/crucible-backups"
    fi
}

remove_node_modules() {
    echo ""
    echo -e "${BOLD}Step 7: Remove Dependencies & Build Artifacts${NC}"
    local freed=0

    for dir in "${PROJECT_DIR}/client/node_modules"; do
        if [ -d "$dir" ]; then
            local size
            size=$(du -sh "$dir" 2>/dev/null | cut -f1)
            rm -rf "$dir"
            success "Removed $(basename "$(dirname "$dir")")/node_modules (${size})"
            freed=1
        fi
    done

    if [ -d "${PROJECT_DIR}/client/dist" ]; then
        rm -rf "${PROJECT_DIR}/client/dist"
        success "Removed client/dist build output"
        freed=1
    fi

    # Python artifacts
    if [ -d "${PROJECT_DIR}/backend/.venv" ]; then
        local vsize
        vsize=$(du -sh "${PROJECT_DIR}/backend/.venv" 2>/dev/null | cut -f1)
        rm -rf "${PROJECT_DIR}/backend/.venv"
        success "Removed backend/.venv (${vsize})"
        freed=1
    fi
    if find "${PROJECT_DIR}/backend" -type d \( -name "__pycache__" -o -name ".pytest_cache" \) 2>/dev/null | grep -q .; then
        find "${PROJECT_DIR}/backend" -type d \( -name "__pycache__" -o -name ".pytest_cache" \) -exec rm -rf {} + 2>/dev/null || true
        success "Removed Python caches (__pycache__, .pytest_cache)"
        freed=1
    fi

    if [ "$freed" -eq 0 ]; then info "No dependency or build artifacts found"; skip; fi
}

remove_systemd() {
    echo ""
    echo -e "${BOLD}Step 8: Remove systemd Services (rootless + system, if configured)${NC}"
    local found=0

    # Rootless user units, see docs/07-operations.md → Auto-start on boot (RHEL8: podman generate systemd / Quadlet)
    local user_unit="${HOME}/.config/systemd/user/${USER_UNIT}"
    if [ -f "$user_unit" ]; then
        systemctl --user stop "${USER_UNIT}" 2>/dev/null || true
        systemctl --user disable "${USER_UNIT}" 2>/dev/null || true
        rm -f "$user_unit"
        systemctl --user daemon-reload 2>/dev/null || true
        success "User systemd unit removed (${USER_UNIT})"
        found=1
    fi
    local quadlet="${HOME}/.config/containers/systemd/${QUADLET_FILE}"
    if [ -f "$quadlet" ]; then
        systemctl --user stop "${QUADLET_UNIT}" 2>/dev/null || true
        rm -f "$quadlet"
        systemctl --user daemon-reload 2>/dev/null || true
        success "Quadlet unit removed (${QUADLET_FILE})"
        found=1
    fi
    if [ "$found" -eq 1 ]; then
        # Removing a unit file leaves systemd holding an in-memory "failed"
        # record for it, which then shows up forever in `systemctl --user
        # list-units` as "not-found failed failed". Clear that residue.
        systemctl --user reset-failed "${USER_UNIT}" 2>/dev/null || true
        systemctl --user reset-failed "${QUADLET_UNIT}" 2>/dev/null || true
        info "Login lingering was left enabled; disable with: sudo loginctl disable-linger \$USER"
    fi

    # Legacy system-wide unit (the default instance only; it predates instances)
    local service_file="/etc/systemd/system/crucible.service"
    if [ -z "${CRUCIBLE_INSTANCE}" ] && [ -f "$service_file" ]; then
        warn "System-wide systemd service found — requires sudo to remove"
        if confirm "Remove systemd service?"; then
            sudo systemctl stop crucible 2>/dev/null || true
            sudo systemctl disable crucible 2>/dev/null || true
            sudo rm -f "$service_file"
            sudo systemctl daemon-reload
            success "systemd service removed"
        else
            warn "Skipped systemd service removal"
        fi
        found=1
    fi

    if [ "$found" -eq 0 ]; then info "No systemd services installed"; skip; fi
}

remove_project() {
    echo ""
    echo -e "${BOLD}Step 9: Remove Project Directory${NC}"
    warn "This will delete ALL source code at:"
    echo "  ${PROJECT_DIR}"
    echo ""
    if confirm "Are you absolutely sure?"; then
        # We need to cd out before removing
        cd "${PROJECT_DIR}/.."
        rm -rf "${PROJECT_DIR}"
        success "Project directory removed"
    else
        warn "Skipped project directory removal"
    fi
}

# ── Summary ──────────────────────────────────────────────────

show_summary() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║   ✅ Cleanup Complete!                                    ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo ""
}

# ── Dry Run ──────────────────────────────────────────────────

dry_run() {
    show_header
    echo -e "${BOLD}Dry Run — the following items would be removed:${NC}"
    echo ""

    # Containers (both stacks)
    local name
    for name in ${CONTAINERS}; do
        if $RUNTIME ps -a --format '{{.Names}}' 2>/dev/null | grep "^${name}$" >/dev/null; then
            echo -e "  ${RED}✗${NC} Container: ${name}"
        else
            echo -e "  ${GREEN}✓${NC} Container ${name}: (already removed)"
        fi
    done

    # Images (both stacks)
    for name in ${IMAGES}; do
        if $RUNTIME images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep "${name}:latest$" >/dev/null; then
            echo -e "  ${RED}✗${NC} Image: ${name}:latest"
        else
            echo -e "  ${GREEN}✓${NC} Image ${name}: (already removed)"
        fi
    done

    # Base images (removed by --full only)
    local bimg
    for bimg in ${BASE_IMAGES}; do
        if $RUNTIME image inspect "${bimg}" >/dev/null 2>&1; then
            echo -e "  ${RED}✗${NC} Base image (--full only): ${bimg}"
        else
            echo -e "  ${GREEN}✓${NC} Base image ${bimg}: (not present)"
        fi
    done

    # Cron entries (monitor / cert-expiry / backup) — this folder's only
    local cron_hits cron_other
    cron_hits=$(cron_mine | wc -l | tr -d ' ')
    cron_other=$(cron_others | wc -l | tr -d ' ')
    if [ "${cron_hits}" -gt 0 ]; then
        echo -e "  ${RED}✗${NC} Cron job(s): ${cron_hits} crucible entr(y/ies) for this folder (monitor / cert-expiry / backup)"
    else
        echo -e "  ${GREEN}✓${NC} Cron jobs for this folder: (none found)"
    fi
    if [ "${cron_other}" -gt 0 ]; then
        echo -e "  ${BLUE}ℹ${NC} Cron job(s) for other checkouts: ${cron_other}, left in place"
    fi

    # Cron logs
    local log
    for log in ${CRON_LOGS}; do
        if [ -f "${log}" ]; then
            echo -e "  ${RED}✗${NC} Log: ${log}"
        else
            echo -e "  ${GREEN}✓${NC} Log ${log}: (not found)"
        fi
    done

    # Certs
    if [ -d "${PROJECT_DIR}/certs" ]; then
        echo -e "  ${RED}✗${NC} SSL certificates: certs/"
    else
        echo -e "  ${GREEN}✓${NC} SSL certificates: (not found)"
    fi

    # Data
    if [ -d "${PROJECT_DIR}/data" ]; then
        local dbsize
        dbsize=$(du -sh "${PROJECT_DIR}/data" 2>/dev/null | cut -f1)
        echo -e "  ${RED}✗${NC} Application data: data/ (${dbsize})"
    else
        echo -e "  ${GREEN}✓${NC} Application data: (not found)"
    fi

    # backups/
    if [ -d "${PROJECT_DIR}/backups" ]; then
        echo -e "  ${RED}✗${NC} Local backups: backups/ ($(du -sh "${PROJECT_DIR}/backups" 2>/dev/null | cut -f1))"
    else
        echo -e "  ${GREEN}✓${NC} Local backups: (not found)"
    fi

    # Python venv
    if [ -d "${PROJECT_DIR}/backend/.venv" ]; then
        echo -e "  ${RED}✗${NC} Python venv: backend/.venv ($(du -sh "${PROJECT_DIR}/backend/.venv" 2>/dev/null | cut -f1))"
    else
        echo -e "  ${GREEN}✓${NC} Python venv: (not found)"
    fi

    # node_modules
    local total_nm=0
    for dir in "${PROJECT_DIR}/client/node_modules"; do
        if [ -d "$dir" ]; then
            local nmsize
            nmsize=$(du -sh "$dir" 2>/dev/null | cut -f1)
            echo -e "  ${RED}✗${NC} $(echo "$dir" | sed "s|${PROJECT_DIR}/||"): (${nmsize})"
            total_nm=1
        fi
    done
    [ "$total_nm" -eq 0 ] && echo -e "  ${GREEN}✓${NC} node_modules: (not found)"

    # Build artifacts
    if [ -d "${PROJECT_DIR}/client/dist" ]; then
        echo -e "  ${RED}✗${NC} Build output: client/dist/"
    else
        echo -e "  ${GREEN}✓${NC} Build output: (not found)"
    fi

    # systemd (system-wide + rootless user units + Quadlet)
    if [ -z "${CRUCIBLE_INSTANCE}" ]; then
        if [ -f "/etc/systemd/system/crucible.service" ]; then
            echo -e "  ${RED}✗${NC} systemd service: crucible.service"
        else
            echo -e "  ${GREEN}✓${NC} systemd service: (not installed)"
        fi
    fi
    if [ -f "${HOME}/.config/systemd/user/${USER_UNIT}" ]; then
        echo -e "  ${RED}✗${NC} user systemd unit: ${USER_UNIT}"
    else
        echo -e "  ${GREEN}✓${NC} user systemd unit ${USER_UNIT}: (not installed)"
    fi
    if [ -f "${HOME}/.config/containers/systemd/${QUADLET_FILE}" ]; then
        echo -e "  ${RED}✗${NC} Quadlet unit: ${QUADLET_FILE}"
    else
        echo -e "  ${GREEN}✓${NC} Quadlet unit ${QUADLET_FILE}: (not installed)"
    fi

    echo ""
    echo -e "${BLUE}ℹ ${NC}No changes were made. Run without --dry-run to proceed."
    echo ""
}

# ── Mode: Partial ────────────────────────────────────────────

run_partial() {
    show_header
    echo -e "${BOLD}Partial Cleanup${NC} — removes runtime artifacts, keeps source code & data"
    echo ""

    stop_container
    remove_container
    remove_image
    remove_cron
    remove_certs
    remove_node_modules
    show_summary

    echo "Source code, data, and base images are preserved."
    echo "To redeploy later: ./setup-after-clone-py.sh"
    echo ""
}

# ── Mode: Full ───────────────────────────────────────────────

run_full() {
    show_header
    echo -e "${RED}${BOLD}Full Uninstall${NC} — removes EVERYTHING including data and source code"
    echo ""
    warn "This will permanently delete all application data and source code."
    echo ""

    if ! confirm "Continue with full uninstall?"; then
        echo ""
        info "Aborted."
        exit 0
    fi

    stop_container
    remove_container
    remove_image
    remove_base_images
    remove_cron
    remove_certs
    backup_data
    remove_data
    remove_node_modules
    remove_systemd
    remove_project
    show_summary
}

# ── Mode: Interactive ────────────────────────────────────────

run_interactive() {
    show_header
    echo -e "${BOLD}Interactive Cleanup${NC} — choose what to remove step by step"
    echo ""

    # Step 1-3: Container
    if confirm "Stop and remove container + image?"; then
        stop_container
        remove_container
        remove_image
    fi

    # Step 3b: Base images
    if confirm "Remove base images (python:3.12-slim, node:18-alpine)? Re-downloaded on next build"; then
        remove_base_images
    fi

    # Step 4: Cron
    if confirm "Remove crucible cron jobs (monitor / cert-expiry / backup) and their logs?"; then
        remove_cron
    fi

    # Step 5: Certs
    if confirm "Remove local SSL certificate copies?"; then
        remove_certs
    fi

    # Step 6: Data
    if confirm "Remove application data? (chemicals, samples, etc.)"; then
        if confirm "  Back up data before removing?"; then
            backup_data
        fi
        remove_data
    fi

    # Step 7: node_modules
    if confirm "Remove node_modules and build artifacts?"; then
        remove_node_modules
    fi

    # Step 8: systemd
    remove_systemd

    # Step 9: Project
    echo ""
    if confirm "Remove the entire project directory?"; then
        remove_project
    fi

    show_summary
}

# ── Main ─────────────────────────────────────────────────────

MODE="${1:---interactive}"

case "$MODE" in
    --partial|-p)
        run_partial
        ;;
    --full|-f)
        run_full
        ;;
    --interactive|-i)
        run_interactive
        ;;
    --dry-run|-d)
        dry_run
        ;;
    --help|-h|help)
        show_help
        ;;
    *)
        error "Unknown option: $MODE"
        echo ""
        show_help
        exit 1
        ;;
esac
