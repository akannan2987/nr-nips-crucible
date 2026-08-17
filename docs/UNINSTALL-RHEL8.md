# RHEL8 Uninstall — Crucible: Pandora Toolbox Enhancement (v2.0)

How to cleanly remove Crucible from the **RHEL8 VM** (rootless podman).
Companion documents: [RHEL8 Install & Run](INSTALL-RHEL8.md) ·
[macOS Uninstall](UNINSTALL-MACOS.md).

> The dedicated `uninstall.sh` script (repo root) does most of the work and is
> the same script used on macOS. The full uninstall/reinstall runbook lives in
> **[DEPLOYMENT.md → Uninstall and reinstall](../DEPLOYMENT.md#uninstall-and-reinstall)**.

## Table of Contents

- [1. Before you start](#1-before-you-start)
- [2. Preview first (always safe)](#2-preview-first-always-safe)
- [3. Choose an uninstall mode](#3-choose-an-uninstall-mode)
- [4. Manual cleanup the script does not do](#4-manual-cleanup-the-script-does-not-do)
- [5. Verify removal](#5-verify-removal)
- [6. Reinstalling later](#6-reinstalling-later)

---

## 1. Before you start

This is a **production** machine — take a final data backup and copy it to
**another machine you trust** (e.g. your Mac) first, so the data survives even
if the VM itself is later wiped or decommissioned:

```bash
# 1. On the VM: take a consistent snapshot
./container-py.sh backup                      # → backups/crucible-<stamp>.db

# 2. From your OTHER machine (e.g. your Mac), pull the backup off the VM:
scp <your-user>@<vm-hostname>:/path/to/crucible/backups/crucible-<stamp>.db ~/
```

Note: `--full` also takes an automatic last backup to
`~/crucible-backups/crucible-final-<stamp>.db` before deleting `data/` — a
safety net so a full uninstall can never destroy data irreversibly. But that
copy lives **on the VM itself**; it does not replace the off-machine copy
above.

---

## 2. Preview first (always safe)

```bash
./uninstall.sh --dry-run
# Lists exactly what would be removed — including any systemd user unit
# (~/.config/systemd/user/container-crucible-py.service), Quadlet file
# (~/.config/containers/systemd/crucible-py.container), and legacy system
# unit. Makes NO changes.
```

---

## 3. Choose an uninstall mode

```bash
./uninstall.sh              # interactive (default): y/N prompt for most steps
                            # (note: rootless systemd/Quadlet units are removed WITHOUT a prompt)
./uninstall.sh --partial    # no prompts — keeps source code and data/
./uninstall.sh --full       # removes EVERYTHING, including data and the project folder
./uninstall.sh --help
```

What each mode removes:

| Removed | `--partial` | `--full` |
|---|---|---|
| `crucible-py` container + image (and dangling images) | ✅ | ✅ |
| All crucible cron entries (`monitor.sh`, `cert-expiry-check.sh`, nightly backup) | ✅ | ✅ |
| Their logs (`/tmp/crucible-monitor.log`, `~/crucible-cert.log`, `~/crucible-backup.log`) | ✅ | ✅ |
| `certs/` directory | ✅ | ✅ |
| `client/node_modules`, `client/dist`, `backend/.venv`, Python caches | ✅ | ✅ |
| Base images (`python:3.12-slim`, `node:18-alpine`) | ❌ kept | ✅ (re-downloaded on next build) |
| systemd user unit + Quadlet file (with `daemon-reload`) | ❌ | ✅ |
| `data/` (SQLite DB) and `backups/` | ❌ kept | ✅ (after a final safety backup to `~/crucible-backups/`) |
| The whole project directory | ❌ kept | ✅ (separate "Are you absolutely sure?" confirmation) |

> 💡 Certs can be re-copied from the corporate store afterwards via
> `./setup-after-clone-py.sh` (needs `.env.local` — see
> [INSTALL-RHEL8.md §3](INSTALL-RHEL8.md#3-https-with-corporate-certificates)).

---

## 4. Manual cleanup the script does not do

`uninstall.sh` handles the container, images, cron entries, logs, and rootless
systemd units. What remains manual:

```bash
# PostgreSQL artifacts (only if you ever used USE_POSTGRES=true — kept manual
# because removing the crucible-pgdata volume deletes PostgreSQL DATA)
podman rm -f crucible-db
podman volume rm crucible-pgdata
podman network rm crucible-net

# Firewall rule (whichever case applied at install time)
sudo firewall-cmd --permanent --remove-port=49160/tcp && sudo firewall-cmd --reload
# or: sudo iptables -D INPUT -p tcp --dport 49160 -j ACCEPT && sudo service iptables save

# Lingering (uninstall.sh leaves it enabled on purpose)
sudo loginctl disable-linger $USER
```

---

## 5. Verify removal

```bash
podman ps -a | grep crucible                      # → no output
podman images | grep crucible                     # → no output
podman volume ls | grep crucible                  # → no output
podman network ls | grep crucible                 # → no output
crontab -l | grep -iE 'crucible|monitor.sh|cert-expiry' # → no output
ls ~/crucible-cert.log ~/crucible-backup.log 2>/dev/null # → no output
systemctl --user list-units | grep crucible       # → no output
ss -tlnp | grep 49160                             # → no output
sudo firewall-cmd --list-ports 2>/dev/null        # → 49160/tcp gone (if firewalld)
ls ~/crucible-backups/                            # final data backup, if you ran --full
```

---

## 6. Reinstalling later

```bash
# Fresh clone of the PRIVATE repo (RHEL8 VM)
git clone https://github.com/nestle-it/nr-nips-crucible.git
cd nr-nips-crucible

# Recreate .env.local FIRST — a full uninstall deleted it, and without it the
# app comes up HTTP with no certificates (see INSTALL-RHEL8.md §3):
cat > .env.local <<'EOF'
CERT_SOURCE=<cert-store-path>
USE_HTTPS=true
EOF

./setup-after-clone-py.sh

# Restore data if you kept a backup
./container-py.sh restore ~/crucible-backups/crucible-final-<stamp>.db
```

Full instructions: [INSTALL-RHEL8.md](INSTALL-RHEL8.md) (including firewall,
auto-start, and monitoring re-setup).

---

**Last Updated:** August 8, 2026
