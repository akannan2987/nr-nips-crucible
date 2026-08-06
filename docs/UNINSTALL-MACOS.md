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
| `monitor.sh` cron line + `/tmp/crucible-monitor.log` | ✅ | ✅ |
| `certs/` directory | ✅ | ✅ |
| `client/node_modules`, `client/dist`, `backend/.venv`, Python caches | ✅ | ✅ |
| `data/` (SQLite DB) and `backups/` | ❌ kept | ✅ (after a final safety backup to `~/crucible-backups/crucible-final-<stamp>.db`) |
| The whole project directory | ❌ kept | ✅ (separate "Are you absolutely sure?" confirmation) |

> ⚠️ `--partial` removes **more than its `--help` text claims**: besides the
> container/image/cron/logs it also deletes `certs/` and the dependency
> artifacts (`node_modules`, `dist`, `.venv`). Source code and `data/` are kept.

> 💡 Keep a copy of real certificates **outside** the repo
> (e.g. `~/.crucible/certs/`) — `certs/` is deleted by both `--partial` and
> `--full`, and offered for deletion in interactive mode.

---

## 3. Manual cleanup the script does not do

`uninstall.sh` only targets the `crucible-py` container and image, and only
strips cron lines matching `monitor.sh`. If you used the optional extras:

```bash
# PostgreSQL artifacts (only if you ever used USE_POSTGRES=true)
podman rm -f crucible-db
podman volume rm crucible-pgdata
podman network rm crucible-net

# Base images are deliberately left behind
podman image prune -a          # removes python:3.12-slim, node:18-alpine, etc.

# Manually-added cron lines survive (cert expiry, nightly backup)
crontab -l                     # inspect
crontab -l | grep -v 'cert-expiry-check.sh' | grep -v 'container-py.sh backup' | crontab -
rm -f ~/crucible-cert.log ~/crucible-backup.log

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
crontab -l | grep -i crucible    # → no output (also check: grep monitor.sh)
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

**Last Updated:** August 6, 2026
