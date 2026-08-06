# Deployment Guide — Crucible: Pandora Toolbox Enhancement (v2.0)

Operational runbooks for deploying the Crucible **Python/FastAPI** backend on
macOS (development) and the RHEL8 VM (production).

The container scripts are runtime-agnostic — they auto-detect **podman or
docker** (override with `CONTAINER_RUNTIME=docker|podman`). Nothing is
hardcoded to a hostname or platform: the app reads `PORT` (default 49160) and
binds `0.0.0.0`, so the same image runs unmodified on macOS and RHEL8.

> For the history of the Node/Express → Python/FastAPI migration and the
> codebase learning map, see [MIGRATION.md](MIGRATION.md).

---

## Table of Contents

- [Architecture at a glance](#architecture-at-a-glance)
- [Prerequisites](#prerequisites)
- [Port: 5942 → 49160 (RHEL8 VM)](#port-5942--49160-rhel8-vm)
- [Quick Start (after clone)](#quick-start-after-clone)
- [Runbook A — macOS (Docker)](#runbook-a--macos-docker)
- [Runbook B — macOS (Podman)](#runbook-b--macos-podman)
- [Runbook C — RHEL8 VM (Podman)](#runbook-c--rhel8-vm-podman)
- [SSL/TLS certificate setup](#ssltls-certificate-setup)
- [Environment variables](#environment-variables)
- [Live-mounted directories](#live-mounted-directories)
- [Database: SQLite and PostgreSQL](#database-sqlite-and-postgresql)
- [Health monitoring](#health-monitoring)
- [Auto-start on boot (systemd)](#auto-start-on-boot-systemd)
- [Backup and restore](#backup-and-restore)
- [Maintenance and operational tasks](#maintenance-and-operational-tasks)
- [Troubleshooting](#troubleshooting)
- [Security](#security)
- [Uninstall and reinstall](#uninstall-and-reinstall)

---

## Architecture at a glance

A single **FastAPI** process (served by uvicorn) does everything:

- answers all `/api/*` routes (chemicals, samples, screening, toxicology, stats),
- serves the built React client (`client/dist`) as static files,
- serves `/architecture` (interactive architecture page),
- stores data in **SQLite** (`data/crucible.db`) by default via SQLAlchemy 2 — **optional PostgreSQL** by changing `DATABASE_URL` (see [Database](#database-sqlite-and-postgresql)).

The container image is **`crucible-py`**, built from
[backend/Dockerfile](backend/Dockerfile) (a multi-stage build: a Node stage
builds the React bundle, the final `python:3.12-slim` stage contains no Node).
Everything is wrapped by [container-py.sh](container-py.sh).

---

## Prerequisites

### System

- **OS**: Linux (RHEL 8) or macOS
- **CPU/RAM/Disk**: 2 cores / 2 GB / 10 GB minimum (4 cores / 4 GB recommended)

### Software

- **Podman** or **Docker** (containerized deployment covers everything else)
- **Git**, **curl**
- **OpenSSL** (certificate verification)
- Bare-metal development only: **Python 3.12+** (backend) and **Node.js 18+** (to build the React client)

### Network

- **Port 49160** reachable (not blocked by a host firewall)
- **Outbound internet** during the image build (pip + npm downloads)

### Certificates (for HTTPS)

Access to the corporate certificate store on the VM. Its actual path is
site-specific and not committed — set it once in an untracked `.env.local`
file next to `setup-after-clone-py.sh` (environment variables override it):

```
CERT_SOURCE=<cert-store-path>
CERT_HOSTNAME=<vm-hostname>   # optional; defaults to `hostname -f`
```

Required files in the store: `<vm-hostname>.cer` (→ `certs/server.crt`) and
`<vm-hostname>.key` (→ `certs/server.key`).

---

## Port: 5942 → 49160 (RHEL8 VM)

The application moved from port **5942** to **49160**. On the RHEL8 VM
(`<vm-hostname>`) run the following, in order:

```bash
cd /path/to/crucible          # wherever the repo is checked out on the VM
git pull

# Rebuild the image and (re)start on the new port
./container-py.sh rebuild

# Open the new port and close the old one (firewalld case — see Runbook C
# for the plain-iptables and no-firewall cases).
sudo firewall-cmd --permanent --add-port=49160/tcp
sudo firewall-cmd --permanent --remove-port=5942/tcp   # ok if "not enabled"
sudo firewall-cmd --reload
sudo firewall-cmd --list-ports                          # verify 49160/tcp

# Verify
curl --noproxy '*' -s http://localhost:49160/api/stats   # expect JSON stats
```

Notes:

- The app reads `PORT` (default 49160) and binds `0.0.0.0`; the container
  scripts accept `CRUCIBLE_PORT=<n>` overrides (a generic `PORT` env var is
  **ignored** to avoid clashes on shared machines).
- Rootless podman cannot bind ports below 1024; 49160 is unaffected.
- macOS quirk: Apple's `remoted` daemon listens on ports 49152+ on a
  link-local IPv6 address, so a wildcard bind of 49160 fails on Macs.
  The scripts publish on `127.0.0.1` on macOS and `0.0.0.0` on Linux;
  override with `HOST_BIND=<ip>`.

---

## Quick Start (after clone)

One command does everything (certs when available, build, start, verify,
optional monitoring cron) — on macOS **and** the RHEL8 VM:

```bash
git clone https://github.com/nestle-it/nr-nips-crucible.git
cd nr-nips-crucible
./setup-after-clone-py.sh
```

> **Private repo:** `nestle-it/nr-nips-crucible` needs authentication — clone
> over HTTPS with a Personal Access Token, or use an SSH key
> (`git@github.com:nestle-it/nr-nips-crucible.git`). The scripts are unaffected
> by which remote or clone method you use.

It will:

1. Copy SSL certificates from the Nestlé certificate store (when available; skipped gracefully on macOS)
2. Verify certificate/key pair integrity (MD5 modulus match)
3. Build the `crucible-py` image
4. Start the container (HTTPS when certs exist, else HTTP)
5. Verify the API answers
6. Optionally install the health-monitoring cron job

Non-interactive: `SETUP_MONITOR=y ./setup-after-clone-py.sh` (or `n`).

---

## Runbook A — macOS (Docker)

**Prerequisites:** Docker Desktop installed and **running**.

```bash
# 1. Clone (first time) or update
git clone https://github.com/nestle-it/nr-nips-crucible.git && cd nr-nips-crucible   # first time
git pull                                                               # update

# 2. Build (force docker even if podman is also installed)
CONTAINER_RUNTIME=docker ./container-py.sh build

# 3. Start (publishes 127.0.0.1:49160 on macOS)
CONTAINER_RUNTIME=docker ./container-py.sh start

# 4. Verify
curl -s http://localhost:49160/api/stats          # → JSON with counts
open http://localhost:49160                        # full UI in the browser

# 5. Logs / status / stop / update
CONTAINER_RUNTIME=docker ./container-py.sh logs      # Ctrl-C to detach
CONTAINER_RUNTIME=docker ./container-py.sh status
CONTAINER_RUNTIME=docker ./container-py.sh stop
git pull && CONTAINER_RUNTIME=docker ./container-py.sh rebuild
```

Tip: `export CONTAINER_RUNTIME=docker` once per shell instead of prefixing
every command. Without it the script prefers podman when both are installed.

---

## Runbook B — macOS (Podman)

**Prerequisites:** Podman ≥ 5. Podman on macOS = a thin client plus a Linux
VM (`podman machine`). **The VM does not auto-start on login** — the script
checks and tells you; the command is:

```bash
podman machine start        # ~15 s; 'podman machine list' shows state
```

Worth knowing:

- The VM is rootless — ports below 1024 cannot be bound (49160 is fine).
- Default VM RAM is 2 GiB. The image build (npm build + pip install of
  RDKit/pandas) fits, but if a build is OOM-killed (exit 137), grow it once:
  `podman machine stop && podman machine set --memory 4096 && podman machine start`
- Apple Silicon: images build for the VM's architecture. Check with
  `podman machine ssh uname -m`. For an explicit amd64 image use
  `PLATFORM=linux/amd64 ./container-py.sh build` (slower, emulated). The
  `rdkit` wheel is published for macOS arm64 and linux x86_64/aarch64, so no
  compiler is needed either way.

```bash
git clone https://github.com/nestle-it/nr-nips-crucible.git && cd nr-nips-crucible
podman machine start 2>/dev/null || true
./container-py.sh build      # podman auto-detected; --format docker applied automatically
./container-py.sh start
curl -s http://localhost:49160/api/stats
open http://localhost:49160
```

---

## Runbook C — RHEL8 VM (Podman)

Target: `<vm-hostname>`, rootless podman, port 49160.

```bash
# 0. Prerequisites (once): git + podman (RHEL8 AppStream)
sudo dnf install -y git podman
podman --version           # any 4.x/5.x is fine

# 1. Clone (first time) or update
git clone https://github.com/nestle-it/nr-nips-crucible.git && cd nr-nips-crucible   # first time
cd /path/to/crucible && git pull                                       # update
chmod +x container-py.sh                                               # first time only

# (Shortcut: ./setup-after-clone-py.sh does the build, start, verify and the
#  monitoring cron in one command, plus the SSL-cert copy. The manual steps
#  below remain for understanding and troubleshooting.)

# 2. Build the image (native linux/amd64 build)
./container-py.sh build

# 3. Open the firewall port (once) — check what firewall exists first.
rpm -q firewalld iptables-services       # what is installed?
sudo iptables -L INPUT -n | head          # empty chains + policy ACCEPT = no host firewall

#   Case A — firewalld installed:
sudo firewall-cmd --permanent --add-port=49160/tcp
sudo firewall-cmd --permanent --remove-port=5942/tcp   # ok if "not enabled"
sudo firewall-cmd --reload
sudo firewall-cmd --list-ports                          # verify 49160/tcp

#   Case B — plain iptables with real rules:
sudo iptables -I INPUT -p tcp --dport 49160 -j ACCEPT
sudo service iptables save                # persists only with iptables-services

#   Case C — no host firewall at all (common on internal VMs): nothing to do.

# 4. Start (publishes 0.0.0.0:49160 on Linux automatically).
#    A generic PORT variable in your shell is ignored; override with CRUCIBLE_PORT=<n>.
./container-py.sh start

# 5. Verify
curl --noproxy '*' -s http://localhost:49160/api/stats    # JSON counts
curl --noproxy '*' -s http://localhost:49160/ | grep -o '<title>[^<]*</title>'
# From your workstation: http://<vm-hostname>:49160

# 6. Logs / status / stop / update
./container-py.sh logs
./container-py.sh status
./container-py.sh stop
git pull && ./container-py.sh rebuild
```

### Enable HTTPS (optional)

The backend serves TLS in-process (uvicorn) from the `certs/` directory:

```bash
# One-time: put certificates in certs/
./setup-after-clone-py.sh     # copies the Nestlé-signed certs from the corporate cert store (VM)
# or, for a self-signed dev cert:  ./setup-ssl.sh

# Start in TLS mode (recreates the container with certs mounted read-only)
./container-py.sh start-ssl

# Verify (-k only needed for self-signed certs)
curl --noproxy '*' -sk https://localhost:49160/api/stats
```

The app is then at `https://<vm-hostname>:49160`. Notes:

- HTTPS *replaces* HTTP on the port — plain `http://` requests are refused.
  Switch back with `./container-py.sh stop && podman rm crucible-py && ./container-py.sh start`.
- The container healthcheck probes HTTP then HTTPS, so it stays `healthy` in either mode.
- If `monitor.sh` runs in cron, point it at TLS:
  `CONTAINER_NAME=crucible-py API_URL=https://localhost:49160/api/stats ./monitor.sh`
- For the Quadlet unit, add `Environment=USE_HTTPS=true` and
  `Volume=%h/crucible/certs:/app/certs:Z,ro` (plus `SSL_CERT_PATH` /
  `SSL_KEY_PATH` if your file names differ).
- Missing/unreadable certificates never take the app down — it logs a warning
  and falls back to HTTP.

---

## SSL/TLS certificate setup

Certificates are **never committed to git** and must be set up per deployment.

### Automatic (recommended)

```bash
./setup-after-clone-py.sh
```

### Manual

```bash
mkdir -p certs
CERT_SOURCE="<cert-store-path>"
cp "$CERT_SOURCE/<vm-hostname>.cer" certs/server.crt
cp "$CERT_SOURCE/<vm-hostname>.key" certs/server.key
chmod 600 certs/server.key
chmod 644 certs/server.crt
```

### Verify the certificate/key pair

A mismatched certificate and key will fail the TLS handshake. Both hashes
**must** be identical:

```bash
openssl x509 -noout -modulus -in certs/server.crt | openssl md5
openssl rsa  -noout -modulus -in certs/server.key | openssl md5
```

### Rotating / replacing the certificate

Use this when the key is compromised or the certificate is renewed. The
database is untouched (it lives on the `./data` volume), so this only swaps the
cert/key and restarts TLS:

```bash
# 1. Keep the current cert/key as a rollback copy
cp certs/server.crt certs/server.crt.bak 2>/dev/null || true
cp certs/server.key certs/server.key.bak 2>/dev/null || true

# 2. Install the NEW cert + key (from the Nestlé store or wherever it was issued)
cp /path/to/new/server.crt certs/server.crt
cp /path/to/new/server.key certs/server.key
chmod 644 certs/server.crt && chmod 600 certs/server.key

# 3. Verify the pair matches BEFORE restarting — both hashes must be identical
openssl x509 -noout -modulus -in certs/server.crt | openssl md5
openssl rsa  -noout -modulus -in certs/server.key | openssl md5

# 4. Restart in HTTPS mode to load the new cert, then verify
./container-py.sh start-ssl
podman exec crucible-py python /app/backend/scripts/healthcheck.py && echo healthy
curl --noproxy '*' -kv https://localhost:49160/api/stats 2>&1 | grep -iE 'subject:|issuer:|expire'
```

> Shortcut: `CERT_SOURCE=/path/to/new ./setup-after-clone-py.sh` copies and
> verifies the pair for you. Once the new cert is confirmed working, delete the
> `.bak` files — the old (exposed) key is then retired.

### Certificate-expiry monitoring

`./cert-expiry-check.sh` reports how long the current certificate is valid and
**warns when it is within `WARN_DAYS` (default 30) of expiring** — so a renewal
never sneaks up on you. Exit code `0` = OK, `1` = expiring soon / expired /
unreadable. Works on macOS and RHEL8 (no container required).

```bash
./cert-expiry-check.sh                     # check certs/server.crt (default)
WARN_DAYS=60 ./cert-expiry-check.sh        # warn earlier
CERT_FILE=/path/to/other.crt ./cert-expiry-check.sh
```

Run it weekly from cron (logs to `~/crucible-cert.log`):

```bash
crontab -e
# Mondays 08:00 — warn if the cert expires within 30 days:
0 8 * * 1 cd /path/to/crucible && ./cert-expiry-check.sh >> ~/crucible-cert.log 2>&1
```

When it warns, follow "Rotating / replacing the certificate" above.

### Self-signed (development only)

```bash
./setup-ssl.sh
```

Generates a self-signed certificate for this host with 365-day validity;
browsers will show a security warning.

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `49160` | HTTP/HTTPS port the app binds (inside the container) |
| `CRUCIBLE_PORT` | *(unset)* | Port override for `container-py.sh` (a generic `PORT` in the shell is ignored) |
| `HOST_BIND` | `127.0.0.1` (macOS) / `0.0.0.0` (Linux) | Published-port interface |
| `USE_HTTPS` | `false` | `true` + cert files present → uvicorn serves TLS |
| `SSL_CERT_PATH` | `/app/certs/server.crt` | TLS certificate path (in-container) |
| `SSL_KEY_PATH` | `/app/certs/server.key` | TLS private-key path (in-container) |
| `DATABASE_URL` | `sqlite:///<repo>/data/crucible.db` | SQLAlchemy connection string. PostgreSQL: `postgresql+psycopg://user:pass@host/crucible` |
| `USE_POSTGRES` | `false` | `true` → `container-py.sh` runs the app against the managed Postgres container (see [Database](#database-sqlite-and-postgresql)) |
| `AUTO_INIT_DB` | `true` (`false` in the image) | When `true` the app runs `create_all()` on startup. The container sets `false` so **Alembic** owns the schema instead |
| `CONTAINER_RUNTIME` | *(auto-detect)* | Force `podman` or `docker` |
| `PLATFORM` | *(native)* | Cross-build target, e.g. `linux/amd64` |

The container is created (HTTP mode) roughly as:

```bash
podman run -d --name crucible-py \
  -p 0.0.0.0:49160:49160 \
  -v ./data:/app/data:Z \
  -e PORT=49160 \
  --restart unless-stopped \
  crucible-py:latest
```

In HTTPS mode `start-ssl` additionally mounts `./certs:/app/certs:Z,ro` and
sets `USE_HTTPS=true`.

> **SELinux (RHEL8):** the `:Z` suffix relabels a bind-mount so the container
> can access it. The scripts always append it; if you mount volumes manually,
> do the same or you will see `Permission denied` on `/app/data`.

---

## Live-mounted directories

`data/` is bind-mounted so the database persists across container restarts and
rebuilds:

| Host path | Container path | Mode | Purpose |
|-----------|---------------|------|---------|
| `./data/` | `/app/data` | read-write (`:Z`) | SQLite database (`crucible.db`) |
| `./certs/` | `/app/certs` | read-only (`:Z,ro`, HTTPS mode) | SSL cert + key |

The application code (`backend/app`, built `client/dist`, `docs/`) is **baked
into the image**. Changes to routes, React components, or docs require a
rebuild: `./container-py.sh rebuild`.

---

## Database: SQLite and PostgreSQL

The app talks to the database only through **SQLAlchemy 2**, so the same code
runs on either engine. The engine is chosen by `DATABASE_URL`.

### SQLite (default)

Nothing to configure. Data lives in the bind-mounted `data/crucible.db`; back
it up with `./container-py.sh backup` (see [Backup and restore](#backup-and-restore)).
This is the right choice for a single-node dev/UAT deployment.

### PostgreSQL (optional)

`container-py.sh` can run a managed Postgres container alongside the app. The
two containers share a private network (`crucible-net`) and the database
persists in a named volume (`crucible-pgdata`).

```bash
# 1. Bring up PostgreSQL (creates the network + volume the first time)
./container-py.sh db-start

# 2. Start the app pointed at PostgreSQL
USE_POSTGRES=true ./container-py.sh start          # or start-ssl for HTTPS

# psql shell / stop the database when needed
./container-py.sh db-shell
./container-py.sh db-stop
```

When `USE_POSTGRES=true`, `start`/`start-ssl` attach the app to `crucible-net`,
set `DATABASE_URL=postgresql+psycopg://crucible:crucible@crucible-db:5432/crucible`
and `AUTO_INIT_DB=false`. Override any of these with the matching env vars
(`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DB_CONTAINER_NAME`,
`DB_NETWORK`, `DB_VOLUME`, `DB_HOST_PORT`), or point `DATABASE_URL` at an
external/managed Postgres and skip `db-start` entirely.

> On the `doc` JSON column, PostgreSQL uses **`JSONB`** automatically (via a
> SQLAlchemy type variant); SQLite uses plain `JSON`. No code changes needed.

### Schema is owned by Alembic (in the container)

The image runs [backend/scripts/entrypoint.sh](backend/scripts/entrypoint.sh)
at start, which calls
[backend/scripts/db_bootstrap.py](backend/scripts/db_bootstrap.py) before
uvicorn. Bootstrap is **adopt-or-upgrade** and safe to run repeatedly:

- **empty database** → `alembic upgrade head` (creates the schema),
- **existing pre-Alembic schema** (e.g. a `data/crucible.db` created by an
  older build) → stamp `0001_initial`, then `upgrade head`,
- **already Alembic-managed** → `upgrade head` (a no-op when current).

Because `AUTO_INIT_DB=false` in the image, the app never races the migration.
Outside the container (local dev, tests) `AUTO_INIT_DB` defaults to `true`, so
`create_all()` keeps working with no Alembic step.

### Migrating existing SQLite data into PostgreSQL

[backend/scripts/migrate_sqlite_to_postgres.py](backend/scripts/migrate_sqlite_to_postgres.py)
copies every row (preserving `seq` order) and is idempotent — re-running skips
rows that already exist.

```bash
# with the target Postgres schema already created (db-start + one app start,
# or `alembic upgrade head` against the target)
cd backend
python scripts/migrate_sqlite_to_postgres.py \
  --source "sqlite:///../data/crucible.db" \
  --target "postgresql+psycopg://crucible:crucible@localhost:5432/crucible"
```

### Creating a new migration

After changing `backend/app/models.py`, autogenerate and review a revision:

```bash
cd backend
alembic revision --autogenerate -m "describe change"   # writes alembic/versions/<id>_*.py
alembic upgrade head                                    # apply locally
alembic check                                           # verify no drift remains
```

Commit the generated file in `backend/alembic/versions/`. The container applies
it automatically on the next start.

---

## Health monitoring

`setup-after-clone-py.sh` installs a cron job automatically. Manual install /
check:

```bash
crontab -l | grep monitor.sh          # is it installed, and for which container?
# correct entry (use https:// after start-ssl):
# */5 * * * * cd /path/to/crucible && CONTAINER_NAME=crucible-py API_URL=http://localhost:49160/api/stats ./monitor.sh
tail -5 /tmp/crucible-monitor.log     # what has it been doing?
```

`monitor.sh` sends a GET to `/api/stats`; on a non-200 response it restarts
the `crucible-py` container and logs to `/tmp/crucible-monitor.log`. The
container also has a built-in `HEALTHCHECK` (every 30 s) that probes
`/api/stats` (see [backend/scripts/healthcheck.py](backend/scripts/healthcheck.py)).

Run it manually any time: `./monitor.sh`.

---

## Auto-start on boot (systemd)

Rootless containers die with your login session unless you enable lingering
and a systemd unit:

```bash
# Allow user services to run without an active login
sudo loginctl enable-linger $USER

# Option 1 (quick, podman 4.x): generate a unit from the container
mkdir -p ~/.config/systemd/user
podman generate systemd --new --name crucible-py --files
mv container-crucible-py.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now container-crucible-py.service

# Option 2 (preferred on podman ≥ 4.4): Quadlet
mkdir -p ~/.config/containers/systemd
cat > ~/.config/containers/systemd/crucible-py.container <<'EOF'
[Unit]
Description=Crucible Python backend

[Container]
Image=localhost/crucible-py:latest
ContainerName=crucible-py
PublishPort=0.0.0.0:49160:49160
Volume=%h/crucible/data:/app/data:Z
Environment=PORT=49160

[Service]
Restart=always

[Install]
WantedBy=default.target
EOF
# Adjust the Volume= path to the actual repo checkout, then:
systemctl --user daemon-reload
systemctl --user start crucible-py.service
```

---

## Backup and restore

Everything worth backing up lives in `data/crucible.db`. Identical commands on
macOS and the RHEL8 VM (the script handles podman vs docker, running vs
stopped):

```bash
./container-py.sh backup                                   # → backups/crucible-<stamp>.db
./container-py.sh restore                                  # lists available backups
./container-py.sh restore backups/crucible-<stamp>.db      # stop → swap db → restart
```

- **Safe while running** — uses SQLite's online-backup API inside the
  container, so you never get a torn copy. Never plain-`cp` a *live* SQLite
  file; that can catch it mid-write and corrupt the backup.
- Restore keeps the current database as `data/crucible.db.pre-restore` (safety
  net) before swapping. Verify afterwards with
  `curl --noproxy '*' -s http://localhost:49160/api/stats`.
- Override the destination with `BACKUP_DIR=/path ./container-py.sh backup`.

### Moving data between machines

A backup file is portable — copy it and restore on the other machine:

```bash
# source machine
./container-py.sh backup
scp backups/crucible-<stamp>.db user@other-machine:/path/to/crucible/backups/
# target machine
./container-py.sh restore backups/crucible-<stamp>.db
```

### Scheduled backups on the RHEL8 VM (recommended)

```bash
crontab -e
# Nightly at 02:00, keep the 14 most recent, log to ~/crucible-backup.log:
0 2 * * * cd /path/to/crucible && USER=$(id -un) XDG_RUNTIME_DIR=/run/user/$(id -u) ./container-py.sh backup >> ~/crucible-backup.log 2>&1 && ls -t backups/crucible-*.db | tail -n +15 | xargs -r rm
```

> **Cron + rootless podman:** the `USER=$(id -un) XDG_RUNTIME_DIR=/run/user/$(id -u)`
> prefix is required. Cron's minimal environment otherwise cannot locate the
> rootless podman storage (on a network-mounted home it resolves to a bad path), so
> `container-py.sh` would silently fall back to an **unsafe plain `cp`** of the
> live database. The same prefix applies to the `monitor.sh` cron entry.

Because `backups/` lives on the VM's own disk, also copy important backups
off-machine periodically — a backup on the same disk as the database does not
survive a disk failure.

---

## Maintenance and operational tasks

Periodic and as-needed operations. The detailed runbooks are in the sections
referenced below — this table is the "when to do it" summary.

| Task | When | How |
|---|---|---|
| **Rotate the TLS cert/key** | On certificate renewal, or **immediately if the key is exposed/compromised** (e.g. it was ever committed to git) | [SSL/TLS certificate setup](#ssltls-certificate-setup) → "Rotating / replacing the certificate": install the new pair, then `./container-py.sh start-ssl` |
| **Check cert expiry** | Weekly (cron) — catches renewals before they lapse | `./cert-expiry-check.sh` (see [SSL/TLS → Certificate-expiry monitoring](#ssltls-certificate-setup)) |
| **Automate nightly backups** | Recommended — set up **once** on the RHEL8 VM. The database is not in git, so backups are the safety net | [Backup and restore](#backup-and-restore) → "Scheduled backups on the RHEL8 VM": a `crontab` line |
| **Copy backups off-machine** | Weekly, and before risky changes | `scp` a recent `backups/crucible-*.db` to another host (see [Backup and restore](#backup-and-restore)) |
| **Purge a secret from git history** | Only **after** rotating a key that had been committed, and only if you also want the old key unrecoverable from history | see [Purging a secret from git history](#purging-a-secret-from-git-history) below |

### Purging a secret from git history

Untracking a file (`git rm --cached` + `.gitignore`) stops *future* commits
from including it, but the file stays in past commits. If a secret such as
`certs/server.key` was ever committed and pushed, **rotating the key is the
real fix** — once the old key is retired it no longer matters that history
holds it. Purge history only if you additionally want it scrubbed.

> ⚠️ **Destructive and disruptive.** History rewriting changes every commit
> SHA after the affected point and requires a **force-push to all branches**.
> Coordinate with the team first — everyone must re-clone (or hard-reset)
> afterwards. Always rotate the key *before* this, never instead of it.

```bash
# 1. Install the tool once
pip install git-filter-repo

# 2. In a FRESH clone, strip the file(s) from all history
git filter-repo --invert-paths \
  --path certs/server.key --path certs/server.crt --path data/crucible.db

# 3. Re-add the remote (filter-repo removes it) and force-push every branch + tags
git remote add origin <repo-url>
git push --force --all origin
git push --force --tags origin

# 4. Everyone else re-syncs:  git fetch && git reset --hard origin/<branch>   (or re-clone)
```

For a private repo, rotating the key is usually enough; treat the history
purge as belt-and-suspenders.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Works on the VM, unreachable from workstation | host firewall | firewalld: `sudo firewall-cmd --permanent --add-port=49160/tcp && sudo firewall-cmd --reload` · plain iptables: `sudo iptables -I INPUT -p tcp --dport 49160 -j ACCEPT` (+ `service iptables save`) · if neither is installed and `iptables -L INPUT` is empty, the blocker is the network, not the host |
| `sudo: firewall-cmd: command not found` | firewalld not installed | do **not** install it (would impose default-deny); diagnose with `rpm -q firewalld iptables-services` and `sudo iptables -L INPUT -n`, then use the iptables or no-firewall path in Runbook C step 3 |
| Container binds an unexpected port (`rootlessport listen tcp 0.0.0.0:3000: address already in use`) | a `PORT` variable exported in the shell | the scripts **ignore** a generic `PORT` (override only via `CRUCIBLE_PORT=<n>`). If it persists: `git pull`, `podman rm -f crucible-py`, `./container-py.sh start` |
| `/app/data` empty / `Permission denied` in logs | SELinux blocks the bind-mount | the scripts mount with `:Z`; if you mount manually, always append `:Z` |
| `bind: permission denied` on a port | rootless podman cannot bind ports < 1024 | use ports ≥ 1024 (49160 is fine) or `sudo sysctl net.ipv4.ip_unprivileged_port_start=<n>` |
| `address already in use` on 49160 | an old container still mapped | `podman ps -a`, then `podman rm -f <name>` |
| Image pull prompts "Please select an image" | short image name | already handled — the Dockerfile uses fully-qualified names (`docker.io/library/...`) |
| Container gone after logout/reboot | rootless containers die with the session | `sudo loginctl enable-linger $USER` + a systemd unit (see above) |
| Healthcheck `unhealthy` but curl works | image built without `--format docker` (podman OCI drops HEALTHCHECK) | rebuild with `./container-py.sh build` (flag applied automatically) |
| Healthcheck `unhealthy` while the app serves 200s (especially in HTTPS mode) | the in-container probe was routed through the corporate proxy → `403` (a plain `urllib`/`curl` without `--noproxy` hits the proxy, whose `no_proxy` does not list `127.0.0.1`) | fixed in `backend/scripts/healthcheck.py`, which now bypasses the proxy — rebuild to pick up the fix: `./container-py.sh build && ./container-py.sh start-ssl` (or `start` for HTTP) |
| Corporate proxy breaks localhost curl | proxy env vars | use `curl --noproxy '*' ...` (the scripts already do) |
| `podman ps` shows `Up ... (starting)` | healthcheck hasn't run yet (30 s interval) | normal — flips to `(healthy)` after the first successful probe |
| TLS handshake fails on `start-ssl` | mismatched cert/key | verify with the modulus-hash check above; re-copy from the cert store; `./container-py.sh rebuild` |
| Database looks empty after a restart | `data/` not mounted / wrong checkout path | confirm `./data/crucible.db` exists and the container mounts `./data:/app/data:Z` |

### Reset the database

```bash
rm -f data/crucible.db        # re-created empty on next start
./container-py.sh restart
```

---

## Security

### Current implementation

- **HTTPS/TLS**: production traffic encrypted with official Nestlé certificates (`./container-py.sh start-ssl`)
- **Certificate management**: certs/keys excluded from git; verified on setup; private key `chmod 600`
- **Error handling**: API returns `{"error": ...}` JSON — no sensitive data in responses
- **Container isolation**: runs rootless (podman) on the VM
- **Health monitoring**: automated recovery from crashes

### Protected files (`.gitignore`)

```
certs/             # SSL certificates and private keys
data/*.db          # SQLite database
node_modules/      # dependencies (installed per machine)
client/dist/       # build output
backend/.venv/     # Python virtualenv
```

### Known gaps / future enhancements

- [ ] **SSO / authentication** — none yet (HTTPS is transport encryption only). A FastAPI dependency or an authenticating reverse proxy is the natural hook; plan before wider rollout.
- [ ] Role-based access control (RBAC)
- [ ] Rate limiting and audit logging
- [ ] Certificate-expiry monitoring/alerts

---

## Uninstall and reinstall

### Uninstall

Instructions for partially or completely removing Crucible from the system.


> ℹ️ `uninstall.sh` removes the deployment (works with podman or docker, on macOS and RHEL8). 

Modes:

```bash
./uninstall.sh --dry-run     # preview everything it would remove (safe)
./uninstall.sh --partial     # remove runtime artifacts; keep source & data
./uninstall.sh --full        # remove EVERYTHING (final data backup taken first)
./uninstall.sh               # interactive: choose step by step
```

It removes: the `crucible-py` container + image, the monitoring cron entry and
`/tmp/crucible-monitor.log`, `data/crucible.db` (backed up to
`~/crucible-backups` before deletion in full mode), the local `backups/`
directory, `backend/.venv` and Python caches, and the rootless systemd /
Quadlet units (with a reminder to `sudo loginctl disable-linger $USER`). Base
images (`python:3.12-slim`, `node:18-alpine`) are left in place — prune
manually if wanted.

On the RHEL8 VM, remember the firewall rule if one was added
(`sudo iptables -D INPUT -p tcp --dport 49160 -j ACCEPT`, or the firewalld
`--remove-port` variant).

#### Using the Uninstall Script (Recommended)

The easiest way to clean up is with the `uninstall.sh` script:

```bash
# Interactive — guided step-by-step cleanup
./uninstall.sh

# Partial — remove container, image, cron, logs (keep source & data)
./uninstall.sh --partial

# Full — remove everything including data and source code
./uninstall.sh --full

# Dry run — preview what would be removed without deleting anything
./uninstall.sh --dry-run
```

If you prefer to run the steps manually, follow the guide below.

#### Step 1: Stop the Application

```bash
cd ~/work/Pandora_toolbox/nr-nips-crucible

# Stop the container
./container.sh stop

# Verify it's stopped
podman ps -a --filter name=crucible-py
```

### Step 2: Remove the Container

```bash
# Remove the stopped container
podman rm crucible-py

# Verify removal
podman ps -a --filter name=crucible-py
# ✅ Should show no results
```

### Step 3: Remove the Container Image

```bash
# Remove the Crucible image
podman rmi crucible-py:latest

# Verify removal
podman images | grep crucible
# ✅ Should show no results

# (Optional) Remove any dangling/orphaned images
podman image prune -f
```

### Step 4: Remove Health Monitoring Cron Job

```bash
# View current cron jobs
crontab -l

# Remove the pandora monitor entry
crontab -l | grep -v 'monitor.sh' | crontab -

# Remove the crucible backup monitor entry
crontab -l | grep -v 'container-py.sh backup' | crontab -

# Verify removal
crontab -l | grep crucible-py
# ✅ Should show no results

# Remove monitor log file
rm -f /tmp/crucible-monitor.log
```

### Step 5: Remove SSL Certificates

```bash
# Delete local certificate copies
rm -rf certs/

# ⚠️ Do NOT delete the source certificates at:
# <cert-store-path>/
# Those are shared infrastructure certificates.
```

### Step 6: Remove Application Data

> ⚠️ **Warning**: This permanently deletes all uploaded chemicals, samples, screening, and toxicology data.

```bash
# Delete database
rm -rf data/

# If using named volumes
podman volume rm crucible-data 2>/dev/null
```

**To back up before deleting:**

```bash
mkdir -p ~/crucible-backups/
cp data/crucible.db ~/crucible-backups/crucible-final-$(date +%Y%m%d-%H%M%S).db
```

### Step 7: Remove node_modules (Optional)

If you plan to keep the source code but want to free disk space:

```bash
rm -rf node_modules/ client/node_modules/ server/node_modules/

# You can reinstall later with:
# npm run install:all
```

### Step 8: Remove the Project Directory (Full Removal)

> ⚠️ **Warning**: This deletes all source code. Make sure you've pushed any changes to git first.

```bash
cd ~/work/Pandora_toolbox/
rm -rf nr-nips-crucible
```

### Step 9: Remove systemd Service (If Configured)

If you set up the optional systemd service:

```bash
sudo systemctl stop crucible-py
sudo systemctl disable crucible-py
sudo rm /etc/systemd/system/crucible-py.service
sudo systemctl daemon-reload
```

#### Cleanup Summary

The following table lists everything that gets created during installation and where to find it:

| Component | Location | Cleanup Command |
|-----------|----------|----------------|
| Container | `crucible-py` | `podman rm crucible-py` |
| Image | `crucible-py:latest` | `podman rmi crucible-py:latest` |
| Data volume | `./data/` or `crucible-data` | `rm -rf data/` or `podman volume rm crucible-data` |
| SSL certificates | `./certs/` | `rm -rf certs/` |
| Cron job monitor | User crontab | `crontab -l \| grep -v 'monitor.sh' \| crontab -` |
| Cron job backup | User crontab | `crontab -l \| grep -v 'container-py.sh backup' \| crontab -` |
| Monitor log | `/tmp/crucible-monitor.log` | `rm -f /tmp/crucible-monitor.log` |
| node_modules | `./node_modules/`, `client/`, `server/` | `rm -rf node_modules/ client/node_modules/ server/node_modules/` |
| Build output | `client/dist/` | `rm -rf client/dist/` |
| systemd service | `/etc/systemd/system/crucible-py.service` | `sudo rm` + `systemctl daemon-reload` |
| Project source | Full project directory | `rm -rf nr-nips-crucible/` |


#### Partial Cleanup (Keep Source Code)

If you want to stop running the application but keep the repository for future use:

```bash
# Automated (recommended)
./uninstall.sh --partial

# Or manually:
./container.sh clean
crontab -l | grep -v 'monitor.sh' | crontab -
crontab -l | grep -v 'container-py.sh backup' | crontab -
rm -f /tmp/crucible-monitor.log
rm -rf certs/ data/

# The source code remains intact and can be re-deployed with:
# ./setup-after-clone-py.sh
```

### Reinstall / redeploy

Reinstalling is the same as a first deploy. The single command below works on
**both macOS and the RHEL8 VM** — it auto-detects podman/docker and copies
certs when they are available:

```bash
# 1. Get the source back if a --full uninstall removed it
git clone https://github.com/nestle-it/nr-nips-crucible.git
cd nr-nips-crucible  # (or: cd into your existing checkout and run `git pull`)

# 2. Build + start + verify (+ optional monitoring cron) in one step
./setup-after-clone-py.sh
```

Prefer the individual steps? They are identical on both platforms:

```bash
./container-py.sh build
./container-py.sh start          # HTTP  (or ./container-py.sh start-ssl for HTTPS)
curl --noproxy '*' -s http://localhost:49160/api/stats   # expect JSON stats
```

Restore data afterwards if you kept a backup (a `--full` uninstall leaves a
final copy in `~/crucible-backups`):

```bash
./container-py.sh restore ~/crucible-backups/crucible-final-<stamp>.db
```

**Platform-specific reminders:**

| | macOS (dev) | RHEL8 VM (production) |
|---|---|---|
| Before building | Podman: `podman machine start` · Docker: start Docker Desktop | `sudo dnf install -y git podman` (first time only) |
| Certificates | usually none → starts in HTTP (see [SSL/TLS](#ssltls-certificate-setup)) | `setup-after-clone-py.sh` copies Nestlé certs from the corporate cert store → HTTPS |
| Firewall | not needed | reopen the port if you removed it (see [Runbook C](#runbook-c--rhel8-vm-podman)) |
| Auto-start on boot | not needed | re-enable the systemd/Quadlet unit (see [Auto-start on boot](#auto-start-on-boot-systemd)) |

Full first-deploy walkthroughs with troubleshooting: [Runbook A](#runbook-a--macos-docker)
(macOS Docker), [Runbook B](#runbook-b--macos-podman) (macOS Podman),
[Runbook C](#runbook-c--rhel8-vm-podman) (RHEL8 Podman).


---

## Scaling

### Horizontal Scaling

For high availability, deploy multiple instances:

```bash
# Instance 1
podman run -d --name crucible-py-1 -p 49160:49160 ...

# Instance 2
podman run -d --name crucible-py-2 -p 5944:49160 ...

# Use load balancer (nginx) to distribute traffic
```

### Vertical Scaling

Increase container resources:

```bash
podman run -d \
  --name crucible-py \
  --cpus 4 \
  --memory 4g \
  -p 49160:49160 \
  crucible-py:latest
```

---


### Environment Variables Reference

Complete list of all environment variables used by Crucible:

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `49160` | Application port (HTTP or HTTPS depending on `USE_HTTPS`) |
| `USE_HTTPS` | `false` | Set to `true` to enable TLS. Requires valid cert/key files. |
| `SSL_CERT_PATH` | `/app/certs/server.crt` | Path to SSL certificate file |
| `SSL_KEY_PATH` | `/app/certs/server.key` | Path to SSL private key file |
| `CA_BUNDLE_PATH` | `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem` | CA bundle for certificate chain (overridden to `/etc/ssl/certs/ca-certificates.crt` in Alpine containers) |
| `NODE_ENV` | `undefined` | Set to `production` for optimized builds |
| `NODE_TLS_REJECT_UNAUTHORIZED` | `1` | Set to `0` only for development with self-signed certs |

---

### Server Runtime Behaviour

#### Timeouts

| Setting | Value | Purpose |
|---------|-------|---------|
| `keepAliveTimeout` | 65,000 ms | How long to keep idle connections open |
| `headersTimeout` | 66,000 ms | Maximum time to receive request headers |
| `server.timeout` | 120,000 ms | Maximum time for the entire request/response cycle |

#### Memory Monitoring

The server logs memory usage every **5 minutes** to stdout:
```
Memory: RSS=85MB, Heap=42MB
```

#### Error Resilience

- **`uncaughtException`** — logged but does NOT crash the server (keeps running)
- **`unhandledRejection`** — logged but does NOT crash the server
- Combined with Podman `--restart=always` and the cron health monitor, this ensures maximum uptime.

---

### Support

For deployment issues:
- Email: `<maintainer-email>`
- Slack: #crucible
- Docs: [README.md](README.md) | [API.md](API.md)

---

**Last Updated:** August 28, 2026
