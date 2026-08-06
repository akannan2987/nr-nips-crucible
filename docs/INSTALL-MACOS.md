# macOS Install & Run — Crucible: Pandora Toolbox Enhancement (v2.0)

Step-by-step guide to install, run, and verify Crucible on **macOS** (development
machine), including HTTPS. Companion documents: [macOS Uninstall](UNINSTALL-MACOS.md) ·
[RHEL8 Install & Run](INSTALL-RHEL8.md) · [RHEL8 Uninstall](UNINSTALL-RHEL8.md).

> **Repository for macOS:** clone from the **public** repo
> `https://github.com/akannan2987/nr-nips-crucible` (no authentication needed).
> The RHEL8 production deployment uses the private Nestlé repo instead — see
> [INSTALL-RHEL8.md](INSTALL-RHEL8.md).
>
> For deep-dive material (all runbooks, SSL rotation, PostgreSQL, systemd) see
> **[DEPLOYMENT.md](../DEPLOYMENT.md)** — this document is the fastest safe path
> on a Mac.

## Table of Contents

- [1. Prerequisites](#1-prerequisites)
- [2. Install and run (HTTP)](#2-install-and-run-http)
- [3. Enable HTTPS](#3-enable-https)
- [4. Verification checklist](#4-verification-checklist)
- [5. Day-2 operations](#5-day-2-operations)
- [6. macOS-specific gotchas](#6-macos-specific-gotchas)

---

## 1. Prerequisites

A container runtime (either one — the scripts auto-detect, podman preferred):

```bash
# Option A — Podman (recommended)
brew install podman
podman machine init          # first time only
podman machine start         # every session — the VM does NOT auto-start on login

# Option B — Docker Desktop
brew install --cask docker   # then launch Docker Desktop and wait until it is running
```

Also required: `git`, `curl`, and `openssl` (all present on a standard macOS +
Homebrew setup), outbound internet during the image build, and a free port
49160 (`lsof -i :49160` should print nothing).

Only needed for bare-metal development (hot reload, running tests):
Python 3.12+ and Node.js 18+ / npm 8+.

---

## 2. Install and run (HTTP)

```bash
# 1. Clone the PUBLIC repository
git clone https://github.com/akannan2987/nr-nips-crucible.git
cd nr-nips-crucible

# 2. One-shot setup: build image, start container, verify the API
./setup-after-clone-py.sh
#    Non-interactive: SETUP_MONITOR=n ./setup-after-clone-py.sh
#    (SETUP_MONITOR=y installs the */5-minute health-monitoring cron instead of asking)

# ✅ On a Mac with no corporate certificate store the script prints
#    "No certificate store ... (normal on macOS)" and starts in HTTP mode.
#    It then polls the API for up to 60 s and confirms it answers.
```

Manual alternative (what the one-shot script does internally):

```bash
./container-py.sh build      # podman/docker build of backend/Dockerfile → crucible-py:latest
./container-py.sh start      # run on http://localhost:49160 (SQLite in ./data, bind-mounted)
```

Open the app: <http://localhost:49160> — on macOS the port is published on
**127.0.0.1 only** (see [gotchas](#6-macos-specific-gotchas)).

---

## 3. Enable HTTPS

`./container-py.sh start-ssl` requires **both** `certs/server.crt` and
`certs/server.key` to exist. Two ways to get them on a Mac:

```bash
# Option A — self-signed development certificate (browser will warn; that's expected)
./setup-ssl.sh
#    Optional: SSL_DOMAIN=my.host.name ./setup-ssl.sh   (default CN: hostname -f)

# Option B — real certificates you already hold (e.g. a local backup kept
# OUTSIDE the repository, such as ~/.crucible/certs)
mkdir -p certs
cp ~/.crucible/certs/server.crt certs/server.crt
cp ~/.crucible/certs/server.key certs/server.key
chmod 600 certs/server.key

# Verify the pair matches — both commands MUST print the same MD5 hash
openssl x509 -noout -modulus -in certs/server.crt | openssl md5
openssl rsa  -noout -modulus -in certs/server.key | openssl md5
```

Then start in TLS mode (no rebuild needed — certs are mounted at runtime,
never baked into the image):

```bash
./container-py.sh start-ssl
# ✅ Verify (use -k for self-signed certificates):
curl --noproxy '*' -sk https://localhost:49160/api/stats
```

HTTPS **replaces** HTTP on the same port 49160 — plain `http://` requests are
refused in SSL mode. To switch back to HTTP:

```bash
./container-py.sh stop
podman rm crucible-py        # or: docker rm crucible-py
./container-py.sh start
```

> ⚠️ **Never commit certificates.** `certs/`, `*.key`, and `*.crt` are excluded
> via `.gitignore`. Keep a backup of real certs outside the repository
> (e.g. `~/.crucible/certs/` with `chmod 600` on the key).

---

## 4. Verification checklist

Run this same checklist after every install or redeploy. The **identical**
checklist (plus external-access checks) exists for the VM in
[INSTALL-RHEL8.md](INSTALL-RHEL8.md#5-verification-checklist).

```bash
# V1. API answers with stats JSON (must contain "chemicals")
curl --noproxy '*' -s  http://localhost:49160/api/stats     # HTTP mode
curl --noproxy '*' -sk https://localhost:49160/api/stats    # HTTPS mode

# V2. Container is up and (after ~30 s) healthy. `status` detects HTTP vs
#     HTTPS mode and prints the stats JSON for whichever is in use.
./container-py.sh status

# V3. UI loads in the browser (React app + architecture page)
open http://localhost:49160
open http://localhost:49160/architecture

# V4. Logs are clean (Ctrl-C to detach)
./container-py.sh logs

# V5. Health monitor runs (logs to /tmp/crucible-monitor.log)
./monitor.sh                 # HTTPS mode: API_URL=https://localhost:49160/api/stats ./monitor.sh

# V6. Backup / restore round-trip works
./container-py.sh backup     # → backups/crucible-<stamp>.db

# V7. Backend test suite passes (bare-metal venv required)
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/pytest
```

---

## 5. Day-2 operations

```bash
# Update to a new version. rebuild preserves the protocol mode (an HTTPS
# deployment comes back as HTTPS) and is also how changed env vars take effect.
git pull && ./container-py.sh rebuild

# Backups (safe while running — uses SQLite's online-backup API)
./container-py.sh backup
./container-py.sh restore backups/crucible-<stamp>.db

# Certificate expiry check (exit 1 when < 30 days remain; cron-friendly)
./cert-expiry-check.sh
WARN_DAYS=60 ./cert-expiry-check.sh

# Optional PostgreSQL instead of SQLite
./container-py.sh db-start
USE_POSTGRES=true ./container-py.sh start
```

Key environment variables (full table in [DEPLOYMENT.md](../DEPLOYMENT.md)):
`CRUCIBLE_PORT` (`container-py.sh`'s only port override — it deliberately
ignores a generic `PORT` shell variable; note `monitor.sh` and `setup-ssl.sh`
**do** read `PORT`, so on a non-default port set `API_URL=...` for the monitor
explicitly), `HOST_BIND` (default `127.0.0.1` on macOS),
`CONTAINER_RUNTIME=podman|docker`, `USE_POSTGRES`, `DATABASE_URL`.

---

## 6. macOS-specific gotchas

- **Podman machine is mandatory** — every `container-py.sh` command checks the
  VM state on macOS and aborts with instructions if it isn't running
  (`podman machine start`).
- **127.0.0.1 binding**: macOS publishes the port on loopback only, because
  Apple's `remoted` daemon occupies ports 49152+ on a link-local address and
  breaks wildcard binds. Other machines can't reach a Mac deployment unless
  you set `HOST_BIND` to a routable IP.
- **`start` reuses an existing container as-is** — new `CRUCIBLE_PORT`,
  `HOST_BIND`, or `USE_POSTGRES` values are not applied. The script warns when
  the running container's port differs from the one you asked for and prints
  the port actually in use. To apply the change: `./container-py.sh rebuild`
  (or `stop` + `rm` + `start`). `start-ssl` always recreates the container.
- **Corporate proxy / VPN**: always use `curl --noproxy '*'` for localhost
  checks (all project scripts already do).
- **Build OOM (exit 137) under podman**: grow the VM —
  `podman machine stop && podman machine set --memory 4096 && podman machine start`.
- **Monitoring cron**: macOS cron can silently drop a first-time install; the
  setup script re-reads the crontab to confirm it persisted (you may need to
  grant `cron` Full Disk Access in System Settings).
- The `:Z` suffix on volume mounts is SELinux relabelling for RHEL8 — it is a
  harmless no-op on macOS.

---

**See also:** [macOS Uninstall](UNINSTALL-MACOS.md) ·
[Full deployment guide](../DEPLOYMENT.md) · [Project README](../README.md)

**Last Updated:** August 6, 2026
