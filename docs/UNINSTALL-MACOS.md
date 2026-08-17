# macOS Uninstall — Crucible: Pandora Toolbox Enhancement (v2.0)

How to cleanly remove Crucible from a **macOS** machine. Companion documents:
[macOS Install & Run](INSTALL-MACOS.md) · [RHEL8 Uninstall](UNINSTALL-RHEL8.md).

> The dedicated `uninstall.sh` script (repo root) does most of the work and is
> the same script used on RHEL8. The full uninstall/reinstall runbook lives in
> **[DEPLOYMENT.md → Uninstall and reinstall](../DEPLOYMENT.md#uninstall-and-reinstall)**.

## Table of Contents

- [1. Preview first (always safe)](#1-preview-first-always-safe)
- [2. Choose an uninstall mode](#2-choose-an-uninstall-mode)
- [3. Manual cleanup the script does not do](#3-manual-cleanup-the-script-does-not-do)
- [4. Verify removal](#4-verify-removal)
- [5. Reinstalling later](#5-reinstalling-later)

---

## 1. Preview first (always safe)

```bash
./uninstall.sh --dry-run
# Lists exactly what would be removed. Makes NO changes.
```

---

## 2. Choose an uninstall mode

```bash
./uninstall.sh              # interactive (default): y/N prompt per step
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
| `data/` (SQLite DB) and `backups/` | ❌ kept | ✅ (after a final safety backup to `~/crucible-backups/crucible-final-<stamp>.db`) |
| The whole project directory | ❌ kept | ✅ (separate "Are you absolutely sure?" confirmation) |

> 💡 Keep a copy of real certificates **outside** the repo
> (e.g. `~/.crucible/certs/`) — `certs/` is deleted by both `--partial` and
> `--full`, and offered for deletion in interactive mode.

---

## 3. Manual cleanup the script does not do

`uninstall.sh` handles the container, images, cron entries, and logs. What
remains manual:

```bash
# PostgreSQL artifacts (only if you ever used USE_POSTGRES=true — kept manual
# because removing the crucible-pgdata volume deletes PostgreSQL DATA)
podman rm -f crucible-db
podman volume rm crucible-pgdata
podman network rm crucible-net

# Podman VM / runtime itself (only if you want it fully gone)
podman machine stop && podman machine rm
brew uninstall podman          # or: brew uninstall --cask docker
```

(Substitute `docker` for `podman` in the container commands if you used Docker.)

There is no launchd integration and no firewall/systemd configuration on macOS
— monitoring is plain user cron, so nothing else to clean.

---

## 4. Verify removal

```bash
podman ps -a | grep crucible     # → no output
podman images | grep crucible    # → no output
crontab -l | grep -iE 'crucible|monitor.sh|cert-expiry' # → no output
ls ~/crucible-cert.log ~/crucible-backup.log 2>/dev/null # → no output
lsof -i :49160                   # → no output
ls ~/crucible-backups/           # final data backup, if you ran --full
```

---

## 5. Reinstalling later

```bash
# Fresh clone of the PUBLIC repo (macOS)
git clone https://github.com/akannan2987/nr-nips-crucible.git
cd nr-nips-crucible
./setup-after-clone-py.sh

# Restore data if you kept a backup
./container-py.sh restore ~/crucible-backups/crucible-final-<stamp>.db
```

Full instructions: [INSTALL-MACOS.md](INSTALL-MACOS.md).

---

**Last Updated:** August 8, 2026
