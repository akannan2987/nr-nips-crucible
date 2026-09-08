# Crucible release notes

What changed, when, and why — newest first. Written for the returning
reader, including future-you.

Versions follow **semantic versioning** (`MAJOR.MINOR.PATCH`): a fix bumps
PATCH, a new capability that breaks nothing bumps MINOR, and a change that
would break existing users bumps MAJOR. The number tells you what kind of
change you are getting.

---

## v2.8.0 — 2026-09-08 — "Six tracks, and the rule written down first"

A planning release: no application code changed. Two things the owner asked
for after the first hands-on use of the reset tools, both documents.

**Added**
- **The plan runs as tracks.** [`docs/05-roadmap.md`](docs/05-roadmap.md) is
  reorganised into six tracks — one per module (Chemical Registry, Screening
  Data, Sample Management, Toxicology, Query Console) and a shared spine —
  each with the phases it builds next, what each adds, why, and what it
  waits on; the same shape my other projects use. New phases are named by
  track code and number (`CR-3`); the handbook's build log gained a *Track*
  column and assigns every earlier phase to one. Phases 06 and 07 keep their
  numbers and are also SH-2 and SH-3.
- **The registry-first rule, as a specification.** The owner described the
  new identification logic; it is written down in
  [`docs/09-chemical-identification.md`](docs/09-chemical-identification.md#the-next-rule-registry-first--specification)
  as five rules, what "basic information" means, how the rule is re-run over
  rows already loaded, ten decisions with recommendations, and what "done"
  means — phase SD-1, **specified and awaiting agreement before any code**.
  The rule that runs today is unchanged and still described above it.
- **Planned from the owner's requests**, each in its track with a *waits on*:
  the module renames (SH-1), JSON upload and a terminal import command for
  every module (CR-3, SD-2, SM-2), sort, search and filter per column
  (CR-1), Compact, Complete and PubChem views (CR-2), the incomplete-entries
  notice with a PubChem review step (CR-4), and the unregistered-compounds
  notice and review table (CR-5).
- Two figures: the six tracks, and the registry as a door with two keys.
  Eleven glossary entries (track, phase code, shared spine, registry-first
  rule, specification, unregistered compound, incomplete entry, notice,
  view, sort, filter).

**Recorded**
- R-2 now waits on the specification being agreed as well as the owner's
  go: emptying the registry only makes sense once the rule the refilled
  registry must satisfy is known.

**Deliberately not done**
- No code. The renames, the table features and the rule are planned, not
  built; each ships as its own phase with its own tutorial and release note.

---

## v2.7.0 — 2026-09-08 — "Which rows, which chemical, are you sure"

Three things the first hands-on use of the link buttons asked for.

**Added**
- **Act on every matching row, not one page.** Tick the page, then *Select
  all N matching rows*; link and unlink then apply to every row matching the
  table's current search and filters, across all pages. The endpoints accept
  the same filters as the table (`match`), so one request does what the
  screen shows.
- **A confirmation before a link is written.** After picking a compound, the
  chooser shows its name, CAS number, formula and identifier from the
  registry entry itself, and asks *Yes, link N row(s)*. The registry list is
  unchanged; the details come from the compound's own record.
- **Every unlink says what it touched.** The API answers with rows per
  chemical, most first; the removal script prints the same breakdown in every
  mode, before and after writing, instead of a bare row count.
- **`--unlink-only`** on the removal script: detach the rows of named
  chemicals and keep their entries.
- Five more tests; the suite is 105.

**Recorded**
- R-1 of the registry reset was run on production on 2026-09-08 by the owner,
  from the browser: every screening row unlinked, the 664 registry entries
  kept, a backup from before it held outside the repository.

---

## v2.6.1 — 2026-09-08 — "Verify with the curl you have"

**Fixed**
- `verify-deploy.sh` used a curl option that exists only from curl 7.71; run
  with RHEL 8's system curl it failed every request and reported thirteen
  failures against a working deployment. It had passed before only because
  the shell it ran from had a conda environment with a newer curl. The script
  now retries by hand and runs with the oldest curl in use (lesson 31).

---

## v2.6.0 — 2026-09-08 — "Link and unlink, by hand"

**Added**
- **Buttons on the Screening page** to link a row to a registered chemical
  (a chooser over the registry, filtered as you type), to unlink it, to do
  either for a set of ticked rows, and **Unlink all rows…**, which asks for
  the words to be typed because the only undo is a backup. None of them ever
  deletes a chemical.
- **Two endpoints behind them**: `POST /api/screening/link`
  (`record_ids`, `chemical_id`) and `POST /api/screening/unlink`
  (`record_ids`, or `all: true`). A link is written in both places it lives.
  Four tests; the suite is 100. Documented in the
  [API reference](docs/08-api-reference.md#link-or-unlink-screening-records)
  and the [cookbook](docs/08-api-cookbook.md#linking-rows-to-a-chemical-by-hand).
- A batched `set_links` verb in the data-access layer, so a 43,000-row unlink
  takes seconds, not minutes.

**Known limitations (deliberate)**
- The chooser lists registered chemicals only; a compound that is not in the
  registry is registered in the Chemicals module first, on purpose.
- Tick boxes cover the current page; use a filter and a larger page size to
  act on more rows at once.

---

## v2.5.0 — 2026-09-08 — "Taking every card out of the drawer"

The tools for the registry reset. No data changed in this release; the reset
itself is an operation the owner runs, twice-gated, on production.

**Added**
- **Two reset modes on the removal script**, `backend/scripts/remove_chemicals.py`:
  `--unlink-all` clears the link on every screening, sample and toxicology
  row and keeps every chemical entry; `--all` unlinks everything and then
  removes every chemical. Both write nothing without `--apply`, commit in
  batches of 5,000 rows with a progress line, and clear the link in both
  places it lives — the indexed column and the stored document.
- **The removal script's first tests** (`backend/tests/test_remove_chemicals.py`,
  six cases): the report mode is provably dry; removing one entry unlinks
  only its rows; `--unlink-all` keeps every chemical; `--all` empties the
  registry and rows keep their source names; the job-only selector; nothing
  matching is an error. The suite is 96 tests.
- The procedure, with expected output at each step:
  [phase R](docs/04-phase-tutorials/phase-r-registry-reset.md) and
  [chemical identification → Resetting the registry](docs/09-chemical-identification.md#resetting-the-registry).

**Fixed**
- The removal script would have crashed on the first sample it met: a sample
  has no `chemical_id` column and links through a list inside its document.
  Found by the script's first test; the script now unlinks samples through
  that list (lesson 30).

**Known limitations (deliberate)**
- The reset is not reversible by the script; the backup taken before each
  step is the undo button, and the procedure says where to copy it.
- The new identification logic (R-3) is not designed yet; it is written down
  and agreed before any code.

---

## v2.4.1 — 2026-09-08 — "The gate knows which repository it is in"

A one-step fix to the workflow shipped in v2.4.0, found by its first run in
the private repository.

**Fixed**
- **The safety gate now runs only in the public repository.** The v2.4.0
  workflow assumed the private repository runs no workflows; it does, and
  its first run failed at the gate, which refused the six real workbooks the
  private repository carries on purpose. That is the gate doing its job in
  the wrong place. Every other check — linter, tests on Linux and macOS,
  client build, figure determinism, links — runs in both repositories, so the
  deployed content is tested too; the gate is conditional on the repository
  name. The workflow's comment, the tutorial, the git-workflow guide and the
  contributing guide say so; lesson 29 records the assumption.

---

## v2.4.0 — 2026-09-07 — "The same build, every time"

A build-and-checks release. The application's behaviour is unchanged; what
changed is how surely two builds are the same, and who checks a push.

**Added**
- **`backend/requirements.lock`** — 44 exact versions, resolved inside the
  same `python:3.12-slim` image the Dockerfile builds from, by one command:
  `./container-py.sh lock`. `requirements.txt` keeps the ranges (what the
  project asks for); the lock records what it got. The Dockerfile, the CI
  workflow and the test virtual environment all install from the lock.
  Running the command twice gives the same file byte for byte.
- **A linter with an explicit rule set** (`backend/ruff.toml`): real errors,
  unused names, import order, modern 3.12 syntax, common bugs. 182 findings
  fixed — 180 automatically, two by hand — so `ruff check .` prints
  `All checks passed!`, and the same rules run in CI.
- **Continuous integration on the public repository**
  (`.github/workflows/ci.yml`): on every push, a Linux and a macOS runner
  install from the lock on Python 3.12, run the linter and the 90 tests,
  regenerate the figures and expect no diff, check every documentation link,
  and run the safety gate; a second job builds the client with Node 18 from
  its own lockfile. (v2.4.1: the workflow runs in both repositories; the
  gate only in the public one.)
- **`check-links.py`** — the documentation link checker as a tracked,
  cross-platform script, so CI and a laptop run the same one.
- Tutorial: [phase 05b](docs/04-phase-tutorials/phase-05b-reproducible-builds-and-ci.md).

**Changed**
- RDKit is capped at the newest release with pre-built packages for every
  machine this project uses — the Linux image and VM, the macOS CI runner,
  and the Intel Mac the code is developed on. The comment beside the cap
  says how to check the next release before lifting it.
- The publication gate is now run *after* `git add`, so new files are checked
  before their first commit; the contributing guide and the cheat sheet say so.

**Known limitations (deliberate)**
- No Windows runner until the Windows guide has been walked by a person; a
  runner's failures would be hard to tell from the guide's.
- One lock resolved on Linux serves every platform because every pinned
  package ships wheels for Linux and macOS on Python 3.12 to 3.14. A second
  package with patchy wheel coverage would be the trigger for a
  cross-platform resolver.

---

## v2.3.1 — 2026-09-07 — "Diagrams that render"

A documentation-only follow-up to v2.3.0; the application is unchanged.

**Changed**
- **Every text-art diagram is now a rendered diagram.** The README's
  how-it-works, the architecture document's system view, deployment view and
  three data flows (now sequence diagrams), the schema document's
  entity-relationship diagram, the playbook's four-stage upload flow and the
  identification decision flow are written in the diagram language the
  public host renders natively, so they appear as pictures with real arrows
  rather than as monospaced boxes.
- The operations runbook opens with a picture of the two machines, the ports,
  the cron jobs and the systemd unit.
- **The banner** sits on a deep indigo gradient instead of near-black, with
  the four record symbols on a light card so every element reads.
- The figure index says which diagram form to use when: the diagram language
  for anything that will change with the code, generated SVG for the ideas
  that need drawing.

**Fixed**
- **The example row in the document-is-truth figure named a real laboratory
  workbook.** The figure now uses a synthetic file name. The gate had passed
  because the figures were not yet tracked when it ran: `check-public-safe.sh`
  searched tracked files only. It now searches untracked files as well, so a
  new file is checked before its first commit, not after.

**Known limitations (deliberate)**
- The diagram language renders on the public host and in most editors, not
  in every markdown viewer. The generated SVG figures render everywhere.

---

## v2.3.0 — 2026-09-07 — "One document set, in reading order"

A documentation release; the application is unchanged. The documentation is
reshaped to the structure my other projects use: numbered files whose names
give the reading order, one living handbook as the spine, one tutorial per
build phase, both roadmaps, a third platform guide, and figures for the ideas
newcomers stumble on. Four steps, each its own commit.

**Changed (step 1 — the numbered set, 2026-09-07)**
- Fifteen documents renamed with `git mv`, so their history follows them.
  `DEPLOYMENT.md`, `API.md` and `MIGRATION.md` move from the repository root
  into `docs/`. Full mapping:

  | Was | Now |
  |---|---|
  | `docs/GLOSSARY.md` | `docs/00-glossary.md` |
  | `docs/INSTALL-MACOS.md` · `docs/INSTALL-RHEL8.md` | `docs/01-setup-macos.md` · `docs/01-setup-rhel8.md` |
  | `docs/UNINSTALL-MACOS.md` · `docs/UNINSTALL-RHEL8.md` | `docs/01-uninstall-macos.md` · `docs/01-uninstall-rhel8.md` |
  | `docs/architecture.md` · `docs/database-schema.md` | `docs/02-architecture.md` · `docs/02-database-schema.md` |
  | `docs/GITOPS-WORKFLOW.md` | `docs/03-git-workflow.md` |
  | `DEPLOYMENT.md` | `docs/07-operations.md` |
  | `API.md` · `docs/API-COOKBOOK.md` | `docs/08-api-reference.md` · `docs/08-api-cookbook.md` |
  | `docs/CHEMICAL-IDENTIFICATION.md` · `docs/QUERY-COOKBOOK.md` | `docs/09-chemical-identification.md` · `docs/09-query-cookbook.md` |
  | `docs/PLAYBOOK.md` | `docs/10-user-playbook.md` |
  | `MIGRATION.md` | `docs/12-history.md` |

- Every relative link in the repository rewritten in one scripted pass and
  checked; the wording that named the old files updated too, in docs, scripts,
  code comments and the interactive architecture page.
- A one-line stub stays at each old path for one release, so bookmarks and the
  private mirror's links keep landing somewhere; `DEPLOYMENT.md`'s stub keeps
  the eleven headings other documents used to link to. The stubs go in the
  release after next.
- The README's documentation index is now one table in reading order.

**Added (step 2 — the handbook, 2026-09-07)**
- **`docs/HANDBOOK.md`** — the living spine: a status box (§0) updated with
  every phase commit, the story so far on one page, then Day 0 to today in
  order — understand the domain, set up once, run it, understand the design,
  how a change travels, the build phase by phase (the only build log in the
  repository), operate it, real laboratory data, what comes next, lessons —
  and a one-screen cheat sheet. Each stage says its goal, why it comes where
  it does, numbered reading steps with *why*, and "you are done when".
- **`docs/05-roadmap.md`** — the README roadmap moved out, keeping the
  "waits on" framing, plus the next three phases, the carried items and what
  is deliberately not planned.
- **`docs/11-lessons-learned.md`** — the README's "bumps" moved out, grouped
  by where they were found and numbered.
- Every document's first line now reads `[← README] · [Handbook] · [Glossary]`.
- **The README is a front door again**: what a registry is, the problem, how it
  works, the module table, a quick start, one documentation index with the
  handbook first, the repository map, the honesty notes, licence and author.
  Its container, development, testing, HTTPS, monitoring, troubleshooting,
  security and uninstall sections moved to `docs/07-operations.md`,
  `backend/README.md` and `docs/02-architecture.md`, where the same material
  already had a home; nothing was dropped.

**Added (step 3 — the tutorials, the roadmaps, the third platform, 2026-09-07)**
- **`docs/04-phase-tutorials/`** — one tutorial per build phase, 00 to 05, in
  the shape my other projects use: why the phase existed, what it built, steps
  with *what / how / why / you should see / if instead*, a checkpoint, what it
  deliberately did not do, and the commits that shipped it. Phases 00–04 are
  **reconstructed** from these release notes, the git log and the guides, and
  say *not recorded* where the history is silent. Each opens with a diagram.
- **`docs/06-product-and-technology-roadmap.md`** — from one VM to a product:
  every candidate technology (product surface, identity and access, data
  platform, chemistry and knowledge, language-model and agent components,
  cloud and operations, the regulatory frame, discoverability) answered with
  the same three questions and given a verdict and a trigger. The honest
  count: two *required now* items beyond what exists — authentication and
  name normalisation — and a small CI phase.
- **`docs/01-setup-windows.md`** — the third platform, to the depth of the
  macOS guide: Docker Desktop and Git Bash, or a Linux distribution under
  WSL 2. **Marked untested** until walked on a real PC; every expected output
  says so.
- **`docs/08-api-cookbook.md`** absorbs the API testing guide as one section,
  *Fetching a compound from PubChem and registering it*, rewritten: the text
  that called PubChem linking "proposed" now points at the identification job
  that does it, and carries the caution the job learned about unranked lookups.
  A stub stays at `docs/API-TESTING-GUIDE.md` for one release.
- **`docs/11-lessons-learned.md`** now holds all 27 lessons, grouped and
  numbered; six that were only in private notes are public for the first time.
- Glossary: 32 new entries for the terms these documents introduce.
- `CONTRIBUTING.md`: the stale "update these files" list replaced by the
  documentation norms the handbook enforces.

**Added (step 4 — the figures, 2026-09-07)**
- **`docs/img/`** — eleven figures, all produced by one dependency-free script,
  `docs/img/make_figures.py`, so they are edited as text, carry no metadata and
  diff like code. One symbol per record type (hexagon, vial, plate, dose
  curve) is defined once and used everywhere. Each figure sits under the
  heading that explains its idea: the four record types, the document-is-truth
  rule, the request path, the two repositories and three folders, the loop
  after setup, two-stage identification, the container on three platforms,
  set-up-once, and the timeline. A banner and a mark for the README.
- **`CONTRIBUTING.md`** rewritten to the shape of my other projects: ways to
  contribute, branch model, the day-to-day loop, the push sequence (linked,
  not repeated), release flow, code norms, documentation norms, review norms.
  The old file's pull-request template, manual testing checklist and file tree
  duplicated the playbook and the README and are gone.

**Known limitations (deliberate)**
- The Windows guide has not been walked. Its checklist is the definition of
  done for that platform.
- The stubs at the fifteen old document paths stay for this release and go in
  the next.
- The figures are static. The one interactive figure remains the architecture
  page served at `/architecture`.

---

## v2.2.2 — 2026-09-07 — "One description of the interactive page"

A documentation-only release. Nothing in the application changed.

**Changed**
- **The interactive architecture page now has one home.** The section in
  [docs/02-architecture.md](docs/02-architecture.md#interactive-architecture-page)
  explains what the page is, how to open it on each platform, what each of its
  six tabs shows and where the same facts live in text, how FastAPI serves it,
  and the edit → rebuild → checklist → publish loop for changing it — with two
  diagrams. Two earlier tutorials that described the page's construction step
  by step, `docs/architecture-template-tutorial.md` and
  `docs/architecture-template-tutorial-pandora-example.md`, are removed; their
  reusable parts (the architecture-brief-first method, the stable-`id` rule,
  the `offset-path` pitfall, the browser checklist) moved into that section.
  Neither file was linked from any other document.
- Glossary gains **SVG** and **interactive architecture page**.

**Known limitations (deliberate)**
- The page is a second description of the architecture and can drift from the
  text. The section states the rule — change the text first, then the page —
  but nothing enforces it.

---

## v2.2.1 — 2026-08-31 — "Checking what we registered"

A correctness release. Auditing the chemical registry found that compounds had
been registered carrying other substances' chemistry, and traced it to how a
registry number was looked up.

**Fixed**
- **Looking a compound up by registry number returned the wrong compound.** The
  public database's cross-reference endpoint lists every compound *referencing*
  a number, ordered by internal identifier, and the code took the first. Of 319
  compounds registered from a proposal file, **19 held another substance's
  formula, weight and structure** — while every registry number in the source
  file was correct. The compound that owns a number lists it among its own
  synonyms, so candidates are now checked, and a number no candidate claims
  registers nothing rather than a guess.
- Identification was never affected: it requires a compound's name and its
  registry number to resolve to the same substance, so every one of these was
  rejected. That is what the rule is for.

**Added**
- `scripts/audit_chemicals.py` — flags registered compounds whose formula
  contradicts their own name: a carbon chain the formula cannot hold, or an
  element the name never accounts for. Entries where both names agree exactly
  are exempt, as are cells naming two co-eluting compounds.
- Registry maintenance is documented end to end in
  [docs/CHEMICAL-IDENTIFICATION.md](docs/09-chemical-identification.md): auditing,
  reviewing, removing without orphaning measurements, and recovering afterwards.
- Working files produced while auditing are gitignored. They carry real compound
  names, and the publication gate would not have objected to them.

**Known limitations (deliberate)**
- The audit flags contradictions it can **measure**. A wrong registry number
  pointing at a compound of similar composition leaves nothing to measure —
  three such entries were found only by reading the pairs by hand. A pass is not
  a guarantee.
- 22 compounds were removed and their 232 measurements now show the name the
  source file recorded. They are real substances and can be re-registered, but
  the proposal file should be reviewed first.

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
  [docs/CHEMICAL-IDENTIFICATION.md](docs/09-chemical-identification.md).
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

**See also:** [README](README.md) · [the documentation index](README.md#the-documentation-in-order) · [Glossary](docs/00-glossary.md)
