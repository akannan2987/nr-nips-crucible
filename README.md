# Crucible: Pandora Toolbox Enhancement (v2.0)

Chemical and Sample Management System - MVP

A comprehensive web application for managing chemical compounds, samples, screening data, and toxicology information with an integrated Electronic Lab Notebook (ELN). Deployed with **HTTPS/TLS** encryption using official Nestlé SSL certificates.

**[Documentation index](#the-documentation-in-order)** · **[Glossary](docs/GLOSSARY.md)** · **[Release notes](NEWS.md)** · **[API cookbook](docs/API-COOKBOOK.md)**

> **New to any of this?** Every technical term used anywhere in this repository —
> container, port, certificate, migration, CAS number, SLIMS — is explained in
> plain words, with everyday comparisons, in **[docs/GLOSSARY.md](docs/GLOSSARY.md)**.
> If you meet a word that isn't there and isn't obvious, that's a documentation
> bug worth reporting. You are not expected to arrive already knowing the
> vocabulary.

## 🚀 Quick Start

### Setup after clone

Clone from the repository that matches your platform:

```bash
# macOS (development) — PUBLIC repo, no authentication needed:
git clone https://github.com/akannan2987/nr-nips-crucible.git

# RHEL8 VM (production) — PRIVATE Nestlé repo (PAT over HTTPS, or SSH key):
git clone https://github.com/nestle-it/nr-nips-crucible.git

cd nr-nips-crucible

# One command does everything — on macOS AND the RHEL8 VM:
./setup-after-clone-py.sh
```

> **Two repositories, one codebase:** macOS development tracks the public
> mirror `akannan2987/nr-nips-crucible`; the RHEL8 VM deploys from the private
> `nestle-it/nr-nips-crucible` (SSH form:
> `git@github.com:nestle-it/nr-nips-crucible.git`). Certificates, databases,
> and internal data are excluded from both via `.gitignore`.
> How changes move between them — and the `./check-public-safe.sh` gate to run
> before every public push — is documented in
> **[docs/GITOPS-WORKFLOW.md](docs/GITOPS-WORKFLOW.md)**.

That one command copies and verifies SSL certificates (when a certificate store
exists), builds the image, starts the app (HTTPS when certs exist, else HTTP),
polls the API until it answers, and optionally installs the monitoring cron
(`SETUP_MONITOR=n` to skip the prompt). Every step, its expected output, and
every likely mistake: **[macOS Install](docs/INSTALL-MACOS.md)** ·
**[RHEL8 Install](docs/INSTALL-RHEL8.md)**; deep runbooks in
**[DEPLOYMENT.md](DEPLOYMENT.md)**.

### Which guide should I follow?

- **This README** — overview, quick start, and the fastest path to a running app.
- **Platform guides** — the per-platform install/run and uninstall walk-throughs: [macOS Install](docs/INSTALL-MACOS.md) · [macOS Uninstall](docs/UNINSTALL-MACOS.md) · [RHEL8 Install](docs/INSTALL-RHEL8.md) · [RHEL8 Uninstall](docs/UNINSTALL-RHEL8.md). Start here for a fresh machine.
- **[GitOps Workflow](docs/GITOPS-WORKFLOW.md)** — how a change travels: Mac authoring → `./check-public-safe.sh` → public repo (3 branches) → VM mirror → private repo → production.
- **[DEPLOYMENT.md](DEPLOYMENT.md)** — the **deep operational reference**: all runbooks, SSL/TLS rotation, PostgreSQL, systemd/Quadlet, backups, maintenance, and troubleshooting.

| I want to… | Command | Detailed guide |
|---|---|---|
| **Deploy** (first time or redeploy) | `./setup-after-clone-py.sh` | [macOS Install](docs/INSTALL-MACOS.md) / [RHEL8 Install](docs/INSTALL-RHEL8.md) · deep dive: [Runbook A](DEPLOYMENT.md#runbook-a--macos-docker) / [B](DEPLOYMENT.md#runbook-b--macos-podman) / [C](DEPLOYMENT.md#runbook-c--rhel8-vm-podman) |
| **Enable HTTPS** | `./container-py.sh start-ssl` | [macOS](docs/INSTALL-MACOS.md#3-enable-https) / [RHEL8](docs/INSTALL-RHEL8.md#3-https-with-corporate-certificates) · [SSL/TLS setup](DEPLOYMENT.md#ssltls-certificate-setup) |
| **Update to a new version** | `git pull && ./container-py.sh rebuild` | [RHEL8 Day-2 ops](docs/INSTALL-RHEL8.md#6-day-2-operations) |
| **Back up / restore data** | `./container-py.sh backup` · `restore` | [Backup and restore](DEPLOYMENT.md#backup-and-restore) |
| **Uninstall** | `./uninstall.sh --full` (or `--partial`) | [macOS Uninstall](docs/UNINSTALL-MACOS.md) / [RHEL8 Uninstall](docs/UNINSTALL-RHEL8.md) |
| **Reinstall after uninstall** | `./setup-after-clone-py.sh` | [Reinstall / redeploy](DEPLOYMENT.md#uninstall-and-reinstall) |
| **Routine maintenance** (cert rotation, backup cron, history purge) | — | [Maintenance and operational tasks](DEPLOYMENT.md#maintenance-and-operational-tasks) |

**macOS vs RHEL8 at a glance** (the scripts are the same on both — they auto-detect podman/docker):

| | macOS (dev) | RHEL8 VM (production) |
|---|---|---|
| Clone from | **public** `akannan2987/nr-nips-crucible` | **private** `nestle-it/nr-nips-crucible` |
| Before deploy | start Docker Desktop **or** `podman machine start` | `dnf install podman` (first time) |
| Runs as | **HTTP** on `localhost:49160` (`./setup-ssl.sh` for local HTTPS) | **HTTPS** on `0.0.0.0:49160` (Nestlé certs) |
| Extra prod steps | none | open firewall port + systemd auto-start |
| Deploy guide | [macOS Install](docs/INSTALL-MACOS.md) | [RHEL8 Install](docs/INSTALL-RHEL8.md) |
| Uninstall guide | [macOS Uninstall](docs/UNINSTALL-MACOS.md) | [RHEL8 Uninstall](docs/UNINSTALL-RHEL8.md) (+ firewall rule) |

### 🔁 The project lifecycle — end to end

Every stage of working on this project, in order. Each stage links to the doc
that owns the details; the one-liners are reminders, not substitutes.

| # | Stage | Where | One-liner | Full guide |
|---|-------|-------|-----------|------------|
| 0 | **Understand the two repos** | — | public = Mac authoring · private = VM deploys; content flows public → private only | [GitOps §1](docs/GITOPS-WORKFLOW.md#1-the-two-repositories) |
| 1 | **One-time setup** (folders + remotes) | Mac + VM | clone the right repo into the right folder | [GitOps §2](docs/GITOPS-WORKFLOW.md#2-one-time-setup) |
| 2 | **Install & run** | Mac / VM | `./setup-after-clone-py.sh` | [macOS](docs/INSTALL-MACOS.md) / [RHEL8](docs/INSTALL-RHEL8.md) |
| 3 | **Develop + test** | ▶ Mac | edit → `cd backend && .venv/bin/pytest` → `./container-py.sh rebuild` | [GitOps Flow A step 1](docs/GITOPS-WORKFLOW.md#4-flow-a---a-change-from-start-to-finish) |
| 4 | **Security gate** | ▶ Mac | `./check-public-safe.sh` → must print `✓ SAFE TO PUSH` | [GitOps §3 rules](docs/GITOPS-WORKFLOW.md#3-golden-rules) |
| 5 | **Publish to public repo** | ▶ Mac | `git push origin develop develop:beta develop:master` | [GitOps Flow A steps 3–5](docs/GITOPS-WORKFLOW.md#4-flow-a---a-change-from-start-to-finish) |
| 6 | **Mirror public → private** | ▶ VM `~/work/Pandora_toolbox/crucible-mirror` | `git fetch public && git checkout public/develop -- .` → commit → push | [GitOps Flow A steps 6–9](docs/GITOPS-WORKFLOW.md#4-flow-a---a-change-from-start-to-finish) |
| 7 | **Deploy to production** | ▶ VM prod folder | `./container-py.sh backup` → `git pull` → `./container-py.sh rebuild` | [RHEL8 §6 Day-2 ops](docs/INSTALL-RHEL8.md#6-day-2-operations) |
| 8 | **Verify the deployment** | Mac / VM | checklist V1–V7 (Mac) / V1–V9 (VM) | [macOS §4](docs/INSTALL-MACOS.md#4-verification-checklist) / [RHEL8 §5](docs/INSTALL-RHEL8.md#5-verification-checklist) |
| 9 | **Confirm repo sync** | ▶ VM mirror | `git diff --stat public/develop develop` → only private-only files | [GitOps §6](docs/GITOPS-WORKFLOW.md#6-checking-the-two-repos-are-in-sync) |
| 10 | **Routine ops** | VM (+ Mac) | backups, health monitoring, cert-expiry cron | [DEPLOYMENT → Maintenance](DEPLOYMENT.md#maintenance-and-operational-tasks) |
| 11 | **Uninstall** (when needed) | Mac / VM | `./uninstall.sh --dry-run` first, always | [macOS](docs/UNINSTALL-MACOS.md) / [RHEL8](docs/UNINSTALL-RHEL8.md) |

A fix discovered **on the VM** travels back as a patch (never a push):
[GitOps Flow B](docs/GITOPS-WORKFLOW.md#5-flow-b---a-fix-discovered-on-the-vm).

---

## ✨ Features

- **Chemicals Management**: Upload and manage chemicals with bulk operations (no upload limit; optimized for 15,000+)
- **Sample Management**: Manage samples linked to chemicals (no upload limit; optimized for 1,000+)
- **Screening Data**: Store and link screening assay results to chemicals
- **Toxicology Data**: Manage toxicology study data linked to chemicals
- **Bulk Operations**: Multi-select, bulk delete, and bulk edit functionality
- **Live Dashboard**: Auto-refreshing dashboard with real-time statistics (5s interval)
- **Excel Upload**: Bulk import via Excel files with custom column mapping
- **RESTful API**: Complete API for programmatic access
- **HTTPS/TLS**: Encrypted connections using official Nestlé SSL certificates
- **Health Monitoring**: Automated health checks with auto-restart capability

---

## 🏗️ Architecture

> ℹ️ The backend was migrated from Node.js/Express to **Python/FastAPI**
> (strangler-fig) with an identical API contract; the React client is
> unchanged. The legacy Node stack has been retired — see the brief history
> in **[MIGRATION.md](MIGRATION.md)**.

**Tech Stack:**
- **Frontend**: React 18 + Vite 5 + Tailwind CSS 3.4
- **Backend**: Python 3.12 + FastAPI + uvicorn
- **Database**: SQLite by default via SQLAlchemy 2 (`data/crucible.db`); optional **PostgreSQL** via `DATABASE_URL`, schema managed by **Alembic** in the container
- **Chemistry**: RDKit (SDF/structure handling)
- **Excel**: openpyxl (SLIMS sample template + chemical templates)
- **Container**: `crucible-py` image, managed by `container-py.sh` (podman or docker)

**Modules:**
1. **ELN (Electronic Lab Notebook)**: Upload interface for all data types
2. **Data Viewer**: Search, filter, and view all uploaded data
3. **Dashboard**: Real-time statistics and capacity monitoring

📚 **[View Architecture Details →](docs/architecture.md)** · **[Migration Guide →](MIGRATION.md)**

---

## 📦 Installation

**Prerequisites:** Podman or Docker (the containerized deployment needs nothing
else) plus OpenSSL for certificate verification; production HTTPS additionally
needs access to the corporate certificate store, and bare-metal development
wants Python 3.12+ and Node.js 18+ / npm 8+.

The install itself is one command — `./setup-after-clone-py.sh` — documented
step by step, for a reader with no prior container experience, in
**[macOS Install → §1 Prerequisites](docs/INSTALL-MACOS.md#1-prerequisites)**
and **[RHEL8 Install → §1 Prerequisites](docs/INSTALL-RHEL8.md#1-prerequisites-one-time-vm-setup)**.

---

## 🛠️ Development

Bare-metal setup (Python venv + dependencies) is in
**[backend/README.md → Quickstart](backend/README.md#quickstart-macos)**; the
React client additionally needs `cd client && npm install` once.

**Hot reload — two terminals** (frontend on `http://localhost:3000`, API on `http://localhost:8000`):

```bash
# Terminal 1 — FastAPI with auto-reload on a side port
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

# Terminal 2 — React dev server, proxying /api to the backend above
cd client && VITE_API_PROXY_TARGET=http://localhost:8000 npm run dev
```

**Bare-metal production build** (serves API + built client on `http://localhost:49160`):

```bash
cd client && npm run build                                  # → client/dist
cd ../backend && PORT=49160 .venv/bin/python -m app.main
```

Module layout, every environment variable, and the generated FastAPI `/docs`
page: **[backend/README.md](backend/README.md)**.

---

## 🧪 Testing

```bash
cd backend
.venv/bin/pytest                     # contract-parity tests + unit tests
```

The suite locks the **v1 API contract** (response keys, messages, status codes)
so the backend can be refactored safely, and covers API parity for every module
(CRUD, duplicate rejection, pagination quirks, capacity limits), SDF parsing
(V2000/V3000 incl. line continuations, S-Groups, polymer/mixture detection,
stereochemistry, formal charges, Tier 1 named fields), SLIMS sample parsing
(3-row header, field renames, European date normalisation), and static/SPA
serving. 📚 **[backend/README.md](backend/README.md)** ·
**[Architecture → Testing](docs/architecture.md#testing)**

---

## 🐳 Container Deployment

Both scripts auto-detect **podman or docker** (override with
`CONTAINER_RUNTIME=docker|podman`) and check the podman VM state on macOS.
Port override: `CRUCIBLE_PORT=<n>` (a generic `PORT` env var is ignored to
avoid clashes on shared machines).

Deploying and updating on the RHEL8 VM (the field-tested backup → `git pull` →
`rebuild` → verify sequence, plus firewall, SELinux and systemd auto-start):
**[RHEL8 Install → §6 Day-2 operations](docs/INSTALL-RHEL8.md#6-day-2-operations)**.

### Container commands

```bash
./container-py.sh build       # Build image (node build stage + python:3.12-slim)
./container-py.sh start       # Start on port 49160 (HTTP)
./container-py.sh start-ssl   # Start with HTTPS (certs/server.crt + server.key)
./container-py.sh status      # Status + /api/stats healthcheck
./container-py.sh logs        # View logs
./container-py.sh stop        # Stop container
./container-py.sh rebuild     # Rebuild image + restart
./container-py.sh shell       # Shell inside the container
./container-py.sh clean       # Remove container and image
```

**PostgreSQL (optional — SQLite is the default):**

```bash
./container-py.sh db-start    # Start the managed PostgreSQL container (once)
./container-py.sh db-stop     # Stop it
./container-py.sh db-shell    # Open a psql shell
USE_POSTGRES=true ./container-py.sh start   # run the app against PostgreSQL
```

### 💾 Backup & Restore (same commands on Mac and RHEL8)

```bash
./container-py.sh backup       # consistent snapshot → backups/ (safe while running)
./container-py.sh restore      # list available backups
./container-py.sh restore backups/crucible-<stamp>.db   # stop → swap db → restart
```

Safe while running (SQLite's online-backup API — never plain-`cp` a live
database). Retention, the VM's nightly cron, and machine-to-machine transfer:
**[DEPLOYMENT.md → Backup and restore](DEPLOYMENT.md#backup-and-restore)**.

📚 **[View Full Deployment Guide →](DEPLOYMENT.md)**

---

## 🔒 HTTPS / SSL Configuration

TLS is served **in-process by uvicorn** from the `certs/` directory
(`server.crt` / `server.key`, plus `ca.crt` from `Nestle_Root_CA.cer` where the
root is needed) — via `./container-py.sh start-ssl`, or automatically when
`USE_HTTPS=true`. Certs are runtime-mounted read-only, never baked into the
image. This is transport encryption only; user *authentication* (SSO) remains a
planned enhancement.

On the VM, certificates come from the corporate store, whose site-specific path
is set once in an untracked `.env.local` (`CERT_SOURCE`, optional
`CERT_HOSTNAME`) — **[RHEL8 §3](docs/INSTALL-RHEL8.md#3-https-with-corporate-certificates)**.
Self-signed dev certs on a Mac (`./setup-ssl.sh`) — **[macOS §3](docs/INSTALL-MACOS.md#3-enable-https)**.
Rotation, expiry monitoring, and the cert/key modulus check —
**[DEPLOYMENT.md](DEPLOYMENT.md#ssltls-certificate-setup)**.

> ⚠️ **Security**: SSL certificates and private keys are excluded from git via `.gitignore`. Never commit these files.

---

## 🌐 Access URLs

| Environment | URL | Protocol |
|-------------|-----|----------|
| **Production (HTTPS)** | `https://<vm-hostname>:49160` | HTTPS/TLS |
| **Architecture Docs** | `https://<vm-hostname>:49160/architecture` | HTTPS/TLS |
| Development (Frontend) | `http://localhost:3000` | HTTP |
| Development (API) | `http://localhost:49160` | HTTP |

---

## 📡 API Endpoints

Quick reference of available endpoints:

**Statistics & Dashboard:**
- `GET /api/stats` - Get dashboard statistics

**Chemicals:**
- `GET /api/chemicals` - List all chemicals (paginated)
- `POST /api/chemicals` - Add a single chemical
- `POST /api/chemicals/upload/excel` - Bulk upload via Excel
- `POST /api/chemicals/bulk/delete` - Bulk delete chemicals
- `POST /api/chemicals/bulk/update` - Bulk update chemicals

**Samples, Screening, Toxicology:**
- Similar CRUD endpoints available for each module

📚 **[View Full API Documentation →](API.md)** · **[Copy-paste recipes →](docs/API-COOKBOOK.md)** · **[Worked curl/Python examples →](docs/API-TESTING-GUIDE.md)**

---

## 📊 Excel Upload Format

For bulk chemical uploads, prepare an Excel file with these columns:

| Column | Maps To | Required |
|--------|---------|----------|
| `DTX_ID` | Chemical ID | Optional (auto-generated) |
| `NESTLE_ID` | Nestle ID | Optional |
| `CHEMICAL_NAME` | Chemical Name | **Required** |
| `CAS_NO` | CAS Number | Optional |
| `MOL_WEIGHT_ORIG` | Molecular Weight | Optional |
| `MOL_FORMULA` | Molecular Formula | Optional |
| `Supplier_ref` | Supplier Reference | Optional |

📥 **[Download Excel Templates →](docs/excel-templates/)** — synthetic example
templates for chemicals (CSV/XLSX/SDF), samples, screening, and toxicology,
with the exact column names each upload endpoint reads.

---

## 🗄️ Database Schema

Four collections/tables: `chemicals`, `samples`, `screening`, `toxicology`.

Each table stores the full record as a JSON `doc` column plus indexed lookup
columns (hybrid document pattern). **SQLite (`data/crucible.db`) is the
default**; **PostgreSQL is optional** via `DATABASE_URL` (the `doc` column
becomes JSONB). In the container, **Alembic** owns the schema and brings it to
head on startup; local dev and tests create the tables automatically.

📚 **[Database Schema Details →](docs/database-schema.md)** · **[SQLite vs PostgreSQL setup →](DEPLOYMENT.md#database-sqlite-and-postgresql)**

---

## 📊 Health Monitoring

A cron job runs `monitor.sh` every 5 minutes: it GETs `/api/stats`, restarts the
`crucible-py` container on a non-200 answer, and logs to
`/tmp/crucible-monitor.log`. The container also carries its own HEALTHCHECK.

```bash
SETUP_MONITOR=y ./setup-after-clone-py.sh   # supported install path
./monitor.sh                                # run one check by hand
```

Never hand-write a simplified cron line — on RHEL8 it **requires** a
`USER=…`/`XDG_RUNTIME_DIR=…` prefix for rootless podman:
**[RHEL8 §4.3](docs/INSTALL-RHEL8.md#43-health-monitoring)**. Separately,
`./cert-expiry-check.sh` warns when the certificate is within `WARN_DAYS`
(default 30) of expiring — weekly cron example and the rest in
**[DEPLOYMENT.md → Health monitoring](DEPLOYMENT.md#health-monitoring)**.

---

## 🔧 Troubleshooting

| Symptom | First thing to try |
|---|---|
| Port 49160 already in use | `lsof -i :49160` to find the holder; `fuser -k 49160/tcp` to free it |
| App unreachable / container misbehaving | `./container-py.sh status`, then `./container-py.sh logs` — the real error is in the last ~20 lines |
| TLS handshake fails after `start-ssl` | cert and key are from different pairs — compare the modulus MD5 hashes, then `./setup-after-clone-py.sh` |
| Reachable on the VM but not from a workstation | host firewall — open port 49160 for the case that applies (firewalld / plain iptables / none) |
| Database looks wrong and you want a clean slate | `rm -f data/crucible.db` — re-created empty on the next start |

Beginner-oriented walkthroughs of the actual error messages (cause and named
fix for each): **[macOS Install → Troubleshooting](docs/INSTALL-MACOS.md#troubleshooting)**
and **[RHEL8 Install → §7 RHEL8-specific gotchas](docs/INSTALL-RHEL8.md#7-rhel8-specific-gotchas)**.
The deep symptom/cause/fix table — SELinux, rootless port binding, proxy-broken
healthchecks, systemd — is **[DEPLOYMENT.md → Troubleshooting](DEPLOYMENT.md#troubleshooting)**.

---

## 🧹 Uninstall & Reinstall

One `uninstall.sh` script covers both platforms and both runtimes:

- `./uninstall.sh --dry-run` — preview exactly what would go. **Run this first, always.**
- `./uninstall.sh` — interactive; choose what to remove step by step
- `./uninstall.sh --partial` — runtime artifacts only; source and `data/` kept
- `./uninstall.sh --full` — everything, including data and the project directory

> ⚠️ `--full` deletes the database, taking a final safety backup to
> `~/crucible-backups/crucible-final-<stamp>.db` first — restore it with
> `./container-py.sh restore <path>`. Reinstalling is the same
> `./setup-after-clone-py.sh` as a first install.

📚 What each mode removes, what it deliberately leaves behind, and how to
verify: **[macOS Uninstall →](docs/UNINSTALL-MACOS.md)** ·
**[RHEL8 Uninstall →](docs/UNINSTALL-RHEL8.md)** (adds firewall, systemd,
lingering) · **[Reinstall runbook →](DEPLOYMENT.md#uninstall-and-reinstall)**

---

## 🔐 Security

### What's Protected

- **HTTPS/TLS**: All production traffic encrypted with official Nestlé certificates
- **Git Safety**: SSL certificates, private keys, and database files excluded via `.gitignore`
- **Pre-push gate**: `./check-public-safe.sh` must print `✓ SAFE TO PUSH` before every
  public push — it verifies no secret paths are tracked, only sanitized templates ship,
  and no internal identifiers appear in tracked content. Where it sits in the
  public→private flow: **[docs/GITOPS-WORKFLOW.md](docs/GITOPS-WORKFLOW.md)**
- **File Permissions**: Private key restricted to `chmod 600`
- **Error Handling**: No sensitive data exposed in error responses

### Files Excluded from Git

The repository ships a comprehensive `.gitignore`. Highlights:

```
certs/ *.key *.crt   # SSL certificates and private keys (all formats)
data/  backups/ *.db # SQLite database and backups
.env / .env.*        # environment files and secrets (incl. the VM's .env.local)
node_modules/        # dependencies (installed per machine)
client/dist/         # build output
backend/.venv/       # Python virtualenv
docs/excel-templates/…  # only sanitized *_template.* files tracked; any other workbook stays local
crucible-costar-prompt.md  # local working notes (never published)
```

Keep a backup of real certificates **outside** the repository (e.g.
`~/.crucible/certs/` with `chmod 600` on the key) — every uninstall mode
deletes `certs/`.

### Future Security Enhancements

- [ ] SSO Login Integration
- [ ] Role-based access control
- [ ] Rate limiting
- [ ] Audit logging

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

> 📋 **Before pushing**: run `./check-public-safe.sh` (must print `✓ SAFE TO PUSH`),
> follow the [Pre-Push Checklist](CONTRIBUTING.md#pre-push-checklist-before-pushing-to-develop),
> then push all three branches and mirror to the private repo per the
> [GitOps Workflow](docs/GITOPS-WORKFLOW.md).

---

## The documentation, in order

Every guide, in the order a newcomer should meet them. The install guides
assume **no prior experience** with containers, terminals, or servers: every
technical word is explained where it first appears, every command shows the
output you should get, and likely mistakes get a named fix.

**Start here**

| # | Guide | What it teaches |
|---|-------|-----------------|
| 00 | **[Glossary](docs/GLOSSARY.md)** | Every term in the project, in plain words — read it, or keep it open in a tab |
| 01 | **[macOS Install & Run](docs/INSTALL-MACOS.md)** | From a blank Mac to the app running: containers, ports, HTTPS. Uses the **public** repo |
| 02 | **[RHEL8 Install & Run](docs/INSTALL-RHEL8.md)** | The production deployment: rootless podman, SELinux, firewall, real certificates, surviving a reboot. Uses the **private** repo |
| 03 | **[API Cookbook](docs/API-COOKBOOK.md)** | Copy-paste recipes for talking to the app — every answer captured from a live instance |
| 04 | **[GitOps Workflow](docs/GITOPS-WORKFLOW.md)** | How a change travels from your Mac to the server, and the safety gate that stops secrets escaping |
| 05 | **[macOS Uninstall](docs/UNINSTALL-MACOS.md)** | Clean removal, starting with what you cannot get back |
| 06 | **[RHEL8 Uninstall](docs/UNINSTALL-RHEL8.md)** | The same, plus the server-only pieces (systemd, firewall, cron) |

**Reference — look things up as needed**

| Document | What it holds |
|----------|---------------|
| **[Deployment Guide](DEPLOYMENT.md)** | The deep operational reference: all runbooks, certificate rotation, PostgreSQL, systemd, troubleshooting |
| **[API Documentation](API.md)** | Complete REST API reference, endpoint by endpoint |
| **[API Testing Guide](docs/API-TESTING-GUIDE.md)** | Worked `curl` and Python examples |
| **[Architecture](docs/architecture.md)** | How the pieces fit together |
| **[Database Schema](docs/database-schema.md)** | The storage pattern (SQLite + optional PostgreSQL/Alembic) |
| **[Upload Templates](docs/excel-templates/)** | The spreadsheet formats each module accepts |
| **[Backend README](backend/README.md)** | Python backend: quickstart, tests, environment variables |
| **[Contributing Guidelines](CONTRIBUTING.md)** | How to make and publish a change |
| **[Release notes](NEWS.md)** | What changed in each version, and why |
| **[MIGRATION.md](MIGRATION.md)** | History of the Node→Python migration |

---

## 🎯 Future Enhancements

- [ ] SSO Login Integration
- [ ] Advanced search and filtering with facets
- [ ] Data export functionality (Excel, CSV, JSON)
- [ ] Chemical structure visualization
- [ ] Batch upload improvements with validation
- [ ] Audit trail and version history
- [ ] Advanced analytics and reporting

---

## 📄 License

Intended license: MIT. A `LICENSE` file has not yet been added — pending the
repository owner's decision (note this code originates from an internal
project; confirm licensing before adding the file).

---

## 👥 Authors

**Abhilash Kannan** - Computational Sciences, Nestle Research

For support, contact: `<maintainer-email>`

---

**Last Updated:** August 24, 2026
