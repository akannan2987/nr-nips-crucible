[← README](../README.md) · [All docs in order](../README.md#the-documentation-in-order) · [Glossary](GLOSSARY.md)

# macOS Install & Run — Crucible: Pandora Toolbox Enhancement (v2.0)

**Prerequisites:** a Mac, an internet connection, and about 30 minutes. No prior experience with containers or terminals needed.
**Learning goal:** after this guide you will understand what a container is and why this app uses one, how to start and stop the app, how to check it is healthy, and how to serve it over HTTPS — plus you will have it running.
**Time:** ~30 minutes, most of it waiting for the first image build.

> ### How to read this doc
>
> **Numbered steps are things you do.** The text between them explains *why* —
> skip it on your second read, but read it on your first, because every piece of
> jargon in this project is defined the first time it appears.
>
> **Grey boxes are commands.** You type (or paste) them into the **Terminal** —
> the app on your Mac that lets you talk to the computer by typing sentences
> instead of clicking buttons. Think: a text-message conversation with your Mac.
> To open it: press `Cmd`+`Space` (that's Spotlight, the Mac's search bar), type
> `Terminal`, press `Return`. A window opens with a blinking cursor. That cursor
> is the computer waiting for you.
>
> **Lines starting with `#` inside a grey box are comments, not commands.** They
> are notes to you. You can paste them along with the command — the Terminal
> ignores them — or leave them out. Either way works.
>
> After each command you will find **You should see:** (roughly what appears on
> screen) and **What it means:** (a one-line translation). Where a command can
> plausibly go sideways, an **If instead:** branch names the symptom and the fix.
>
> Nothing here is dangerous. Nothing here deletes your files. The one guide that
> *does* delete things is the [Uninstall guide](UNINSTALL-MACOS.md), and it warns
> you loudly.

Step-by-step guide to install, run, and verify Crucible on **macOS** (development
machine), including HTTPS. Companion documents: [macOS Uninstall](UNINSTALL-MACOS.md) ·
[RHEL8 Install & Run](INSTALL-RHEL8.md) · [RHEL8 Uninstall](UNINSTALL-RHEL8.md).

> **Repository for macOS:** clone from the **public** repo
> `https://github.com/akannan2987/nr-nips-crucible` (no authentication needed).
> The RHEL8 production deployment uses the private Nestlé repo instead — see
> [INSTALL-RHEL8.md](INSTALL-RHEL8.md).
>
> A **repository** (or **repo**) ([glossary](GLOSSARY.md#the-git-words)) is a
> project folder with a full history of every change ever made to it. To
> **clone** a repository is to download your own complete copy, history and all.
> "Public" here means anyone can clone it without a password.
>
> For deep-dive material (all runbooks, SSL rotation, PostgreSQL, systemd) see
> **[DEPLOYMENT.md](../DEPLOYMENT.md)** — this document is the fastest safe path
> on a Mac.

### What you are actually installing

Crucible is a lab-data web application — chemicals, samples, screening,
toxicology. It has two halves: a **backend** (the part that stores and serves the
data, written in Python) and a **frontend** (the part you look at in a browser,
written in React). You will not install either of them piece by piece. Instead
you install *one* thing that carries both:

**container** ([glossary](GLOSSARY.md#the-container-words)) — a sealed lunchbox
holding an application plus every library and setting it needs. It runs on your
Mac but does not mix with your Mac: it cannot be broken by your Python version,
and it cannot break anything of yours. Delete the lunchbox and every trace of the
app goes with it.

**image** ([glossary](GLOSSARY.md#the-container-words)) — the recipe (and packed
ingredients) the lunchbox is built from. You build the image once; you can start
and stop containers from it as often as you like. This is why the first run is
slow and every run afterwards is fast.

**container runtime** ([glossary](GLOSSARY.md#the-container-words)) — the program
that builds images and runs containers. This project works with either of the two
common ones, **podman** or **docker**, and picks whichever it finds. Podman is
preferred here mostly because it needs no paid licence and no background
privileges.

> **Where do all the packages go?** Nowhere on your computer. Python, FastAPI,
> RDKit and the rest live *inside* the container image, not in your system
> folders — which is why this project needs no virtual environment, and why an
> uninstall can remove every trace. If that raises questions, the glossary
> answers them in one place:
> **[Why this project has no virtual environment](GLOSSARY.md#the-container-words)**.

## Table of Contents

- [1. Prerequisites](#1-prerequisites)
- [2. Install and run (HTTP)](#2-install-and-run-http)
- [3. Enable HTTPS](#3-enable-https)
- [4. Verification checklist](#4-verification-checklist)
- [5. Day-2 operations](#5-day-2-operations)
- [6. macOS-specific gotchas](#6-macos-specific-gotchas)
- [What you have now](#what-you-have-now)
- [Troubleshooting](#troubleshooting)

---

## 1. Prerequisites

*Time: about 10 minutes, most of it downloading.*

A container runtime (either one — the scripts auto-detect, podman preferred):

```bash
# Option A — Podman (recommended)
brew install podman
podman machine init          # first time only
podman machine start         # every session — the VM does NOT auto-start on login

# Option B — Docker Desktop
brew install --cask docker   # then launch Docker Desktop and wait until it is running
```

**You should see:** for Option A, a few minutes of download chatter from
`brew install podman`, then from `podman machine init` a progress bar
("Downloading VM image…") and finally `Machine init complete`, and from
`podman machine start` a short block ending in
`Machine "podman-machine-default" started successfully`.

**What it means:** you now have a working container runtime. Take the three
commands one at a time; each finishes before you type the next.

Some vocabulary you just used:

- **brew** — [Homebrew](https://brew.sh), the unofficial-but-universal app store
  for Mac command-line software. If `brew` is not found, install it first from
  that site; it prints one command to paste.
- **podman machine** ([glossary](GLOSSARY.md#the-container-words)) — containers
  are a Linux invention, and your Mac is not Linux. So podman quietly runs a tiny
  Linux computer inside your Mac (a **virtual machine**, or VM) and puts the
  containers in there. `podman machine init` builds that little computer once;
  `podman machine start` switches it on.

> ⚠️ **The podman machine does not survive a reboot, and does not start when you
> log in.** After every restart of your Mac, your first command is
> `podman machine start`. If you forget, every project command will politely
> refuse and tell you exactly this. It is the single most common stumble on
> macOS, and it is harmless.

**If instead:** `brew install podman` ends with a warning about `PATH`, follow the
instruction Homebrew prints. (**PATH** is the list of folders your computer
searches when you type a program's name. If a program is installed but not on the
PATH, your Mac insists it does not exist.)

**If instead:** you chose Option B, remember Docker Desktop is a normal Mac app —
you must actually launch it from Applications and wait for its whale icon to stop
animating before any command here will work.

Also required: `git`, `curl`, and `openssl` (all present on a standard macOS +
Homebrew setup), outbound internet during the image build, and a free port
49160 (`lsof -i :49160` should print nothing).

Three more definitions, and then we start:

- **port** ([glossary](GLOSSARY.md#the-web-and-api-words)) — one of your
  computer's numbered doors. A machine has one address but tens of thousands of
  numbered doors, so many network programs can coexist without shouting over each
  other. Crucible uses door number **49160**.
- **localhost** ([glossary](GLOSSARY.md#the-web-and-api-words)) — `127.0.0.1`,
  the address that always means *this very machine*. `http://localhost:49160` is
  therefore "knock on door 49160 of the computer I am sitting at".
- **`curl`** ([glossary](GLOSSARY.md#the-web-and-api-words)) — a browser with no
  windows. It fetches a web address and prints the raw answer as text. We use it
  for checks because it is honest and scriptable.
- **`lsof -i :49160`** — "list open files, filtered to internet door 49160".
  Silence means nothing is using that door yet.

**You should see:** nothing at all from `lsof -i :49160`.

**What it means:** port 49160 is free. (Silence = success — a very Unix habit.)

**If instead:** `lsof` prints a line naming some process, something else already
holds that door. Either stop that program, or run Crucible on a different door by
setting `CRUCIBLE_PORT` (see [§5](#5-day-2-operations)).

Only needed for bare-metal development (hot reload, running tests):
Python 3.12+ and Node.js 18+ / npm 8+. ("**Bare-metal**" here just means running
the code directly on your Mac instead of inside the container. You do not need
this to *use* the app — only to develop it, or to run the test suite in
[V7](#4-verification-checklist).)

---

## 2. Install and run (HTTP)

*Time: 5–10 minutes, nearly all of it the first image build.*

```bash
# 1. Clone the PUBLIC repository
git clone https://github.com/akannan2987/nr-nips-crucible.git
cd nr-nips-crucible

# 2. One-shot setup: build image, start container, verify the API
./setup-after-clone-py.sh
#    Non-interactive: SETUP_MONITOR=n ./setup-after-clone-py.sh
#    (SETUP_MONITOR=y installs the */5-minute health-monitoring cron instead of asking)

# ✅ On a Mac with no corporate certificate store the script prints
#    "No certificate store ... (normal on macOS)" and starts in HTTP mode.
#    It then polls the API for up to 60 s and confirms it answers.
```

Line by line, since this is the important one:

- `git clone …` downloads the project into a new folder called
  `nr-nips-crucible` inside whatever folder your Terminal is currently sitting
  in (usually your home folder).
- `cd nr-nips-crucible` means "**c**hange **d**irectory" — walk into that folder.
  Everything after this point assumes you are standing inside it.
- `./setup-after-clone-py.sh` runs the setup script. The leading `./` means "the
  file right here in this folder", not "some program installed on the system".
  `.sh` marks it as a **shell script** — a saved list of Terminal commands.

**You should see:** a banner, then five numbered steps scrolling past:

```
Step 1: SSL certificates
  – No certificate store configured (normal on macOS)
    → will start in HTTP mode. ...
Step 2: Building the crucible-py image (first build takes a few minutes)...
Step 3: Starting the container...
Step 4: Verifying the API...
  ✓ API is answering:
{"chemicals":{"total":...
Step 5: Health monitoring (cron job, every 5 minutes)
  Install/refresh the monitoring cron job? (y/n)
```

…ending with `✅ Python backend setup complete!` and the address to open.

**What it means:** the image was built, a container was started from it, and the
app answered a real request. You are done installing.

**Step 2 is the slow one — the first build takes 5–10 minutes. Good moment for a
coffee.** It scrolls hundreds of lines of download and compile output. That wall
of text is normal and is not error output; the runtime narrates everything it
does. Later builds reuse most of the work and take seconds.

**Step 5 asks you a question.** It offers to install a **cron**
([glossary](GLOSSARY.md#the-container-words)) job — cron is your Mac's kitchen
timer for programs: "run this every five minutes, forever, whether or not anyone
is logged in". Here it runs a health check that restarts the app if it stops
answering. `y` is a reasonable answer; `n` is equally fine on a laptop you turn
off nightly. To skip the question entirely, use the `SETUP_MONITOR=n` form shown
in the comment.

**If instead:** the script stops at Step 2 with
`✗ The podman machine VM is not running` — you skipped or lost
`podman machine start`. Run it, then re-run the setup script; it is safe to run
again.

**If instead:** Step 4 prints `✗ API did not answer within 60s` — the container
started but the app inside is unhappy. Run `./container-py.sh logs` and read the
last twenty lines; see [Troubleshooting](#troubleshooting).

Manual alternative (what the one-shot script does internally):

```bash
./container-py.sh build      # podman/docker build of backend/Dockerfile → crucible-py:latest
./container-py.sh start      # run on http://localhost:49160 (SQLite in ./data, bind-mounted)
```

Use these two if you prefer watching each stage separately, or when something
went wrong and you want to retry just one half.

**You should see:** from `build`, `✓ Image built successfully`; from `start`,
`✓ Container started successfully` followed by `Access the application at:` and
the localhost address.

**What it means:** `crucible-py:latest` is the image (the recipe);
`crucible-py` is the container (the running lunchbox). Same name, two different
things — that is a container-world convention you will meet everywhere.

Two terms from those comments:

- **SQLite** ([glossary](GLOSSARY.md#the-data-words)) — a **database**
  ([glossary](GLOSSARY.md#the-data-words)) that lives in a single ordinary file
  (`data/crucible.db`). A database is an organised container holding one or more
  tables; think of a filing cabinet for tables. SQLite is the version with no
  server, no password, and no setup — just the cabinet, as a file you can copy.
- **bind mount** ([glossary](GLOSSARY.md#the-container-words)) — a shared
  doorway between a folder on your Mac and a folder inside the container. `data/`
  is bind-mounted, which is why **your data survives when the container is
  deleted**: the file was never inside the lunchbox, only visible through it.

Open the app: <http://localhost:49160> — on macOS the port is published on
**127.0.0.1 only** (see [gotchas](#6-macos-specific-gotchas)).

**You should see:** the Crucible dashboard in your browser, with counts for
chemicals, samples, screening, and toxicology.

**What it means:** everything works. Both halves — the React frontend you are
looking at and the Python backend feeding it — are being served by that one
container.

---

## 3. Enable HTTPS

*Time: about 5 minutes. Optional on a Mac — skip it unless you want to rehearse
the production setup.*

So far the app speaks **HTTP** ([glossary](GLOSSARY.md#the-web-and-api-words)) —
the plain, unencrypted language of the web, where anyone positioned between the
two ends could read the traffic. **HTTPS** is the same language inside a sealed
envelope. On `localhost` nothing leaves your machine, so plain HTTP is genuinely
fine here; you enable HTTPS on the Mac mainly to test what production does.

Sealing the envelope needs two files:

- **TLS/SSL certificate** ([glossary](GLOSSARY.md#the-web-and-api-words)) — a
  public ID card for the server, saying "I really am this host", countersigned by
  someone. (TLS is the modern name; SSL is the old name; everyone still says SSL.)
- **private key** ([glossary](GLOSSARY.md#the-web-and-api-words)) — the secret
  half that proves the ID card belongs to you. Anyone holding the key *is* the
  server, as far as the internet is concerned, which is why it is guarded and
  never committed.
- **self-signed certificate** ([glossary](GLOSSARY.md#the-web-and-api-words)) —
  an ID card you countersigned yourself. The encryption is real; the *identity
  claim* is worth nothing to a stranger. Browsers therefore show a warning. For
  local development this is correct and expected, not a failure.

`./container-py.sh start-ssl` requires **both** `certs/server.crt` and
`certs/server.key` to exist. Two ways to get them on a Mac:

```bash
# Option A — self-signed development certificate (browser will warn; that's expected)
./setup-ssl.sh
#    Optional: SSL_DOMAIN=my.host.name ./setup-ssl.sh   (default CN: hostname -f)

# Option B — real certificates you already hold (e.g. a local backup kept
# OUTSIDE the repository, such as ~/.crucible/certs)
mkdir -p certs
cp ~/.crucible/certs/server.crt certs/server.crt
cp ~/.crucible/certs/server.key certs/server.key
chmod 600 certs/server.key

# Verify the pair matches — both commands MUST print the same MD5 hash
openssl x509 -noout -modulus -in certs/server.crt | openssl md5
openssl rsa  -noout -modulus -in certs/server.key | openssl md5
```

**You should see:** from Option A, `✓ SSL certificates generated successfully!`
and a list of the two files it made. From the two `openssl` commands in either
option, two lines that are **character-for-character identical**, like
`MD5(stdin)= 7f3a…`.

**What it means:** the certificate and the key are two halves of the same pair.
If the halves differ, the server will refuse to start or browsers will reject it,
and the error message will be far less clear than this check.

**If instead:** the two hashes differ — you have mixed up files from two different
certificate sets. Re-copy both from the same source, or just run `./setup-ssl.sh`
to generate a fresh matching pair.

**If instead:** Option B fails with `No such file or directory` — you have no
backup at `~/.crucible/certs/` yet. Use Option A. (`~` is shorthand for your home
folder; `chmod 600` means "only I may read or write this file", the standard
posture for a private key.)

Then start in TLS mode (no rebuild needed — certs are mounted at runtime,
never baked into the image):

```bash
./container-py.sh start-ssl
# ✅ Verify (use -k for self-signed certificates):
curl --noproxy '*' -sk https://localhost:49160/api/stats
```

**You should see:** `✓ Container started with HTTPS`, the `https://localhost:49160`
address, and a note about the browser warning. Then from `curl`, one dense line of
JSON beginning `{"chemicals":{"total":`.

**What it means:** the app is now serving the sealed version. The `curl` flags:
`-s` = silent (no progress bar), `-k` = accept a self-signed certificate without
complaining, `--noproxy '*'` = never route this through a corporate **proxy**
([glossary](GLOSSARY.md#the-web-and-api-words)) — a middleman server your
employer's network may force traffic through. A proxy has no business relaying a
request to your own machine, but it will try, and the request dies there.

**If instead:** you get `curl: (60) SSL certificate problem` — you left off `-k`.
Add it. That error is the browser warning in text form, and here it is expected.

**If instead:** the browser shows a full-page red "Your connection is not private"
warning — that is the self-signed certificate doing exactly its job. Click
**Advanced** → **Proceed**.

HTTPS **replaces** HTTP on the same port 49160 — plain `http://` requests are
refused in SSL mode. To switch back to HTTP:

```bash
./container-py.sh stop
podman rm crucible-py        # or: docker rm crucible-py
./container-py.sh start
```

**You should see:** `✓ Container 'crucible-py' stopped`, then `crucible-py`
echoed back by `rm`, then `✓ Container started successfully`.

**What it means:** the protocol is fixed at the moment a container is created, so
switching means throwing that container away and making a new one. Nothing of
value is lost: `stop` pauses it, `rm` **rem**oves it, and your database is in
`data/` on your Mac, untouched (that bind mount again).

> ⚠️ **Never commit certificates.** `certs/`, `*.key`, and `*.crt` are excluded
> via `.gitignore`. Keep a backup of real certs outside the repository
> (e.g. `~/.crucible/certs/` with `chmod 600` on the key).
>
> (**.gitignore** ([glossary](GLOSSARY.md#the-git-words)) is a list of files Git
> must pretend not to see. It is what stops a stray `git add .` from publishing
> your private key to a public repository — a mistake that cannot be undone by
> deleting it later, because the history keeps everything.)

> 💡 On the Mac, HTTP is the sensible default and nothing extra is needed. If
> you want this machine to *always* start HTTPS (like the production VM does),
> create an untracked `.env.local` containing `USE_HTTPS=true` — then plain
> `start`/`rebuild` come up HTTPS automatically. See
> [INSTALL-RHEL8.md §3](INSTALL-RHEL8.md#3-https-with-corporate-certificates).
>
> ("Untracked" means Git ignores the file, so each machine keeps its own — which
> is the point: your Mac and the server can disagree about HTTPS without either
> overwriting the other.)

---

## 4. Verification checklist

*Time: 2 minutes for V1–V6; add 3–5 minutes for V7 the first time.*

Run this same checklist after every install or redeploy. The **identical**
checklist (plus external-access checks) exists for the VM in
[INSTALL-RHEL8.md](INSTALL-RHEL8.md#5-verification-checklist).

Seven checks. Nothing here changes anything — they only look. Run whichever line
matches the mode you are in (HTTP or HTTPS); do not run both.

```bash
# V1. API answers with stats JSON (must contain "chemicals")
curl --noproxy '*' -s  http://localhost:49160/api/stats     # HTTP mode
curl --noproxy '*' -sk https://localhost:49160/api/stats    # HTTPS mode
```

**You should see:** a single long line of JSON starting
`{"chemicals":{"total":42,"max":...` (your numbers will differ).

**What it means:** the backend is alive and can read the database. JSON is just a
text format for structured data — the language the frontend and backend use
between themselves. This is the single most informative check in the list: if V1
passes, the app fundamentally works.

**If instead:** you get nothing at all and `curl` exits quietly, you are probably
probing `http://` while the container is running HTTPS (or the reverse). Try the
other line. **If instead:** `Connection refused` — the container is not running;
go to V2.

```bash
# V2. Container is up and (after ~30 s) healthy. `status` detects HTTP vs
#     HTTPS mode and prints the stats JSON for whichever is in use.
./container-py.sh status
```

**You should see:** a small table (`NAMES  STATUS  PORTS`) with `crucible-py` and
a status like `Up 4 minutes (healthy)`, then `✓ Container is running`, then the
same JSON as V1.

**What it means:** `(healthy)` comes from the container's **healthcheck**
([glossary](GLOSSARY.md#the-container-words)) — a small self-test the runtime
runs every 30 seconds, like a pulse check. Immediately after starting you will
see `(starting)` or `(health: starting)` instead; wait half a minute. A blank
`STATUS` column, or `Exited`, means the app stopped.

```bash
# V3. UI loads in the browser (React app + architecture page)
open http://localhost:49160
open http://localhost:49160/architecture
```

**You should see:** two browser tabs — the dashboard, and an architecture diagram
page.

**What it means:** the frontend is being served correctly and can reach the
backend. (`open` is a macOS command meaning "hand this to whatever app normally
handles it" — for a URL, your default browser.)

```bash
# V4. Logs are clean (Ctrl-C to detach)
./container-py.sh logs
```

**You should see:** startup lines from Uvicorn (the web server inside the
container) and one line per request you have made. It then *appears to hang* —
that is intentional; it is following the log live, waiting for new lines.

**What it means:** you are reading the app's diary. Press `Ctrl`+`C` to stop
watching. **This does not stop the app** — `Ctrl`+`C` only ends the command you
are currently watching. The container keeps running.

```bash
# V5. Health monitor runs (logs to /tmp/crucible-monitor.log)
./monitor.sh                 # HTTPS mode: API_URL=https://localhost:49160/api/stats ./monitor.sh
```

**You should see:** two timestamped lines, ending in `✓ Application is healthy`.

**What it means:** this is the script that cron runs every five minutes. Running
it by hand proves the automated version will work. If it finds the app
unresponsive it restarts the container and says so. Note the HTTPS form: the
monitor assumes plain HTTP unless you tell it otherwise with `API_URL`.

```bash
# V6. Backup / restore round-trip works
./container-py.sh backup     # → backups/crucible-<stamp>.db
```

**You should see:** `Creating consistent online backup (app keeps running)...`
then `✓ Backup complete:` and the new file's path and size.

**What it means:** you have a copy of the whole database as one file, taken
safely while the app was running (SQLite has a proper online-backup mechanism —
this is not a risky file copy). `<stamp>` is a date-and-time stamp, so backups
never overwrite each other. Do this before anything you consider risky.

```bash
# V7. Backend test suite passes (bare-metal venv required)
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/pytest
```

**You should see:** a few minutes of `pip` download output, then a run of dots
and a green summary line like `==== 214 passed in 6.31s ====`.

**What it means:** the backend's own automated tests all agree the code behaves.
Two new words:

- **virtual environment (venv)** ([glossary](GLOSSARY.md#the-python-and-testing-words)) —
  a private Python sandbox in a folder (`backend/.venv`). It keeps this project's
  libraries away from your Mac's system Python, so nothing you install here can
  break anything else. A container for Python packages only — much lighter, much
  narrower.
- **pytest** ([glossary](GLOSSARY.md#the-python-and-testing-words)) — the tool that finds
  and runs the project's tests. One dot per test; `F` for a failure.

**If instead:** `python3: command not found` — V7 is the one check that needs
Python installed on the Mac itself (`brew install python@3.12`). V1–V6 do not.
Skipping V7 is fine if you are only running the app, not changing it.

**If instead:** you are still inside `backend/` afterwards — you are. `cd ..`
returns you to the project root, where all the `./container-py.sh` commands live.

---

## 5. Day-2 operations

"Day 2" is everything after the install: the small set of commands you will
actually use week to week.

```bash
# Update to a new version. rebuild preserves the protocol mode (an HTTPS
# deployment comes back as HTTPS) and is also how changed env vars take effect.
git pull && ./container-py.sh rebuild
```

**You should see:** either `Already up to date.` from `git pull`, or a summary of
changed files, followed by a build and `✓ Container started successfully`.

**What it means:** `git pull` fetches the newest code from GitHub; `rebuild`
makes a fresh image from it and replaces the running container. Your data is
untouched. `&&` means "and only if the first command succeeded" — so a failed
pull will not trigger a pointless rebuild.

```bash
# Backups (safe while running — uses SQLite's online-backup API)
./container-py.sh backup
./container-py.sh restore backups/crucible-<stamp>.db
```

**You should see:** from `restore`, a stop, a swap, a restart, and
`✓ Restored crucible-<stamp>.db → data/crucible.db`.

**What it means:** restore replaces today's database with the backup's contents.
Replace `<stamp>` with a real filename — run `ls backups/` to see them, or run
`restore` with no argument and it lists them for you. The database being replaced
is kept as `data/crucible.db.pre-restore`, so even a mistaken restore is
recoverable.

```bash
# Certificate expiry check (exit 1 when < 30 days remain; cron-friendly)
./cert-expiry-check.sh
WARN_DAYS=60 ./cert-expiry-check.sh
```

**What it means:** certificates expire, usually at the worst possible moment.
This prints the days remaining and signals failure ("exit 1", the Unix way a
command says *something is wrong*) once you are inside the warning window — which
is what makes it useful as a cron job. Only relevant if you enabled HTTPS.

```bash
# Optional PostgreSQL instead of SQLite
./container-py.sh db-start
USE_POSTGRES=true ./container-py.sh start
```

**What it means:** PostgreSQL is a full database *server* — heavier than SQLite,
and unnecessary on a laptop. It exists here for production-parity testing. If you
do not know you need it, you do not need it.

Key environment variables (full table in [DEPLOYMENT.md](../DEPLOYMENT.md)):
`CRUCIBLE_PORT` (`container-py.sh`'s only port override — it deliberately
ignores a generic `PORT` shell variable; note `monitor.sh` and `setup-ssl.sh`
**do** read `PORT`, so on a non-default port set `API_URL=...` for the monitor
explicitly), `HOST_BIND` (default `127.0.0.1` on macOS),
`CONTAINER_RUNTIME=podman|docker`, `USE_POSTGRES`, `DATABASE_URL`.

An **environment variable** is a setting you hand to a command by writing it in
front of the command, as in `USE_POSTGRES=true ./container-py.sh start`. It
applies to that one run only — it is a sticky note on a single command, not a
saved preference. (To make one permanent for this machine, put it in
`.env.local`, as described in [§3](#3-enable-https).)

---

## 6. macOS-specific gotchas

Each of these has cost somebody an afternoon. They are all normal and none of
them mean you did something wrong.

- **Podman machine is mandatory** — every `container-py.sh` command checks the
  VM state on macOS and aborts with instructions if it isn't running
  (`podman machine start`).
  → *In plain terms:* the little Linux computer must be awake before anything
  container-shaped can happen. After every Mac reboot, start it first.
- **127.0.0.1 binding**: macOS publishes the port on loopback only, because
  Apple's `remoted` daemon occupies ports 49152+ on a link-local address and
  breaks wildcard binds. Other machines can't reach a Mac deployment unless
  you set `HOST_BIND` to a routable IP.
  → *In plain terms:* your Mac's copy answers only to you. A colleague on the
  same Wi-Fi cannot open it. That is a deliberate macOS-only restriction working
  around an Apple background service, not a bug in Crucible.
- **`start` reuses an existing container as-is** — new `CRUCIBLE_PORT`,
  `HOST_BIND`, or `USE_POSTGRES` values are not applied. The script warns when
  the running container's port differs from the one you asked for and prints
  the port actually in use. To apply the change: `./container-py.sh rebuild`
  (or `stop` + `rm` + `start`). `start-ssl` always recreates the container.
  → *In plain terms:* settings are baked in when a container is *created*.
  `start` on an existing container just switches it back on with its old
  settings. Change a setting → recreate the container.
- **Corporate proxy / VPN**: always use `curl --noproxy '*'` for localhost
  checks (all project scripts already do).
  → *In plain terms:* without that flag, a company proxy may intercept a request
  meant for your own machine and drop it, producing a mysterious timeout.
- **Build OOM (exit 137) under podman**: grow the VM —
  `podman machine stop && podman machine set --memory 4096 && podman machine start`.
  → *In plain terms:* OOM = "out of memory"; exit code 137 is how Linux reports
  "I killed this because it ran out of RAM". The fix gives the little Linux
  computer 4 GB instead of its default.
- **Monitoring cron**: macOS cron can silently drop a first-time install; the
  setup script re-reads the crontab to confirm it persisted (you may need to
  grant `cron` Full Disk Access in System Settings).
  → *In plain terms:* macOS security can quietly block cron. If the setup script
  says the entry did not persist, it prints the manual command to run.
- The `:Z` suffix on volume mounts is SELinux relabelling for RHEL8 — it is a
  harmless no-op on macOS.
  → *In plain terms:* you may spot `:Z` in the scripts. It is a security setting
  for the Linux server. On your Mac it does precisely nothing. Ignore it.

---

## What you have now

If you followed along, you have:

- A **container runtime** on your Mac (podman or Docker) and, with podman, a
  small Linux VM that hosts the containers.
- A local **clone** of the public Crucible repository.
- An **image** called `crucible-py:latest` — the recipe — and a running
  **container** called `crucible-py` built from it.
- The app answering at **<http://localhost:49160>** (or `https://` if you did
  §3), with its **SQLite** database in `data/crucible.db`, safely on your Mac
  rather than inside the container.
- Optionally, a **cron** job checking the app's health every five minutes.
- A verified backup in `backups/`, if you ran V6.

And the four commands that cover most days:

```bash
./container-py.sh status     # is it alive?
./container-py.sh logs       # what is it saying? (Ctrl-C to stop watching)
./container-py.sh backup     # make a safety copy
./container-py.sh stop       # switch it off
```

Starting it again tomorrow is two commands: `podman machine start`, then
`./container-py.sh start`.

---

## Troubleshooting

Each entry is: the literal message — the cause — the fix.

**`✗ The podman machine VM is not running (state: stopped)`** — the little Linux
VM that hosts your containers is switched off, usually because you rebooted —
run `podman machine start`, then repeat your command.

**`✗ Neither podman nor docker found. Install one, or set CONTAINER_RUNTIME.`** —
no container runtime is installed, or it is installed but not on your PATH — go
back to [§1](#1-prerequisites) and install podman; if it is definitely installed,
close and reopen the Terminal so it re-reads your PATH.

**`command not found: brew`** — Homebrew is not installed — install it from
[brew.sh](https://brew.sh), then reopen the Terminal.

**`curl: (7) Failed to connect to localhost port 49160: Connection refused`** —
nothing is listening on that door; the container is stopped or was never created
— run `./container-py.sh status`, then `./container-py.sh start`.

**`curl: (60) SSL certificate problem: self-signed certificate`** — you asked
`curl` to verify an ID card that nobody official signed — add `-k`, which is
correct and expected for a development certificate.

**`curl` returns nothing, no error, exit code 0** — you probed `http://` on a
container running HTTPS (or vice versa) — run `./container-py.sh status`, which
detects the mode and probes the right one.

**`⚠ Existing container is published on 49160, not 8080.`** — you changed
`CRUCIBLE_PORT` but `start` reused the old container with its old settings — run
`./container-py.sh rebuild`.

**`✗ SSL certificates not found in .../certs/`** — `start-ssl` needs both
`certs/server.crt` and `certs/server.key`, and at least one is missing — run
`./setup-ssl.sh` to generate a self-signed pair.

**`✗ Failed to build image` with exit code 137** — the build ran out of memory
inside the podman VM — `podman machine stop && podman machine set --memory 4096 && podman machine start`,
then build again.

**`✗ API did not answer within 60s — check: ./container-py.sh logs`** — the
container started but the app inside failed, most often a port clash or a corrupt
database file — run `./container-py.sh logs` and read the last ~20 lines; the
real error is there.

**`✗ Cron entry did not persist.`** — macOS blocked the crontab write — grant
`cron` Full Disk Access in System Settings → Privacy & Security, or paste the
manual command the script prints.

**Browser: "Your connection is not private" / `NET::ERR_CERT_AUTHORITY_INVALID`** —
your self-signed certificate, behaving exactly as designed — click **Advanced**,
then **Proceed to localhost (unsafe)**. On `localhost` this is safe.

**A wall of red-and-yellow text during the build** — almost always ordinary
progress and deprecation chatter, not failure — the only verdict that counts is
the last line: `✓ Image built successfully` or `✗ Failed to build image`.

---

**See also:** [macOS Uninstall](UNINSTALL-MACOS.md) ·
[Full deployment guide](../DEPLOYMENT.md) · [Project README](../README.md)

**Last Updated:** August 6, 2026

---

**Next:** [Uninstall guide](UNINSTALL-MACOS.md) — how to cleanly remove
everything when you're done, and which two things you can never get back.
