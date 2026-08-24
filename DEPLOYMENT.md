[← README](README.md) · [All docs in order](README.md#the-documentation-in-order) · [Glossary](docs/GLOSSARY.md)

# Deployment Guide — Crucible: Pandora Toolbox Enhancement (v2.0)

Operational **reference** for the Crucible **Python/FastAPI** backend on macOS
(development) and the RHEL8 VM (production).

> **Step-by-step walkthroughs live in the platform guides.** Install:
> [docs/INSTALL-MACOS.md](docs/INSTALL-MACOS.md) ·
> [docs/INSTALL-RHEL8.md](docs/INSTALL-RHEL8.md). Uninstall:
> [docs/UNINSTALL-MACOS.md](docs/UNINSTALL-MACOS.md) ·
> [docs/UNINSTALL-RHEL8.md](docs/UNINSTALL-RHEL8.md). **This document is the
> reference** — architecture, environment variables, database, backups,
> maintenance, troubleshooting — and the canonical home for material the guides
> link back to (the Quadlet unit, the env table, the cron lines).

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
- [Scaling](#scaling)

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
USE_HTTPS=true                # makes plain `start`/`rebuild` come up HTTPS
```

Required files in the store: `<vm-hostname>.cer` (→ `certs/server.crt`) and
`<vm-hostname>.key` (→ `certs/server.key`).

`container-py.sh` also reads `.env.local`: with `USE_HTTPS=true` set there,
plain `./container-py.sh start` and `rebuild` start in HTTPS mode even when no
container exists yet (fresh install, post-uninstall) — without it, `rebuild`
can only preserve the mode of an existing container and defaults to HTTP from
scratch. Environment variables always override `.env.local`.

---

## Port: 5942 → 49160 (RHEL8 VM)

The application moved from port **5942** to **49160**. On the RHEL8 VM
(`<vm-hostname>`) run the following, in order:

```bash
cd /path/to/crucible          # wherever the repo is checked out on the VM
git pull

# Rebuild the image and (re)start on the new port
./container-py.sh rebuild

# Open the new port and close the old one (firewalld case — see
# docs/INSTALL-RHEL8.md §1.4 for the plain-iptables and no-firewall cases).
sudo firewall-cmd --permanent --add-port=49160/tcp
sudo firewall-cmd --permanent --remove-port=5942/tcp   # ok if "not enabled"
sudo firewall-cmd --reload
sudo firewall-cmd --list-ports                          # verify 49160/tcp

# Verify
curl --noproxy '*' -sS http://localhost:49160/api/stats   # expect JSON stats
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
./setup-after-clone-py.sh
```

Non-interactive: `SETUP_MONITOR=y ./setup-after-clone-py.sh` (or `n`).

> **Private repo:** `nestle-it/nr-nips-crucible` needs authentication — clone
> over HTTPS with a Personal Access Token, or use an SSH key
> (`git@github.com:nestle-it/nr-nips-crucible.git`). The scripts are unaffected
> by which remote or clone method you use.

Guided walkthroughs, with expected output at every step:
[docs/INSTALL-MACOS.md](docs/INSTALL-MACOS.md) ·
[docs/INSTALL-RHEL8.md](docs/INSTALL-RHEL8.md).

---

## Runbook A — macOS (Docker)

Full walkthrough: [docs/INSTALL-MACOS.md](docs/INSTALL-MACOS.md) (Docker
Desktop is Option B in its §1).

Docker-specific detail the guide does not spell out: when podman **and** docker
are both installed the scripts prefer podman, so force Docker explicitly with
`CONTAINER_RUNTIME=docker`:

```bash
export CONTAINER_RUNTIME=docker      # once per shell, instead of prefixing every command
./container-py.sh build
./container-py.sh start
```

---

## Runbook B — macOS (Podman)

Full walkthrough: [docs/INSTALL-MACOS.md](docs/INSTALL-MACOS.md) — including
`podman machine start` (the VM does **not** auto-start on login) and the build
OOM fix (`podman machine stop && podman machine set --memory 4096 && podman machine start`).

Architecture detail not covered there: images build for the podman VM's
architecture. Check it with `podman machine ssh uname -m`. On Apple Silicon,
for an explicit amd64 image use:

```bash
PLATFORM=linux/amd64 ./container-py.sh build     # slower, emulated
```

The `rdkit` wheel is published for macOS arm64 and linux x86_64/aarch64, so no
compiler is needed either way. The VM is rootless — ports below 1024 cannot be
bound (49160 is fine).

---

## Runbook C — RHEL8 VM (Podman)

Full walkthrough: [docs/INSTALL-RHEL8.md](docs/INSTALL-RHEL8.md). It covers
packages (§1.1), rootless subuid/subgid (§1.2), lingering (§1.3), the firewall
three-case diagnosis — firewalld / plain iptables / no host firewall (§1.4),
the one-shot and manual install paths (§2), HTTPS with corporate certificates
(§3), auto-start and monitoring (§4), and a verification checklist (§5).

Target: `<vm-hostname>`, rootless podman, port 49160. The condensed command
set, once the prerequisites in §1 are done:

```bash
./container-py.sh build
./container-py.sh start                                   # publishes 0.0.0.0:49160 on Linux
curl --noproxy '*' -sS http://localhost:49160/api/stats    # JSON counts
curl --noproxy '*' -sS http://localhost:49160/ | grep -o '<title>[^<]*</title>'
./container-py.sh logs | status | stop
git pull && ./container-py.sh rebuild
```

---

## SSL/TLS certificate setup

Certificates are **never committed to git** and must be set up per deployment.

**Initial setup** (copying from the corporate store, self-signed dev certs,
`start-ssl`, switching back to HTTP) is walked through in
[docs/INSTALL-RHEL8.md](docs/INSTALL-RHEL8.md) §3 and
[docs/INSTALL-MACOS.md](docs/INSTALL-MACOS.md) §3. In short:
`./setup-after-clone-py.sh` (corporate certs) or `./setup-ssl.sh` (self-signed,
365-day validity, development only), then `./container-py.sh start-ssl`.

Two behaviours worth knowing anywhere certificates are involved:

- The container healthcheck probes HTTP **then** HTTPS, so the same image stays
  `healthy` in either mode.
- Missing or unreadable certificates never take the app down — it logs a
  warning and falls back to HTTP.

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

> Shortcut: `rm certs/server.crt certs/server.key && CERT_SOURCE=/path/to/new ./setup-after-clone-py.sh`
> — the script only copies into an **empty** `certs/` (with the old pair still
> present it keeps the existing certificates), and it also rebuilds the image
> and restarts, so the manual steps 1–4 above are lighter for a pure cert swap.
> Once the new cert is confirmed working, delete the `.bak` files — the old
> (exposed) key is then retired.

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

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `49160` | HTTP/HTTPS port the app binds (inside the container) |
| `CRUCIBLE_PORT` | *(unset)* | Port override for `container-py.sh` (a generic `PORT` in the shell is ignored) |
| `HOST_BIND` | `127.0.0.1` (macOS) / `0.0.0.0` (Linux) | Published-port interface |
| `USE_HTTPS` | `false` | `true` + cert files present → uvicorn serves TLS. Set it in the VM's `.env.local` so `start`/`rebuild` default to HTTPS |
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

`setup-after-clone-py.sh` installs a cron job automatically — the guided setup
is [docs/INSTALL-RHEL8.md](docs/INSTALL-RHEL8.md) §4. The canonical crontab
entry (**one line**; use `https://` after `start-ssl`) is:

```bash
*/5 * * * * cd /path/to/crucible && USER=$(id -un) XDG_RUNTIME_DIR=/run/user/$(id -u) CONTAINER_NAME=crucible-py API_URL=http://localhost:49160/api/stats ./monitor.sh
```

Manual install / check:

```bash
crontab -l | grep monitor.sh          # is it installed, and for which container?
tail -5 /tmp/crucible-monitor.log     # what has it been doing?
```

`monitor.sh` sends a GET to `/api/stats`; on a non-200 response it restarts
the `crucible-py` container and logs to `/tmp/crucible-monitor.log`. The
container also has a built-in `HEALTHCHECK` (every 30 s) that probes
`/api/stats` (see [backend/scripts/healthcheck.py](backend/scripts/healthcheck.py)).

Run it manually any time: `./monitor.sh`.

> The `USER=$(id -un) XDG_RUNTIME_DIR=/run/user/$(id -u)` prefix is required
> under cron with rootless podman — see the note in
> [Backup and restore](#backup-and-restore).

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

Option 1 (`podman generate systemd`) is walked through step by step, with
expected output and the common failure modes, in
[docs/INSTALL-RHEL8.md](docs/INSTALL-RHEL8.md) §4.2. The Quadlet unit above is
the canonical copy — that guide links back here for it.

**For an HTTPS deployment**, add to the Quadlet `[Container]` section:

```
Environment=USE_HTTPS=true
Volume=%h/crucible/certs:/app/certs:Z,ro
```

plus `SSL_CERT_PATH` / `SSL_KEY_PATH` if your file names differ from
`server.crt` / `server.key`.

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
  `curl --noproxy '*' -sS http://localhost:49160/api/stats`.
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
| **Check cert expiry** | Weekly (cron) — catches renewals before they lapse | `./cert-expiry-check.sh` (see [SSL/TLS → Certificate-expiry monitoring](#certificate-expiry-monitoring)) |
| **Automate nightly backups** | Recommended — set up **once** on the RHEL8 VM. The database is not in git, so backups are the safety net | [Backup and restore](#backup-and-restore) → "Scheduled backups on the RHEL8 VM": a `crontab` line |
| **Copy backups off-machine** | Weekly, and before risky changes | `scp` a recent `backups/crucible-*.db` to another host (see [Backup and restore](#backup-and-restore)) |
| **Reclaim disk from old images** | Every few rebuilds — each `rebuild` orphans the previous image | `podman image prune -f` (see [Reclaiming disk space](#reclaiming-disk-space) below) |
| **Purge a secret from git history** | Only **after** rotating a key that had been committed, and only if you also want the old key unrecoverable from history | see [Purging a secret from git history](#purging-a-secret-from-git-history) below |

### Reclaiming disk space

Every `./container-py.sh rebuild` builds a new image and leaves the previous
one behind without a name — a **dangling image**. They are invisible in normal
use but each one is the full image size (~555 MB here), so a handful of
rebuilds can quietly consume several gigabytes.

```bash
# See what is dangling (untagged leftovers show as <none>)
podman images

# Reclaim the space — removes ALL dangling images, keeps the tagged ones
podman image prune -f
```

`./uninstall.sh` prunes dangling images automatically as part of its image
step, so this is only needed between uninstalls. It is safe: tagged images
(`crucible-py:latest`, `python:3.12-slim`, `node:18-alpine`) are never
touched, and anything removed is rebuilt on the next `build`.

> Note it prunes dangling images for **all** projects on the machine, not just
> Crucible's. That is normally what you want; on a shared machine, run
> `podman images` first and check nothing else is relying on an untagged image.

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
| `sudo: firewall-cmd: command not found` | firewalld not installed | do **not** install it (would impose default-deny); diagnose with `rpm -q firewalld iptables-services` and `sudo iptables -L INPUT -n`, then use the iptables or no-firewall path in [docs/INSTALL-RHEL8.md](docs/INSTALL-RHEL8.md) §1.4 |
| Container binds an unexpected port (`rootlessport listen tcp 0.0.0.0:3000: address already in use`) | a `PORT` variable exported in the shell | the scripts **ignore** a generic `PORT` (override only via `CRUCIBLE_PORT=<n>`). If it persists: `git pull`, `podman rm -f crucible-py`, `./container-py.sh start` |
| `/app/data` empty / `Permission denied` in logs | SELinux blocks the bind-mount | the scripts mount with `:Z`; if you mount manually, always append `:Z` |
| `bind: permission denied` on a port | rootless podman cannot bind ports < 1024 | use ports ≥ 1024 (49160 is fine) or `sudo sysctl net.ipv4.ip_unprivileged_port_start=<n>` |
| `address already in use` on 49160 | an old container still mapped | `podman ps -a`, then `podman rm -f <name>` |
| Image pull prompts "Please select an image" | short image name | already handled — the Dockerfile uses fully-qualified names (`docker.io/library/...`) |
| Container gone after logout/reboot | rootless containers die with the session | `sudo loginctl enable-linger $USER` + a systemd unit (see [Auto-start on boot](#auto-start-on-boot-systemd)) |
| Healthcheck `unhealthy` but curl works | image built without `--format docker` (podman OCI drops HEALTHCHECK) | rebuild with `./container-py.sh build` (flag applied automatically) |
| Healthcheck `unhealthy` while the app serves 200s (especially in HTTPS mode) | the in-container probe was routed through the corporate proxy → `403` (a plain `urllib`/`curl` without `--noproxy` hits the proxy, whose `no_proxy` does not list `127.0.0.1`) | fixed in `backend/scripts/healthcheck.py`, which now bypasses the proxy — rebuild to pick up the fix: `./container-py.sh rebuild` (preserves HTTP/HTTPS mode) |
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
/certs/            # SSL certificates (plus *.key/*.crt/*.pem/... globs)
/data/             # SQLite database and runtime data
/backups/          # local database backups
.env, .env.*, *.env  # environment files / secrets (.env.example is tracked)
node_modules/      # dependencies (installed per machine)
client/dist/       # build output
.venv/             # Python virtualenv
```

(Excerpt — see the actual [.gitignore](.gitignore) for the full list.)

### Known gaps / future enhancements

- [ ] **SSO / authentication** — none yet (HTTPS is transport encryption only). A FastAPI dependency or an authenticating reverse proxy is the natural hook; plan before wider rollout.
- [ ] Role-based access control (RBAC)
- [ ] Rate limiting and audit logging
- [x] Certificate-expiry monitoring — done: `./cert-expiry-check.sh` (see [Certificate-expiry monitoring](#certificate-expiry-monitoring))

---

## Uninstall and reinstall

Full walkthroughs — what you cannot get back, a dry-run preview, mode-by-mode
detail, manual leftovers, and a verification checklist — are in
[docs/UNINSTALL-MACOS.md](docs/UNINSTALL-MACOS.md) and
[docs/UNINSTALL-RHEL8.md](docs/UNINSTALL-RHEL8.md).

`./uninstall.sh` removes the deployment (podman or docker, macOS or RHEL8):

```bash
./uninstall.sh --dry-run     # preview everything it would remove (safe)
./uninstall.sh --partial     # remove runtime artifacts; keep source & data
./uninstall.sh --full        # remove EVERYTHING (final data backup taken first)
./uninstall.sh               # interactive: choose step by step
```

On the RHEL8 VM, remember the firewall rule if one was added
(`sudo iptables -D INPUT -p tcp --dport 49160 -j ACCEPT`, or the firewalld
`--remove-port` variant).

### Cleanup Summary

Everything installation creates, where it lives, and the command that removes it:

| Component | Location | Cleanup Command |
|-----------|----------|----------------|
| Container | `crucible-py` | `podman rm crucible-py` |
| Image | `crucible-py:latest` | `podman rmi crucible-py:latest` |
| Data | `./data/` (bind mount) | `rm -rf data/` |
| PostgreSQL (only if `USE_POSTGRES=true`) | `crucible-db` container, `crucible-pgdata` volume, `crucible-net` network | `podman rm -f crucible-db && podman volume rm crucible-pgdata && podman network rm crucible-net` |
| SSL certificates | `./certs/` | `rm -rf certs/` |
| Cron jobs (monitor, cert-expiry, backup) | User crontab | `crontab -l \| grep -vE 'monitor\.sh\|cert-expiry-check\.sh\|container-py\.sh backup' \| crontab -` |
| Cron logs | `/tmp/crucible-monitor.log`, `~/crucible-cert.log`, `~/crucible-backup.log` | `rm -f /tmp/crucible-monitor.log ~/crucible-cert.log ~/crucible-backup.log` |
| Base images (`--full` only) | `python:3.12-slim`, `node:18-alpine` | `podman rmi python:3.12-slim node:18-alpine` (re-downloaded on next build) |
| node_modules | `client/node_modules/` | `rm -rf client/node_modules/` |
| Build output | `client/dist/` | `rm -rf client/dist/` |
| Python venv | `backend/.venv/` | `rm -rf backend/.venv/` |
| systemd user units | `~/.config/systemd/user/container-crucible-py.service` and `~/.config/containers/systemd/crucible-py.container` | `systemctl --user disable --now container-crucible-py.service` · `systemctl --user stop crucible-py.service` · `rm -f` both files · `systemctl --user daemon-reload` · optionally `sudo loginctl disable-linger $USER` |
| Project source | Full project directory | `rm -rf nr-nips-crucible/` |

> ⚠️ Never delete the **source** certificates in `<cert-store-path>/` — those
> are shared infrastructure.

### Reinstall / redeploy

Reinstalling is the same as a first deploy: `./setup-after-clone-py.sh` on
either platform. **Recreate the untracked `.env.local` first** on the VM — a
`--full` uninstall deleted it with the project directory, and without it (or
the equivalent environment variables) the setup script finds no cert store and
silently starts in plain HTTP:

```bash
printf 'CERT_SOURCE=<cert-store-path>\nCERT_HOSTNAME=<vm-hostname>\nUSE_HTTPS=true\n' > .env.local
./setup-after-clone-py.sh
```

See [Certificates (for HTTPS)](#certificates-for-https) for the `.env.local`
format. Restore data afterwards if you kept a backup (a `--full` uninstall
leaves a final copy in `~/crucible-backups`):

```bash
./container-py.sh restore ~/crucible-backups/crucible-final-<stamp>.db
```

Other reminders on redeploy: reopen the VM firewall port if you removed it, and
re-enable the systemd/Quadlet unit (see
[Auto-start on boot](#auto-start-on-boot-systemd)).

---

## Scaling

The deployment is **single-node by design** on SQLite — never run a second
app instance against the same SQLite file (concurrent writers corrupt it).
Before any multi-instance setup, switch to PostgreSQL (`USE_POSTGRES=true`,
see [Database](#database-sqlite-and-postgresql)). Vertical resources
(`--cpus`, `--memory`) can be set at container creation if ever needed.

---

### Server Runtime Behaviour

Resilience comes from three layers: the in-image `HEALTHCHECK` (every 30 s,
[backend/scripts/healthcheck.py](backend/scripts/healthcheck.py)), the
container `--restart unless-stopped` policy, and the optional `monitor.sh`
cron (see [Health monitoring](#health-monitoring)).

---

### Support

For deployment issues:
- Email: `<maintainer-email>`
- Slack: #crucible
- Docs: [README.md](README.md) | [API.md](API.md)

---

**Last Updated:** August 24, 2026
