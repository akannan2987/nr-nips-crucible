# Crucible release notes

What changed, when, and why — newest first. Written for the returning
reader, including future-you.

Versions follow **semantic versioning** (`MAJOR.MINOR.PATCH`): a fix bumps
PATCH, a new capability that breaks nothing bumps MINOR, and a change that
would break existing users bumps MAJOR. The number tells you what kind of
change you are getting.

---

## v2.2.0 — 2026-08-25 — "Real data"

The first release to carry a laboratory's own export rather than synthetic
templates. One deployment now holds 49,065 screening records.

**Added**
- **Template-driven ingestion.** A `TemplateSpec` describes how to read a
  laboratory file — how to recognise it, what its columns mean, how each one is
  cleaned — as data rather than code. Adding a template should mean adding a
  spec; if it needs a new parser, the design has failed.
- **A data-driven screening table.** Columns come from the records themselves,
  because files from different laboratories share almost no field names. Raw
  view, column chooser, per-column filters, sorting on every column, and export
  to CSV, TSV, XLSX or JSON — including the untouched source row.
- **Chemical identification**, in two stages: match against compounds already
  registered, then consult PubChem, registering only where a compound's name
  and its CAS number agree. See
  [docs/CHEMICAL-IDENTIFICATION.md](docs/CHEMICAL-IDENTIFICATION.md).
- **A read-only SQL console** (`/api/query` and a Query tab). The database
  connection is opened read-only, so writes are refused by SQLite itself rather
  than by a filter that could be worked around.
- **`verify-deploy.sh`** — sixteen post-deploy checks in one command.
- Maintenance tools for the registry: proposing compounds for review, merging
  entries that describe one substance, and removing entries without orphaning
  the measurements that reference them.

**Changed**
- Bulk inserts commit once rather than once per row. The previous behaviour
  turned a 49,000-row import into 49,000 flushes to disk.
- `index.html` is served `no-cache`. It names a content-hashed bundle, so a
  cached copy pinned browsers to an old build.

**Known limitations (deliberate)**
- **Roughly three quarters of unidentified compounds carry no CAS number in the
  source file.** No identification strategy can work from a free-typed name
  alone; the fix is upstream, in the export.
- Identification is strict by design: a compound is registered only when two
  independent identifiers agree. That leaves real compounds unidentified when
  their name is written in a house style — a trade made knowingly, in favour of
  never attaching a measurement to the wrong substance.
- `DELETE /api/chemicals/:id` still removes an entry without unlinking the rows
  that reference it. Use `scripts/remove_chemicals.py` until the contract can
  change.
- `/api/*` remains unauthenticated, which the query console makes more
  conspicuous.

---

## v2.1.0 — 2026-08-24 — "Written for a newcomer"

A documentation release. No application code changed; the app behaves
exactly as in 2.0.x. What changed is who can follow it.

**Added**
- `docs/GLOSSARY.md` — every technical term used anywhere in this
  repository, defined in plain words with everyday comparisons: containers,
  ports, certificates, migrations, Git, and the lab vocabulary
  (CAS number, SDF, SLIMS, NOAEL). Grouped by subject rather than
  alphabetically. Its stated contract: **a term missing from the glossary is
  a documentation bug.**
- `docs/API-COOKBOOK.md` — copy-paste recipes for the API, each one a
  plain-English question, and every response captured from a real running
  instance rather than invented. Includes a section on the requests that are
  *supposed* to be refused, and why.
- `NEWS.md` — this file.
- A **documentation index** in the README listing every guide in reading
  order, with what each one teaches.

**Changed**
- The install and uninstall guides for both platforms now assume no prior
  knowledge: every technical word is explained where it first appears, every
  command shows its expected output, and likely mistakes get an
  "if instead" branch instead of silence.
- Every document in `docs/` carries the same navigation line back to the
  README, the index, and the glossary.

**Known limitations (deliberate)**
- `/api/*` remains unauthenticated. Suitable for internal, trusted-network
  use only; authentication is the next roadmap item.
- The TLS private key on the production host has not yet been reissued (see
  Security below).

---

## v2.0.3 — 2026-08-17 — HTTPS survives a fresh install

