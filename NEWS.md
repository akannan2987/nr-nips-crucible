# Crucible release notes

What changed, when, and why — newest first. Written for the returning
reader, including future-you.

Versions follow **semantic versioning** (`MAJOR.MINOR.PATCH`): a fix bumps
PATCH, a new capability that breaks nothing bumps MINOR, and a change that
would break existing users bumps MAJOR. The number tells you what kind of
change you are getting.

---

## v2.21.0 — 2026-09-22 — "Prod and Beta, said in the page"

Phase **SH-13**, asked for the morning the beta instance went live: the two
tabs looked identical apart from a port number in the corner. Now every
page says which instance it is, in a word and in colour, and the first
change to rebuild the container since the beta instance exists travels the
new route: beta first, production by promotion.

**Added**
- **The label.** An indigo **Prod** pill on a white bar for production, an
  amber **Beta** pill on a pale amber bar for the beta instance, next to
  the page title; the same word in square brackets at the start of the
  browser tab's title; a sentence on hover. "Running on port" stays.
- **`GET /api/instance`**, answering `{"name":"beta","label":"Beta","port":49161,"https":true}`
  (production: `"name":""`, `"label":"Prod"`). Open, no data, and it stays
  open when the login arrives, because the login page has to say where it
  is. `/api/stats` is unchanged.
- **The name travels into the container.** `container-py.sh` passes
  `CRUCIBLE_INSTANCE` and the optional `CRUCIBLE_INSTANCE_LABEL` from
  `.env.local` into both `podman run` commands; the label is derived from
  the same name the scripts use, so the page and the terminal cannot
  disagree. `CRUCIBLE_INSTANCE_LABEL=Production` spells it your way.
- Five tests (150); the tutorial with a test for every route; a figure.

