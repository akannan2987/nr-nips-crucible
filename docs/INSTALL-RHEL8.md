# RHEL8 Install & Run — Crucible: Pandora Toolbox Enhancement (v2.0)

Step-by-step guide to install, run, and verify Crucible on the **RHEL8 VM**
(production, rootless podman, HTTPS with corporate certificates). Companion
documents: [RHEL8 Uninstall](UNINSTALL-RHEL8.md) ·
[macOS Install & Run](INSTALL-MACOS.md) · [macOS Uninstall](UNINSTALL-MACOS.md).

> **Repository for RHEL8:** clone from the **private** Nestlé repo
> `https://github.com/nestle-it/nr-nips-crucible` (requires a Personal Access
> Token over HTTPS, or an SSH key: `git@github.com:nestle-it/nr-nips-crucible.git`).
> macOS development uses the public repo instead — see
> [INSTALL-MACOS.md](INSTALL-MACOS.md).
>
> This guide uses placeholders for internal values — `<vm-hostname>` for the
> VM's FQDN and `<cert-store-path>` for the corporate certificate store. No
> internal values are hardcoded anywhere: on the VM you configure them **once**
> in an untracked `.env.local` file (section 3), or pass `CERT_SOURCE=` /
> `CERT_HOSTNAME=` as environment variables. The full runbook with
> troubleshooting is
> **[DEPLOYMENT.md → Runbook C](../DEPLOYMENT.md#runbook-c--rhel8-vm-podman)**.

## Table of Contents

- [1. Prerequisites (one-time VM setup)](#1-prerequisites-one-time-vm-setup)
- [2. Install and run](#2-install-and-run)
- [3. HTTPS with corporate certificates](#3-https-with-corporate-certificates)
- [4. Auto-start on boot and monitoring](#4-auto-start-on-boot-and-monitoring)
- [5. Verification checklist](#5-verification-checklist)
- [6. Day-2 operations](#6-day-2-operations)
- [7. RHEL8-specific gotchas](#7-rhel8-specific-gotchas)

---

## 1. Prerequisites (one-time VM setup)

```bash
# 1. Packages (curl/openssl are normally present already)
sudo dnf install -y git podman
podman --version                          # any 4.x / 5.x is fine

# 2. Rootless user namespaces (normally provisioned by the podman package)
grep $USER /etc/subuid /etc/subgid        # should print a range for your user
# If missing:
#   sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 $USER
#   podman system migrate

# 3. Lingering — required so the container survives logout/reboot
sudo loginctl enable-linger $USER

# 4. Firewall — diagnose FIRST, then open port 49160 for the case that applies
rpm -q firewalld iptables-services
sudo iptables -L INPUT -n | head
# Case A — firewalld running:
#   sudo firewall-cmd --permanent --add-port=49160/tcp && sudo firewall-cmd --reload
# Case B — plain iptables with real rules:
#   sudo iptables -I INPUT -p tcp --dport 49160 -j ACCEPT && sudo service iptables save
# Case C — no host firewall (common on internal VMs): nothing to do.
#   Do NOT install firewalld just for this — it would impose default-deny.
```

Also required: git access to the **private** repo (PAT or SSH key), outbound
internet during the image build, and — for HTTPS — read access to the corporate
certificate store on the VM.

---

## 2. Install and run

```bash
# 1. Clone the PRIVATE repository
git clone https://github.com/nestle-it/nr-nips-crucible.git
cd nr-nips-crucible
chmod +x *.sh                             # first time only (all helper scripts)

# 2. One-shot setup: copy + verify certs, build, start (HTTPS when certs
#    exist), verify the API, optionally install the monitoring cron
./setup-after-clone-py.sh
#    Non-interactive: SETUP_MONITOR=y ./setup-after-clone-py.sh
#    For HTTPS, configure the cert store FIRST via .env.local (see section 3),
#    or one-off: CERT_SOURCE=<cert-store-path> ./setup-after-clone-py.sh

# ✅ The script polls the API for up to 60 s and exits non-zero (with a
#    pointer to ./container-py.sh logs) if the app never answers.
```

Manual alternative (what the one-shot script does internally):

```bash
./container-py.sh build       # podman build --format docker … → crucible-py:latest
./container-py.sh start-ssl   # HTTPS (needs certs/ — see section 3), or:
./container-py.sh start       # HTTP on 0.0.0.0:49160
```

On Linux the port is published on **0.0.0.0**, so the app is reachable from
other machines once the firewall allows it: `https://<vm-hostname>:49160`.

---

## 3. HTTPS with corporate certificates

`./container-py.sh start-ssl` requires `certs/server.crt` **and**
`certs/server.key`. `setup-after-clone-py.sh` places them automatically from
the corporate store once it knows where that store is — configure it **once**
per VM in an untracked `.env.local` file (gitignored, survives `git pull`;
environment variables override it):

```bash
cat > .env.local <<'EOF'
CERT_SOURCE=<cert-store-path>
CERT_HOSTNAME=<vm-hostname>
EOF
# CERT_HOSTNAME is optional — it defaults to `hostname -f`, which on the VM
# already resolves to the right FQDN. The store must contain
# <vm-hostname>.cer and <vm-hostname>.key.
./setup-after-clone-py.sh
```

Manual placement (what the script does internally):

```bash
mkdir -p certs
cp <cert-store-path>/<vm-hostname>.cer certs/server.crt
cp <cert-store-path>/<vm-hostname>.key certs/server.key
chmod 600 certs/server.key
chmod 644 certs/server.crt

# Verify the pair matches — both commands MUST print the same MD5 hash
openssl x509 -noout -modulus -in certs/server.crt | openssl md5
openssl rsa  -noout -modulus -in certs/server.key | openssl md5

# Start in TLS mode (always recreates the container; no rebuild needed —
# certs are runtime-mounted read-only, never baked into the image)
./container-py.sh start-ssl

# ✅ Verify (Nestlé-signed certs validate without -k):
curl --noproxy '*' -s https://localhost:49160/api/stats
```

HTTPS **replaces** HTTP on port 49160. Switch back with
`./container-py.sh stop && podman rm crucible-py && ./container-py.sh start`.

Certificate expiry monitoring (warns when < 30 days remain):

```bash
./cert-expiry-check.sh                    # manual check, exit 1 = expiring/expired
crontab -e   # add the weekly check (Mondays 08:00):
# 0 8 * * 1 cd /path/to/crucible && ./cert-expiry-check.sh >> ~/crucible-cert.log 2>&1
```

Certificate rotation (renewal or reissue): see
[DEPLOYMENT.md → Maintenance](../DEPLOYMENT.md#maintenance-and-operational-tasks).
Shortcut — **remove the old pair first** (the setup script keeps existing
certs and skips the copy if `certs/` is already populated):
`rm certs/server.crt certs/server.key && CERT_SOURCE=/path/to/new ./setup-after-clone-py.sh`,
then `./container-py.sh start-ssl`.

> ⚠️ **Never commit certificates** — `certs/`, `*.key`, and `*.crt` are
> `.gitignore`d. The private key must stay `chmod 600`.

---

## 4. Auto-start on boot and monitoring

Rootless containers die with your login session — `--restart unless-stopped`
alone does **not** survive a reboot. You need lingering (section 1) plus a
systemd **user** unit:

```bash
# Quick variant (podman 4.x): generate a user unit from the running container
mkdir -p ~/.config/systemd/user
podman generate systemd --new --name crucible-py --files
mv container-crucible-py.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now container-crucible-py.service
```

The preferred **Quadlet** variant (podman ≥ 4.4) and the full unit content are
in [DEPLOYMENT.md → Auto-start on boot](../DEPLOYMENT.md#auto-start-on-boot-systemd).
If you use the Quadlet file, **adjust its `Volume=` path** to your actual
checkout or the app starts with an empty database.

Health monitoring (auto-restart on failed health checks):

```bash
SETUP_MONITOR=y ./setup-after-clone-py.sh     # installs/refreshes the cron line
crontab -l | grep monitor.sh                  # verify; the installed entry is ONE line:
# */5 * * * * cd <repo> && USER=<user> XDG_RUNTIME_DIR=/run/user/<uid> CONTAINER_NAME=crucible-py API_URL=https://localhost:49160/api/stats ./monitor.sh
tail -5 /tmp/crucible-monitor.log
```

> ⚠️ The `USER=… XDG_RUNTIME_DIR=…` prefix is **required** for rootless podman
> under cron — without it podman resolves its storage to a bad path and the
> monitor cannot restart the container. Let the setup script write the line
> rather than copying simplified examples.

---

## 5. Verification checklist

Run this same checklist after every install or redeploy. It mirrors the macOS
checklist in [INSTALL-MACOS.md](INSTALL-MACOS.md#4-verification-checklist),
plus the external-access checks (V8–V9) that only apply to the VM.

```bash
# V1. API answers with stats JSON (must contain "chemicals")
curl --noproxy '*' -s  http://localhost:49160/api/stats     # HTTP mode
curl --noproxy '*' -s  https://localhost:49160/api/stats    # HTTPS mode (no -k needed with corporate certs)

# V2. Container is up and (after ~30 s) healthy. `status` detects HTTP vs
#     HTTPS mode and prints the stats JSON for whichever is in use.
./container-py.sh status
podman exec crucible-py python /app/backend/scripts/healthcheck.py && echo healthy

# V3. UI loads (from the VM)
curl --noproxy '*' -s https://localhost:49160/ | grep -o '<title>[^<]*</title>'

# V4. Logs are clean (Ctrl-C to detach)
./container-py.sh logs

# V5. Health monitor runs (logs to /tmp/crucible-monitor.log)
./monitor.sh                 # HTTPS mode: API_URL=https://localhost:49160/api/stats ./monitor.sh

# V6. Backup / restore round-trip works
./container-py.sh backup     # → backups/crucible-<stamp>.db

# V7. Backend test suite passes (bare-metal venv; optional on the VM)
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/pytest

# V8. Reachable from a workstation (browser or curl):
#     https://<vm-hostname>:49160  and  https://<vm-hostname>:49160/architecture

# V9. Survives a reboot (after section 4):
systemctl --user status container-crucible-py.service   # or the Quadlet unit
```

---

## 6. Day-2 operations

```bash
# Update to a new version (field-tested sequence)
cd /path/to/crucible
cp -r data ~/data-backup-$(date +%Y%m%d)      # belt-and-braces before upgrades
git pull
./container-py.sh rebuild                     # rebuild + recreate; preserves the
                                              # protocol mode (HTTPS stays HTTPS)

# Backups (safe while running — SQLite online-backup API; never plain-cp a live DB)
./container-py.sh backup
./container-py.sh restore backups/crucible-<stamp>.db

# Recommended nightly backup cron (02:00, keep last 14).
# NOTE: a crontab entry must be a single line — paste the following as ONE line:
# 0 2 * * * cd /path/to/crucible && USER=$(id -un) XDG_RUNTIME_DIR=/run/user/$(id -u) ./container-py.sh backup >> ~/crucible-backup.log 2>&1 && ls -t backups/crucible-*.db | tail -n +15 | xargs -r rm

# Optional PostgreSQL instead of SQLite
./container-py.sh db-start
USE_POSTGRES=true ./container-py.sh start-ssl
```

Key environment variables (full table in [DEPLOYMENT.md](../DEPLOYMENT.md)):
`CRUCIBLE_PORT` (`container-py.sh`'s only port override — it deliberately
ignores a generic `PORT` shell variable, which matters on shared VMs; note
`monitor.sh` **does** read `PORT`, so on a non-default port set
`API_URL=...` for the monitor explicitly), `HOST_BIND` (default `0.0.0.0` on
Linux), `USE_POSTGRES`, `DATABASE_URL`, `CERT_SOURCE` / `CERT_HOSTNAME`
(setup script).

---

## 7. RHEL8-specific gotchas

- **SELinux**: every bind mount must carry the `:Z` suffix (the scripts already
  do: `data/ → /app/data:Z`, `certs/ → /app/certs:Z,ro`). Running `podman run`
  manually without `:Z` yields `Permission denied` / an empty `/app/data`.
- **Rootless limits**: ports < 1024 cannot be bound (49160 is fine); containers
  need lingering + a systemd user unit to survive reboots.
- **Corporate proxy**: always `curl --noproxy '*'` for localhost checks — the
  proxy otherwise intercepts them. The in-container healthcheck already
  bypasses the proxy; if `status` ever shows *unhealthy* while curl works,
  rebuild to pick up the proxy-bypassing healthcheck.
- **`podman build` needs `--format docker`** (the script adds it): podman's
  native OCI format silently drops the Dockerfile `HEALTHCHECK`.
- **`start` reuses an existing container as-is** — env/port changes need
  `rebuild` (or `stop` + `rm` + `start`); the script warns and prints the port
  actually in use when it differs from the one requested. `start-ssl` always
  recreates.
- **Custom port**: `setup-after-clone-py.sh`'s verify loop hardcodes 49160 — with
  `CRUCIBLE_PORT=<other>` the container is fine but the script's verification
  falsely fails; verify manually instead.
- **Cron + rootless podman on a network-mounted home directory**: any cron
  line invoking podman needs the `USER=… XDG_RUNTIME_DIR=…` prefix (see
  section 4).

---

**See also:** [RHEL8 Uninstall](UNINSTALL-RHEL8.md) ·
[Full deployment guide](../DEPLOYMENT.md) · [Project README](../README.md)

**Last Updated:** August 6, 2026
