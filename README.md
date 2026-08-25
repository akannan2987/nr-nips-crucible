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

## What is a chemical registry? (start here)

Imagine a toxicologist who needs to know whether a compound has been tested
before. Somebody screened it two years ago, but the results are in a
spreadsheet on a laptop that has since been reimaged. The physical sample was
logged under a different identifier, by a colleague who has changed teams. The
toxicology study that followed sits in a third file, named after the study
rather than the compound. Nobody can prove the three describe the same
substance, so the compound is re-ordered, re-prepared and re-tested — weeks of
work to learn something the organisation already knew.

A **chemical registry** — one catalogue that gives every compound a single
identity, and keeps everything ever measured about it attached to that
identity. Instead of asking *which file has this in it?*, you ask the registry.

Four words that recur throughout this project, in the order the work happens:

- A **chemical** is the substance itself, on paper: a name, a molecular
  formula, usually a **CAS number** (the internationally agreed identifier for
  a substance — the same string means the same compound in any lab in the
  world).
- A **sample** is a physical quantity of that chemical sitting in a vial: a
  batch, a concentration, a location, an expiry.
- **Screening** is the fast, broad first test — run a sample against an assay
  and record what happened.
- A **toxicology study** is the slow, careful one that follows: dose levels,
  endpoints, a **NOAEL** (the highest dose at which nothing harmful was
  observed).

Every one of these terms, and every technical one below, is defined in plain
words in the **[Glossary](docs/GLOSSARY.md)**.

---

## The problem this project tackles

**The pain point.** Laboratory data arrives as spreadsheets. Each is correct on
its own and useless next to the others: the same compound appears under a
supplier code in one file, a CAS number in another, and a free-typed name in a
third. Nothing enforces that they refer to the same thing, so the link between
a compound, the vial it went into, and the result that came out exists only in
somebody's memory. When that person moves on, the link goes with them.

**Why it matters.** Work gets repeated because nobody can prove it was already
done. Safety questions take days to answer because answering them means finding
files rather than querying data. And the answers are unauditable: a number in a
spreadsheet cannot say where it came from.

**What Crucible is.** A web application that holds all four kinds of record in
one place, keyed to one chemical identity, uploadable from the spreadsheet and
structure formats laboratories already produce — and readable back out through
a REST API so other tools can ask it questions. It runs on one machine, in one
container, against a single database file. It is deliberately small: this is a
system of record, not an analysis platform.

---

## How it works

```
   Your spreadsheet or structure file
   (.xlsx · .csv · .sdf)
              │
              ▼
   ┌──────────────────────┐   You map your column names to the fields
   │  Upload (ELN page)   │   Crucible knows. Nothing is renamed on disk.
   └──────────┬───────────┘
              ▼
   ┌──────────────────────┐   openpyxl reads spreadsheets; RDKit reads
   │  Parse & validate    │   chemical structures. Bad rows are reported,
   └──────────┬───────────┘   not silently dropped.
              ▼
   ┌──────────────────────┐   Every record is stored whole, as JSON, plus a
   │  Store (SQLite)      │   few indexed columns for finding it again.
   └──────────┬───────────┘   Your original fields survive verbatim.
              │
      ┌───────┴────────┐
      ▼                ▼
 ┌─────────┐    ┌─────────────┐
 │ Browser │    │  REST API   │  Same data, two doors: people use the
 │ Viewer  │    │  /api/*     │  web pages, programs use the endpoints.
 │Dashboard│    └─────────────┘
 └─────────┘
```

