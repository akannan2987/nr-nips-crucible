# Crucible: Pandora Toolbox Enhancement (v2.0)

Chemical and Sample Management System - MVP

A comprehensive web application for managing chemical compounds, samples, screening data, and toxicology information with an integrated Electronic Lab Notebook (ELN). Deployed with **HTTPS/TLS** encryption using official Nestlé SSL certificates.

## 🚀 Quick Start

### Setup after clone

Clone from the repository that matches your platform:

```bash
# macOS (development) — PUBLIC repo, no authentication needed:
git clone https://github.com/akannan2987/nr-nips-crucible.git

# RHEL8 VM (production) — PRIVATE Nestlé repo (PAT over HTTPS, or SSH key):
git clone https://github.com/nestle-it/nr-nips-crucible.git

cd nr-nips-crucible

# One command does everything (certs if available, build, start,
# verify, optional monitoring cron) — on macOS AND the RHEL8 VM:
./setup-after-clone-py.sh

# Or the individual steps:
./container-py.sh build      # build (auto-detects podman or docker)
./container-py.sh start      # run on http://localhost:49160
```

> **Two repositories, one codebase:** macOS development tracks the public
> mirror `akannan2987/nr-nips-crucible`; the RHEL8 VM deploys from the private
> `nestle-it/nr-nips-crucible` (SSH form:
> `git@github.com:nestle-it/nr-nips-crucible.git`). Certificates, databases,
> and internal data are excluded from both via `.gitignore`.
> How changes move between them — and the `./check-public-safe.sh` gate to run
> before every public push — is documented in
> **[docs/GITOPS-WORKFLOW.md](docs/GITOPS-WORKFLOW.md)**.

The setup script will:
1. Copy SSL certificates from the Nestlé certificate store (when available)
2. Verify certificate/key pair integrity
3. Build the container image
4. Start the application (HTTPS when certs exist, else HTTP)
5. Verify the API answers
6. Optionally configure health monitoring

Full runbooks (macOS Docker/Podman, RHEL8 Podman): **[DEPLOYMENT.md](DEPLOYMENT.md)**

Access the application:
- **Production (HTTPS):** `https://<vm-hostname>:49160`
- **Development:** `http://localhost:3000` (frontend dev server) + `http://localhost:49160` (API)

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
| 6 | **Mirror public → private** | ▶ VM `~/crucible-mirror` | `git fetch public && git checkout public/develop -- .` → commit → push | [GitOps Flow A steps 6–9](docs/GITOPS-WORKFLOW.md#4-flow-a---a-change-from-start-to-finish) |
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

### Prerequisites

- Podman or Docker (for containerized deployment — covers everything else)
- For bare-metal development only:
  - Python 3.12+ (backend)
  - Node.js 18+ and npm 8+ (to build the React client)
- OpenSSL (for certificate verification)
- Access to Nestlé certificate store (for HTTPS in production)

### Install Dependencies (bare-metal development)

```bash
# From the project root directory:

# Python backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# React client (for the dev server / production build)
cd ../client
npm install
```

---

## 🛠️ Development

### Local Development (Hot Reload)

```bash
# Terminal 1 — FastAPI with auto-reload on a side port
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

# Terminal 2 — React dev server, proxying /api to the backend above
cd client && VITE_API_PROXY_TARGET=http://localhost:8000 npm run dev
```

This starts:
- Frontend dev server: `http://localhost:3000`
- Backend API server: `http://localhost:8000`

### Build for Production

```bash
# Build the React frontend (output: client/dist)
cd client && npm run build

# Start the production server on port 49160 (serves API + built client)
cd ../backend && PORT=49160 .venv/bin/python -m app.main
```

Production app runs at: `http://localhost:49160`

---

## 🧪 Testing

### Python backend

```bash
cd backend
.venv/bin/pytest                     # contract-parity tests + unit tests
```

The suite locks the **v1 API contract** (response keys, messages, status
codes) plus SDF/Excel parsing behaviour, so the backend can be refactored
safely. See [backend/README.md](backend/README.md) for details.

Tests cover:
- **API parity**: Statistics, Chemicals CRUD + duplicate rejection, Samples CRUD, Screening (chemical linkage + filter), Toxicology, capacity limits, pagination quirks
- **SDF parsing**: V2000/V3000 parsing, V3000 line continuations, S-Groups (SRU/MUL/COP/MIX/SUP), polymer & mixture detection, stereochemistry, formal charges, catch-all metadata, Tier 1 named fields (`dtxsid`, `preferred_name`, `monoisotopic_mass`, `ms_ready_smiles`, `synonyms`)
- **Samples parsing**: SLIMS 3-row header detection, field renames (`Barcode`→`sample_id`, etc.), European date normalisation (`DD/MM/YYYY`→ISO), metadata preservation, `chemical_ids` linkage defaults
- **Static serving**: architecture page + SPA fallback

---

## 🐳 Container Deployment

Both scripts auto-detect **podman or docker** (override with
`CONTAINER_RUNTIME=docker|podman`) and check the podman VM state on macOS.
Port override: `CRUCIBLE_PORT=<n>` (a generic `PORT` env var is ignored to
avoid clashes on shared machines).

### Deploy on the RHEL8 VM (production) — field-tested sequence

```bash
# On the VM (full runbook with troubleshooting: DEPLOYMENT.md)
cd /path/to/crucible
cp -r data ~/data-backup-$(date +%Y%m%d)  # back up production data
git pull
./container-py.sh rebuild                 # rebuild + restart on 0.0.0.0:49160
                                          # (preserves HTTP/HTTPS mode)
curl --noproxy '*' -sk https://localhost:49160/api/stats   # or http:// on an HTTP deploy
# then: systemd auto-start and cutover checklist (DEPLOYMENT.md)
```

App URL: `https://<vm-hostname>:49160` (or `http://` on an HTTP deploy). Firewall notes
(firewalld vs plain iptables vs none): DEPLOYMENT.md.

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

Backs up `data/crucible.db` using SQLite's online-backup API (never a torn
copy). Details, VM cron schedule, and machine-to-machine transfer:
**[DEPLOYMENT.md](DEPLOYMENT.md)**.

