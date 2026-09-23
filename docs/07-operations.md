[← README](../README.md) · [Handbook](HANDBOOK.md) · [Glossary](00-glossary.md)

# Deployment Guide — Crucible: Pandora Toolbox Enhancement (v2.0)

Operational **reference** for the Crucible **Python/FastAPI** backend on the
development machine and the RHEL8 VM (production).

> **Step-by-step walkthroughs live in the platform guides.** Install:
> [docs/01-setup-macos.md](01-setup-macos.md) ·
> [docs/01-setup-rhel8.md](01-setup-rhel8.md). Uninstall:
> [docs/01-uninstall-macos.md](01-uninstall-macos.md) ·
> [docs/01-uninstall-rhel8.md](01-uninstall-rhel8.md). **This document is the
> reference** — architecture, environment variables, database, backups,
> maintenance, troubleshooting — and the canonical home for material the guides
> link back to (the Quadlet unit, the env table, the cron lines).

The container scripts are runtime-agnostic — they auto-detect **podman or
docker** (override with `CONTAINER_RUNTIME=docker|podman`). Nothing is
hardcoded to a hostname or platform: the app reads `PORT` (default 49160) and
binds `0.0.0.0`, so the same image runs unmodified on every platform.

> For the history of the Node/Express → Python/FastAPI migration and the
> codebase learning map, see [docs/12-history.md](12-history.md).

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
- [Two instances on one machine](#two-instances-on-one-machine)
- [Backup and restore](#backup-and-restore)
- [Maintenance and operational tasks](#maintenance-and-operational-tasks)
- [Troubleshooting](#troubleshooting)
- [Security](#security)
- [Uninstall and reinstall](#uninstall-and-reinstall)
- [Scaling](#scaling)

---

## Architecture at a glance

```mermaid
flowchart LR
    subgraph dev["Development machine"]
        M["container-py.sh start<br/>HTTP on 127.0.0.1:49160"]
    end
    subgraph vm["RHEL 8 VM (production)"]
        direction TB
        P["container-py.sh start-ssl<br/>HTTPS on 0.0.0.0:49160<br/>USE_HTTPS=true in .env.local"]
        D[("data/crucible.db<br/>backups/ nightly")]
        CR["cron: monitor.sh every 5 min<br/>cert-expiry-check.sh weekly<br/>backup nightly"]
        SD["systemd user unit + lingering<br/>survives logout and reboot"]
        P --> D
        CR -.-> P
        SD -.-> P
    end
    W["workstations on the internal network"] -- "https://vm-hostname:49160" --> P
```

A single **FastAPI** process (served by uvicorn) does everything:

- answers all `/api/*` routes (chemicals, samples, screening, toxicology, stats),
- serves the built React client (`client/dist`) as static files,
- serves `/architecture` (interactive architecture page),
- stores data in **SQLite** (`data/crucible.db`) by default via SQLAlchemy 2 — **optional PostgreSQL** by changing `DATABASE_URL` (see [Database](#database-sqlite-and-postgresql)).

The container image is **`crucible-py`**, built from
[backend/Dockerfile](../backend/Dockerfile) (a multi-stage build: a Node stage
builds the React bundle, the final `python:3.12-slim` stage contains no Node).
Everything is wrapped by [container-py.sh](../container-py.sh).

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
# docs/01-setup-rhel8.md §1.4 for the plain-iptables and no-firewall cases).
sudo firewall-cmd --permanent --add-port=49160/tcp
sudo firewall-cmd --permanent --remove-port=5942/tcp   # ok if "not enabled"
sudo firewall-cmd --reload
sudo firewall-cmd --list-ports                          # verify 49160/tcp

# Verify
curl --noproxy '*' -sS http://localhost:49160/api/health  # expect {"status":"ok"}; /api/stats needs the token once the login is on
```

Notes:

- The app reads `PORT` (default 49160) and binds `0.0.0.0`; the container
  scripts accept `CRUCIBLE_PORT=<n>` overrides (a generic `PORT` env var is
  **ignored** to avoid clashes on shared machines).
- Rootless podman cannot bind ports below 1024; 49160 is unaffected.
- macOS quirk: Apple's `remoted` daemon listens on ports 49152+ on a
  link-local IPv6 address, so a wildcard bind of 49160 fails on macOS.
  The scripts publish on `127.0.0.1` on macOS and `0.0.0.0` on Linux;
  override with `HOST_BIND=<ip>`.

---

## Quick Start (after clone)

One command does everything (certs when available, build, start, verify,
optional monitoring cron) — on the development machine **and** the RHEL8 VM:

```bash
./setup-after-clone-py.sh
```

Non-interactive: `SETUP_MONITOR=y ./setup-after-clone-py.sh` (or `n`).

> **Private repo:** `nestle-it/nr-nips-crucible` needs authentication — clone
> over HTTPS with a Personal Access Token, or use an SSH key
> (`git@github.com:nestle-it/nr-nips-crucible.git`). The scripts are unaffected
> by which remote or clone method you use.

Guided walkthroughs, with expected output at every step:
[docs/01-setup-macos.md](01-setup-macos.md) ·
[docs/01-setup-rhel8.md](01-setup-rhel8.md) ·
[docs/01-setup-windows.md](01-setup-windows.md) (untested).

### Container commands

Both scripts auto-detect **podman or docker** (override with
`CONTAINER_RUNTIME=docker|podman`) and check the podman VM state on macOS.
Port override: `CRUCIBLE_PORT=<n>` (a generic `PORT` env var is ignored to
avoid clashes on shared machines). Every command acts on **the instance of
the folder it runs in**: with `CRUCIBLE_INSTANCE=beta` in that folder's
`.env.local` the image and container are `crucible-py-beta`, and `help`
and `status` say so ([Two instances on one machine](#two-instances-on-one-machine)).

```bash
./container-py.sh build       # Build image (node build stage + python:3.12-slim)
./container-py.sh start       # Start (HTTPS when .env.local says so); on the server the service takes the container over; returns when the app answers
./container-py.sh start-ssl   # Start with HTTPS (certs/server.crt + server.key)
./container-py.sh status      # Container row, the service's state, the /api/health probe, the login mode and the counts — docs/15-run-stop-status.md
./container-py.sh logs        # View logs
./container-py.sh stop        # Stop (through the service when the service runs it)
./container-py.sh rebuild     # Rebuild image + restart, preserving HTTP/HTTPS mode
./container-py.sh script remove_chemicals.py CHEM-000042   # Run a maintenance script inside the container; no name = list them
./container-py.sh import chemicals ~/registry.json         # Load a chemicals file (json, csv, tsv, xlsx, xls, sdf) through the same code as the upload page
./container-py.sh export chemicals ~/registry-export.json  # Write every registry entry to a re-importable JSON file
./container-py.sh shell       # Shell inside the container
./container-py.sh clean       # Remove container and image
./container-py.sh backup      # Consistent snapshot → backups/ (safe while running)
./container-py.sh restore     # List backups; with a file: stop → swap db → restart; with a FOLDER: the newest crucible-*.db in it
./container-py.sh lock        # Regenerate backend/requirements.lock inside the base image (after editing requirements.txt)
```

**PostgreSQL (optional — SQLite is the default):**

```bash
./container-py.sh db-start    # Start the managed PostgreSQL container (once)
./container-py.sh db-stop     # Stop it
./container-py.sh db-shell    # Open a psql shell
USE_POSTGRES=true ./container-py.sh start   # run the app against PostgreSQL
```

### Where the app answers

| Environment | URL | Protocol |
|-------------|-----|----------|
| Production | `https://<vm-hostname>:49160` | HTTPS/TLS |
| Beta instance (the testers' copy — [`14-beta-instance.md`](14-beta-instance.md)) | `https://<vm-hostname>:49161` | HTTPS/TLS |
| Interactive architecture page | `https://<vm-hostname>:49160/architecture` | HTTPS/TLS |
| Development, the built app | `http://localhost:49160` | HTTP |
| Development, React dev server (hot reload) | `http://localhost:3000`, proxying `/api` to the backend | HTTP |
| Generated API explorer | `http://localhost:49160/docs` | HTTP |

---

## Runbook A — macOS (Docker)

Full walkthrough: [docs/01-setup-macos.md](01-setup-macos.md) (Docker
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

Full walkthrough: [docs/01-setup-macos.md](01-setup-macos.md) — including
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

Full walkthrough: [docs/01-setup-rhel8.md](01-setup-rhel8.md). It covers
packages (§1.1), rootless subuid/subgid (§1.2), lingering (§1.3), the firewall
three-case diagnosis — firewalld / plain iptables / no host firewall (§1.4),
the one-shot and manual install paths (§2), HTTPS with corporate certificates
(§3), auto-start and monitoring (§4), and a verification checklist (§5).

Target: `<vm-hostname>`, rootless podman, port 49160. The condensed command
set, once the prerequisites in §1 are done:

```bash
./container-py.sh build
./container-py.sh start                                   # publishes 0.0.0.0:49160 on Linux
curl --noproxy '*' -sS http://localhost:49160/api/stats    # JSON counts (with the login on: -H "Authorization: Bearer <token>")
curl --noproxy '*' -sS http://localhost:49160/ | grep -o '<title>[^<]*</title>'
./container-py.sh logs | status | stop
git pull && ./container-py.sh rebuild
```

---

## SSL/TLS certificate setup

Certificates are **never committed to git** and must be set up per deployment.

**Initial setup** (copying from the corporate store, self-signed dev certs,
`start-ssl`, switching back to HTTP) is walked through in
[docs/01-setup-rhel8.md](01-setup-rhel8.md) §3 and
[docs/01-setup-macos.md](01-setup-macos.md) §3. In short:
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
./container-py.sh script healthcheck.py && echo healthy
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
# From the production checkout, print the line with real paths substituted:
echo "0 8 * * 1 CERT_FILE=$(pwd)/certs/server.crt $(pwd)/cert-expiry-check.sh >> ~/crucible-cert.log 2>&1"
crontab -e     # paste it verbatim — Mondays 08:00, warn within 30 days
```

**Absolute `CERT_FILE`, and let the `echo` write the line.** Both guard the
same failure: this check reads `certs/server.crt` relative to its working
directory, so a `cd` into the wrong clone — or a placeholder path left
unsubstituted — produces a job that reports nothing wrong forever. `no
certificate at … — nothing to check` exits 0, so the absence of a certificate
is indistinguishable from a healthy one to anything watching exit codes.

Verify once, and read the output rather than the status:

```bash
CERT_FILE="$(pwd)/certs/server.crt" ./cert-expiry-check.sh    # → a real expiry date
```

When it warns, follow "Rotating / replacing the certificate" above.

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `49160` | HTTP/HTTPS port the app binds (inside the container) |
| `CRUCIBLE_PORT` | *(unset)* | Port override for `container-py.sh`, `setup-after-clone-py.sh` and `monitor.sh` (a generic `PORT` in the shell is ignored). The beta instance sets `49161` in its `.env.local` |
| `CRUCIBLE_INSTANCE_LABEL` | *(unset)* | The word the page's corner shows for this instance (SH-13). Unset: *Prod* for the default instance, the name capitalised for a named one (*Beta*). Set it in `.env.local` to spell it your way (*Production*); `container-py.sh` passes it into the container; a rebuild applies it |
| `CRUCIBLE_INSTANCE` | *(unset)* | Names a second instance run from another checkout: the image, the container and the optional Postgres container, network and volume become `crucible-py-<name>`, `crucible-db-<name>`…; the monitor log becomes `/tmp/crucible-monitor-<name>.log`; `uninstall.sh` removes only that instance. Lowercase letters, digits and hyphens. Set in the folder's `.env.local`; the environment wins — [Two instances on one machine](#two-instances-on-one-machine) |
| `AUTH_MODE` | `off` | The login: `off` leaves every route open; `token` (v2.22.0, [phase SH-3a](04-phase-tutorials/phase-sh-3a-token-gate.md)) makes every `/api` route except `/api/health`, `/api/instance` and `/api/auth/*` answer 401 without `CRUCIBLE_TOKEN`; `local` (v2.23.0, [phase SH-3b](04-phase-tutorials/phase-sh-3b-local-accounts.md)) asks for a username and a password from the accounts made with `./container-py.sh users`, gives each a role, and lets scripts in with a personal token. Set it in the instance's `.env.local`; `container-py.sh` validates it and passes it in; a change needs the container recreated (`stop`, `start`) |
| `CRUCIBLE_TOKEN` | *(unset)* | The shared secret of the token mode, at least 32 characters (`python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`). In `.env.local` only, which the script makes owner-only; never printed, never in git. Ignored in the local mode |
| `SESSION_SECRET` | *(unset)* | The key that signs the local mode's session cookie, same rules as the token (at least 32 characters, `.env.local` only, never printed); required when `AUTH_MODE=local`. A new value signs every browser out at once; each instance has its own |
| `SESSION_HOURS` | `10` | How long the login page's cookie lasts (decision A6, a working day): from the login on the token rung, from the last request on the local rung (the cookie is re-issued after `SESSION_SLIDE_SECONDS`, 300, of age) |
| `CORS_ORIGINS` | *(empty: closed)* | Comma-separated origins allowed to call the API from a browser on another site (decision A7). The page is served by this process, so nothing that ships needs it |
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
  -e AUTH_MODE=off -e CRUCIBLE_TOKEN= \
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

## Two instances on one machine

Since v2.20.0 a second, complete copy of the application can run beside
the first on the same machine: the **beta instance** the testers use, on
port 49161, with its own data. The design and the decisions are in
[`14-beta-instance.md`](14-beta-instance.md); the server walk is
[`01-setup-rhel8.md` §8](01-setup-rhel8.md#8-a-second-instance-for-user-testing-beta);
the phase that built it, with a test for every route, is
[phase SH-12](04-phase-tutorials/phase-sh-12-beta-instance.md). The
runbook facts:

![The three lines of the beta folder's .env.local fan out to the image, container, service unit, monitor log, cron line and address](img/fig_instance_name.svg)

| | Per folder (the scripts read the folder's `.env.local`) | Shared |
|---|---|---|
| Names | image and container `crucible-py-<instance>`; the Postgres container, network and volume likewise | the scripts, the image recipe (`backend/Dockerfile`) |
| Port | `CRUCIBLE_PORT` — production 49160, beta 49161 | — |
| Files | `data/`, `backups/`, `certs/`, `.env.local` | the certificate *content* (it names the host, not the port, so the same pair is copied into both `certs/`) |
| Boot and watch | one service unit `container-crucible-py-<instance>.service`; one monitor cron line; one log `/tmp/crucible-monitor-<instance>.log` | the weekly certificate check and the nightly backup line belong to production's folder |
| Removal | `./uninstall.sh` in a folder removes that folder's instance and the cron lines that name that folder, nothing else | — |

One rule to remember: **every script acts on the folder it runs in.**
`./container-py.sh rebuild` in the beta folder recreates `crucible-py-beta`
and never restarts `crucible-py`; `./monitor.sh` there probes 49161;
`./uninstall.sh --dry-run` there opens with `Instance: beta`. Check with
`./container-py.sh help | grep Usage` when in doubt, and `pwd` before
anything destructive. In a browser, the page's own corner says which
instance it is: a **Prod** pill in indigo or a **Beta** pill in amber, and
`[Prod]` or `[Beta]` on the tab (SH-13).

**Status, stop, start, per instance.** The everyday commands, what each
output means, and surviving a reboot are on one page,
[`15-run-stop-status.md`](15-run-stop-status.md); the short form:

| I want to… | Production, in `~/work/Pandora_toolbox/nr-nips-crucible` | Beta, in `…/nr-nips-crucible-beta` |
|---|---|---|
| Is it running, and what does it answer? | `./container-py.sh status` | same |
| Which instance is this folder? | `./container-py.sh help \| grep Usage` → `instance: default → crucible-py, port 49160` | → `instance: beta → crucible-py-beta, port 49161` |
| See its log | `./container-py.sh logs` (Ctrl-C to leave) | same |
| Stop it | `./container-py.sh stop` | same |
| Start it again | `./container-py.sh start` (HTTPS when `.env.local` says so) | same |
| Restart it | `./container-py.sh restart` | same |
| Rebuild after a code change | `./container-py.sh backup && ./container-py.sh rebuild`, then regenerate the unit (below) | same |
| Full check | `./verify-deploy.sh https://localhost:49160` | `./verify-deploy.sh https://localhost:49161` |
| Both at once | `podman ps` from anywhere | |
| What the monitor saw | `tail -3 /tmp/crucible-monitor.log` | `tail -3 /tmp/crucible-monitor-beta.log` |
| The boot-time unit | `systemctl --user status container-crucible-py.service` | `systemctl --user status container-crucible-py-beta.service` |

**One supervisor, two doors.** Since v2.21.2 the systemd service is the
thing that runs the application on the server, and `container-py.sh` is
the tool that builds and updates it and then hands over: after every
container the script creates (`rebuild`, `start`, `start-ssl`, `restore`)
it rewrites the unit from that container, starts the service, which takes
the container over, and waits until the application answers. Its `status`,
`stop` and `restart` go through the service when the service is running
it. So `systemctl --user status|stop|start|restart container-crucible-py[-beta].service`
and the script's `status|stop|start|restart` always agree, and the unit is
`active (enabled)` whenever the application runs. Before it touches a
container the script still stops an active service first (lesson 36).
The whole story, step by step, is [`15-run-stop-status.md`](15-run-stop-status.md).
On a machine with no unit file, no `systemctl`, or Docker, none of this
runs and the script is the only door.

**Refreshing beta from production** (one way, on request — never the reverse):

```bash
cd ~/work/Pandora_toolbox/nr-nips-crucible && ./container-py.sh backup
cd ~/work/Pandora_toolbox/nr-nips-crucible-beta && ./container-py.sh restore ../nr-nips-crucible/backups
```

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

The image runs [backend/scripts/entrypoint.sh](../backend/scripts/entrypoint.sh)
at start, which calls
[backend/scripts/db_bootstrap.py](../backend/scripts/db_bootstrap.py) before
uvicorn. Bootstrap is **adopt-or-upgrade** and safe to run repeatedly:

- **empty database** → `alembic upgrade head` (creates the schema),
- **existing pre-Alembic schema** (e.g. a `data/crucible.db` created by an
  older build) → stamp `0001_initial`, then `upgrade head`,
- **already Alembic-managed** → `upgrade head` (a no-op when current).

Because `AUTO_INIT_DB=false` in the image, the app never races the migration.
Outside the container (local dev, tests) `AUTO_INIT_DB` defaults to `true`, so
`create_all()` keeps working with no Alembic step.

### Migrating existing SQLite data into PostgreSQL

[backend/scripts/migrate_sqlite_to_postgres.py](../backend/scripts/migrate_sqlite_to_postgres.py)
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
is [docs/01-setup-rhel8.md](01-setup-rhel8.md) §4. The canonical crontab
entry (**one line per instance**; use `https://` after `start-ssl`) is:

```bash
*/5 * * * * cd /path/to/crucible && USER=$(id -un) XDG_RUNTIME_DIR=/run/user/$(id -u) CONTAINER_NAME=crucible-py API_URL=http://localhost:49160/api/health ./monitor.sh
```

and, on a server with a beta instance, a second line written by the setup
script run in the beta folder, ending
`CONTAINER_NAME=crucible-py-beta API_URL=https://localhost:49161/api/health ./monitor.sh`.
Re-running the setup in a folder replaces **that folder's** line only. A
line written before v2.22.0 names `/api/stats`; it keeps working, because
the monitor tries `/api/health` first at the same address (next paragraph).

Manual install / check:

```bash
crontab -l | grep monitor.sh              # is it installed, and for which container(s)?
tail -5 /tmp/crucible-monitor.log         # what has production's been doing?
tail -5 /tmp/crucible-monitor-beta.log    # and beta's (one log per instance)
```

`monitor.sh` sends a GET to `/api/health`, the route that needs no login
and answers `{"status":"ok"}` and nothing else; on a non-200 response it
restarts the named container and logs to `/tmp/crucible-monitor.log`
(`/tmp/crucible-monitor-<instance>.log` for a named instance). It always
tries `/api/health` at the address its cron line names and falls back to
that address only when the route does not exist (a container older than
v2.22.0 answers 404), so an old line naming `/api/stats` cannot make it
restart a healthy application for answering 401. The container also has a
built-in `HEALTHCHECK` (every 30 s) that probes `/api/health` (see
[backend/scripts/healthcheck.py](../backend/scripts/healthcheck.py)).

Run it manually any time: `./monitor.sh` — run by hand it reads the
folder's `.env.local`, so in the beta folder it probes 49161 and would
restart `crucible-py-beta`, never production. Since v2.22.1 it ignores a
generic `PORT` in the shell, as the container script always did (before,
a shell exporting `PORT=3000` made it probe the wrong port in a folder
without `CRUCIBLE_PORT` and restart a healthy production), and it refuses
to restart a container whose published port is not the one it probed,
naming both ports instead (lesson 39).

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
[docs/01-setup-rhel8.md](01-setup-rhel8.md) §4.2. The Quadlet unit above is
the canonical copy — that guide links back here for it.

**One unit per instance.** The beta instance gets its own:
`podman generate systemd --new --name crucible-py-beta --files` writes
`container-crucible-py-beta.service`; a Quadlet file for it is the block
above saved as `crucible-py-beta.container` with `Image=localhost/crucible-py-beta:latest`,
`ContainerName=crucible-py-beta`, `PublishPort=0.0.0.0:49161:49161`,
`Environment=PORT=49161`, `Environment=CRUCIBLE_INSTANCE=beta` (the page's
label, SH-13) and the beta folder's `data/` in `Volume=`
([`01-setup-rhel8.md` §8](01-setup-rhel8.md#8-a-second-instance-for-user-testing-beta)).

**When to regenerate a generated unit.** A unit written by
`podman generate systemd --new` records the exact `podman run` command of
the container it was made from: image, port, mounts, environment. Whenever
a new version changes that command (v2.21.0 added the instance variables;
a later one may add the login's), the unit must be written again after the
rebuild, or the next boot starts the container the old way. **Since
v2.21.1 `container-py.sh` does this itself** after every container it
creates (`rebuild`, `start`, `start-ssl`, `restore`) whenever the unit file
exists, and since v2.21.2 it then starts the service so that the service
owns the container: you will see `Rewriting container-crucible-py-beta.service
from the container just created`, `✓ … rewritten (enabled: enabled)`,
`Handing the container to the service …` and `✓ … is active`. By hand,
should you ever need it, it is four commands in the instance's folder, with
its container running:

```bash
podman generate systemd --new --name crucible-py-beta --files     # crucible-py for production
mv container-crucible-py-beta.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user is-enabled container-crucible-py-beta.service    # still: enabled
```

The running container is not touched; only the recipe card is rewritten.
The release note says when a version needs this; when in doubt, it is
harmless to do after every rebuild.

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
the development machine and the RHEL8 VM (the script handles podman vs docker, running vs
stopped):

```bash
./container-py.sh backup                                   # → backups/crucible-<stamp>.db
./container-py.sh restore                                  # lists available backups
./container-py.sh restore backups/crucible-<stamp>.db      # stop → swap db → restart
./container-py.sh restore backups                          # the same with the NEWEST crucible-*.db in that folder (any folder)
```

- **Safe while running** — uses SQLite's online-backup API inside the
  container, so you never get a torn copy. Never plain-`cp` a *live* SQLite
  file; that can catch it mid-write and corrupt the backup.
- Restore keeps the current database as `data/crucible.db.pre-restore` (safety
  net) before swapping. Verify afterwards with
  `curl --noproxy '*' -sS http://localhost:49160/api/stats` (with the login
  on, add `-H "Authorization: Bearer <token>"`).
- Override the destination with `BACKUP_DIR=/path ./container-py.sh backup`.

### Refreshing the beta instance from production

The same two commands, on one machine, one way. `restore` given a folder
takes its newest backup, so no timestamp is copied by hand; beta's previous
database is kept as `data/crucible.db.pre-restore`. Nothing is written to
production's folder, and no command exists that restores in the other
direction from anywhere but production's own folder.

```bash
cd ~/work/Pandora_toolbox/nr-nips-crucible      && ./container-py.sh backup
cd ~/work/Pandora_toolbox/nr-nips-crucible-beta && ./container-py.sh restore ../nr-nips-crucible/backups
curl --noproxy '*' -sSk -H "Authorization: Bearer <beta's token>" https://localhost:49161/api/stats   # the same counts as production's (the header: beta's login is on)
```

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

**First things to try**, before the full table:

| Symptom | First thing to try |
|---|---|
| Port 49160 already in use | `lsof -i :49160` to find the holder; `fuser -k 49160/tcp` to free it |
| App unreachable / container misbehaving | `./container-py.sh status`, then `./container-py.sh logs` — the real error is in the last ~20 lines |
| TLS handshake fails after `start-ssl` | cert and key are from different pairs — compare the modulus hashes ([SSL/TLS](#ssltls-certificate-setup)), then `./setup-after-clone-py.sh` |
| Reachable on the VM but not from a workstation | host firewall — open port 49160 for the case that applies (firewalld / plain iptables / none) |
| Database looks wrong and you want a clean slate | [Reset the database](#reset-the-database) below — it is re-created empty on the next start |
| `curl` answers `{"error":"Not authenticated"}` | the login is on for that instance: add `-H "Authorization: Bearer <token>"` (the shared token from its `.env.local` on the token rung; a personal token from `./container-py.sh users token <name>` on the local rung), or ask `/api/health`, which is open — [The login](#the-login-turn-it-on-rotate-the-token-turn-it-off) · [Accounts](#accounts-add-a-person-reset-a-password-disable-a-leaver-issue-a-token) |
| `curl` or the page answers `{"error":"Forbidden: this needs the admin role (yours: viewer)"}` | the account's role does not allow the verb (local mode): reading needs a viewer, writing an editor, deleting, merging and clearing an admin; `./container-py.sh users role <name> <role>` if that is wrong — [Accounts](#accounts-add-a-person-reset-a-password-disable-a-leaver-issue-a-token) |
| The login page refuses a token you are sure of | the container was not recreated after `.env.local` changed: `./container-py.sh stop` then `start`; compare with `grep CRUCIBLE_TOKEN .env.local` |
| The login page refuses a username and password you are sure of | `./container-py.sh users list`: `LOCKED` after ten wrong tries (`users unlock <name>`), `DISABLED` (`users enable`), or the person is on the other instance (accounts are per instance); otherwise `users reset <name>` and hand the new temporary password over |
| `./container-py.sh users …` says there is no users table | the container runs an image older than v2.23.0, or was started without its entrypoint: `./container-py.sh rebuild` |
| `./monitor.sh` by hand says `restart failed`, and its log names a port that is not the instance's | before v2.22.1 a generic `PORT` in the shell was honoured; now ignored, and the monitor refuses to restart a container at a port it does not publish. Set `CRUCIBLE_PORT` in the folder's `.env.local` if the instance is on a non-default port |
| The monitor log shows a restart every five minutes | the container runs an image older than v2.22.0 with the login on somewhere else, or the application really is down: `./container-py.sh logs` |

Beginner-oriented walkthroughs of the actual error messages, with a named fix
for each: [docs/01-setup-macos.md → Troubleshooting](01-setup-macos.md#troubleshooting) ·
[docs/01-setup-rhel8.md → §7 RHEL8-specific gotchas](01-setup-rhel8.md#7-rhel8-specific-gotchas).

| Symptom | Cause | Fix |
|---|---|---|
| Works on the VM, unreachable from workstation | host firewall | firewalld: `sudo firewall-cmd --permanent --add-port=49160/tcp && sudo firewall-cmd --reload` · plain iptables: `sudo iptables -I INPUT -p tcp --dport 49160 -j ACCEPT` (+ `service iptables save`) · if neither is installed and `iptables -L INPUT` is empty, the blocker is the network, not the host |
| `sudo: firewall-cmd: command not found` | firewalld not installed | do **not** install it (would impose default-deny); diagnose with `rpm -q firewalld iptables-services` and `sudo iptables -L INPUT -n`, then use the iptables or no-firewall path in [docs/01-setup-rhel8.md](01-setup-rhel8.md) §1.4 |
| Container binds an unexpected port (`rootlessport listen tcp 0.0.0.0:3000: address already in use`) | a `PORT` variable exported in the shell | the scripts **ignore** a generic `PORT` (override only via `CRUCIBLE_PORT=<n>`). If it persists: `git pull`, `podman rm -f crucible-py`, `./container-py.sh start` |
| `/app/data` empty / `Permission denied` in logs | SELinux blocks the bind-mount | the scripts mount with `:Z`; if you mount manually, always append `:Z` |
| `bind: permission denied` on a port | rootless podman cannot bind ports < 1024 | use ports ≥ 1024 (49160 is fine) or `sudo sysctl net.ipv4.ip_unprivileged_port_start=<n>` |
| `address already in use` on 49160 | an old container still mapped | `podman ps -a`, then `podman rm -f <name>` |
| Image pull prompts "Please select an image" | short image name | already handled — the Dockerfile uses fully-qualified names (`docker.io/library/...`) |
| Container gone after logout/reboot | rootless containers die with the session | `sudo loginctl enable-linger $USER` + a systemd unit (see [Auto-start on boot](#auto-start-on-boot-systemd)) |
| A second checkout's `rebuild` replaced or restarted **production** (`crucible-py`) | its `.env.local` lacks `CRUCIBLE_INSTANCE` (and `CRUCIBLE_PORT`), so both folders name the same container | write the two lines, `./container-py.sh help \| grep Usage` must say `instance: beta`, then `rebuild` there; production's container is restarted by `./container-py.sh start` in **its** folder ([Two instances](#two-instances-on-one-machine)) |
| `address already in use` on 49160 when starting the second instance | `CRUCIBLE_PORT` missing from the beta folder's `.env.local` | add `CRUCIBLE_PORT=49161`, then `./container-py.sh rebuild` in that folder |
| Healthcheck `unhealthy` but curl works | image built without `--format docker` (podman OCI drops HEALTHCHECK) | rebuild with `./container-py.sh build` (flag applied automatically) |
| Healthcheck `unhealthy` while the app serves 200s (especially in HTTPS mode) | the in-container probe was routed through the corporate proxy → `403` (a plain `urllib`/`curl` without `--noproxy` hits the proxy, whose `no_proxy` does not list `127.0.0.1`) | fixed in `backend/scripts/healthcheck.py`, which now bypasses the proxy — rebuild to pick up the fix: `./container-py.sh rebuild` (preserves HTTP/HTTPS mode) |
| Corporate proxy breaks localhost curl | proxy env vars | use `curl --noproxy '*' ...` (the scripts already do) |
| `verify-deploy.sh` prints `curl: option --retry-all-errors: is unknown` and many FAILs | a script from before v2.6.1 run with RHEL 8's system curl 7.61 (a conda shell has a newer curl and hid it) | `git pull` — the script no longer uses the option (lesson 31); the FAILs said nothing about the deployment |
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
- **The login (v2.22.0)**: a token gate behind one flag, `AUTH_MODE`; one guard declared per router; a login page; a cookie that is a keyed hash of the token; every comparison constant-time; the token in `.env.local` only — [phase SH-3a](04-phase-tutorials/phase-sh-3a-token-gate.md), runbook below
- **Local accounts (v2.23.0)**: `AUTH_MODE=local`; usernames and Argon2-hashed passwords in a `users` table the API never returns and the query console refuses; three roles enforced by one rule; a signed, sliding session cookie keyed by `SESSION_SECRET`; personal tokens for scripts, revoked by name; a lockout after ten wrong passwords — [phase SH-3b](04-phase-tutorials/phase-sh-3b-local-accounts.md), runbook below
- **Cross-origin policy**: closed (v2.22.0, decision A7); `CORS_ORIGINS` reopens it for a named site
- **Pre-push gate**: `./check-public-safe.sh` must print `✓ SAFE TO PUSH` before
  every public push — it verifies no secret paths are tracked, only sanitised
  templates ship, and no internal identifiers appear in tracked content. Where
  it sits in the public → private flow: [docs/03-git-workflow.md](03-git-workflow.md)

Keep a backup of real certificates **outside** the repository (for example
`~/.crucible/certs/`, directory `700`, key `600`) — every uninstall mode
deletes `certs/`, and no clone can restore them.

### The login: turn it on, rotate the token, turn it off

Since v2.22.0 ([phase SH-3a](04-phase-tutorials/phase-sh-3a-token-gate.md)).
The login is a **setting**, not code: two lines in the instance's
`.env.local`, and the container recreated so they reach it. A promotion
changes nothing here by itself.

![The token goes from the owner-only settings file through the container script into the container and the guard; a browser gets a cookie that is a keyed hash, a script sends a bearer header; the token is never in git, logs, errors or the page](img/fig_token_travels.svg)

```bash
# ▶ VM - the instance's folder (done on beta and on production 2026-09-22; the same lines after a reinstall)
printf 'AUTH_MODE=token\nCRUCIBLE_TOKEN=%s\n' "$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" >> .env.local
chmod 600 .env.local
./container-py.sh backup
./container-py.sh stop          # through the service: the container is removed
./container-py.sh start         # a new container with the two lines; the unit rewritten, owner-only; handed over
curl --noproxy '*' -sSk https://localhost:49161/api/stats; echo      # {"error":"Not authenticated"}
CRUCIBLE_TOKEN="$(grep '^CRUCIBLE_TOKEN=' .env.local | cut -d= -f2-)" ./verify-deploy.sh https://localhost:49161   # 19 passed (since v2.23.0; 18 before)
```

Hand the token to each person out of band (in person, or the
organisation's password manager), never in an e-mail body or a chat. Read
it back with `grep '^CRUCIBLE_TOKEN=' .env.local`. Each instance has **its
own** token (decision A11): run the generation line in each folder, never
copy one folder's line into the other; the testers' token opens beta only,
the laboratory's opens production only.

**Rotate** (a leaver, a leak, once a quarter): every browser is signed out
at once and every script needs the new value.

```bash
new="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" && sed -i "s|^CRUCIBLE_TOKEN=.*|CRUCIBLE_TOKEN=${new}|" .env.local && unset new
./container-py.sh stop && ./container-py.sh start
```

**Turn it off:** `sed -i 's|^AUTH_MODE=.*|AUTH_MODE=off|' .env.local`, then
the same `stop` and `start`. The token line can stay; it is ignored.

**Why `stop` and `start`, not `restart`.** The service's unit records the
run command the container was created with, environment included;
`restart` brings that container back unchanged. `stop` through the service
removes it; `start` creates a new one from the current file. On a
development machine, which has no service, use `rebuild`.

**What still works without the token:** `/api/health` (the probes),
`/api/instance` (the label), `/api/auth/*` (the door), the page's own
files. What needs it: everything else, sent as
`-H "Authorization: Bearer <token>"` by scripts and `curl`, or pasted once
into the login page by a person. The maintenance scripts inside the
container are unaffected: they read the database, not the API.

### Accounts: add a person, reset a password, disable a leaver, issue a token

Since v2.23.0 ([phase SH-3b](04-phase-tutorials/phase-sh-3b-local-accounts.md)).
The second rung: instead of one shared token, one **account** per person,
with a **role**, and a **personal token** for each script. The accounts
live in the instance's database and are managed from its folder with
`./container-py.sh users …`, which runs `backend/scripts/manage_users.py`
inside the container against the database directly: it works whatever
`AUTH_MODE` says, so the first admin is created before the switch and a
locked-out operator can always get back in. A password or a token is
printed **once**, when made; what the table keeps is a hash.

![The life of an account: add, hand over out of band, first login and change password, a personal token for a script, a reset, a disable; each step one command or one click; secrets shown once and stored as hashes](img/fig_account_lifecycle.svg)

**Turn it on** (done on beta 2026-09-22 and on production 2026-09-23,
there in two moments, the accounts first and the switch at an announced minute — [Step 9](04-phase-tutorials/phase-sh-3b-local-accounts.md#step-9--turn-it-on-beta-first) and [Step 10](04-phase-tutorials/phase-sh-3b-local-accounts.md#step-10--production-in-two-moments-the-accounts-then-the-switch) of the tutorial):

```bash
# ▶ VM - the instance's folder; the container is running this version (block 3 or 6 rebuilt it)
./container-py.sh users add <your-username> --role admin --name "<Your Name>"     # a temporary password, shown once
./container-py.sh users add <person> --role viewer --name "<Their Name>"          # one per person: viewer, editor or admin
./container-py.sh users list
sed -i 's|^AUTH_MODE=.*|AUTH_MODE=local|' .env.local                              # the CRUCIBLE_TOKEN line stays: ignored, and your way back
printf 'SESSION_SECRET=%s\n' "$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" >> .env.local
chmod 600 .env.local
./container-py.sh backup
./container-py.sh stop && ./container-py.sh start                                 # a setting reaches a container only when it is created
curl --noproxy '*' -sSk https://localhost:49161/api/auth/me; echo                 # {"mode":"local","authenticated":false,"user":null}
./container-py.sh users token <your-username>                                      # your personal token, once
CRUCIBLE_TOKEN='<your-username>:…' ./verify-deploy.sh https://localhost:49161     # 19 passed
```

Hand each temporary password over out of band (in person, or the
organisation's password manager), never in an e-mail body or a chat; the
person replaces it on their first visit with *Change password* in the top
bar. Each instance has its own accounts and its own `SESSION_SECRET`
(decision A11 again): generated in each folder, never copied across.

**The accounts may come first, the switch later.** The `users` lines and
the `sed`, `printf`, `stop`, `start` lines above need not be one block: an
account created while the login is still the token is stored and ignored
by the door until the mode is `local`, so the operator can create the
accounts on a quiet morning, hand the passwords over during the week, and
flip the door at an announced minute. That is how production moved
([Step 10 of the tutorial, in two moments](04-phase-tutorials/phase-sh-3b-local-accounts.md#step-10--production-in-two-moments-the-accounts-then-the-switch)). While accounts
wait, `./container-py.sh status` lists them with the word *waiting*
(v2.23.3); the state between the two moments, and how to test it by every
route, is [in the tutorial](04-phase-tutorials/phase-sh-3b-local-accounts.md#between-the-two-moments-production-after-step-10a-before-step-10b).

![Production's login in two moments: first the accounts are created while the door still takes the token and the page still shows the token box; later, at an announced moment, the mode switches to local and the same rows are used; between the two, hours or days](img/fig_two_moments.svg)

What the minute of the switch changes, and for whom: a browser signed in
with the token lands on the login page, a script with the shared token
answers 401 until it has a personal token, and the monitor, the data and
the accounts do not notice ([tested route by route](04-phase-tutorials/phase-sh-3b-local-accounts.md#after-the-switch-production-on-accounts-step-10b)).

![The minute of the switch: the settings file before and after, the five steps in between (backup, stop, start, unit rewritten, answers), and what changes for a browser, a script, the monitor, the data and the accounts](img/fig_switch_minute.svg)

| I want to… | Command | Effective |
|---|---|---|
| see who exists, with role, state, token, last login | `./container-py.sh users list` (`--json` for a script); never a hash | — |
| a forgotten password | `./container-py.sh users reset <name>`: a new temporary one, shown once; every browser signed in as them is out within a minute | on their next request |
| change a role | `./container-py.sh users role <name> viewer\|editor\|admin` | on their next request |
| a leaver | `./container-py.sh users disable <name>`: refused at the login page, by cookie and by token | at once |
| back in | `./container-py.sh users enable <name>` | at once |
| ten wrong passwords | `./container-py.sh users unlock <name>` (or wait fifteen minutes) | at once |
| a script needs in | `./container-py.sh users token <name>`: `<name>:…`, shown once; sent as `-H "Authorization: Bearer <it>"`, with the account's role — the walk, start to finish, with a shell and a Python script: [the cookbook](08-api-cookbook.md#a-script-with-a-personal-token-start-to-finish) | at once |
| that script is retired | `./container-py.sh users token <name> --revoke` | at once |
| the account itself gone | `./container-py.sh users remove <name> --apply` (a report without `--apply`); `disable` is usually the better choice | at once |

None of these need a restart. **Roles**, in one line: a viewer reads,
exports and queries; an editor also uploads, links and edits; an admin also
deletes, merges, clears, and manages the accounts (from the terminal).
Too low a role answers 403 naming the role needed; the page shows it as a
message. The rule is one function, `required_role`, from the request's
verb and path ([phase SH-3b, Step 4](04-phase-tutorials/phase-sh-3b-local-accounts.md#step-4--three-roles-one-rule)).

**Rotate the session secret** (a leak, or once a quarter): a new value on
its line, then `stop` and `start`; every browser is signed out at once,
personal tokens are unaffected.

```bash
new="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" && sed -i "s|^SESSION_SECRET=.*|SESSION_SECRET=${new}|" .env.local && unset new
./container-py.sh stop && ./container-py.sh start
```

**Back to the token, or off:** `sed -i 's|^AUTH_MODE=.*|AUTH_MODE=token|' .env.local`
(or `off`), then the same `stop` and `start`. The accounts stay in the
database, ignored until the mode is `local` again.

**After a `restore`** (beta refreshed from production's backup): the
accounts are part of the database, so beta's are now production's; create
the testers again with `users add`.

**What the local mode changes for the probes and the scripts:** nothing.
`/api/health`, `/api/instance` and `/api/auth/me` stay open; the monitor
and the container's probe ask `/api/health`; the maintenance scripts read
the database. `./container-py.sh status` holds no personal token, so in
this mode it reports the counts from the database itself and lists the
accounts.

### Protected files (`.gitignore`)

```
/certs/            # SSL certificates (plus *.key/*.crt/*.pem/... globs)
/data/             # SQLite database and runtime data
/backups/          # local database backups
.env, .env.*, *.env  # environment files / secrets; the VM keeps CERT_SOURCE, CERT_HOSTNAME, USE_HTTPS and, with the login on, AUTH_MODE and CRUCIBLE_TOKEN or SESSION_SECRET in an untracked .env.local (docs/01-setup-rhel8.md §3.2)
node_modules/      # dependencies (installed per machine)
client/dist/       # build output
.venv/             # Python virtualenv
```

(Excerpt — see the actual [.gitignore](../.gitignore) for the full list.)

### Known gaps / future enhancements

- [x] **Authentication, rung 1** — the token gate (v2.22.0): the runbook above, `AUTH_MODE` and `CRUCIBLE_TOKEN` in the environment table. Still to come on the same ladder: single sign-on (SH-3c, on hold at the owner's request) — [`13-authentication.md`](13-authentication.md)
- [x] **Authentication, rung 2** — local accounts (v2.23.0): the accounts runbook above, `SESSION_SECRET` in the environment table, three roles enforced by the guard
- [ ] Role-based access control in the page (buttons greyed out by role) and an accounts page for the admin (SH-4)
- [ ] Rate limiting and audit logging (*who* on every record: SH-4)
- [x] Certificate-expiry monitoring — done: `./cert-expiry-check.sh` (see [Certificate-expiry monitoring](#certificate-expiry-monitoring))

---

## Uninstall and reinstall

Full walkthroughs — what you cannot get back, a dry-run preview, mode-by-mode
detail, manual leftovers, and a verification checklist — are in
[docs/01-uninstall-macos.md](01-uninstall-macos.md) and
[docs/01-uninstall-rhel8.md](01-uninstall-rhel8.md).

`./uninstall.sh` removes the deployment (podman or docker, on any platform):

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
| systemd user units | `~/.config/systemd/user/container-crucible-py.service` and `~/.config/containers/systemd/crucible-py.container` (`…crucible-py-beta…` for the beta instance; `uninstall.sh` picks the folder's own) | `systemctl --user disable --now container-crucible-py.service` · `systemctl --user stop crucible-py.service` · `rm -f` both files · `systemctl --user daemon-reload` · optionally `sudo loginctl disable-linger $USER` |
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
[backend/scripts/healthcheck.py](../backend/scripts/healthcheck.py)), the
container `--restart unless-stopped` policy, and the optional `monitor.sh`
cron (see [Health monitoring](#health-monitoring)).

---

### Support

For deployment issues:
- Email: `<maintainer-email>`
- Slack: #crucible
- Docs: [README.md](../README.md) | [docs/08-api-reference.md](08-api-reference.md)

---

**Last Updated:** September 23, 2026
