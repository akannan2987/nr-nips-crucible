[← README](../README.md) · [All docs in order](../README.md#the-documentation-in-order)

# Glossary — every term in this project, in plain words

No prior knowledge assumed. If a word appears in any document, script, or
code comment in this repository and isn't explained here (and isn't
obvious), that's a **documentation bug** — please say so, or add it.

Terms are grouped by the world they come from, not alphabetically, because
words are easier to learn in the company they keep. Use your browser's
find (`Ctrl+F` / `Cmd+F`) to jump to one.

- [The container words](#the-container-words) — containers, podman, ports, SELinux, systemd, cron
- [The web and API words](#the-web-and-api-words) — HTTP, HTTPS, certificates, APIs, JSON, curl
- [The data words](#the-data-words) — databases, SQLite, schemas, migrations, backups
- [The Git words](#the-git-words) — repositories, commits, branches, remotes
- [The lab and chemistry words](#the-lab-and-chemistry-words) — assays, CAS numbers, SDF, SLIMS
- [The Python and testing words](#the-python-and-testing-words) — virtual environments, pytest
- [The project words](#the-project-words) — how *this* project is put together

---

## The container words

> ### Why this project has no virtual environment
>
> If you have met Python before, you have probably been told that every
> project needs its own **virtual environment** so its packages don't collide
> with another project's. That advice is right — for software that runs
> *directly on your computer*. Crucible doesn't.
>
> Everything the application needs lives inside the **container image**:
> its own copy of Python, its own FastAPI, its own RDKit, even its own
> miniature Linux operating system. None of it is installed on your Mac or on
> the server. You can prove this on any machine that runs Crucible:
>
> ```bash
> python3 -c "import fastapi"   # ModuleNotFoundError — not on your computer
> ```
>
> …and yet the app runs perfectly, because that library sits inside the image
> at `/usr/local/lib/python3.12/site-packages/`. That *is* a system directory
> — but it belongs to the **container's** filesystem, a disposable sandbox,
> not to your machine. Delete the image and every trace goes with it.
>
> So a container is not a weaker form of isolation than a virtual
> environment. It is a stronger one:
>
> | Isolates… | Virtual environment | Container |
> |---|---|---|
> | Python packages | yes | yes |
> | System libraries (the C code RDKit needs) | no — shared with your machine | yes |
> | The operating system | no | yes |
> | The filesystem | no — sees your whole disk | yes — sees only what you mount |
> | Networking and processes | no | yes |
> | Behaves identically on macOS and RHEL8 | no | yes — the whole point |
>
> Adding a virtual environment *inside* a container would be pointless: the
> container already holds exactly one application, with nothing to collide
> with.
>
> **The one exception.** `backend/.venv` does exist, and it is a real virtual
> environment — but only for running the app *outside* a container: the test
> suite (`pytest`) and hot-reload development. It is optional, it lives inside
> the project folder rather than system-wide, and the app never uses it. An
> uninstall removes it; a reinstall does **not** bring it back. Recreate it
> only when you want to run tests:
>
> ```bash
> cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
> ```
>
> **What about Node?** The React interface is compiled by Node during the
> image build, and then that entire build stage is thrown away — the finished
> image contains no Node at all, only the compiled result. `client/node_modules`
> appears on your machine only if you install it deliberately for frontend
> development.

**Container** — a sealed lunchbox for a program. Inside it sits the app
*and* everything the app needs to run: the right Python version, the right
libraries, the right folder layout. Because the lunchbox carries its own
supplies, the app behaves identically on your Mac and on the company
server — even though those two machines are otherwise nothing alike. This
is the single idea that makes "it works on my machine" stop being an
excuse.

**Image** — the recipe and the shopping list for a container, frozen into a
file. You *build* an image once; you then *run* it to get a container. One
image can start many containers, the way one recipe can cook many dinners.
Crucible's image is named `crucible-py:latest`.

**Container vs. image** — the image is the cake recipe; the container is a
cake baked from it. Deleting a cake doesn't delete the recipe.

**Podman / Docker** — two programs that do the same job: build images and
run containers. They understand the same commands, so this project's
scripts work with either and pick whichever you have installed (Podman
first if both). **Container runtime** is the umbrella term for "whichever
one of these you're using".

**Podman machine** — a wrinkle that only affects Macs. Containers are a
Linux invention, so on macOS Podman quietly runs a small hidden Linux
computer inside your Mac and puts the containers in there. You have to
switch it on (`podman machine start`) before anything works, and it does
*not* start by itself when you log in. On the Linux server there is no such
layer — containers run directly.

**Rootless** — running containers as your ordinary user account instead of
as the machine's administrator. Like cooking in your own kitchen rather
than demanding the keys to the restaurant: safer, and if you set something
on fire only your own dinner is affected. The RHEL8 server runs Crucible
rootless, which is why a few extra steps (lingering, subuid) exist.

**Root / administrator** — the all-powerful account on a Unix machine.
`sudo` means "do this next command as root". Needed for installing system
packages and opening firewall ports; deliberately *not* needed to run
Crucible.

**subuid / subgid** — a range of pretend user-ID numbers the system lends
you so that a rootless container can have its own internal "root" user
without that being the real root of your machine. A stage name: inside the
container the program thinks it's the boss; outside, it's still just you.
Normally set up automatically when Podman is installed.

**Port** — a numbered door on a computer. One machine runs many network
programs at once, and ports keep them apart: door 443 for secure websites,
door 22 for SSH, and **door 49160 for Crucible**. When you visit
`localhost:49160` you're knocking on that specific door.

**localhost / 127.0.0.1** — "this very machine". A request to localhost
never leaves the computer it started on. Useful mental check: if a URL says
localhost, no one else in the world can reach it.

**0.0.0.0** — "every door on every network card" — i.e. accept visitors
from other machines too. The RHEL8 server publishes on `0.0.0.0` so
colleagues can reach the app; your Mac publishes on `127.0.0.1` so nothing
leaks onto the office network.

**Bind mount** — a window cut between a folder on your real computer and a
folder inside the container. Crucible mounts `./data` this way, which is
why your database survives when the container is deleted and rebuilt: the
file was never *inside* the lunchbox, only visible through the window.

**Volume** — a storage area that the container runtime manages for you,
rather than a folder you can see. Crucible only uses one, `crucible-pgdata`,
and only if you switch on the optional PostgreSQL database.

**SELinux** — a security guard built into Red Hat Linux that checks not
just *who* you are but *what* each file is labelled for. By default it
refuses to let a container read your folders, which looks like a baffling
"Permission denied" even though the permissions look fine.

**`:Z` (the SELinux suffix)** — the polite note that fixes the above. Adding
`:Z` to a mounted folder tells Podman "relabel this so my container is
allowed to use it". Every mount in this project carries it. It does nothing
at all on macOS, harmlessly.

**Healthcheck** — a heartbeat monitor baked into the image. Every 30
seconds the container asks itself "am I still answering?" and reports
`healthy` or `unhealthy`. This is why `./container-py.sh status` can tell
you the app is alive rather than merely running.

**Daemon** — a program that runs quietly in the background with no window,
waiting to do its job. The container runtime and the web server are
daemons.

**systemd** — the Linux program that starts everything else when a machine
boots, and restarts things that die. If you want Crucible to come back
after the server reboots, systemd is who you ask.

**systemd user unit** — a small recipe file telling systemd "run this, for
this user, at boot". Crucible's is
`~/.config/systemd/user/container-crucible-py.service`.

**Quadlet** — a newer, tidier way of writing that recipe for containers
specifically (`crucible-py.container`). Same purpose, less boilerplate.

**Lingering** — normally Linux shuts down all your programs when you log
out, which would kill the app the moment you close your SSH session.
`sudo loginctl enable-linger $USER` tells the system "keep this user's
services running even when they're not logged in". Essential on the server.

**Cron** — an alarm clock for commands. You give it a schedule and a
command; it runs the command on that schedule forever, whether or not
you're logged in. Crucible uses it for health monitoring and certificate
expiry checks.

**Crontab** — your personal list of cron alarms (`crontab -l` to see it,
`crontab -e` to edit it). It belongs to your *user account*, not to any
folder — which is why an uninstall has to clean it up explicitly.

**The five cron fields** — a schedule like `0 8 * * 1` reads left to right:

| Field | `0 8 * * 1` | Meaning |
|---|---|---|
| minute | `0` | at minute 0 |
| hour | `8` | at 8 a.m. |
| day of month | `*` | every day of the month |
| month | `*` | every month |
| day of week | `1` | but only on Mondays (0 = Sunday) |

So `0 8 * * 1` = **every Monday at 08:00**. An asterisk means "every".
`*/5 * * * *` means "every 5 minutes".

**Firewall** — a doorman for the machine's ports, deciding which doors
accept visitors from outside. **firewalld** and **iptables** are two
different doormen; Red Hat machines use one, the other, or neither.

**Image prune** — throwing away images you no longer need.
"**Dangling**" images are anonymous leftovers from previous builds — real
disk space, no name, no purpose.

---

## The web and API words

**Server** — a computer whose job is answering requests from other
computers. Also used for the *program* doing the answering. The RHEL8 VM is
a server; your Mac is not (it just pretends to be one, for you alone).

**Client** — whoever is asking. Your browser is a client. So is `curl`.

**HTTP** — the language browsers and servers speak. When you type an
address, your browser sends an HTTP request and gets a page back.

**HTTPS** — the same conversation, sealed in an envelope. The **S** is for
secure: anyone intercepting the traffic sees scrambled noise instead of
your data. Lab data should always travel this way outside your own machine.

**TLS (and SSL)** — the actual sealing technology behind the S in HTTPS.
SSL is the old name; people still say it out of habit. When this project's
docs say "SSL certificates", they mean TLS.

**Certificate** — an ID card for a website, signed by an authority the
browser already trusts. It proves the server really is who it claims to be.
Crucible's lives at `certs/server.crt`.

**Private key** — the secret half of the ID card, which must never leave
the server or enter Git. If the certificate is your passport, the private
key is your signature: anyone holding it can impersonate you. Crucible's
sits at `certs/server.key` with permissions `600` (readable only by you),
and the whole `certs/` folder is excluded from version control.

**Subject Alternative Name (SAN)** — the list of hostnames a certificate is
valid for, written inside the certificate itself. A certificate issued to
`server.example.com` says so in its SAN, and a client asking for any *other*
name — including `localhost` — will refuse it with a "name mismatch" error even
though the certificate is perfectly genuine. That is hostname checking working,
not a fault. It is why a `localhost` probe against a corporate certificate needs
`-k`, while asking for the machine's real name validates cleanly.

**Certificate authority (CA)** — the trusted issuer that signs
certificates, like a passport office. Nestlé runs an internal one, which is
why the server's certificate is trusted inside the company network.

**Self-signed certificate** — an ID card you printed yourself. It encrypts
traffic perfectly well, but no authority vouches for it, so browsers show a
scary warning. Fine for testing on your own Mac (`./setup-ssl.sh` makes
one); not for production.

**`-k` (in curl)** — "don't check the ID card". Needed for self-signed
certificates, and a sign you should *not* use it against a real server: if
a corporate certificate needs `-k`, something is wrong.

**Certificate expiry** — certificates stop being valid on a fixed date, and
a website with an expired one throws visitors an alarming warning.
`./cert-expiry-check.sh` warns you 30 days ahead so this never surprises
you.

**API (Application Programming Interface)** — a website built for programs
instead of people. You request a specific address and, instead of a styled
page with buttons, you get back raw structured data. Crucible's API lives
under `/api`.

**Endpoint** — one specific address within an API, with one specific job.
`/api/chemicals` is the endpoint for chemicals; `/api/stats` is the
endpoint for the dashboard totals. Think of the API as a building and each
endpoint as a numbered service window.

**REST** — a common set of manners for APIs: use the address to say *what*
you want, and the HTTP verb to say *what to do with it*.

**GET / POST / PUT / DELETE** — those verbs. GET = "show me", POST =
"here's a new one", PUT = "replace this one", DELETE = "remove this one".

**Status code** — the three-digit answer to every request. `200` = fine,
`201` = created, `404` = no such thing, `500` = the server broke. You'll
see these in every `curl` example.

**JSON** — the text format the API answers in: labelled values in braces,
readable by both people and programs. `{"name": "Caffeine"}` is JSON.
Pipe it through `python3 -m json.tool` to see it neatly indented.

**curl** — a program that fetches a URL from the terminal instead of a
browser. It's how the docs demonstrate the API without clicking anything.
`-s` means "quietly, no progress bar".

**Proxy** — a middleman your company routes internet traffic through.
Helpful for the outside world, unhelpful for `localhost`, which it may try
to intercept. That's why every command in this project says
`--noproxy '*'` — "don't use the middleman for this one".

**uvicorn** — the web server program that actually listens on port 49160
and hands requests to the app.

**FastAPI** — the Python toolkit the backend is written with. It turns
Python functions into API endpoints and generates the interactive
documentation at `/docs` for free.

**Swagger UI / `/docs`** — a clickable, self-updating manual for the API,
generated from the code itself and served by the running app at
`http://localhost:49160/docs`. You can try requests in the browser there.

**React** — the toolkit the user interface (the part with buttons and
tables) is built with.

**Vite** — the tool that packages the React code into plain files a browser
can read. Its output lands in `client/dist`.

**SPA (single-page application)** — a website that loads once and then
redraws itself as you click, instead of fetching a whole new page each
time. Crucible's interface is one.

**Static files** — files served exactly as they sit on disk (the built
React app, images), as opposed to answers calculated per request.

**Relative URL** — a link written as `/api/chemicals` rather than
`https://some-host/api/chemicals`. Because it names no host, the same code
works on your Mac and the server unchanged. This project insists on them.

---

## The data words

**Database** — an organised container for tables, built for answering
precise questions quickly. Think: a filing cabinet, where each drawer is a
table.

**Table** — data in rows and columns, like one sheet of a spreadsheet. One
**row** = one thing (one chemical). One **column** = one fact about it
(its name, its CAS number).

**SQLite** — the database program Crucible uses by default. Its defining
trait: the entire database is a single ordinary file on disk —
`data/crucible.db`. No server to run, no account to create, nothing to
configure. You can copy it, email it, or back it up like any other file.

**PostgreSQL** — a heavier database that runs as its own service and
handles many simultaneous users well. Crucible supports it as an *option*
for later growth; SQLite remains the default.

**SQL** — the language for asking databases questions. You mostly won't
need it here: the app and the API ask on your behalf.

**Schema** — the shape of the data: which tables exist, which columns they
have, what type each column holds. The blueprint, as opposed to the
contents.

**Migration** — a recorded, repeatable change to that blueprint — adding a
column, say — that can be applied to an existing database *without*
throwing away what's in it. Like adding a new field to a paper form and
agreeing what to write in it for all the forms already filed.

**Alembic** — the tool that stores and applies those migrations. Inside the
container it brings the database up to the current shape automatically at
startup, so you never have to think about it.

**ORM (Object-Relational Mapper)** — a translator letting Python code talk
about "a chemical" while the database stores rows and columns.
**SQLAlchemy** is the one this project uses.

**The `doc` column (this project's storage pattern)** — every table keeps
the complete record as one JSON blob in a column called `doc`, *plus* a few
important fields copied out into ordinary indexed columns for fast
searching. The blob is the source of truth; the extracted columns are a
convenience. It means an unexpected field in an upload is never silently
thrown away.

**Index** — a lookup shortcut, exactly like the index at the back of a
book: instead of reading every page to find "caffeine", the database checks
the index and jumps straight there.

**Primary key** — the column guaranteeing each row is distinct. Crucible's
internal one is `id`, an automatically generated unique string.

**Business key** — the identifier *humans* actually use: `chemical_id`
(e.g. `CHEM-0001`) or `sample_id`. Unique, meaningful, and what you'd quote
to a colleague.

**UUID** — a long random-looking identifier (`7b7a84b8-79b3-…`) generated
so as to be unique everywhere, forever, without coordination.

**Upsert** — "update if it exists, insert if it doesn't". Crucible's
chemical uploads work this way: re-uploading the same file corrects the
existing records instead of creating duplicates.

**Duplicate** — the same real-world thing recorded twice. Prevented here by
the business key.

**Backup** — a copy of your data kept somewhere else, made *before* you
need it. `./container-py.sh backup` writes one to `backups/`.

**Online backup / a "torn" copy** — copying a database file while the app
is writing to it can capture a half-finished state — a torn copy, quietly
corrupt. Crucible's backup command uses SQLite's official backup mechanism
to take a consistent snapshot even while the app runs. This is why you
should never just `cp` a live database.

**Restore** — putting a backup back. Crucible's restore stops the app,
keeps the current database as `.pre-restore` (in case you change your
mind), swaps in the backup, and restarts.

**Excel / `.xlsx`** — the spreadsheet format used for bulk uploads.
Curiously, an `.xlsx` file is secretly a zip archive of XML files — which
is why sending a `.csv` to an Excel-only endpoint produces the baffling
error `File is not a zip file`.

**CSV** — "comma-separated values": a plain-text table, one line per row.
Simpler than Excel and readable in any editor. Only the chemicals endpoint
accepts it.

---

## The Git words

**Git** — a save-game system for a project. Every meaningful change becomes
a named snapshot you can return to, compare against, or undo. It runs on
your own machine; GitHub is optional.

**GitHub** — a website that hosts Git projects so they can be shared and
backed up.

**Repository (repo)** — the project folder plus its entire history. This
project has two: a **public** one on a personal account (sanitised, used
for development on the Mac) and a **private** corporate one (used to deploy
the server).

**Clone** — making your own complete copy of a repository, history and all.

**Commit** — one saved snapshot, with a message explaining why. The unit of
history.

**Commit message** — that explanation. Written for whoever reads the
history later, usually you.

**Staging (`git add`)** — choosing which changes go into the next commit.
Think of putting items in a box (`git add`) before labelling and sealing it
(`git commit`).

**Branch** — a parallel line of history, so unfinished work doesn't disturb
the working version. This project uses `develop`, `beta`, and `master`,
kept at the same point.

**HEAD** — "the commit you're currently standing on".

**Detached HEAD** — standing on a specific commit rather than on a branch.
Harmless, but new commits made there belong to no branch and are easy to
lose. Git warns you loudly. `git switch <branch>` gets you back.

**Remote** — a copy of the repository somewhere else, referred to by a
nickname. `origin` is the conventional nickname for "the one I cloned
from".

**Push / pull / fetch** — push sends your commits to a remote; fetch
downloads the remote's commits without touching your files; pull is fetch
plus merge.

**Fast-forward** — the tidiest kind of update: your branch simply steps
forward along the same line, because nothing has diverged. `--ff-only`
means "refuse to do it any other way", which protects you from accidental
merge tangles.

**Merge conflict** — what happens when two people changed the same lines
and Git can't decide. Not an error, just a question.

**`.gitignore`** — a list of files Git must pretend not to see: secrets,
databases, generated build output, machine junk. In this project it's the
main thing standing between the certificates and the public internet.

**Tracked / untracked** — a file Git is watching versus one it isn't. Note
that adding a rule to `.gitignore` does **not** untrack a file Git already
follows.

**File mode (`100644` vs `100755`)** — Git records whether a file is
executable. `100644` is an ordinary file; `100755` is a script you can run
with `./name.sh`. A line reading `mode change 100755 => 100644` means a
script just lost its ability to run — worth fixing before committing.

**History rewriting** — changing past commits. Powerful, and dangerous on a
shared repository: everyone else's copy becomes incompatible.

**Mirror (in this project)** — copying the *content* of one repository into
another that has an unrelated history, using
`git checkout public/develop -- .`. Necessary here because the two repos
were started separately and cannot push to each other. See
[GITOPS-WORKFLOW.md](GITOPS-WORKFLOW.md).

---

## The columns Crucible adds to imported data

When a laboratory file is imported, its own columns are kept under their own
headings. Crucible adds a few more, marked **+** in the data table. Each exists
because cleaning found something that would otherwise have been lost without
trace. Nothing in your file corresponds to them.

**Derived column** — a column this application calculated, as opposed to one
that was in the file you uploaded. Like a note written in the margin of a
document: useful, but not part of the original.

**chemical_id** — the link from a result to a compound in the Chemicals table.
Created during import, keyed on the CAS number when there is one and on the
compound's name when there is not. It is how the application knows that a
result in one file and a result in another concern the same substance.

**cas_alternatives** — the second and later CAS numbers when one cell named
more than one substance. Analytical chemistry sometimes cannot separate two
candidates for a single peak, so the cell reads `5398-11-8 / 6386-38-5`. The
first becomes the CAS number; the rest are kept here rather than discarded.

**below_detection_limit** — `true` when a measurement cell held a sentence such
as "No compounds found above 0.01 mg/kg" instead of a number. That is a genuine
result — the sample was clean — and the flag keeps it distinct from a
measurement that was never taken. Without it, "we looked and found nothing" and
"we never looked" would be indistinguishable.

**duplicate_group** — a marker shared by rows identical on the fields that
identify a measurement (sample, compound, simulant, retention index). They may
be true repeat measurements, or an artefact of several exports having been
combined into one file. Crucible does not decide which: nothing is removed, and
the marker only makes them findable.

**`…_note` columns** — the original text of a cell that should have held a
number but did not. The numeric column beside it is empty for those rows, and
the note preserves what the file actually said.

**created_at** — when the record was imported. Not when the measurement was
made; that is the file's own date column.

---

## The lab and chemistry words

**Chemical registry** — one catalogue that gives every compound a single
identity, so that everything ever measured about it can be attached to that
identity instead of scattered across separate files. It is what this
application is: the registry is the point, and the upload pages, viewer and API
are ways in and out of it. Compare a library catalogue — its value is not the
cards, it is that every copy of a book resolves to one entry.

**Chemical** — in this app, one compound record: a name, identifiers, and
structural facts. The anchor everything else links to.

**Sample** — a physical thing in the lab (a material, a batch) that can be
linked to one or more chemicals.

**Screening** — testing many compounds against an assay to see which ones
do something. The results table holds one row per measurement.

**Toxicology** — the study of harmful effects: which dose of what, in which
species, produced which outcome.

**Assay** — one laboratory test procedure with a defined readout. "Cell
viability (MTT)" is an assay.

**CAS number** — a unique registry number for a chemical substance, written
like `58-08-2` (that one is caffeine). Beware: Excel loves to mistake these
for dates — keep the column formatted as text.

**Molecular formula** — which atoms and how many: caffeine is
`C8H10N4O2`.

**Molecular weight** — how heavy one molecule is, in grams per mole.

**SMILES** — a way of writing a molecule's structure as a single line of
text, so software can read it.

**InChI / InChIKey** — another structure-as-text standard; the InChIKey is
a fixed-length version handy for lookups.

**SDF (Structure-Data File)** — a chemistry file format holding molecules
*and* their data fields together. Crucible can import them directly.

**V2000 / V3000** — two generations of the SDF layout. Both are supported.

**RDKit** — the chemistry toolkit the backend uses to read structures and
compute formulas, weights, and stereochemistry.

**Stereochemistry** — the three-dimensional arrangement of a molecule.
Two compounds can share a formula and behave completely differently
because of it.

**Polymer / mixture** — substances that aren't a single defined molecule.
The importer detects and flags them.

**SLIMS** — the laboratory information system samples are exported from.
Its export has an unusual **three-row header** (machine field names on row
2, human labels on row 3, data from row 4), which is why the sample
template looks odd and must not be flattened.

**ELN (Electronic Lab Notebook)** — the digital replacement for a paper lab
notebook; the module of this app where uploads happen.

**IC50 / EC50** — the concentration producing half of the maximum
inhibition (IC) or effect (EC). Lower means more potent.

**NOAEL** — No Observed Adverse Effect Level: the highest dose at which
nothing bad was seen.

**LOAEL** — Lowest Observed Adverse Effect Level: the lowest dose at which
something bad *was* seen.

**LD50** — the dose that proved lethal to half of a test population. A
blunt, historical measure of acute toxicity.

**Route of administration** — how a substance was given: oral, dermal,
inhalation.

---

## The Python and testing words

**Python** — the programming language the backend is written in.

**Package / library** — a toolbox of code someone else published, which you
install and use rather than writing yourself. RDKit and FastAPI are
packages.

**Dependency** — a package your project needs in order to run. Listed in
`backend/requirements.txt`.

**Virtual environment (`venv`)** — a project's own private, sealed set of
packages, kept in a folder (`backend/.venv`) instead of shared with the
whole computer. Without it, upgrading a package for one project can
silently break another. Like giving each project its own toolbox rather
than one communal pile.

**pip** — the command that installs Python packages.

**pytest** — the program that runs the automated tests. Crucible has 47.

**Test / test suite** — a claim about the code, written as code: "given
this input, the function must return exactly this". Run them after any
change; they turn red when something breaks.

**Contract test** — a test that pins the *external behaviour* (the exact
keys and messages the API returns), so the inside can be rewritten without
surprising anyone using it.

---

## The project words

**Environment variable** — a named value handed to a program when it
starts, rather than written inside it. Used for settings that differ
between machines (which port, which database, whether to use HTTPS). Note
they're inherited *at start-up, from whoever launched the program* — which
is why setting one in a terminal doesn't affect an app started from
somewhere else.

**`.env.local`** — this project's file of machine-specific settings
(`CERT_SOURCE`, `CERT_HOSTNAME`, `USE_HTTPS`). It is deliberately **not**
committed, survives updates, and is the one piece a fresh clone can't
restore for you. On the production server, treat creating it as step one.

**Placeholder / redaction** — a stand-in like `<vm-hostname>` or
`<cert-store-path>` written in the documentation where the real internal
value would otherwise be published. The real values live only in
`.env.local` on the machine that needs them.

**Development vs. production** — development is where you try things (your
Mac, HTTP, data you can throw away); production is the real deployment
other people depend on (the RHEL8 VM, HTTPS, real data). Different rules
apply: back up before touching production.

**Deployment** — putting a new version of the app where people use it.

**Build** — turning source code into something runnable: here, assembling
the container image.

**Rebuild** — build again and restart with the new version. Crucible's
`rebuild` deliberately preserves whether you were running HTTP or HTTPS.

**Idempotent** — safe to run twice: doing it again changes nothing further.
The setup script and the uploads are designed this way, so a retry after an
interruption is never dangerous.

**Dry run** — showing what *would* happen without doing it.
`./uninstall.sh --dry-run` is the safest command in the project.

**Health monitoring** — `monitor.sh`, run every 5 minutes by cron, checks
the app answers and restarts it if not.

**GitOps** — treating the Git repository as the single source of truth for
what should be deployed: you change code by committing, and deployment
follows from that. This project's flow is written up in
[GITOPS-WORKFLOW.md](GITOPS-WORKFLOW.md).

**The safety gate (`check-public-safe.sh`)** — a script that inspects what
Git is tracking and refuses the all-clear if anything sensitive (a
certificate, a database, real lab data, an internal hostname) would be
published. Run it before every public push.

**Sanitised** — with internal details removed. The public repository holds
a sanitised copy of this project: same code, no internal hostnames, no real
lab data, no certificates.

**Synthetic data** — invented example data that looks real enough to test
with but describes nothing real. Every row in the shipped upload templates
is synthetic.

---

**Something missing?** If you met a word in this project that isn't here,
that's a gap worth filling — the whole point of this file is that nobody
should have to already know the vocabulary to follow the documentation.

**Last Updated:** August 25, 2026