📚 **[View Full Deployment Guide →](DEPLOYMENT.md)**

---

## 🔒 HTTPS / SSL Configuration

The app serves **HTTPS with official Nestlé SSL certificates** from the
`certs/` directory via `./container-py.sh start-ssl` (uvicorn TLS — see
[DEPLOYMENT.md](DEPLOYMENT.md)). Note: HTTPS is transport encryption; user
*authentication* (SSO login) is still a planned enhancement.

### Certificate Source

Certificates are sourced from the corporate certificate store on the VM.
The store's actual path is site-specific and is **not** committed — configure
it once on the VM in an untracked `.env.local` file next to
`setup-after-clone-py.sh` (see [docs/INSTALL-RHEL8.md](docs/INSTALL-RHEL8.md#3-https-with-corporate-certificates)):

```
CERT_SOURCE=<cert-store-path>
CERT_HOSTNAME=<vm-hostname>   # optional; defaults to `hostname -f`
```

### Certificate Files (in `certs/` directory - NOT committed to git)

| File | Source | Purpose |
|------|--------|---------|
| `server.crt` | `<vm-hostname>.cer` | Server certificate |
| `server.key` | `<vm-hostname>.key` | Private key |
| `ca.crt` | `Nestle_Root_CA.cer` | CA root certificate |

### Verify Certificate/Key Pair

```bash
# Both commands must output the same MD5 hash
openssl x509 -noout -modulus -in certs/server.crt | openssl md5
openssl rsa -noout -modulus -in certs/server.key | openssl md5
```

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

📚 **[View Full API Documentation →](API.md)**

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

Automated health monitoring checks the application every 5 minutes and auto-restarts if unresponsive.

### Setup Monitoring

```bash
# Supported install path — writes the correct cron line for the platform
# (on RHEL8 the line REQUIRES a USER=…/XDG_RUNTIME_DIR=… prefix for rootless
# podman; see docs/INSTALL-RHEL8.md §4 — don't hand-write a simplified line):
SETUP_MONITOR=y ./setup-after-clone-py.sh

# Or run a health check manually
./monitor.sh
```

### Monitor Logs

```bash
# View monitoring log
tail -f /tmp/crucible-monitor.log

# Check cron job
crontab -l | grep monitor.sh
```

### Certificate Expiry

For HTTPS deployments, check how long the TLS certificate stays valid
(cron-friendly; warns at 30 days by default):

```bash
./cert-expiry-check.sh                 # check certs/server.crt
WARN_DAYS=60 ./cert-expiry-check.sh    # warn earlier
```

Weekly cron example and details: **[DEPLOYMENT.md → Health monitoring](DEPLOYMENT.md#health-monitoring)**.

### Stability Features

- **Container health check**: Docker/Podman HEALTHCHECK against `/api/stats` every 30 seconds, with auto-restart via `monitor.sh` cron
- **Schema management**: in the container, **Alembic** brings the schema to head on startup (`AUTO_INIT_DB=false`); local dev and tests create tables automatically (`Base.metadata.create_all`)
- **Graceful errors**: API returns `{"error": ...}` JSON; no sensitive data in error responses

---

## 🔧 Troubleshooting

### Port Already in Use

```bash
# Check what's using port 49160
lsof -i :49160

# Kill the process
fuser -k 49160/tcp
```

### Container Issues

```bash
# View logs
./container-py.sh logs

# Restart container with HTTPS
./container-py.sh stop && ./container-py.sh start-ssl
```

### SSL Certificate Mismatch

```bash
# Verify certificate and key match
CERT_HASH=$(openssl x509 -noout -modulus -in certs/server.crt | openssl md5)
KEY_HASH=$(openssl rsa -noout -modulus -in certs/server.key | openssl md5)

echo "Cert: $CERT_HASH"
echo "Key:  $KEY_HASH"

# If they don't match, re-run setup:
./setup-after-clone-py.sh
```

### Application Unreachable

```bash
# Run health check
./monitor.sh

# Check container status
./container-py.sh status

# Full restart with HTTPS
./container-py.sh stop
./container-py.sh start-ssl
```

### Database Reset

```bash
# Delete the SQLite file — re-created empty on next start
rm -f data/crucible.db
```

---

## 🧹 Uninstall & Reinstall

A dedicated `uninstall.sh` script handles all cleanup operations (podman or
docker, macOS or RHEL8):

```bash
# Interactive mode — choose what to remove step by step
./uninstall.sh

# Partial cleanup — remove runtime artifacts, keep source & data
./uninstall.sh --partial

# Full uninstall — remove everything including data & source code
./uninstall.sh --full

# Preview what would be removed (no changes made)
./uninstall.sh --dry-run
```

The script removes: the `crucible-py` container and image, the monitoring cron
job and logs, SSL certs, application data (`crucible.db`, with a final safety
backup to `~/crucible-backups`), local `backups/`, `client/node_modules` +
`client/dist`, `backend/.venv` + Python caches, systemd services (rootless
user unit and Quadlet), and the project directory.

**To reinstall / redeploy** (same command on macOS and the RHEL8 VM):

```bash
# from a fresh clone, or an existing checkout after `git pull`
./setup-after-clone-py.sh

# restore data if you kept a backup:
./container-py.sh restore ~/crucible-backups/crucible-final-<stamp>.db
```

📚 Platform guides: **[macOS Uninstall →](docs/UNINSTALL-MACOS.md)** ·
**[RHEL8 Uninstall →](docs/UNINSTALL-RHEL8.md)** ·
**[Full uninstall + reinstall runbook →](DEPLOYMENT.md#uninstall-and-reinstall)**

---

## 🔐 Security

### What's Protected

- **HTTPS/TLS**: All production traffic encrypted with official Nestlé certificates
- **Git Safety**: SSL certificates, private keys, and database files excluded via `.gitignore`
- **Pre-push gate**: `./check-public-safe.sh` must print `✓ SAFE TO PUSH` before every
  public push — it verifies no secret paths are tracked, only sanitized templates ship,
  and no internal identifiers appear in tracked content
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

## 📝 Documentation

| Document | Description |
|----------|-------------|
| **[GitOps Workflow](docs/GITOPS-WORKFLOW.md)** | How changes flow between the public and private repos, and the pre-push safety gate |
| **[macOS Install & Run](docs/INSTALL-MACOS.md)** | Install, run (HTTP/HTTPS), and verify on macOS — uses the **public** repo |
| **[macOS Uninstall](docs/UNINSTALL-MACOS.md)** | Clean removal from macOS, including manual cleanup and verification |
| **[RHEL8 Install & Run](docs/INSTALL-RHEL8.md)** | Install, run (HTTPS), auto-start, and verify on the RHEL8 VM — uses the **private** repo |
| **[RHEL8 Uninstall](docs/UNINSTALL-RHEL8.md)** | Clean removal from the RHEL8 VM (systemd, firewall, cron, Postgres artifacts) |
| **[Deployment Guide](DEPLOYMENT.md)** | Deep reference: runbooks (macOS Docker/Podman, RHEL8 Podman), SSL setup, monitoring, systemd auto-start |
| **[Backend README](backend/README.md)** | Python backend: quickstart, tests, env vars, vite proxy |
| **[API Documentation](API.md)** | Complete REST API reference |
| **[API Testing Guide](docs/API-TESTING-GUIDE.md)** | Worked `curl` examples for exercising the API |
| **[MIGRATION.md](MIGRATION.md)** | Brief history of the Node→Python migration + learning map |
| **[Architecture](docs/architecture.md)** | System architecture (Python/FastAPI) |
| **[Database Schema](docs/database-schema.md)** | Hybrid document pattern (SQLite + optional PostgreSQL/Alembic) |
| **[Contributing Guidelines](CONTRIBUTING.md)** | How to contribute |

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

**NIHS Team** - Nestle Institute of Health Sciences

For support, contact: `<maintainer-email>`

---

**Last Updated:** August 7, 2026