Upload a file, map its columns once, and the records land in the database with
their original fields intact. **The full record is kept as JSON and treated as
the source of truth**; the indexed columns beside it exist only to find rows
quickly. That is the single design decision the rest of the system follows
from — it is why an upload never has to be reshaped to fit a schema, and why
adding a field later breaks nothing. The reasoning, and what it costs, is in
**[Architecture → The one rule](docs/architecture.md#the-one-design-rule-everything-else-follows-from)**.

---

## What the system handles

| Module | What it holds | Accepts | Optimised for | Linked to |
|---|---|---|---|---|
| **Chemicals** | The substance: name, CAS number, formula, molecular weight, supplier reference | `.xlsx` · `.csv` · `.sdf` | 15,000+ records | — (the anchor everything else hangs from) |
| **Samples** | The physical vial: batch, concentration, location, expiry | `.xlsx` (SLIMS three-row header) | 1,000+ records | a chemical |
| **Screening** | Assay results: the fast, broad first pass | `.xlsx` | — | a chemical |
| **Toxicology** | Study data: doses, endpoints, NOAEL | `.xlsx` | — | a chemical |

Three ways in and out: the **ELN** upload pages, the **Data Viewer** for search
and filter, and the **Dashboard**, which refreshes counts every five seconds.
Everything the browser does, the **[REST API](API.md)** can do too — the web
pages are simply its first client.

Neither upload limit is a hard cap. They are the volumes the system has been
exercised at; see [About the data](#about-the-data-honesty-notes) for what that
does and does not promise.

---

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
(`SETUP_MONITOR=n` to skip the prompt).

**The guided path.** If you have not deployed a container before — or you want
to know what each step is actually doing rather than watch it scroll past —
follow the platform guide instead of the one-liner. They start from a blank
machine, explain every term where it first appears, show the output each
command should produce, and name the likely mistakes:
**[macOS Install](docs/INSTALL-MACOS.md)** ·
**[RHEL8 Install](docs/INSTALL-RHEL8.md)**. Deep operational runbooks live in
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

### What is not protected

Transport is encrypted; **access is not controlled**. There is no login, no
roles, no rate limiting, and no audit log — anyone who can reach port 49160 can
read and change everything. That is a known, deliberate state for internal
trusted-network use. What each of those waits on is set out in the
[Roadmap](#roadmap), and the practical consequences in
[About the data](#about-the-data-honesty-notes).

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
| 04 | **[Query Cookbook](docs/QUERY-COOKBOOK.md)** | Asking the database questions directly — why queries look unusual here, and recipes that work |
| 05 | **[GitOps Workflow](docs/GITOPS-WORKFLOW.md)** | How a change travels from your Mac to the server, and the safety gate that stops secrets escaping |
| 06 | **[macOS Uninstall](docs/UNINSTALL-MACOS.md)** | Clean removal, starting with what you cannot get back |
| 07 | **[RHEL8 Uninstall](docs/UNINSTALL-RHEL8.md)** | The same, plus the server-only pieces (systemd, firewall, cron) |

**Reference — look things up as needed**

| Document | What it holds |
|----------|---------------|
| **[Deployment Guide](DEPLOYMENT.md)** | The deep operational reference: all runbooks, certificate rotation, PostgreSQL, systemd, troubleshooting |
| **[API Documentation](API.md)** | Complete REST API reference, endpoint by endpoint |
| **[API Testing Guide](docs/API-TESTING-GUIDE.md)** | Worked `curl` and Python examples |
| **[Query Cookbook](docs/QUERY-COOKBOOK.md)** | Read-only SQL against the database, with recipes |
| **[Architecture](docs/architecture.md)** | How the pieces fit together |
| **[Database Schema](docs/database-schema.md)** | The storage pattern (SQLite + optional PostgreSQL/Alembic) |
| **[Upload Templates](docs/excel-templates/)** | The spreadsheet formats each module accepts |
| **[Backend README](backend/README.md)** | Python backend: quickstart, tests, environment variables |
| **[Contributing Guidelines](CONTRIBUTING.md)** | How to make and publish a change |
| **[Release notes](NEWS.md)** | What changed in each version, and why |
| **[MIGRATION.md](MIGRATION.md)** | History of the Node→Python migration |

---

## Repository map

```
nr-nips-crucible/
├── backend/                    the application
│   ├── app/
│   │   ├── main.py             FastAPI app: starts uvicorn, serves the SPA
│   │   ├── routers/            one thin file per module — chemicals, samples,
│   │   │                       screening, toxicology, stats
│   │   ├── store.py            all data access lives here, not in the routers
│   │   ├── models.py           the four tables (indexed columns + JSON doc)
│   │   ├── schemas.py          Pydantic shapes — deliberately lenient
│   │   ├── database.py         engine + get_db session dependency
│   │   └── utils/              excel.py · samples_excel.py · sdf.py (the parsers)
│   ├── alembic/                schema migrations; owns the schema in the container
│   ├── tests/                  47 tests, mostly contract-parity
│   └── Dockerfile              multi-stage: Node builds the UI, then is discarded
├── client/                     React SPA
│   └── src/pages/              Dashboard · <Module>Upload · <Module>View
├── docs/                       every guide (see the index above)
│   └── excel-templates/        synthetic upload templates + their generator
├── container-py.sh             build · start · start-ssl · status · backup · restore
├── setup-after-clone-py.sh     the one-command install
├── uninstall.sh                --dry-run · --partial · --full
├── check-public-safe.sh        the pre-push gate
├── monitor.sh                  health check, run from cron every 5 minutes
└── cert-expiry-check.sh        weekly certificate warning
```

| Path | What it is |
|---|---|
| `backend/app/` | Everything the server does. Routers stay thin; logic lives in `store.py` and `utils/`. |
| `backend/alembic/` | Schema migrations. In the container these run at startup and are the only thing allowed to change the schema. |
| `client/` | The browser interface. Built into `client/dist` and served by the same Python process — there is no second web server. |
| `docs/` | The guides. Written for a reader with no prior container experience. |
| `*.sh` (root) | The operator's toolkit. Same scripts on macOS and RHEL8; they auto-detect podman or docker. |

**Two kinds of "not in Git."** `data/`, `backups/` and `certs/` are absent
because they are *yours* — your records, your certificates — and must never
travel to a shared repository. `client/dist/`, `node_modules/` and
`backend/.venv/` are absent because they are *regenerated*: the build produces
them, and a repository that carried them would only carry them stale. The
[Security](#-security) section lists the full set and why each is excluded.

---

## Build log

Where the work has actually got to. Dates are when the change shipped, not when
it was started.

| Phase | What it covered | When | Status |
|---|---|---|---|
| — | **Node/Express → Python/FastAPI** migration, strangler-fig style: the new backend reproduced the old API exactly, verified by parity tests, so the React client never changed. Legacy stack retired. | pre-2.0 | ✅ Complete |
| — | **PostgreSQL + Alembic** support. Engine-agnostic via `DATABASE_URL`; Alembic owns the schema in the container. SQLite stays the default. | pre-2.0 | ✅ Complete |
| P.1–P.4 | **Public-repo hygiene.** Certificate backups, a comprehensive `.gitignore`, four platform runbooks with mirrored checklists, redaction of every internal hostname/username/path behind placeholders, and six real-data workbooks replaced by synthetic generated ones. | 2026-08-06 (v2.0.0) | ✅ Complete |
| — | **Three fixes found by using the docs**: HTTPS surviving a fresh install, a genuinely complete uninstall, and documentation caught up with the code. | 2026-08-17 (v2.0.x) | ✅ Complete |
| P.5a | **macOS verification.** A full walk of the install guide from a simulated fresh clone, checklist V1–V7. | 2026-08 | ✅ Passed |
| — | **Documentation rewritten for a newcomer**: the glossary, the API cookbook, release notes, and one home per topic across the guides. | 2026-08-24 (v2.1.0) | ✅ Complete |
| P.5b | **RHEL8 production verification**, checklist V1–V9. V8 (external browser access) confirmed against the real access log. V9 (surviving a reboot) is the one item still untested. | in progress | 🔄 Open |
| D | **Schema normalisation** — promote the frequently filtered fields out of JSON into real indexed columns, without changing the API. | next | ⏳ Planned |
| E | **Authentication** — `/api/*` is currently open to anyone who can reach the port. | after D | ⏳ Planned |

Version-by-version detail, including what each release deliberately did *not*
fix, is in **[NEWS.md](NEWS.md)**.

---

## Roadmap

Each item says what it waits on. That is the honest part: most of these are not
hard to build, they are blocked on a decision or on each other.

- **Authentication (SSO or token).** The largest gap. *Waits on:* a decision
  between corporate SSO/OIDC and a simpler token/header scheme, and a
  feature flag — internal users currently rely on there being no login, and
  turning one on without warning would break them mid-week.
- **Schema normalisation of hot fields.** Filtering and sorting currently reach
  inside the JSON document. *Waits on:* identifying which fields are genuinely
  hot, from the client's filters and the query patterns in `store.py`, and
  agreeing them before any migration is written. Guessing here means a
  migration that backfills the wrong columns.
- **Role-based access control.** *Waits on:* authentication. Roles are
  meaningless without identity.
- **Audit trail and version history.** *Waits on:* authentication. A log that
  cannot say *who* is a change log, not an audit trail — and the difference is
  the entire point.
- **Rate limiting.** *Waits on:* authentication, for the same reason: without
  identity the only thing to limit by is IP address, which on a corporate
  network is often one proxy.
- **Faceted search and filtering.** *Waits on:* schema normalisation. Counting
  facets across a JSON column means reading every row.
- **Data export (Excel, CSV, JSON).** *Waits on:* nothing. Simply not built
  yet — the API already returns the data, so this is a convenience layer.
- **Batch upload validation.** Reporting every problem in a file at once
  instead of stopping at the first. *Waits on:* nothing.
- **A `LICENSE` file.** *Waits on:* the repository owner's decision. Until one
  exists, "public on GitHub" still legally means all rights reserved.

2D structure rendering already ships — `MoleculeViewer` draws from the MOL
block or SMILES on the chemical detail view. It is listed here only because it
is easy to assume otherwise.

---

## Bumps hit along the way (kept on purpose)

Every one of these was found by actually running the documented procedure on a
real machine rather than by reading the code. They are recorded because the
lesson generalises, and because a project that lists no mistakes is a project
that has not been verified.

**The update command silently downgraded HTTPS to HTTP.** `rebuild` — the exact
command the update instructions tell you to run — brought the app back on plain
HTTP. Nothing failed, nothing logged a warning; the padlock just quietly went
away. *Lesson: a command that "restarts things" must preserve every mode the
old process was running in, and the ones you forget are the invisible ones.*

**`status` reported nothing at all in TLS mode**, because it probed `http://`
against an HTTPS listener. The healthcheck was structurally incapable of
succeeding on the production configuration.

**`start` printed the port you asked for**, not the port actually being served,
when it reused an existing container. The output was confident and wrong, which
is worse than no output.

**`.env.local` was ignored on a fresh install.** `USE_HTTPS=true` was only
honoured if a container already existed to copy the setting from — so the first
start after an uninstall came up unencrypted, at the moment nobody was
watching.

**`uninstall.sh` aborted halfway through, reporting success.** Six functions
ended with `[ "$found" -eq 0 ] && { ...; }`. When something *was* found, that
expression evaluated false, the function returned non-zero, and `set -e` killed
the script — so the image was never removed. *Lesson: under `set -e`, never end
a bash function with a bare `[ ... ] && { ... }`. Use `if ... fi`.*

**A clean uninstall looked like a failed one.** Removing a systemd unit file
leaves an in-memory record that prints as `not-found failed failed`. Everything
had worked; the output said otherwise. The script now calls `reset-failed`.

**The docs said `cp -r data/` immediately after taking a proper backup.** A
plain copy of a live SQLite file can be quietly corrupt — it opens fine and
fails much later. The guides now copy the snapshot out of `backups/` instead.

**Thirty-five verification commands used `curl -s`.** With `-s`, a failed
request prints *nothing* — indistinguishable from a successful silent one. Every
one became `-sS`. *Lesson: in a document that teaches, a command that can fail
invisibly is worse than no command at all.*

**A weekly certificate check reported "OK" for months without ever looking at a
certificate.** Its cron line pointed at a second checkout that has no `certs/`
directory, and "no certificate present" was being treated as "nothing wrong".
*Lesson: a monitor that cannot fail is not a monitor.*

**The macOS monitoring cron never ran once.** Two independent causes stacked:
cron's minimal `PATH` excludes the podman install location, and macOS blocks
cron from reading `~/Documents` without Full Disk Access. Neither produced an
error anybody saw.

**Verification commands that could not run looked exactly like passing ones.**
After a full uninstall deletes the project directory, the shell is left standing
in a folder that no longer exists, and every `podman` command fails with
`error getting current working directory`. Run as `podman … | grep crucible`,
that failure prints nothing — which is precisely what the guide says a pass
looks like. The uninstall guide now starts those blocks with `cd ~`.

---

## About the data (honesty notes)

- **The data is yours, and none of it is here.** No real records ship in this
  repository. The files in `docs/excel-templates/` are synthetic, generated by
  a tracked script, and exist to show the column names each endpoint reads.
- **Uploads are lenient on purpose.** Every field is optional and unknown
  columns are preserved rather than rejected, so that a spreadsheet never has
  to be reshaped to be accepted. The cost is real: a mistyped column heading
  becomes a new field instead of an error. The system records what you gave it.
- **It does not check your chemistry.** A CAS number is stored, not verified
  against a registry; a molecular formula is not checked against the structure.
  RDKit will reject a structure file it cannot parse, and that is the extent of
  the validation.
- **`/api/*` has no authentication.** Anyone who can reach the port can read
  and write everything. This is a deliberate, documented state for internal
  trusted-network use, not an oversight — and it is the first item on the
  roadmap.
- **There is no audit trail.** Records can be edited and deleted, and nothing
  records who did it or what it was before. Do not use this as evidence of what
  a value was on a given date.
- **SQLite takes one writer at a time.** Correct and fast for this workload,
  which is bulk uploads and many reads. A dozen people uploading simultaneously
  is not the shape it is built for; PostgreSQL is supported for that case.
- **The capacity figures are what has been exercised, not a benchmark.**
  "Optimised for 15,000+" means uploads at that size have been run and behave
  well. It is not a limit, and it is not a guarantee about your hardware.

---

## Why the documentation is so detailed

Because the person who has to redeploy this at 8am is quite likely to be
someone who has never used a container, and quite likely to be its author two
years from now, who has forgotten. Every guide therefore explains each
technical word where it first appears, shows the output a command should
produce, and names the likely mistakes instead of assuming they will not
happen. The glossary carries a standing contract: **a term missing from it is a
documentation bug.**

That is not thoroughness for its own sake. Every bug in the list above was
found because someone followed a written procedure literally and it did not
work. Documentation detailed enough to be followed literally is documentation
detailed enough to be *tested* — and an instruction nobody can test is just a
hope.

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

**Last Updated:** August 25, 2026
