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

This is a **production** machine — take a final data backup off the VM first:

```bash
./container-py.sh backup                      # → backups/crucible-<stamp>.db
scp backups/crucible-<stamp>.db user@safe-machine:~/   # copy it OFF the VM
```

(`--full` also takes an automatic last backup to
`~/crucible-backups/crucible-final-<stamp>.db`, but that stays on the VM.)

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
| `monitor.sh` cron line + `/tmp/crucible-monitor.log` | ✅ | ✅ |
| `certs/` directory | ✅ | ✅ |
| `client/node_modules`, `client/dist`, `backend/.venv`, Python caches | ✅ | ✅ |
| systemd user unit + Quadlet file (with `daemon-reload`) | ❌ | ✅ |
| `data/` (SQLite DB) and `backups/` | ❌ kept | ✅ (after a final safety backup to `~/crucible-backups/`) |
| The whole project directory | ❌ kept | ✅ (separate "Are you absolutely sure?" confirmation) |

> ⚠️ `--partial` removes **more than its `--help` text claims**: besides the
> container/image/cron/logs it also deletes `certs/` and the dependency
> artifacts. Source code and `data/` are kept. Certs can be re-copied from the
> corporate store afterwards via `./setup-after-clone-py.sh`.

---

## 4. Manual cleanup the script does not do

`uninstall.sh` only targets the `crucible-py` container/image and `monitor.sh`
cron lines. Depending on what you set up, also run:

```bash
# PostgreSQL artifacts (only if you ever used USE_POSTGRES=true)
podman rm -f crucible-db
podman volume rm crucible-pgdata
podman network rm crucible-net

# Base images are deliberately left behind
podman image prune -a

# Manually-added cron lines survive (cert expiry, nightly backup)
crontab -l | grep -v 'cert-expiry-check.sh' | grep -v 'container-py.sh backup' | crontab -
rm -f ~/crucible-cert.log ~/crucible-backup.log

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
crontab -l | grep -i crucible                     # → no output (also: grep monitor.sh)
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
./setup-after-clone-py.sh

# Restore data if you kept a backup
./container-py.sh restore ~/crucible-backups/crucible-final-<stamp>.db
```

Full instructions: [INSTALL-RHEL8.md](INSTALL-RHEL8.md) (including firewall,
auto-start, and monitoring re-setup).

---

**Last Updated:** August 6, 2026