- `container-py.sh` now reads `.env.local`, so a machine can declare its
  standing configuration. With `USE_HTTPS=true` set there, plain `start` and
  `rebuild` come up over HTTPS **even when no container exists yet** — a
  fresh install, or the first start after an uninstall. Previously `rebuild`
  could only preserve the mode of a container that was already running, so a
  reinstalled production host quietly came back on plain HTTP.
- Environment variables still override `.env.local`.
- Documented as a production prerequisite: the server's `.env.local` holds
  `CERT_SOURCE`, optionally `CERT_HOSTNAME`, and `USE_HTTPS=true`. It is
  never committed, and it is the one file a fresh clone cannot restore for
  you.

## v2.0.2 — 2026-08-17 — a complete uninstall

- `uninstall.sh` now removes **all** of the project's cron entries (health
  monitor, certificate-expiry check, nightly backup) and their three log
  files, in every mode. Previously it removed only the monitor entry,
  leaving jobs behind that rewrote their logs after the "uninstall".
- `--full` additionally removes the base images (`python:3.12-slim`,
  `node:18-alpine`); `--partial` keeps them so a reinstall is fast.
- `--help` now describes what each mode actually does. The old
  "partial removes more than its help admits" wart is gone.
- Fixed a latent crash: with `set -euo pipefail`, removing cron entries
  aborted the script if the crontab contained *only* Crucible lines.
- Both uninstall guides rewritten to open with what cannot be recovered,
  before any command.

## v2.0.1 — 2026-08-17 — documentation caught up with the code

- Purged retired Node/Express-era instructions from `DEPLOYMENT.md`:
  commands referencing a script that no longer exists, a named volume that
  was never created, a system-wide systemd unit where the real one is a
  rootless user unit, and a scaling example that would have corrupted
  SQLite by running two instances against one file.
- `API.md`: screening and toxicology request/response examples now match the
  fields the backend actually stores; the two template-upload endpoints are
  documented; the dead Postman link is replaced by a pointer to the live
  interactive docs at `/docs`.
- `docs/database-schema.md`: corrected to the real many-chemicals-per-sample
  model, replaced leftover JavaScript query examples with the current data
  access layer, and aligned the field tables with the routers.
- README gained an end-to-end lifecycle table: every stage from first clone
  to deployment, verification, and uninstall, each linking to the guide that
  owns it.

---

## v2.0.0 — 2026-08-06 — "Sanitised, portable, verified"

The release that made this codebase publishable and reproducible on two
very different machines.

**The application**
- Python/FastAPI backend (migrated from Node/Express, contract preserved),
  React frontend, SQLite by default with optional PostgreSQL, Alembic
  owning the schema inside the container.
- Domain modules: chemicals, samples, screening, toxicology, statistics —
  with RDKit structure handling and Excel/SDF import.
- One container image, run by `container-py.sh` on either podman or docker,
  identically on macOS and RHEL8.

**Security and publishability**
- Comprehensive `.gitignore`; certificates, databases, backups, and
  environment files can no longer be committed.
- All internal hostnames, usernames, and shared-filesystem paths replaced
  with placeholders; real values moved to an untracked `.env.local`.
- The six real laboratory workbooks were replaced with **synthetic**
  templates generated by a tracked script, carrying no real data and no
  document metadata. Every one was verified to import successfully through
  the real endpoints.
- `check-public-safe.sh`: a pre-push gate that refuses the all-clear if
  anything sensitive is tracked.

**Verified**
- Full install, HTTPS, backup/restore, and uninstall walked end to end on
  macOS from a simulated fresh clone; every shipped template uploaded
  through the running container.
- 47 automated tests pass, pinning the API contract.

**Three real bugs found by that verification, and fixed**
- `rebuild` silently downgraded an HTTPS deployment to plain HTTP — the very
  command the update instructions told you to run.
- `status` reported nothing in TLS mode, because it probed `http://`.
- `start` printed the port you asked for rather than the port actually being
  served when reusing an existing container.

**Known limitations (deliberate, documented)**
- No authentication on `/api/*`.
- The production TLS private key is the previously exposed one; a genuine
  reissue is an external action still outstanding.
- Public and private repositories share content but not history, by
  construction — see `docs/GITOPS-WORKFLOW.md`.

---

**See also:** [README](README.md) · [the documentation index](README.md#the-documentation-in-order) · [Glossary](docs/GLOSSARY.md)
