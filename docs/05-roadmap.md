[← README](../README.md) · [Handbook](HANDBOOK.md) · [Glossary](00-glossary.md)

# Roadmap — what is planned, in order, and what each item waits on

**What this is:** the plan for *this* system, the internal system of record.
The longer view — from here to an industrialised, hosted product, with a
verdict on every candidate technology — is
[`06-product-and-technology-roadmap.md`](06-product-and-technology-roadmap.md).
**How to read it:** each item says what it waits on. That is the honest part:
most of these are not hard to build; they are blocked on a decision or on
each other. An item that waits on nothing is simply not built yet.

*Everyday version:* a kitchen renovation list. The new hob is easy to fit, but
it waits on the electrician; the electrician waits on the wall being opened;
the tiles wait on nothing and could go in tomorrow. Writing down the *waits on*
is what stops you buying tiles for a wall that is about to be knocked down.

---

## Contents

- [The next three phases](#the-next-three-phases)
- [Planned items and what each waits on](#planned-items-and-what-each-waits-on)
- [Carried items, none blocking](#carried-items-none-blocking)
- [Deliberately not planned](#deliberately-not-planned)

---

## The next three phases

The handbook's [build log](HANDBOOK.md#7-the-build-phase-by-phase) has the full
table. In order:

| # | Phase | One line | Waits on |
|---|---|---|---|
| 05 | Documentation consolidation 🔨 | The numbered document set, the handbook, one tutorial per phase, the roadmaps, the lessons file, the Windows guide, figures | nothing — step 3 of 4 done; figures next |
| 06 | Schema normalisation 🔜 | Promote the frequently filtered and sorted fields out of the JSON document into indexed columns, without changing the API | agreeing the list of "hot" fields first, from the client's filters and the query patterns in `store.py` |
| 07 | Authentication 🔜 | A login in front of `/api/*` | a decision between corporate SSO/OIDC and a simpler token scheme, plus a feature flag |

---

## Planned items and what each waits on

- **Authentication (SSO or token).** The largest gap. *Waits on:* a decision
  between corporate SSO/OIDC and a simpler token/header scheme, and a
  feature flag — internal users currently rely on there being no login, and
  turning one on without warning would break them mid-week.
- **Schema normalisation of hot fields.** Filtering and sorting currently reach
  inside the JSON document. *Waits on:* identifying which fields are genuinely
  hot, from the client's filters and the query patterns in `store.py`, and
  agreeing them before any migration is written. Guessing here means a
  migration that backfills the wrong columns. The design rule this must not
  break: [`02-architecture.md` → The one design rule](02-architecture.md#the-one-design-rule-everything-else-follows-from).
- **Role-based access control.** *Waits on:* authentication. Roles are
  meaningless without identity.
- **Audit trail and version history.** *Waits on:* authentication. A log that
  cannot say *who* is a change log, not an audit trail — and the difference is
  the entire point.
- **Rate limiting.** *Waits on:* authentication, for the same reason: without
  identity the only thing to limit by is IP address, which on a corporate
  network is often one proxy.
- **Faceted search and filtering.** *Waits on:* schema normalisation. Counting
  facets across a JSON column means reading every row — measurable now that a
  real dataset is loaded: an unfiltered page is answered from an index in
  milliseconds, while a filtered one reads the JSON of every row.
- **Ingesting the remaining laboratory templates.** The first is done and the
  pattern holds; each further one should be a spec rather than a parser
  ([`09-chemical-identification.md`](09-chemical-identification.md) and
  [playbook Part 2](10-user-playbook.md#part-2--put-a-laboratory-file-in)
  describe the first). *Waits on:* nothing but the files.
- **Compound-name normalisation.** Around 456 compounds carry a valid CAS
  number but a name written in a house style external databases do not
  recognise (`tertiobutyl` where they expect `tert-butyl`). Normalising those,
  or holding them as synonyms, would identify them without weakening the
  two-identifier matching rule. *Waits on:* nothing.
- **Re-registering the 22 removed compounds.** Real substances with correct
  CAS numbers that a buggy lookup mis-identified (see
  [`11-lessons-learned.md`](11-lessons-learned.md)). The lookup is fixed.
  *Waits on:* a row-by-row review of the proposal file before upload —
  skipping that review is what caused the problem.
- **Deleting a chemical through the API should unlink its rows first.** The
  removal script does; the endpoint does not yet. *Waits on:* nothing; it
  changes what the endpoint does, so the change must be announced and the
  response shape kept.
- **A test for the removal script.** It deletes data and has no automated
  test. *Waits on:* nothing.
- **Data export (Excel, CSV, JSON) from every module.** The screening table
  already exports in all four formats; the other modules do not. *Waits on:*
  nothing — the API already returns the data, so this is a convenience layer.
- **Batch upload validation.** Reporting every problem in a file at once
  instead of stopping at the first. *Waits on:* nothing.
- **Continuous integration on the public repository.** `ruff` and `pytest`
  on Linux and macOS runners for every push. The private repository would not
  run it. *Waits on:* nothing; its own small phase.
- **A `LICENSE` file.** *Waits on:* the repository owner's decision. Until one
  exists, "public on GitHub" still legally means all rights reserved.

2D structure rendering already ships — the molecule viewer draws from the MOL
block or SMILES on the chemical detail view. It is listed here only because it
is easy to assume otherwise.

---

## Carried items, none blocking

Things known and accepted, carried from release to release until their
trigger arrives. They are listed so that nobody rediscovers them.

- **The RHEL 8 reboot check (V9)** has not been performed; it waits on a
  maintenance window. After the next reboot, re-run V1 and confirm the systemd
  user unit is active.
- **The RHEL 8 VM cannot run the test suite bare-metal**: its system Python is
  3.6. The container ships its own 3.12. Documented as a named outcome, not a
  fault.
- **2,278 compounds cannot be identified at all** — the source export carries
  no CAS number for them. The only fix is upstream, in the exporting system.
- **The dependency scanner reports vulnerabilities on the private repository**,
  almost all in the Node build tooling. The multi-stage build discards the
  Node stage, so nothing from `node_modules` ships in the image. Real, not
  urgent; one focused session.

---

## Deliberately not planned

- **An analysis platform.** Crucible is a system of record. Statistics beyond
  counts, plotting and modelling belong in the tools that read from its API.
- **A second web server.** The same Python process serves the API and the
  built client; a reverse proxy would add a moving part without a need.
- **Multi-writer scale.** SQLite takes one writer at a time, which is right
  for bulk uploads and many reads. PostgreSQL is supported for the case where
  that stops being true; it is not the default because nothing yet needs it.

**Last Updated:** September 7, 2026
