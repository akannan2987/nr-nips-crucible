# Contributing to Crucible: Pandora Toolbox Enhancement (v2.0)

Thank you for your interest in contributing to Crucible! This document provides guidelines and instructions for contributing.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Pre-Push Checklist (Before Pushing to Develop)](#pre-push-checklist-before-pushing-to-develop)
- [Promoting Changes Across Branches](#promoting-changes-across-branches)
- [Coding Standards](#coding-standards)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)
- [Testing](#testing)
- [Documentation](#documentation)
- [File Structure](#file-structure)
- [Common Tasks](#common-tasks)
- [Development Cleanup](#development-cleanup)
- [Getting Help](#getting-help)
- [Recognition](#recognition)
- [License](#license)

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inspiring community for all. Please be respectful and constructive in all interactions.

### Our Standards

**Positive behavior includes:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Gracefully accepting constructive criticism
- Focusing on what is best for the community

**Unacceptable behavior includes:**
- Harassment or discriminatory language
- Trolling or inflammatory comments
- Public or private harassment
- Publishing others' private information

---

## Getting Started

### Prerequisites

- Python 3.12+ (FastAPI backend in `backend/`)
- Node.js 18+ and npm 8+ (to build/run the React client)
- Git
- OpenSSL (for certificate verification)
- Podman or Docker (for container testing)
- Basic knowledge of React and FastAPI

### Clone the Public Repo

Crucible uses a **dual-repo model** (see [docs/GITOPS-WORKFLOW.md](docs/GITOPS-WORKFLOW.md) §2.1):
the private `nestle-it` repo is the deploy-only source of truth, and the public
`akannan2987` repo is the sanitized mirror where all changes are authored. The
Mac authoring folder clones **only the public repo** — the private repo is
**never** added as a remote on the Mac, so the folder cannot accidentally push
to it. Content reaches the private repo via the VM mirror folder
(GITOPS-WORKFLOW.md Flow A steps 6-8).

```bash
# Clone the PUBLIC repo — this is the Mac authoring folder
git clone https://github.com/akannan2987/nr-nips-crucible.git
cd nr-nips-crucible
git switch develop

# Confirm: origin must be the PUBLIC repo, and nothing else
git remote -v
```

### Install Dependencies

```bash
# Python backend
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# React client
cd ../client && npm install
```

### Run Development Environment

```bash
# Terminal 1 — FastAPI (auto-reload) on a side port
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

# Terminal 2 — React dev server, proxying /api to the backend above
cd client && VITE_API_PROXY_TARGET=http://localhost:8000 npm run dev
```

---

## Development Workflow

### 1. Create a Branch

```bash
# Update develop (the integration branch)
git switch develop
git pull --ff-only origin develop

# Create feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/bug-description
```

### Branch Naming Convention

- **Features**: `feature/descriptive-name`
- **Bug fixes**: `fix/bug-description`
- **Documentation**: `docs/what-changed`
- **Refactoring**: `refactor/what-refactored`

### 2. Make Changes

- Write clean, readable code
- Follow existing code style
- Add comments for complex logic
- Update documentation if needed

### 3. Test Your Changes

```bash
# Run the backend test suite (contract-parity + unit tests)
cd backend && .venv/bin/pytest

# Run the app locally and smoke-test all modules:
# - Upload chemicals via Excel / SDF
# - Create samples
# - Add screening & toxicology data
# - Bulk operations
# - API endpoints (/api/stats, /api/chemicals, ...)
```

### 4. Commit Changes

```bash
git add .
git commit -m "feat: add bulk export functionality"
```

See [Commit Guidelines](#commit-guidelines) below.

### 5. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

---

## Pre-Push Checklist (Before Pushing to Develop)

> ⚠️ **IMPORTANT**: The `develop` branch is the shared integration branch. Follow this checklist **every time** before pushing to avoid breaking the deployment or leaking sensitive files.

### 🛡️ Step 1: Run the Public-Safety Gate

`origin` is the **public** repo, so every push is a public push.
[docs/GITOPS-WORKFLOW.md](docs/GITOPS-WORKFLOW.md) Golden Rule 4 mandates the
gate script before every one:

```bash
./check-public-safe.sh
# ✅ Must print "✓ SAFE TO PUSH". Do NOT push if it fails —
#    fix what it lists and re-run.
```

The script checks tracked secret paths, the template allowlist, and greps for
internal identifiers — it supersedes the manual checks in Steps 2 and 6 below,
which are kept as optional deep-dives.

### 🔒 Step 2: Verify No Sensitive Files Are Staged (optional deep-dive)

SSL certificates, private keys, and database files must **never** be committed.
`check-public-safe.sh` already covers this; run these by hand if you want to
inspect the staged list yourself.

```bash
# Check what's staged for commit
git status

# Look for ANY of these — they should NOT appear:
#   certs/          *.key    *.crt    *.pem    *.cer
#   data/           .env     .env.local

# Double-check staged files explicitly
git diff --cached --name-only | grep -iE '\.(key|crt|pem|cer|p12|pfx)$|certs/|data/|\.env'
# ✅ This command should return NOTHING. If it returns files, unstage them:
# git reset HEAD <file>
```

### 🧪 Step 3: Test the Application Locally

```bash
# Option A: Quick dev test
cd backend && .venv/bin/pytest        # backend tests must pass
cd ../client && npm run dev
# Open http://localhost:3000 and verify:
#   - Dashboard loads with stats
#   - Chemical upload works
#   - No console errors in browser DevTools

# Option B: Full container test (recommended before pushing)
./container-py.sh build
./container-py.sh start-ssl

# Verify HTTPS endpoint responds
curl --noproxy '*' -k -s https://localhost:49160/api/stats
# ✅ Should return JSON with chemicals/samples/screening/toxicology counts

# Check container logs for errors
podman logs --tail 20 crucible-py
# ✅ Should show uvicorn running with no errors

# Clean up after testing
./container-py.sh stop
```

### 📋 Step 4: Verify the Build Succeeds

```bash
# Build the production frontend
cd client && npm run build
# ✅ Should complete without errors

# Build the container image
./container-py.sh build
# ✅ Should show "Image built successfully"
```

### 🔍 Step 5: Review Your Changes

```bash
# See what files changed
git --no-pager diff --stat

# Review actual code changes (look for debug code, console.logs, etc.)
git --no-pager diff

# If changes are already staged:
git --no-pager diff --cached
```

**Remove before committing:**
- `console.log()` debugging statements
- Hardcoded localhost URLs (use relative paths or environment variables)
- Commented-out code blocks
- Temporary test files

### ✅ Step 6: Verify .gitignore Is Intact (optional deep-dive)

`check-public-safe.sh` (Step 1) also covers this; run manually if in doubt.

```bash
# Ensure .gitignore still protects sensitive files
cat .gitignore | grep -E 'certs|key|crt|pem|data'
# ✅ Should show: certs/, *.key, *.crt, *.pem, data/

# Verify no tracked files should be ignored
git ls-files -i -c --exclude-standard
# ✅ Should return NOTHING
```

### 📝 Step 7: Follow Commit Message Conventions

```bash
# Use conventional commit format
git commit -m "feat(chemicals): add bulk export to CSV"
git commit -m "fix(api): handle duplicate chemical IDs"
git commit -m "docs(readme): update HTTPS setup instructions"

# For multiple changes, use descriptive body:
git commit -m "feat(upload): add SDF file format support

Add parser for SDF chemical structure files.
Includes mol_block extraction and validation.

Closes #42"
```

### 🚀 Step 8: Push to the Public Repo

`origin` on the Mac is the **public** repo. A push promotes `develop`, `beta`,
and `master` together by fast-forward (see
[Promoting Changes Across Branches](#promoting-changes-across-branches)):

```bash
# Re-run the safety gate right before pushing
./check-public-safe.sh                   # must print "✓ SAFE TO PUSH"

# Pull latest changes from develop first (avoid conflicts)
git pull --ff-only origin develop

# If there are conflicts, resolve them and test again (Steps 3-4)

# Push develop and fast-forward beta + master to the same commit
git push origin develop develop:beta develop:master
```

The change is now on the **public** repo only. To carry it into the private
repo, continue with [docs/GITOPS-WORKFLOW.md](docs/GITOPS-WORKFLOW.md)
**Flow A steps 6-11** (mirror public → private on the VM, then deploy).

### 📌 Step 9: Deploy and Verify on the VM

Production pulls from the **private** repo, so a `git pull` there is a no-op
until the mirror steps (GITOPS-WORKFLOW.md Flow A steps 6-9) have copied your
change into it. Once they have, deploy from the production folder exactly as in
Flow A step 10 (folder layout and access: [docs/GITOPS-WORKFLOW.md](docs/GITOPS-WORKFLOW.md) §2.3
and [docs/INSTALL-RHEL8.md](docs/INSTALL-RHEL8.md)):

```bash
# ▶ VM — production folder
./container-py.sh backup                        # always back up first
cp -r data ~/data-backup-$(date +%Y%m%d)
git pull
./container-py.sh rebuild                       # preserves HTTP/HTTPS mode
curl --noproxy '*' -s https://localhost:49160/api/stats

# Check application in browser
# https://<vm-hostname>:49160
```

### 🛑 Quick Reference — DO NOT Push If:

| Check | Command | Expected |
|-------|---------|----------|
| Safety gate passes | `./check-public-safe.sh` | `✓ SAFE TO PUSH` |
| No certs/keys staged | `git diff --cached --name-only \| grep -iE '\.(key\|crt\|pem)'` | Empty output |
| No data files staged | `git diff --cached --name-only \| grep 'data/'` | Empty output |
| Backend tests pass | `cd backend && .venv/bin/pytest` | All green |
| Build succeeds | `cd client && npm run build` | No errors |
| Container starts | `./container-py.sh build && ./container-py.sh start-ssl` | "Image built successfully" |
| API responds | `curl -k -s https://localhost:49160/api/stats` | Valid JSON |
| No debug code | `grep -rn 'console.log' client/src/` | Review & remove |
| .gitignore intact | `cat .gitignore \| grep certs` | `certs/` present |

---

## Promoting Changes Across Branches

`develop`, `beta`, and `master` form a **linear promotion chain**. To move a change up the
chain **while keeping the identical commit SHA on every branch**, promote by **fast-forward** —
never with GitHub's *Merge / Squash / Rebase and merge* buttons for `beta`/`master`, because
each of those mints a **new** SHA and causes `ahead/behind` divergence.

> 💡 A branch keeps the same SHA as another **only** when it is advanced by a fast-forward
> (the ref pointer moves to the exact same commit — no new commit is created). GitHub has no
> "fast-forward merge" button, so this promotion is done from the CLI.

### Prerequisites

- A local `develop` that tracks the remote:
  ```bash
  git fetch origin
  git switch develop            # first time: git switch -c develop origin/develop
  ```
- `beta` and `master` are **fast-forwardable** from `develop` (they carry no commits of their
  own). If they diverge, realign once (see below) and fast-forward promotion works again.
- Direct pushes to `beta`/`master` are allowed — branch protection with *"Require a pull
  request"* will reject the direct fast-forward pushes.

### Standard flow — you are on local `develop`

```bash
# 1. Commit your change on develop — this is the single SHA that lands on all three branches
git add -A
git commit -m "feat(scope): describe the change"

# 2. Push develop AND fast-forward beta + master to that SAME commit (one command)
git push origin develop develop:beta develop:master
```

`develop:beta` / `develop:master` move those remote refs onto develop's exact commit, so
`develop`, `beta`, and `master` all end up on the **identical SHA**.

Explicit, safety-checked variant (`--ff-only` errors instead of creating a new SHA if a branch
cannot be fast-forwarded):

```bash
git push origin develop
git switch beta   && git merge --ff-only develop && git push origin beta
git switch master && git merge --ff-only beta    && git push origin master
git switch develop
```

### Verify all three match

```bash
git fetch origin
for b in develop beta master; do echo "$b -> $(git rev-parse --short origin/$b)"; done
# ✅ all three print the SAME short SHA
```

### Keep your local branches in sync

After promoting, your local `master` (and any local `beta`) is simply **behind** its remote by
the commit(s) you just pushed — a clean **fast-forward**, *not* a divergence. That is the payoff
of promoting by fast-forward instead of a merge/rebase button. Bring them up to date:

```bash
git fetch origin
git branch -f master origin/master      # fast-forward local master without checking it out
# git branch -f beta origin/beta        # repeat if you keep a local beta
```

Or, when the branch is checked out:

```bash
git switch master
git pull --ff-only origin master        # refuses (instead of merging) if it ever diverged
git switch develop
```

> `git branch -f <branch> origin/<branch>` fast-forwards safely **only** when the local branch is
> an **ancestor** of the remote — true right after a clean promotion (`git branch -vv` shows
> `behind N`). If it ever shows `ahead N, behind M`, that is real divergence — use
> *Realigning a diverged branch* below instead.

### Realigning a diverged branch (one-time fix)

If `git branch -vv` shows `ahead N, behind M`, or the branches show different SHAs for
identical content, collapse them onto one commit. This example points `develop` and `beta` at
`master`'s commit (so the protected `master` is not force-pushed):

```bash
git fetch origin
git push --force-with-lease origin origin/master:develop origin/master:beta
git switch master && git reset --hard origin/master     # sync local master
```

> ⚠️ `--force-with-lease` rewrites the shared `develop`/`beta` refs — coordinate with the team,
> and note branch protection may block it. It is content-safe **only** when all branches already
> hold identical content.

### ❌ What breaks SHA parity (avoid)

- GitHub **"Rebase and merge" / "Squash and merge" / "Create a merge commit"** to promote to `beta`/`master`.
- Committing directly on `beta` or `master`.
- `git pull` on a branch that was rebase/squash-merged on the remote — use `git reset --hard origin/<branch>` instead.

> Use PRs (any merge strategy) **only** for `feature/* → develop`. Promote `develop → beta → master` by fast-forward.

---

## Coding Standards

### JavaScript/React

- Use ES6+ syntax
- Prefer `const` over `let`, avoid `var`
- Use arrow functions for callbacks
- Use destructuring where appropriate
- Keep functions small and focused

**Example:**

```javascript
// Good
const getChemicals = async ({ page = 1, limit = 20 }) => {
  const response = await api.get('/chemicals', { params: { page, limit } });
  return response.data;
};

// Avoid
function getChemicals(page, limit) {
  page = page || 1;
  limit = limit || 20;
  var response = api.get('/chemicals', { params: { page: page, limit: limit } });
  return response.data;
}
```

### React Components

- Use functional components with hooks
- Keep components small and reusable
- Use meaningful prop names
- Add PropTypes or TypeScript types

**Example:**

```jsx
// Good
const ChemicalCard = ({ chemical, onDelete }) => {
  const handleDelete = () => onDelete(chemical.id);
  
  return (
    <div className="card">
      <h3>{chemical.name}</h3>
      <button onClick={handleDelete}>Delete</button>
    </div>
  );
};

// Avoid large components with multiple responsibilities
```

### Backend — Python (FastAPI, `backend/`)

- Type hints everywhere; docstrings on public functions
- Pydantic models for request bodies (kept lenient — see `backend/app/schemas.py`)
- **API parity is the contract**: any change to a route must keep the response
  shape identical to `API.md` and pass `backend/tests/` (`.venv/bin/pytest`)
- Keep router files thin; business logic lives in `store.py` or `utils/`
- Prefer clear, idiomatic code over clever one-liners; explain advanced
  constructs (DI, sessions, validators) with a short comment on first use

**Example:**

```python
# Good — thin router, lenient body, {"error": ...} shape on failure
@router.post("", status_code=201)
def add_chemical(body: ChemicalIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    if find_row(db, Chemical, "chemical_id", body.chemical_id):
        raise HTTPException(status_code=400, detail="Chemical ID already exists")
    chemical = {"id": str(uuid.uuid4()), **body.merged_dict(), "created_at": now_iso()}
    insert_doc(db, Chemical, chemical)
    return {"message": "Chemical added successfully", "chemical_id": chemical["chemical_id"]}
```

### CSS/Tailwind

- Use Tailwind utility classes
- Keep custom CSS minimal
- Use responsive design classes
- Follow mobile-first approach

**Example:**

```jsx
// Good
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
  <Card />
</div>

// Avoid inline styles
<div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
```

---

## Commit Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, no logic change)
- **refactor**: Code refactoring
- **perf**: Performance improvements
- **test**: Adding or updating tests
- **chore**: Build process or auxiliary tool changes

### Examples

```bash
# Feature
git commit -m "feat(chemicals): add bulk export to CSV"

# Bug fix
git commit -m "fix(api): handle duplicate chemical IDs properly"

# Documentation
git commit -m "docs(api): add examples for bulk operations"

# Refactoring
git commit -m "refactor(dashboard): extract stats card into component"

# With body
git commit -m "feat(screening): add IC50 calculation

Add automatic IC50 calculation from dose-response curves.
Supports both linear and logarithmic scales.

Closes #123"
```

---

## Pull Request Process

### Before Submitting

- [ ] Code follows project style guidelines
- [ ] All tests pass locally
- [ ] Documentation is updated
- [ ] Commit messages follow conventions
- [ ] No console.log or debugging code
- [ ] No merge conflicts with develop

### PR Title

Follow commit message format:

```
feat(chemicals): add bulk export functionality
fix(api): resolve pagination issue
docs(readme): update installation instructions
```

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring

## Changes Made
- Change 1
- Change 2

## Testing
How were these changes tested?

## Screenshots (if applicable)
Add screenshots for UI changes

## Related Issues
Closes #123
Refs #456
```

### Review Process

1. Automated checks must pass
2. At least one approval from maintainers
3. No unresolved discussions
4. Up-to-date with develop branch

---

## Testing

### Manual Testing Checklist

**Chemicals Module:**
- [ ] Upload Excel file with valid data
- [ ] Upload Excel with invalid data (error handling)
- [ ] Create chemical manually
- [ ] Edit chemical
- [ ] Delete single chemical
- [ ] Bulk select and delete
- [ ] Bulk update fields
- [ ] Search functionality
- [ ] Pagination

**Dashboard:**
- [ ] Statistics display correctly
- [ ] Auto-refresh works (5s interval)
- [ ] Manual refresh button
- [ ] Capacity bars update

**API:**
- [ ] All endpoints return correct status codes
- [ ] Error responses are properly formatted
- [ ] Pagination works correctly
- [ ] Search/filter works

### Testing Commands

```bash
# Run the backend tests
cd backend && .venv/bin/pytest

# Run the dev servers (backend on :8000, client on :3000)
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
cd client && VITE_API_PROXY_TARGET=http://localhost:8000 npm run dev

# Build the client for production
cd client && npm run build

# Test the container build
./container-py.sh build
./container-py.sh start-ssl
./container-py.sh logs

# Test HTTPS endpoint
curl --noproxy '*' -k -s https://localhost:49160/api/stats
```

---

## Documentation

### Code Documentation

- Add JSDoc comments for functions
- Document complex algorithms
- Explain non-obvious code

**Example:**

```javascript
/**
 * Upload chemicals from Excel file
 * @param {File} file - Excel file (.xlsx, .xls, .csv)
 * @returns {Promise<Object>} Upload results with counts and errors
 */
async function uploadChemicalsExcel(file) {
  // Implementation
}
```

### Update Documentation

When making changes, update relevant documentation:

- **README.md**: Overview, installation, quick start
- **API.md**: API endpoint changes
- **DEPLOYMENT.md**: Deployment process changes
- **CONTRIBUTING.md**: Development process changes

---

## File Structure

When adding new files, follow this structure:

```
client/src/
├── components/        # Reusable React components
├── pages/            # Page components
├── services/         # API service functions
├── utils/            # Utility functions
└── styles/           # Global styles

backend/              # Python backend (FastAPI)
├── app/
│   ├── main.py       # App factory, static/SPA serving, error handling
│   ├── routers/      # FastAPI routers (one file per resource)
│   ├── models.py     # SQLAlchemy models (hybrid document pattern)
│   ├── schemas.py    # Pydantic request models
│   ├── store.py      # Data-access helpers
│   ├── compat.py     # JS-semantics helpers (parity)
│   └── utils/        # RDKit SDF, SLIMS Excel, generic Excel parsing
├── scripts/          # healthcheck.py
├── tests/            # Contract-parity + unit tests (pytest)
└── Dockerfile        # python:3.12-slim image (multi-stage)

Root:
├── container-py.sh    # Container management — Python stack (podman/docker)
├── monitor.sh        # Health monitoring script
├── setup-after-clone-py.sh  # Post-clone setup with SSL certs
├── setup-ssl.sh      # SSL certificate setup helper
├── cert-expiry-check.sh  # Certificate expiry check
├── check-public-safe.sh  # Pre-push safety gate (see docs/GITOPS-WORKFLOW.md)
├── uninstall.sh      # Uninstall & cleanup script
├── .gitignore        # Protects certs, data, keys
├── DEPLOYMENT.md     # Deployment runbooks, SSL, systemd
├── MIGRATION.md      # Migration history + learning map
└── docs/             # Documentation (incl. GITOPS-WORKFLOW.md, install/uninstall runbooks)
```

### Security Notes for Contributors

- **Never commit** SSL certificates, private keys, or database files
- The `.gitignore` is configured to exclude `certs/`, `data/`, `*.key`, `*.crt`, `*.pem`
- Always test with `./container-py.sh start-ssl` to verify HTTPS works
- Run `openssl x509/rsa` verification after any certificate changes

---

## Common Tasks

### Adding a New API Endpoint

1. Add a route function to the relevant file in `backend/app/routers/`
2. Keep the router thin — put logic in `store.py` or `utils/`
3. Add an API function in `client/src/services/api.js`
4. Document it in `API.md` and add a test in `backend/tests/`
5. Test with cURL or the OpenAPI docs at `/docs`

### Adding a New UI Component

1. Create component in `client/src/components/`
2. Use Tailwind for styling
3. Add PropTypes or TypeScript
4. Import and use in page component
5. Test in different screen sizes

### Adding a New Page

1. Create page in `client/src/pages/`
2. Add route in `client/src/App.jsx`
3. Add navigation link
4. Update documentation

---

## Development Cleanup

After you're done developing or before switching to a different project, clean up your local environment.

### Quick Cleanup (Recommended)

Use the `uninstall.sh` script:

```bash
# Partial cleanup — removes container, image, cron, logs, keeps source code
./uninstall.sh --partial

# Preview what would be removed first
./uninstall.sh --dry-run
```

### Manual Cleanup

If you prefer to run steps individually:

```bash
# Stop the dev servers (if running): press Ctrl+C in their terminals

# Stop and remove container + image
./container-py.sh clean

# Remove monitoring cron job
crontab -l | grep -v 'monitor.sh' | crontab -
rm -f /tmp/crucible-monitor.log

# Free disk space
rm -rf client/node_modules/ backend/.venv/
rm -rf client/dist/
rm -rf certs/ data/
```

### Full Uninstall

```bash
# Removes everything including data and project directory
./uninstall.sh --full
```

See the [Uninstall and reinstall guide](DEPLOYMENT.md#uninstall-and-reinstall) in the Deployment documentation for complete details.

---

## Getting Help

- **Questions**: Email <maintainer-email>
- **Bugs**: Create an Issue with details
- **Security**: Email <maintainer-email> — do not report security problems in a public Issue

---

## Recognition

Contributors will be recognized in:
- Release notes
- Project README

---

## License

By contributing, you agree that your contributions will be licensed under the
project's license (LICENSE file not yet added — pending owner decision).

---

Thank you for contributing to Crucible! 🎉
