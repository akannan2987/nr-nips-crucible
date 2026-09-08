[← README](README.md) · [Handbook](docs/HANDBOOK.md) · [Glossary](docs/00-glossary.md)

# Contributing to Crucible

**Who this is for:** anyone changing this repository — including me, next
month. It says how the work is organised, the loop every change goes through,
and the norms that keep the code and the documentation trustworthy. The
sequence of commands for publishing lives in one place,
[`docs/03-git-workflow.md`](docs/03-git-workflow.md), and is linked from here
rather than repeated.
**Prerequisites:** a completed setup guide for your platform
([macOS](docs/01-setup-macos.md) · [RHEL 8](docs/01-setup-rhel8.md) ·
[Windows, untested](docs/01-setup-windows.md)) and the test virtual environment
from its V7 check.

---

## Contents

1. [Ways to contribute](#1-ways-to-contribute)
2. [Branch model](#2-branch-model)
3. [The day-to-day loop](#3-the-day-to-day-loop)
4. [The push sequence](#4-the-push-sequence)
5. [Release flow](#5-release-flow)
6. [Code norms](#6-code-norms)
7. [Documentation norms](#7-documentation-norms)
8. [Review norms](#8-review-norms)

---

## 1. Ways to contribute

- **Follow a guide literally and report where it disagrees with the machine.**
  Every bug in [`docs/11-lessons-learned.md`](docs/11-lessons-learned.md) was
  found that way; it is the most valuable contribution this project gets.
  The Windows guide has never been walked and is waiting for exactly this.
- **Add a laboratory template.** A new export format should be a new
  `TemplateSpec` (data), not a new parser (code); see
  [phase 04](docs/04-phase-tutorials/phase-04-template-ingestion.md). If it
  needs new code, say so — that is a design finding.
- **Fix a lesson that is still open.** The roadmap's
  [planned items](docs/05-roadmap.md#where-each-track-stands-and-its-next-phase)
  list the ones that wait on nothing.
- **Improve a document.** A missing glossary term, a command without its
  expected output, a claim that is no longer true. Small, welcome, quick to
  review.

Be constructive and specific; a report that says *what you typed, what you
saw, what you expected* is worth ten opinions.

---

## 2. Branch model

Three branches, always on the same commit after a publish:

| Branch | Role |
|---|---|
| `develop` | Where every change is authored and committed |
| `beta` | Fast-forwarded to `develop` at each push; a staging pointer |
| `master` | Fast-forwarded to `develop` at each push; **production tracks it** |

They are promoted **by fast-forward only** — one push moves all three onto
the identical commit:

```bash
git push origin develop develop:beta develop:master
```

Never use a merge, squash or rebase button to promote `beta` or `master`:
each mints a new commit and the three branches stop agreeing. A branch that
shows `ahead N, behind M` has diverged; the realignment recipe is in
[`03-git-workflow.md` §3](docs/03-git-workflow.md#3-golden-rules).

**Two repositories.** `origin` on a development machine is the **public**
repository, so every push is a public push. The private repository is filled
by copying content from the public one on the VM, never the reverse:
[`03-git-workflow.md` §1](docs/03-git-workflow.md#1-the-two-repositories).

**Feature branches** are optional for a solo author and useful for anyone
else: `feature/<what>`, `fix/<what>`, `docs/<what>`; merge into `develop` by
pull request, then promote as above.

---

## 3. The day-to-day loop

```bash
# 1. be on develop and current
cd ~/Documents/Work/pandora_toolbox/nr-nips-crucible
git switch develop && git pull --ff-only origin develop

# 2. edit code or docs

# 3. the checks, every time — the same ones CI runs on every push
cd backend && .venv/bin/ruff check . && .venv/bin/pytest -q && cd ..   # expect: All checks passed! · 90 passed
bash -n <any-edited>.sh                        # shell scripts must parse
python3 check-links.py                         # expect: links: clean
git add -A && ./check-public-safe.sh           # expect: ✓ SAFE TO PUSH (after add, so new files are seen)

# 4. if code changed: rebuild and probe, for real
./container-py.sh rebuild
curl --noproxy '*' -sS http://localhost:49160/api/stats

# 5. commit and push (section 4)
```

Three self-checks before the commit:

- **Contract.** If a parity test fails, you have changed the public API.
  Propose the change, show the failing test, and wait for sign-off rather
  than editing the assertion.
- **Schema.** If a model changed, there is an Alembic revision, and
  `cd backend && .venv/bin/alembic check` reports no drift.
- **Data jobs.** If a script writes to the database, every commit point is
  gated on `--apply`, writes are batched with progress output, and the dry
  run has been proven dry. Lessons 17 and 18 are why.
- **Dependencies.** If `backend/requirements.txt` changed, `./container-py.sh lock`
  regenerated `backend/requirements.lock` in the same commit, and
  `./container-py.sh rebuild` was run for real. The lock is what the image,
  CI and the test environment install; a changed wish list with an unchanged
  receipt is a lie.

---

## 4. The push sequence

The full sequence — commit on the Mac, push three branches, mirror into the
private repository on the VM, deploy, confirm the two repositories agree —
is written once, with expected output at every step, in
[`03-git-workflow.md` → Flow A](docs/03-git-workflow.md#4-flow-a---a-change-from-start-to-finish).
The one-screen version is the [handbook's cheat sheet](docs/HANDBOOK.md#a-cheat-sheet).

**Commit messages.** Subject in the imperative, about fifty characters, saying
what the change does (*Give the interactive architecture page one home*, not
*docs update*). Body: one bullet per distinct change, each saying what and
why. No type prefixes, no ticket numbers, no trailers naming any tool.
Examples: `git log --format='%s' -15`.

**Mirror after every public push**, not after every session, so that the two
histories pair one commit to one commit.

---

## 5. Release flow

Versions follow **semantic versioning** and are recorded in
[`NEWS.md`](NEWS.md): a fix bumps PATCH, a new capability that breaks nothing
bumps MINOR, a change that would break existing users bumps MAJOR.

**Every version that reaches production is tagged**, in both repositories,
since v2.10.1. A **tag** is a permanent name for one commit (`v2.10.1`), so
that anyone can ask for exactly that version a year later; a **release** is
the tag plus a page on the repository host carrying the `NEWS.md` entry.
The two repositories have different commit identifiers, so the tag is made
twice, once on each side, on the commits that carry the same content. The
exact commands are Step 4c and Step 8 of
[`docs/03-git-workflow.md`](docs/03-git-workflow.md#step-4c---tag-the-release).
Versions before v2.10.1 have no tags; their commits are named in `NEWS.md`.

A release commit carries, in the same commit:

1. The `NEWS.md` entry: what changed, why, and **what the release deliberately
   did not fix** — limitations get equal billing with features.
2. The handbook's §0 status box, and its §7 build-log row if a phase ended.
3. The phase tutorial, if a phase ended, in the shape of the existing ones.

A phase is one coherent, shippable unit with its own tutorial and its own
commit. The definition of done: someone who was not in the room can follow
the tutorial on a blank machine of the stated platform and reach the stated
checkpoint.

---

## 6. Code norms

- **Follow the existing pattern.** Router → `get_db` → `store.py` → ORM;
  every record stored whole in `doc` with a few indexed columns beside it;
  lenient Pydantic schemas (every field optional, unknown keys preserved).
  The one design rule everything follows from is in
  [`02-architecture.md`](docs/02-architecture.md#the-one-design-rule-everything-else-follows-from);
  nothing breaks it without a written decision there.
- **Python:** type hints, FastAPI dependency injection, SQLAlchemy 2.0 style,
  Pydantic v2. Small focused functions. Clear, slightly verbose code over
  clever abstraction; explain an advanced construct with a comment on first
  use. `pathlib`, never string paths; no OS-specific assumptions.
- **React:** functional components with hooks; Tailwind utilities; every API
  call relative (`/api/...`), never a hostname.
- **Shell:** POSIX-friendly bash; runtime-agnostic (podman or docker
  auto-detected); `bash -n` after every edit. Under `set -e` a function never
  ends with a bare `[ … ] && { … }` (lesson 5). Every running mode survives
  `rebuild` (lesson 1).
- **Verification commands cannot fail silently:** `curl -sS`, never `-s`;
  a `grep` whose empty output would look like success is rewritten.
- **Portability:** no hard-coded hostnames, no ports below 1024; respect
  `CRUCIBLE_PORT`, `DATABASE_URL`, `USE_POSTGRES`, `AUTO_INIT_DB`,
  `USE_HTTPS`; mounts carry `:Z`. The container is the isolation layer on all
  three platforms.
- **Dependencies:** justify, don't accumulate. A new dependency, service or
  roadmap technology enters only with a *Required now* verdict in
  [`06-product-and-technology-roadmap.md`](docs/06-product-and-technology-roadmap.md).
  Ranges go in `requirements.txt`; exact versions live only in the generated
  `requirements.lock`; Python 3.12 is the reference interpreter because it is
  the one in the image.
- **Lint clean.** `ruff check .` in `backend/` prints `All checks passed!`;
  the rules are in `backend/ruff.toml` and are the same ones CI runs.
- **Never in a tracked file:** real laboratory data, certificates, keys,
  `.env*`, database files, backups, internal hostnames, usernames, personal
  paths. `.gitignore` is the lock; `check-public-safe.sh` is the guard at the
  door, and it owns the list of internal identifiers — extend it there.

---

## 7. Documentation norms

The documentation is a numbered set with one living spine,
[`docs/HANDBOOK.md`](docs/HANDBOOK.md). The rules that keep it true are in its
last section; the ones every change must respect:

- **One home per topic.** A command, table or explanation that appears in two
  files is a bug. Link to the home with one sentence of context instead.
- **The handbook changes in the same commit** as the work it describes.
- **Every phase has a tutorial** in `docs/04-phase-tutorials/`, in the shape
  the existing ones use: why it exists, what it built, numbered steps with
  *what / how / why / you should see / if instead*, a checkpoint, what it
  deliberately did not do, and the publish block.
- **Every jargon term is explained where it first appears** — bold term, a
  dash, an everyday comparison — and added to
  [`docs/00-glossary.md`](docs/00-glossary.md). A missing term is a bug.
- **Show the output.** Every command that matters has *You should see* and,
  where it can plausibly fail, *If instead* with the named fix.
- **Figures are generated, never pasted.** Every image under `docs/img/` comes
  from [`docs/img/make_figures.py`](docs/img/make_figures.py); edit the script
  and rerun it. One symbol per record type, defined once there, means the same
  thing in every document.
- **Voice:** first person, confident, honest about done versus in progress.
  No marketing words, no closing summaries that restate the section.
- **Nothing in a tracked file or a commit message** names a tool, vendor or
  assistant, and nothing implies the project exists for anything but its
  stated purpose. The safety gate checks paths and identifiers; this rule is
  checked by reading.
- **Diff-anchored writing is for `NEWS.md` only.** Every other document
  describes the system as it is.

---

## 8. Review norms

- **CI must be green** on the public repository before a push is mirrored,
  and it runs again on the private one afterwards: the linter, the tests on
  Linux and macOS, the client build, the figure determinism check, the link
  check, and — public side only — the safety gate. A red run is read before
  anything else is done.
- **Pull requests are for `feature/* → develop` only.** `develop → beta →
  master` is promoted by fast-forward from the command line, never by a
  button.
- **A review reads the tutorial first.** If a change ships without the
  tutorial, handbook row and release note it needs, the review asks for them
  before it reads the code.
- **Look for the failure shape.** Almost every recorded bug is *an operation
  reporting one thing while doing another*: a dry run that writes, a status
  that cannot fail, a check that cannot run and prints what a pass looks like.
  Ask of every new check: *how would this look if the thing it checks were
  absent?*
- **Do not merge a contract change without the failing test in the
  description**, and do not merge a schema change without `alembic check`
  output.
- **Test-database output is not production output.** A number quoted in a
  document says which instance it came from.

**Last Updated:** September 7, 2026