**Recorded**
- The per-instance status/stop/start table and the two-supervisors note
  in [`07-operations.md`](docs/07-operations.md#two-instances-on-one-machine),
  and the rule that a rebuild which changes how the container is created
  is followed by regenerating the service unit, with the four commands.
- "Many testers, one beta" in [`14-beta-instance.md`](docs/14-beta-instance.md#many-testers-one-beta):
  why testers share one instance on purpose, what keeps them apart, and
  when a private sandbox instance is worth its cost.

**Deploy**
- Both instances rebuild, beta first, each after its own backup.
- **Regenerate each service unit after the rebuild** (the container's
  command gained two variables): four commands in the phase tutorial's
  Step 5. Without it, the next boot starts beta without its name.

---

## v2.20.2 — 2026-09-22 — "Beta is live, and the restart message tells the truth"

The beta instance was set up on the server this morning from the RHEL 8
guide's §8, exactly as written: a second folder on `beta`, the same
certificate pair, `crucible-py-beta` on 49161 with the morning's copy of
production's data, its own service unit and monitor line, sixteen deploy
checks passing, production's container not restarted. Two small things
came out of watching the real output.

**Fixed**
- `./container-py.sh restore` (and plain `start`) restarting an *existing*
  HTTPS container printed `Access the application at: http://…`. The
  container was serving HTTPS all along; the message never looked. It now
  reads the scheme from the container, as `status` always did.
- `restore` with no container to restart (after `clean`) started plain
  HTTP even in a folder whose `.env.local` says `USE_HTTPS=true`; it now
  honours the file as `start` does.

**Recorded**
- After a `rebuild`, production's service unit shows *inactive* until the
  next boot, because the rebuild recreates the container outside systemd.
  Enabled and inactive is the expected state; the RHEL 8 guide and the
  phase tutorial now say so.
- The handbook, the specification and the build log record the beta
  instance as live on the server.

---

## v2.20.1 — 2026-09-21 — "The promotion command, corrected"

Documents only. The first promotion after v2.20.0 failed on the Mac with
`error: src refspec beta does not match any`: the command written in the
workflow, the contributing guide, the handbook's cheat sheet, the SH-12
tutorial, the specification's diagram and one figure was
`git push origin beta:master`, and neither the Mac nor the mirror folder
has a *local* branch called `beta` — publishing pushes `develop` *to* the
remote's `beta`, so it exists only on the remote and as the remote-tracking
copy `origin/beta`.

**Fixed**
- The promotion is `git fetch origin && git push origin origin/beta:master`,
  everywhere it is written, with a paragraph in
  [`03-git-workflow.md` Step 11](docs/03-git-workflow.md#step-11---promote-to-production-when-the-testers-agree)
  on why the remote-tracking copy is the right thing to push. A dry run
  from the Mac confirmed it moves `master` to what `beta` has.

**Deliberately not done**
- A local `beta` branch on the authoring machines. It would be one more
  branch to keep level on every publish, for no gain.

---

## v2.20.0 — 2026-09-21 — "A second kitchen: the beta instance"

Phase **SH-12** built, the same day it was planned. A second, complete copy
of the application can now run beside production on one machine — the
**beta instance** the testers use — and none of the scripts run in its
folder can touch production. No application code changed; four shell
scripts and the documents did. Rehearsed end to end on a Mac before the
server was touched: two containers side by side, the one-way data copy, a
beta rebuild that left production's image untouched, sixteen deploy checks
passing on each.

**Added**
- **One file names everything.** `CRUCIBLE_INSTANCE=beta` and
  `CRUCIBLE_PORT=49161` in a folder's untracked `.env.local` make
  `container-py.sh` name its image, container and optional Postgres
  resources `crucible-py-beta`; `help`, `status` and every start say which
  instance they act on; a name with spaces or capitals is refused. Unset,
  nothing changes, on Windows, macOS and RHEL 8 alike.
- **`restore` takes a folder** and uses its newest backup, so refreshing
  beta from production is two commands with no timestamp copied by hand:
  `./container-py.sh backup` in production's folder,
  `./container-py.sh restore ../nr-nips-crucible/backups` in beta's.
- **The setup script** builds and probes the folder's instance and writes a
  monitor cron line naming that folder's container and port.
- **The monitor**, run by hand, reads the folder's `.env.local`; one log
  per instance; the container's name in every line.
- **Two moments in the workflow.** Publish is
  `git push origin develop develop:beta`; the beta instance pulls `beta`.
  Promotion is `git push origin origin/beta:master` (corrected in v2.20.1;
  the first text said `beta:master`), by hand, when the testers agree;
  production pulls `master`. Every machine's commands are in
  [`03-git-workflow.md`](docs/03-git-workflow.md); the `beta` branch means
  the beta instance from now on.
- [`01-setup-rhel8.md` §8](docs/01-setup-rhel8.md#8-a-second-instance-for-user-testing-beta)
  sets the beta instance up on the server; the phase tutorial
  [`phase-sh-12-beta-instance.md`](docs/04-phase-tutorials/phase-sh-12-beta-instance.md)
  has the test for every route; two figures; ADR 0002 accepted.

**Fixed, before it could bite**
- Re-running the setup removed **every** monitor line from the crontab;
  `uninstall.sh` removed **every** crucible cron line and *the* unit; the
  monitor run by hand always probed 49160. With two checkouts on one
  machine each would have hit the other instance. All three are now scoped
  to the folder they run in — matching the folder's path *with what
  follows it*, because beta's path begins with production's (lesson 35).

**Limitations, stated**
- Beta is promoted **as a whole**; there is no promoting one change out of
  three. A change that must not reach production is not published to beta.
- No visible "BETA" ribbon: the header's *Running on port 49161* is the
  cue. An instance label through `/api/stats` is a small later item if the
  testers confuse tabs.
- Beta's data is a copy that ages until refreshed, on request only (B4).
- The server steps are written and rehearsed on a Mac, not yet run on the
  VM: that is the operator's next quarter of an hour.

**Deploy:** production `git pull` only (no application code); then the beta
instance from the RHEL 8 guide's §8. From this version, Flow A publishes to
`develop` and `beta`, and Step 11 promotes.

---

## v2.19.0 — 2026-09-21 — "A place to test, and a way to log in"

No application code. The owner's request of 2026-09-21 — the application
is to go in front of end users for testing — put at the top of the plan.

**Planned, and first**
- **SH-12 · A beta instance for user testing** — a second, complete copy
  of the application on the same server: its own folder on the `beta`
  branch, its own container and image, port 49161, its own database
  refreshed from production's backup on request. Publishing reaches beta;
  production moves only by a deliberate promotion. Specification and
  decisions B1–B6 in [`docs/14-beta-instance.md`](docs/14-beta-instance.md)
  (new); the decision in [ADR 0002](docs/adr/0002-beta-instance.md).
- **SH-3a + SH-3b · The login**, delivered to beta first: the token gate
  and, in full, local accounts with one username and password per tester
  and three roles. Decision A3 revisited and A9, A10 added in
  [`docs/13-authentication.md`](docs/13-authentication.md).

**Recorded**
- The order: SH-12, then the login on beta, then user testing, then
  promotion to production; CR-12 and everything after queue behind them.
  The single sign-on rung still waits on the identity team's registration.

**Deliberately not done**
- Building either phase: each waits on its listed decisions and the
  owner's go.

---

## v2.18.3 — 2026-09-14 — "Dotmatics ID means a DTX identifier"

**Changed**
- The *Dotmatics ID* tag now marks entries that carry a DTX identifier
  (`dtx_id`, the *DTX_ID* column): 9,193 of the 12,539 on the real
  export, not all of them. The first release read the Dotmatics
  registration number instead, which every export row has, so the tag
  told nobody anything. Found by the owner on the day. The rule, the
  chip's explanation and every number in the documents follow.

**Deploy note**
- Backend and client changed: the server **rebuilds**, then hard-reload
  the page.

---

## v2.18.2 — 2026-09-14 — "One answer per click, and the right one"

**Fixed**
- On 12,539 entries the registry page had become unusable: nothing a
  person clicked seemed to work, and the table showed a state no button
  described. Driving the page in a browser showed why. Every click fired
  three requests — the list, the notices and the new summary — and the
  last two recount the whole registry; four quick clicks queued twelve
  requests; answers came back seconds later and out of order, the older
  overwriting the newer. Three changes:
  - the counts are loaded once, when the page opens and after a change,
    not on every click;
  - a click cancels the list request the previous click started, and an
    answer that is no longer the latest is dropped;
  - the three whole-registry answers — notices, summary, columns — are
    cached on the server with one rule: refreshed at once by any write
    through the chemicals API, and within 30 seconds after a write from
    outside it (the import script).
  One test; the suite is 145. Lesson 34.

**Known, not yet fixed**
- Each list request still reads every entry (about 0.7 s alone on
  12,539); that is the design of the server-side sort and filter until
  the schema work of SH-2 promotes the filtered fields into columns.
  Recorded as the trigger for SH-2.

**Deploy note**
- Backend and client changed: the server **rebuilds**. Then **hard-reload
  the page** (Ctrl+F5, or Cmd+Shift+R on a Mac): a tab that stayed open
  keeps the old page code.

---

## v2.18.1 — 2026-09-14 — "An empty table now says why"

**Fixed**
- A text filter typed under a column heading stayed active when the view
  changed, and a filter on a column the new view does not have excluded
  every row. The table then disappeared — and with it the filter boxes, so
  nothing showed what was hiding 12,539 compounds; clicking tags or views
  only narrowed further. Found by the owner an hour after v2.18.0 went
  live. Column filters now belong to the view they were typed in and are
  cleared when the view changes; an empty table lists every filter that is
  narrowing it — search, batch filter, tags, column filters — with a
  **Clear all filters** button and the number of compounds registered.

**Deploy note**
- Client only: the server **rebuilds**. Until then, **Clear sort and
  filters** at the right of the *View:* toolbar, or a reload, brings the
  rows back.

---

## v2.18.0 — 2026-09-14 — "Where every compound came from, at a glance"

Phase CR-11, the first of the owner's two requests of 2026-09-14.
Tutorial: [`docs/04-phase-tutorials/phase-cr-11-counts-and-tags.md`](docs/04-phase-tutorials/phase-cr-11-counts-and-tags.md).

**Added**
- **The counts strip** above the Chemical Registry table — *All compounds
  12,539 · One batch 12,533 · Several batches 6 · Batch rows 12,561* on the
  real export — each a button that filters the table, so the two totals
  people kept meeting side by side now explain themselves.
- **Six source tags**, derived from what each entry records and never
  stored: *Dotmatics ID, Excel upload, SDF upload, CSV upload, JSON
  upload, Manual*. Chips on every row of every view and in the detail;
  tick one or several to filter, with a switch between *all of these*
  and *any of these*. Every import now records the file type it came
  through on the entry (`formats`); the 12,539 existing entries are
  labelled from the source they name.
- `GET /api/chemicals/summary`; `batches`, `tags` and `tags_match` on the
  list, with `tags` on every row; `tags` offered as a column;
  `registry_summary.py` for the terminal. Five tests; the suite is 144.

**Decided, and recorded on the sources page**
- Every Excel file earns *Excel upload*, the Dotmatics export included;
  CSV and JSON files get their own tags; several ticked tags mean all of
  them, with *any* one click away; chips in every view; no *Dotmatics
  export* tag.

**Deliberately not done**
- Tags a person adds by hand; writing `formats` onto entries that predate
  it (they are labelled by inference, correctly); the file's name.

**Deploy note**
- Backend, client and a script changed: the server **rebuilds**, after a
  backup. `POST /api/chemicals` writes exactly the keys it always did —
  *Manual* is inferred, not stored — so the v1 contract is untouched.

---

## v2.17.0 — 2026-09-14 — "Two things the users asked for, written down first"

No application code. The owner's requests of 2026-09-14, specified and
put at the front of the plan, ahead of the screening-data rule.

**Planned**
- **CR-11 · Counts, batch filters and source tags** — a strip above the
  registry table saying how many compounds have one batch, how many have
  several and how many batch rows there are, each a button that filters
  the table; tags derived from the data (*Dotmatics ID*, *Dotmatics
  export*, *SDF upload*, *Excel upload*, *JSON upload*, *API*) shown as
  chips and filterable one at a time or in combination. Specification and
  decisions T1–T3 in [`docs/09-registry-sources.md`](docs/09-registry-sources.md#counting-and-tagging-the-sources).
- **CR-12 · Structures: derive, draw, edit** — one checked structure per
  entry computed from what the sources gave, a picture drawn by the server
  wherever a compound appears, and a structure editor in the browser to
  draw or correct one. Three releases. Specification, the editor
  comparison and decisions S1–S5 in [`docs/09-structures.md`](docs/09-structures.md)
  (new); the *Required now* verdict in the product roadmap.

**Recorded**
- The difference between 12,539 compounds and 12,561 batch rows, with the
  exact split of the six compounds that have several batches, is now in
  the sources page beside the counts the new strip will show.

**Deliberately not done**
- Building either phase: each waits on its listed decisions and the
  owner's go.

---

## v2.16.1 — 2026-09-14 — "A count that cannot see an update"

**Fixed**
- `GET /api/chemicals/columns` kept answering the old columns after the
  export was re-imported on the server: 10 batch columns where 34 had just
  been written. The answer was cached against the number of entries, and a
  re-import that updates every entry in place leaves that number exactly
  where it was. The cache is now also invalidated by any write through the
  chemicals API, and expires after 30 seconds for writes made from outside
  the running process (the import script, a direct Python session). Two
  tests; the suite is 139. Lesson 33.

**Deliberately not done**
- Keying the cache on the newest `updated_at`: correct, but it cost a full
  scan of every document on every call — a second on 12,539 entries —
  which is worse than the bug.

**Deploy note**
- Backend only: the server **rebuilds**. Until then, `./container-py.sh
  restart` after any script import refreshes the columns.

---

## v2.16.0 — 2026-09-09 — "The list on the door, with a pen"

Phase CR-10, pulled ahead of the screening-data build the morning the
banner was first read on production: *until then it runs from the
terminal* is not something the registry's users can act on.
Tutorial: [`docs/04-phase-tutorials/phase-cr-10-attention-page.md`](docs/04-phase-tutorials/phase-cr-10-attention-page.md).

**Added**
- **Needs attention**, a page under Chemical Registry listing everything
  the registry wants a person to look at, with the buttons to act: shared
  identifiers side by side with the other holders (**merge**, or **keep
  both**), batch conflicts with each batch's value (**mark reviewed**),
  pending identifiers (**set it**), doubtful formulas (**mark reviewed**,
  or **delete**, refused while rows are linked). The banner's counts link
  to its sections; the sidebar shows the open count.
- **A review mark** on the entry — `reviewed: {"<what>": "<when>"}` — so a
  decision is data, round-trips through export and import, is visible from
  every route, and can be lifted. A reviewed item stays listed, greyed,
  and stops counting on the banner.
- **One audit module** (`app/audit.py`) and **one merge module**
  (`app/merge.py`) behind the page, four endpoints (`GET /api/chemicals/audit`,
  `POST /api/chemicals/audit/review`, `POST /api/chemicals/merge`,
  `POST /api/chemicals/:id/identifier`) and the two scripts, which are now
  callers: the browser and the terminal cannot disagree about what is
  flagged. The merge script also takes identifiers by hand. Eight tests;
  the suite is 137.

**Changed**
- Shared identifiers are found **from the data** — every CAS number, DTXSID
  and PubChem id held by two or more entries — not from the flags the
  import set, so an entry that arrived by any route is seen and a merged
  entry stops being listed. On the real export that is 221 groups (8 CAS,
  20 DTXSID, 193 PubChem), 419 entries.
- The formula check reads **every name the entry carries** — synonyms,
  other names, the IUPAC and PubChem names — before saying an element is
  unexplained, and no longer reads `tridecafluoro…` as a thirteen-carbon
  chain. On the real export the findings went from 522 to 125 of 6,550
  entries with a formula; every one removed was a name the entry itself
  explained.
- `GET /api/chemicals/notices/summary` gains `formula` and `attention`; every
  count excludes reviewed items. The three original keys keep their
  meaning.

**Deliberately not done**
- Merge from the registry table for a hand-picked pair (CR-8 is now that
  small step); editing a disputed column in place; CSV/XLSX of the list
  (SH-7); a name on the review mark (needs SH-3).

**Deploy note**
- Backend, client and scripts changed: the server **rebuilds**, after a
  backup. The audit takes about 0.8 s on 12,539 entries; the banner and the
  sidebar call it, so the registry page is that much slower to show its
  counts.

---

## v2.15.0 — 2026-09-09 — "A bigger window, and a way to turn the pages"

Phase CR-2 with CR-1, pulled forward the day the real export was loaded.
Tutorial: [`docs/04-phase-tutorials/phase-cr-2-views-sort-filter.md`](docs/04-phase-tutorials/phase-cr-2-views-sort-filter.md).

**Added**
- **Three views on the Chemical Registry table.** *Compact* is the usual
  fourteen columns. *Complete* shows every column the entries actually
  have — 164 on production, 132 of them the files' own headings —
  discovered from the data and chosen from a list that shows each
  column's coverage. *Batches* shows one row per batch of a compound: all
  12,561 rows of the export, the compound's key fields beside the batch's
  34 columns. The view and the chosen columns are remembered per browser.
- **Sorting by any column**, on the server across the whole registry,
  numbers as numbers, entries without a value last in both directions; a
  **filter box under every heading** in the two data-driven views; **rows
  per page** from 20 to 500.
- `view=batches`, `sort`, `order` and `filters` on `GET /api/chemicals`,
  and `GET /api/chemicals/columns`; without the new parameters the list
  answers exactly as before. Five tests; the suite is 129.

**Deliberately not done**
- A separate PubChem view: it is a column choice within Complete.
- Export of the current view (SH-7); filters on the Compact layout.

**Deploy note**
- Backend and client changed: the server **rebuilds**, after a backup.

---

## v2.14.1 — 2026-09-09 — "Nothing a later batch said is lost"

**Fixed**
- When a compound's batch rows disagree on a column, each batch now keeps
  its own value of that column under `batches`; before, only the fact of
  the disagreement was kept and the later batch's value was dropped. Found
  by the owner's question after loading the real export.

**Changed**
- The registry banner no longer sends a browser user to the terminal as
  the only way to act on a flag; it says a browser page is the next
  registry phase. **A rule, recorded in the roadmap:** anything a
  maintenance script can do, the browser must be able to do too. CR-10,
  the attention page, is the first application.

**Recorded**
- The three real files were loaded on production on 2026-09-09 through
  the terminal shortcut: 12,539 entries from the export, 77 structures
  merged, 25 list rows matched; 419 entries share an identifier, 3 have
  batch conflicts; 16 deploy checks pass.

---

## v2.14.0 — 2026-09-09 — "One form per crate type"

Phase CR-9, from the owner's three real files. Tutorial:
[`docs/04-phase-tutorials/phase-cr-9-real-registry-sources.md`](docs/04-phase-tutorials/phase-cr-9-real-registry-sources.md);
the sources, column by column: [`docs/09-registry-sources.md`](docs/09-registry-sources.md).

**Added**
- **The laboratory's registry files as template specs.** The Dotmatics
  export (12,561 rows, 115 columns, one row per batch) becomes one entry
  per registration with the batches folded in and every column kept; the
  registry structure file (77 V3000 molecules, fifty properties each) is
  read by RDKit and merged into the export's entries on DTXSID; the
  limited list registers entries whose identifier is *Coming from
  screening* as pending. Recognised by their columns through the Excel and
  SDF uploads, so every route of CR-3 applies. The decisions — one entry
  per registration, shared identifiers kept and flagged, merge on DTXSID,
  the owner loads the files, this before SD-1 — are recorded on the
  sources page.
- **Flags for a person to judge**, never resolved by the system: shared
  CAS, DTXSID or PubChem identifiers, batches that disagree on a field,
  pending identifiers. A banner on the Chemical Registry page counts them
  (`GET /api/chemicals/notices/summary`), the audit script lists every
  entry, and the deploy check's duplicate test skips flagged pairs.
- Three synthetic templates with the real column and property names;
  seven tests; one figure; five glossary entries.

**Fixed**
- **The structure parser could not read V3000 files.** It stripped a
  blank first line that is the molecule's empty name line, shifting every
  header, so RDKit read the atom counts from the comment line. Every one of
  the 77 real structures is now drawn and analysed.
- **Loading a large file was slow by design**: one commit per entry and a
  rescan of every identifier per insert. Identifiers come from one counter
  and entries are written in batches; the export loads in six seconds on a
  Mac. (Inside the container on macOS it still takes minutes, because the
  mounted disk is slow for a database — a Mac artefact, not a server one.)
- An entry merged from two sources keeps the first source's label; later
  sources are recorded under `merged_from`.

**Recorded, not fixed**
- 419 of the 12,539 entries share an identifier with another entry, and
  three compounds' batches disagree on a field. The audit lists them; the
  decisions are the owner's.
- The template generator's spreadsheet output is not byte-stable; only
  the new template files were committed (SH-11).

**Deploy note**
- Backend, client, scripts and the deploy check changed: the server
  **rebuilds**, after a backup. Nothing is loaded by the deploy; the owner
  loads the three files afterwards, by any route.

---

## v2.13.0 — 2026-09-09 — "One stockroom, three doors"

Phase CR-3. Tutorial:
[`docs/04-phase-tutorials/phase-cr-3-every-way-in.md`](docs/04-phase-tutorials/phase-cr-3-every-way-in.md).

**Added**
- **One door.** `backend/app/imports.py` holds the parsers for every
  chemicals format; the upload page, the API and the terminal all call it,
  so a file behaves identically whichever way it arrives. The spreadsheet
  and structure uploads moved there unchanged — their contract tests did
  not move.
- **JSON, everywhere.** A **JSON Upload** mode on the upload page;
  `POST /api/chemicals/upload/json` for a file and `POST /api/chemicals/import`
  for records in the request body. A record upserts by `chemical_id`, gets
  the next identifier if it has none, keeps every field it carries, and may
  have no CAS number. A synthetic `chemicals_template.json`, one record
  deliberately without a CAS.
- **From the terminal:** `import_file.py chemicals <file>` for any of the
  five formats and `export_chemicals.py -o <file> [--db <url>]`, with
  `./container-py.sh import chemicals <file>` and
  `./container-py.sh export chemicals <file.json>` doing the copying in and
  out through the mounted `data/` folder — no runtime `cp`, so the same on
  podman and Docker, on every platform.
- **The review loop**, decision D10 made real: export the 664 pre-reset
  entries from the backup, review the file, load back what you trust
  ([`09-chemical-identification.md`](docs/09-chemical-identification.md#refilling-the-registry-the-review-loop)).
  The playbook gains *Loading your chemicals list*, the gap the roadmap
  carried since phase 05.
- Six tests; the suite is 117. One figure; three glossary entries.

**Fixed**
- `remove_chemicals.py --all` on an empty registry says *already empty* and
  exits 0, instead of *Nothing matched* and 1.

**Deliberately not done**
- Screening and sample files from the terminal (SD-2, SM-2); attaching rows
  to the refilled entries (SD-1); whole-file validation (SD-4); the review
  itself, which is the owner's.

**Deploy note**
- Backend, client and scripts changed: the server **rebuilds**, after a backup.

---

## v2.12.0 — 2026-09-09 — "Hand the job in at the hatch"

**Added**
- **`./container-py.sh script <name.py> [arguments]`** runs a maintenance
  script inside the container in one line — `./container-py.sh script
  remove_chemicals.py CHEM-000042 --apply` — instead of the runtime's
  `exec` command with the container name and the full path. With no name it
  lists the scripts. Same command on every platform; it finds podman or
  Docker itself. Every document now uses it; the long form still works.
- The CR-6 tutorial's test section spells out the exact `curl` and script
  commands for one, several and every compound, plain and forced.

**Why the scripts cannot simply be run on the server**
- They need the application's Python 3.12 and packages, which exist only
  inside the image; the server's own Python is 3.6 with none of them. On a
  developer's Mac with the test environment they do run directly:
  `cd backend && .venv/bin/python scripts/<name.py> …` against the local
  database.

**Deploy note**
- Only the helper script and documents changed: pull, no rebuild.

---

## v2.11.0 — 2026-09-09 — "The clerk refuses; the archivist empties the folder first"

Phase CR-6, from the owner's rule. Tutorial:
[`docs/04-phase-tutorials/phase-cr-6-delete-unlinks-first.md`](docs/04-phase-tutorials/phase-cr-6-delete-unlinks-first.md).

**Changed — this is a contract change, announced here**
- **Deleting a compound that still has measurements pointing at it is
  refused** — from the browser and from the plain API (`DELETE
  /api/chemicals/{id}`, `POST …/bulk/delete`, `DELETE …/all/clear`): HTTP
  409, `{"error": "N screening rows linked to …; unlink them first …"}`,
  nothing changed. The browser shows *Not deleted — rows are still linked*
  with a button that opens exactly those rows on the Screening Data page.
- **With `force=true`** (a query parameter, or `"force": true` in the bulk
  body) the rows are **unlinked first, then the entry deleted**, always in
  that order, and the answer gains `"unlinked"` counts per module. The
  browser never sends it.
- **With nothing linked, every delete answers exactly as before.** The
  contract tests prove it. One test that had locked the old orphaning
  behaviour was rewritten to assert the refusal.
- The removal script's link logic moved to `backend/app/links.py`, shared
  with the API, so a link is cleared in one way everywhere. The script's
  behaviour is unchanged: report, then on `--apply` unlink, then delete.
- Six new tests; the suite is 111. One figure; two glossary entries.

**Also in this release, documents since v2.10.3**
- The registry's routine tasks on one page, `docs/10-registry-tasks.md`;
  every phase tutorial ends with a *how to test it, by every route* section;
  the README says which page to open first, by reader; production described
  as it is after the reset.

**Deploy note**
- Backend and client changed: the server **rebuilds**, after a backup. On
  production today nothing is linked, so no delete is refused yet; the rule
  becomes visible once the registry is refilled.

---

## v2.10.3 — 2026-09-08 — "An empty registry, on purpose"

**Recorded**
- **R-2 run on production.** After a backup copied outside the repository,
  every one of the 664 registry entries was removed: `Removed 664 entries,
  unlinked 0 rows. 0 chemicals remain.` The 49,065 screening rows are
  untouched, no row is linked, and all 16 deploy checks pass. The registry
  stays empty by design until CR-3 gives it a way to be refilled from a
  curated file and SD-1 attaches rows under the agreed rule
  ([phase R](docs/04-phase-tutorials/phase-r-registry-reset.md)).

**Changed**
- **Removing a compound is documented for every route**, side by side —
  browser, API, terminal — for one, several, every job-created and every
  compound, with the rule *unlink before you delete* and a decision diagram
  ([playbook, Part 6](docs/10-user-playbook.md#removing-a-compound-every-route)).
  The old "never delete through the interface" is gone; the browser is a
  first-class route, with the caveat until CR-6 ships.
- **CR-6 specified from the owner's description**: in the browser a
  compound with linked rows cannot be deleted and the person is told to
  unlink first; the plain API refuses likewise; the API with `force` and
  the terminal script unlink automatically, then delete, always in that
  order ([the specification](docs/09-chemical-identification.md#how-deletion-will-work-after-cr-6--specification)).
  Scheduled right after R-2, one day.

---

## v2.10.2 — 2026-09-08 — "Same name, its own commit; and the decisions"

**Recorded**
- **The registry-first rule is agreed**, D1 to D11 as recommended, and the
  specification now says plainly that a compound may be registered without
  a CAS number (that was always valid; D3 was corrected to match, and D11
  added: a person-registered compound with no CAS attaches rows with the
  same name and no CAS). R-2 now waits only on the owner's go.
- **The authentication ladder is agreed**, A1 to A8 as recommended; the
  decision record is accepted; the token gate (SH-3a) is ready to start.
  The registration request to the identity team is drafted in the plan,
  ready to send, with the licence question in the same message.

**Fixed**
- **The mirror no longer copies the public repository's tags.** The first
  release tag, made on the Mac and fetched into the mirror folder along with
  the commits, took the name before the mirror's own commit could be tagged,
  and was pushed into the private repository pointing at the public commit.
  The mirror's setup now fetches the public remote with tags switched off,
  Step 8b of the workflow checks which commit a tag points at before pushing
  and says what to do when the name is already taken; lesson 32 records it.
  The private tag was deleted and remade on the private commit.

---

## v2.10.1 — 2026-09-08 — "Underline the line and date it"

**The first tagged release**, `v2.10.1`, on both repositories. It marks
everything built since the Python rewrite: the public-repository hygiene,
the platform verification, real laboratory data through a template that is
data, two-stage identification and the registry audit, the numbered
document set and the handbook, reproducible builds and CI, the registry
reset's tools and buttons (R-1 done on production), the plan as six tracks,
the registry-first specification, the module names, and the authentication
plan. Every version before this one is named in this file with its
commit; none was tagged.

**Changed**
- Tagging is a step of the workflow from now on: every version that
  reaches production is tagged in both repositories, with a Release page
  carrying its entry from this file ([`03-git-workflow.md` Step 4c and 8b](docs/03-git-workflow.md#step-4c---tag-the-release), the contributing
  guide's release flow, the cheat sheet).
- **The package decision:** the project's package is the container image,
  published to a registry so machines pull instead of build — recorded as
  *recommended later* with its trigger in the product roadmap and as SH-10
  in the roadmap. Not a Python package: Crucible is run, not imported.
- **The licence is on hold:** the owner is asking the organisation whether
  the public repository may carry an open-source licence and in whose name;
  SH-8 says so.
- Two glossary entries: release tag; package and container registry.

**Deliberately not done**
- No retroactive tags for v2.0.0 to v2.10.0; their commits are named here,
  and a tag that guesses would be worse than none.
- No image published, no registry chosen; the trigger has not fired.

---

## v2.10.0 — 2026-09-08 — "A lock this week, the badge reader when it arrives"

A planning release: no application code changed. The owner asked how a
login could be added, what the ways in are, and how each is built, with
single sign-on as the destination.

**Added**
- **The authentication plan**,
  [`docs/13-authentication.md`](docs/13-authentication.md): what a login is
  (three ideas people run together), where the system stands today, and a
  ladder of three rungs behind one feature flag — a shared token gate in
  days, local accounts with hashed passwords and roles, then single sign-on
  through the organisation's identity provider. Each rung is explained with
  its flow, its pieces, its effort, what it protects against and what it
  does not; seven other ways in are judged with a verdict and a trigger;
  the rules that hold on every rung; how a person and a script log in at
  each; a checklist of what to ask the identity team for **now**, because
  the registration is the long pole; eight decisions for the owner; and the
  three phases SH-3a, SH-3b, SH-3c with what "done" means.
- **Decision records.** A `docs/adr/` folder in the shape my other projects
  use, with [ADR 0001](docs/adr/0001-authentication-ladder.md) recording
  the ladder decision, its alternatives and its consequences.
- The roadmap's shared spine now carries SH-3a/b/c and a small SH-9
  (the rebuild command should wait until the app answers); the product
  roadmap's verdict, the architecture and operations security sections,
  the README index and nine glossary entries point at the plan; one figure.

**Deliberately not done**
- No code, no dependency, no setting. The token gate is two days of work
  once decisions A2, A4 and A7 are agreed.

---

## v2.9.0 — 2026-09-08 — "Signs that say what the department is"

Phase SH-1, the first phase named by its track code. Tutorial:
[`docs/04-phase-tutorials/phase-sh-1-module-names.md`](docs/04-phase-tutorials/phase-sh-1-module-names.md).

**Changed**
- **The three data modules are renamed** in the sidebar, the page headings,
  the dashboard tiles and the interactive architecture page: *Chemicals* →
  **Chemical Registry**, *Samples* → **Sample Management**, *Screening* →
  **Screening Data**. The sidebar entries under them follow (*View Chemical
  Registry*, *Upload Screening Data (ELN)*). Every document that told the
  reader where to click now uses the new names.
- **Nothing else moved.** The web addresses (`/chemicals`, `/samples`,
  `/screening`) and every API path are unchanged, so bookmarks and scripts
  keep working and the API tests did not change. *Query* and *Toxicology*
  keep their labels. The counts on the dashboard's capacity bars still say
  what they count.
- A glossary entry, **Module**, names all five with the labels they had
  before; a figure shows the sidebar before and after.

**Deploy note**
- The web client changed, so the server needs a **rebuild** (with a backup
  first), not just a pull.

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
