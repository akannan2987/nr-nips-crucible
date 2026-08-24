[← README](../README.md) · [All docs in order](../README.md#the-documentation-in-order) · [Glossary](GLOSSARY.md)

# macOS Uninstall — Crucible: Pandora Toolbox Enhancement (v2.0)

**Prerequisites:** a Mac with Crucible installed, and about 10 minutes. If you followed the [install guide](INSTALL-MACOS.md), you are ready.
**Learning goal:** after this guide you will know exactly what an uninstall destroys and what it spares, how to preview a deletion before committing to it, how to remove Crucible at three different depths, and how to prove afterwards that nothing was left behind.
**Time:** ~2 minutes for a preview, ~5 minutes for the removal itself, ~10 if you also tear out the container runtime.

> ### How to read this doc
>
> Commands go in the **Terminal** (`Cmd`+`Space`, type `Terminal`, press
> `Return`). Lines starting with `#` inside a grey box are comments, not
> commands. After each command, **You should see:** shows roughly what appears
> and **What it means:** translates it.
>
> Every technical term is defined the first time it appears — but this guide
> assumes you have met a few of them in the [install guide](INSTALL-MACOS.md).
>
> **This is the one guide in the set that deletes things.** Read the next section
> before you run anything. Then relax: the very first command you will run makes
> no changes at all.

How to cleanly remove Crucible from a **macOS** machine. Companion documents:
[macOS Install & Run](INSTALL-MACOS.md) · [RHEL8 Uninstall](UNINSTALL-RHEL8.md).

> The dedicated `uninstall.sh` script (repo root) does most of the work and is
> the same script used on RHEL8. The full uninstall/reinstall runbook lives in
> **[DEPLOYMENT.md → Uninstall and reinstall](../DEPLOYMENT.md#uninstall-and-reinstall)**.

## Table of Contents

- [Before you delete: what you cannot get back](#before-you-delete-what-you-cannot-get-back)
- [1. Preview first (always safe)](#1-preview-first-always-safe)
- [2. Choose an uninstall mode](#2-choose-an-uninstall-mode)
- [3. Manual cleanup the script does not do](#3-manual-cleanup-the-script-does-not-do)
- [4. Verify removal](#4-verify-removal)
- [5. Reinstalling later](#5-reinstalling-later)
- [What you have now](#what-you-have-now)

---

## Before you delete: what you cannot get back

Most of what an uninstall removes is replaceable. The **container**
([glossary](GLOSSARY.md#the-container-words)) — the sealed lunchbox the app runs
in — and the **image** ([glossary](GLOSSARY.md#the-container-words)) it was built
from can both be rebuilt from the source code in ten minutes. The source code
itself is a **clone** ([glossary](GLOSSARY.md#the-git-words)) of a public
repository on GitHub: delete it and you can clone it again exactly as it was.

Two things are not like that.

**1. Your data — `data/crucible.db`.**

This single file *is* the **database** ([glossary](GLOSSARY.md#the-data-words)) —
the filing cabinet holding every chemical, sample, screening result, and
toxicology record you have entered. **SQLite**
([glossary](GLOSSARY.md#the-data-words)) keeps a whole database in one ordinary
file, which is wonderfully convenient right up until you delete it. There is no
server copy, no cloud copy, no Trash-can safety net once a script removes it.
`--full` removes it.

`--full` does take a safety backup to `~/crucible-backups/` first (`~` is your
home folder), and that is genuinely useful — but it lives on the same disk, and
it will not survive you also deleting that folder later. If the data matters,
make your own copy somewhere else *now*:

```bash
./container-py.sh backup
```

**You should see:** `✓ Backup complete:` followed by a path under `backups/` and
a file size.

**What it means:** you have a consistent snapshot of the database as a single
file, taken safely while the app was running. Copy it somewhere outside the
project folder — another disk, a cloud drive, anywhere the uninstall cannot
reach.

**2. Your certificates — `certs/server.crt` and `certs/server.key`.**

The **TLS/SSL certificate** ([glossary](GLOSSARY.md#the-web-and-api-words)) is
the server's public ID card; the **private key**
([glossary](GLOSSARY.md#the-web-and-api-words)) is the secret half that proves
the card is yours. A **self-signed**
([glossary](GLOSSARY.md#the-web-and-api-words)) development pair — one you
generated yourself with `./setup-ssl.sh` — is no loss at all: regenerate it in
five seconds. But a *real* certificate issued to you by an authority cannot be
regenerated. If you lose the key, you must request a new certificate.

`certs/` is deleted by **both** `--partial` and `--full`, and offered for
deletion in interactive mode. This is why the install guide insists on a backup
kept **outside the repository**, conventionally at `~/.crucible/certs/`. If you
have one there, `certs/` is disposable and this whole section is a non-event.

Not sure whether you have that backup? Check:

```bash
ls -l ~/.crucible/certs/
```

**You should see:** either two files, `server.crt` and `server.key`, or
`No such file or directory`.

**What it means:** two files = you are covered. The error = there is no external
copy, so if `certs/` holds a real (non-self-signed) certificate, copy it out
before you go any further.

### What is safe

For completeness, here is what an uninstall does *not* endanger: your Mac's other
files, your other containers and images (only `crucible-*` names are targeted),
Homebrew itself, and the public GitHub repository — which lives on GitHub's
servers and is entirely unaffected by anything you do here.

---

## 1. Preview first (always safe)

*Time: 30 seconds.*

```bash
./uninstall.sh --dry-run
# Lists exactly what would be removed. Makes NO changes.
```

**You should see:** a banner, then `Dry Run — the following items would be
removed:` and a list where each line is marked either `✗` (present, would be
removed) or `✓` (already gone, nothing to do) — container, image, base images,
cron jobs, logs, certificates, application data with its size, backups, the
Python venv, and so on.

**What it means:** exactly what the removal will touch, with nothing yet touched.
A **dry run** is a rehearsal: the script walks its whole checklist out loud and
deletes nothing. There is no reason not to run this first, every time.

**If instead:** you get `zsh: permission denied: ./uninstall.sh` — the file has
lost its executable flag; run `chmod +x uninstall.sh` and try again.

**If instead:** you get `no such file or directory` — you are not standing in the
project folder. `cd` into it first (`cd ~/nr-nips-crucible`, or wherever you
cloned it).

---

## 2. Choose an uninstall mode

*Time: 2–5 minutes.*

```bash
./uninstall.sh              # interactive (default): y/N prompt per step
./uninstall.sh --partial    # no prompts — keeps source code and data/
./uninstall.sh --full       # removes EVERYTHING, including data and the project folder
./uninstall.sh --help
```

Run **one** of these, not all four. Which one:

- **Plain `./uninstall.sh`** — the safe default, and the right choice if you are
  unsure. It walks through nine steps and asks `(y/N)` before each. The capital
  `N` means "no" is what you get if you just press `Return` — a common Unix
  convention for "the harmless answer is the default".
- **`--partial`** — you want a clean slate to rebuild from, and you want your
  data kept. Removes the container, image, scheduled jobs, and build junk. No
  questions asked.
- **`--full`** — you are finished with this project entirely. Removes the data
  and, with a second confirmation, the project folder itself.
- **`--help`** — prints the option list and exits. Changes nothing.

What each mode removes:

| Removed | `--partial` | `--full` |
|---|---|---|
| `crucible-py` container + image (and dangling images) | ✅ | ✅ |
| All crucible cron entries (`monitor.sh`, `cert-expiry-check.sh`, nightly backup) | ✅ | ✅ |
| Their logs (`/tmp/crucible-monitor.log`, `~/crucible-cert.log`, `~/crucible-backup.log`) | ✅ | ✅ |
| `certs/` directory | ✅ | ✅ |
| `client/node_modules`, `client/dist`, `backend/.venv`, Python caches | ✅ | ✅ |
| Base images (`python:3.12-slim`, `node:18-alpine`) | ❌ kept | ✅ (re-downloaded on next build) |
| `data/` (SQLite DB) and `backups/` | ❌ kept | ✅ (after a final safety backup to `~/crucible-backups/crucible-final-<stamp>.db`) |
| The whole project directory | ❌ kept | ✅ (separate "Are you absolutely sure?" confirmation) |

Reading the table, row by row, for anyone new to the vocabulary:

- **Container + image** — the lunchbox and its recipe. "Dangling" images are
  nameless leftovers from earlier builds, taking up disk space and doing nothing.
- **Cron entries** — **cron** ([glossary](GLOSSARY.md#the-container-words)) is
  your Mac's kitchen timer for programs. Crucible may have installed up to three
  timers: a health check every five minutes, a certificate-expiry check, and a
  nightly backup. Removing the app but leaving its timers running means alarms
  going off for a kitchen that no longer exists — so they go too.
- **Their logs** — the diaries those timers wrote. `/tmp` is a scratch folder
  macOS clears on its own schedule anyway.
- **`certs/`** — see [the warning above](#before-you-delete-what-you-cannot-get-back).
- **`node_modules`, `dist`, `.venv`, caches** — downloaded libraries and build
  output. Large, tedious to regenerate, and never irreplaceable: a single
  install command brings them all back. `.venv` is the **virtual environment**
  ([glossary](GLOSSARY.md#the-container-words)), the project's private Python
  sandbox.
- **Base images** — the generic starting-point images (`python:3.12-slim`,
  `node:18-alpine`) that Crucible's own image was built on top of. `--partial`
  keeps them so your next build is fast; `--full` removes them and the next build
  re-downloads a few hundred megabytes.
- **`data/` and `backups/`** — the irreplaceable row.
- **The project directory** — the folder itself, source code and all. Asked about
  separately, because it is the one step that leaves you with nothing to run the
  other steps *from*.

> **A reinstall does not bring these back.** `./setup-after-clone-py.sh` rebuilds
> the container image, which is all the *application* needs. It does not recreate
> `backend/.venv` (only needed for running tests) or `client/node_modules` (only
> needed for frontend development) — recreate those by hand if you want them. See
> [Why this project has no virtual environment](GLOSSARY.md#the-container-words).


**You should see:** in interactive mode, a run of `Step 1: Stop Container`
through `Step 9: Remove Project Directory`, each with a `? … (y/N)` prompt and
then either `✓` (done) or `↳ Skipped (not found)`. It ends with a
`✅ Cleanup Complete!` banner.

**What it means:** `Skipped (not found)` is not an error — it means that item was
already absent. On a partly-installed machine you will see several of these, and
that is a clean result.

> 💡 Keep a copy of real certificates **outside** the repo
> (e.g. `~/.crucible/certs/`) — `certs/` is deleted by both `--partial` and
> `--full`, and offered for deletion in interactive mode.

---

## 3. Manual cleanup the script does not do

*Time: 2–5 minutes. Entirely optional — in likely order of how much you will
care.*

`uninstall.sh` handles the container, images, cron entries, and logs. What
remains manual:

Everything below is deliberately left to you, because each item is either shared
with other software or destroys data the script has no mandate to touch. Skip any
line that does not apply — most people can skip all of them.

**Most likely to matter: your own backups.** The script never deletes
`~/crucible-backups/`, including the safety copy `--full` puts there. That is on
purpose. Keep it, move it somewhere safer, or delete it yourself once you are
certain you are done.

**If you ever used PostgreSQL** (you would know — it means you ran
`USE_POSTGRES=true` at some point):

```bash
# PostgreSQL artifacts (only if you ever used USE_POSTGRES=true — kept manual
# because removing the crucible-pgdata volume deletes PostgreSQL DATA)
podman rm -f crucible-db
podman volume rm crucible-pgdata
podman network rm crucible-net
```

**You should see:** each command echoes back the name it removed —
`crucible-db`, `crucible-pgdata`, `crucible-net`.

**What it means:** a **volume** is a container-managed storage area, the runtime's
own alternative to keeping data in a folder on your Mac. `crucible-pgdata` holds
the entire PostgreSQL database, so that middle command is as irreversible as
deleting `data/crucible.db` — which is precisely why the script refuses to do it
for you. A **network** is a private virtual wire between containers; removing it
affects nothing else.

**If instead:** `Error: no such container: crucible-db` — you never used
PostgreSQL. Nothing to clean. Move on.

**If you want the container runtime gone as well** — worth it only if Crucible
was the only thing you used it for:

```bash
# Podman VM / runtime itself (only if you want it fully gone)
podman machine stop && podman machine rm
brew uninstall podman          # or: brew uninstall --cask docker
```

**You should see:** from `podman machine rm`, a confirmation prompt listing the
VM files it will delete, then removal; from `brew uninstall`, a short
`Uninstalling /opt/homebrew/…` line.

**What it means:** the first command deletes the small Linux virtual machine
(**podman machine**, [glossary](GLOSSARY.md#the-container-words)) that hosted
your containers, freeing several gigabytes. The second removes podman itself.
**Any other containers you had are inside that VM and go with it** — so check
`podman ps -a` first if you use containers for anything else.

(Substitute `docker` for `podman` in the container commands if you used Docker.)

There is no launchd integration and no firewall/systemd configuration on macOS
— monitoring is plain user cron, so nothing else to clean.

(**launchd** is the macOS equivalent of a service manager, and **systemd** is the
Linux one — the RHEL8 server uses systemd, this Mac uses neither. Crucible's only
scheduled work on a Mac is the cron timers from the table above, and
`uninstall.sh` already removed those.)

---

## 4. Verify removal

*Time: 1 minute.*

Trust, then verify. Each of these looks for a trace of Crucible; the expected
answer is written beside it as a comment. Run them all — the whole block can be
pasted at once.

```bash
podman ps -a | grep crucible     # → no output
podman images | grep crucible    # → no output
crontab -l | grep -iE 'crucible|monitor.sh|cert-expiry' # → no output
ls ~/crucible-cert.log ~/crucible-backup.log 2>/dev/null # → no output
lsof -i :49160                   # → no output
ls ~/crucible-backups/           # final data backup, if you ran --full
```

**You should see:** nothing from the first five lines. From the last one, either
a filename like `crucible-final-20260824-101500.db`, or
`No such file or directory` if you never ran `--full`.

**What it means:** total silence is a complete removal. (Silence = success — a
very Unix habit.) Line by line, each command asks a different question:

- `podman ps -a` lists **all** containers, running or stopped (`-a` = all);
  `grep crucible` keeps only lines mentioning Crucible. No lines = no container.
- `podman images` does the same for images (recipes).
- `crontab -l` **l**ists your scheduled timers; the pattern catches all three
  Crucible jobs. No lines = no orphaned alarms.
- `ls` on the two log files — `2>/dev/null` throws away the "not found"
  complaints, so this line prints something only if a log actually survived.
- `lsof -i :49160` asks who is holding **port**
  ([glossary](GLOSSARY.md#the-web-and-api-words)) 49160 — the numbered door
  Crucible used. Nobody = the app is truly stopped, not merely hidden.

**If instead:** `podman ps -a` still shows `crucible-py` — the container was
stopped but not removed. `podman rm crucible-py` finishes the job.

**If instead:** `crontab -l` prints `crontab: no crontab for <you>` — that is the
strongest possible pass. It means you have no scheduled jobs at all.

**If instead:** `lsof -i :49160` names a process — either the container is still
running (`./container-py.sh stop`), or some unrelated program has since claimed
that door, which is harmless.

**If instead:** every `podman` command answers
`Cannot connect to Podman` — you already removed the podman machine in §3. The
containers went with it; there is nothing left to check.

---

## 5. Reinstalling later

*Time: ~10 minutes, same as a first install.*

Nothing about the uninstall makes a reinstall harder. The project is a public
repository; you simply clone it again.

```bash
# Fresh clone of the PUBLIC repo (macOS)
git clone https://github.com/akannan2987/nr-nips-crucible.git
cd nr-nips-crucible
./setup-after-clone-py.sh
```

**You should see:** the same five-step setup run as the first time, ending in
`✅ Python backend setup complete!`.

**What it means:** you are back where you started. If you removed the base images
with `--full`, this build will be slow again (5–10 minutes) because it
re-downloads them; if you used `--partial`, it will be noticeably quicker.

```bash
# Restore data if you kept a backup
./container-py.sh restore ~/crucible-backups/crucible-final-<stamp>.db
```

**You should see:** the app stop, the database swap, the app restart, and
`✓ Restored crucible-final-<stamp>.db → data/crucible.db`.

**What it means:** your records are back. Replace `<stamp>` with the real
date-and-time in the filename — run `ls ~/crucible-backups/` to read it off, and
type the full name rather than guessing.

**If instead:** `✗ Backup file not found` — the path or the stamp is wrong. List
the folder and copy the exact filename.

And if you had a real certificate backed up outside the repo, HTTPS comes back
with a copy and a restart — see
[INSTALL-MACOS.md §3, Option B](INSTALL-MACOS.md#3-enable-https).

Full instructions: [INSTALL-MACOS.md](INSTALL-MACOS.md).

---

## What you have now

Depending on the mode you chose:

- **After `--partial`:** no container, no image, no scheduled jobs, no
  certificates — but your source code and, crucially, your `data/` and
  `backups/` are exactly as they were. One `./setup-after-clone-py.sh` away from
  running again, with all your records intact.
- **After `--full`:** Crucible is gone from this Mac, apart from the safety
  backup in `~/crucible-backups/` and anything you deliberately copied out. The
  public repository on GitHub is untouched and always re-clonable.
- **After interactive mode:** exactly the steps you said `y` to. Run
  `./uninstall.sh --dry-run` again to see precisely what is left — it is still
  the safest command in this guide.

---

**Last Updated:** August 8, 2026

---

**Next:** [Install guide](INSTALL-MACOS.md) — start over from a clean Mac, now
that you know exactly what gets created and where it lives.
