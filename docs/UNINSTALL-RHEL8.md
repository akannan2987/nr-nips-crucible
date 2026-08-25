[← README](../README.md) · [All docs in order](../README.md#the-documentation-in-order) · [Glossary](GLOSSARY.md)

# RHEL8 Uninstall — Crucible: Pandora Toolbox Enhancement (v2.0)

**Prerequisites:** SSH access to the RHEL8 VM, a second machine to copy the backup to, and about 20 minutes.
**Learning goal:** after this guide you will understand what a server deployment actually leaves lying around — containers, images, cron entries, systemd units, firewall rules, lingering — and how to remove each one deliberately rather than hopefully.
**Time:** ~20 minutes, most of it the backup.

How to cleanly remove Crucible from the **RHEL8 VM** (rootless podman).
Companion documents: [RHEL8 Install & Run](INSTALL-RHEL8.md) ·
[macOS Uninstall](UNINSTALL-MACOS.md).

> The dedicated `uninstall.sh` script (repo root) does most of the work and is
> the same script used on macOS. The full uninstall/reinstall runbook lives in
> **[DEPLOYMENT.md → Uninstall and reinstall](../DEPLOYMENT.md#uninstall-and-reinstall)**.

> ### How to read this doc
>
> **Every command runs on the RHEL8 VM**, over **SSH**
> ([glossary](GLOSSARY.md#the-container-words)) — except the one in section 1
> that deliberately runs on your *other* machine, which is flagged where it
> appears. Confuse the two and you will copy a backup from the VM to the VM,
> which achieves nothing at all.
>
> - Grey boxes are commands; `# hashed lines` inside them are comments the
>   shell ignores.
> - `<vm-hostname>`, `<your-user>`, `<cert-store-path>`, `<stamp>` are
>   **placeholders** — substitute your real values, brackets and all.
> - **You should see:** the literal expected output. **What it means:** one
>   plain sentence. **If instead:** the plausible ways it goes wrong.
> - Verification commands in section 5 carry their expected output as an
>   inline `# → …` comment on the same line.
>
> **Unlike the install guide, parts of this one are irreversible.** Read section
> 1 before running anything. It is not there for form's sake.

## Table of Contents

- [What you cannot get back](#what-you-cannot-get-back)
- [1. Before you start](#1-before-you-start)
- [2. Preview first (always safe)](#2-preview-first-always-safe)
- [3. Choose an uninstall mode](#3-choose-an-uninstall-mode)
- [4. Manual cleanup the script does not do](#4-manual-cleanup-the-script-does-not-do)
- [5. Verify removal](#5-verify-removal)
- [6. Reinstalling later](#6-reinstalling-later)

---

## What you cannot get back

Almost everything here is replaceable. Three things are not, and it is worth
knowing which is which before you type anything.

**Recoverable from the repository** — source code, scripts, the container
image, the built frontend. A `git clone` restores all of it exactly. Deleting
these costs you a rebuild and nothing else.

**Recoverable from the corporate certificate store** — `certs/server.crt` and
`certs/server.key`, re-copied by `setup-after-clone-py.sh`. Costs you five
minutes, assuming you still have read access to the store.

**Gone for good unless you act first:**

1. **Your data.** The SQLite database ([glossary](GLOSSARY.md#the-data-words))
   in `data/` — every chemical, sample, screening result, and toxicology
   record anyone has entered. `--full` deletes it. It takes a safety copy
   first, but that copy sits on the same VM, and a VM that is being
   decommissioned takes its safety copies with it.
2. **`.env.local`.** Three lines: `CERT_SOURCE`, optionally `CERT_HOSTNAME`,
   and `USE_HTTPS=true`. It is untracked by design, so no clone will ever bring
   it back and no repository holds a copy. Write the three lines down somewhere
   outside the VM before you start. (Section 6 shows what to recreate.)
3. **Your accumulated backups.** `backups/` is deleted by `--full` along with
   the rest of the project folder — including, if you are unlucky, the very
   backups you were relying on.

The section below deals with all three. It is short.

## 1. Before you start

**Time:** ~5 minutes, and by far the best-spent five minutes in this document.

This is a **production** machine — take a final data backup and copy it to
**another machine you trust** (e.g. your Mac) first, so the data survives even
if the VM itself is later wiped or decommissioned:

The emphasis on *another machine* is the whole point. A backup that lives only
on the machine you are dismantling is not a backup; it is a copy waiting to be
deleted alongside the original. The rule is older than computers: a backup is
only a backup once it is somewhere else.

```bash
# 1. On the VM: take a consistent snapshot
./container-py.sh backup                      # → backups/crucible-<stamp>.db
```

**Backup** ([glossary](GLOSSARY.md#the-data-words)) — a copy of the database
taken at a single consistent instant, using SQLite's online-backup mechanism
so it is coherent even though the app is still running. (Copying the database
file with `cp` while the app is writing to it can catch it mid-sentence; the
result usually opens fine and is quietly corrupt, which you discover at the
worst possible moment. Use the script.)

**You should see:**

```
✅ Backup written: backups/crucible-20260824-145533.db (4.2 MB)
```

**What it means:** you have a restorable snapshot. Note the `<stamp>` — the
timestamp in the filename — because you need it for the next command. `ls -lh backups/`
lists them if you lose track.

**If instead:** `Error: no container with name or ID "crucible-py"` — the
container is already stopped or gone. Start it (`./container-py.sh start-ssl`),
take the backup, then continue. If it cannot be started at all, copy the whole
`data/` folder off the machine instead and sort it out later; an imperfect copy
beats none.

**If instead:** a 0-byte file — something went wrong. Do not proceed. Check
`ls -lh data/` for a database of plausible size.

```bash
# 2. From your OTHER machine (e.g. your Mac), pull the backup off the VM:
scp <your-user>@<vm-hostname>:/path/to/crucible/backups/crucible-<stamp>.db ~/
```

**This one runs on your laptop, not the VM.** Open a new terminal window on
your own machine and run it there.

**scp** — *secure copy*: `cp` that reaches across the network, using the same
SSH login you already have. The shape is `scp source destination`, and the
`user@host:` prefix marks whichever side is remote. Here the source is remote
(the VM's `backups/` folder) and the destination is local (`~/`, your home
directory).

**You should see:**

```
crucible-20260824-145533.db                   100% 4302KB   9.1MB/s   00:00
```

**What it means:** the file is now on your laptop. Confirm it with
`ls -lh ~/crucible-*.db` and compare the size against what the VM reported. Now
your data survives the VM.

**If instead:** `No such file or directory` — the remote path is wrong.
Replace `/path/to/crucible` with the real checkout path; run `pwd` on the VM
inside the project folder to get it.

**If instead:** `Permission denied (publickey,password)` — the same
credentials that work for `ssh` work here; check the username and hostname.

**If instead:** `ssh: Could not resolve hostname` — your laptop cannot see the
internal name. You may need the corporate VPN.

Note: `--full` also takes an automatic last backup to
`~/crucible-backups/crucible-final-<stamp>.db` before deleting `data/` — a
safety net so a full uninstall can never destroy data irreversibly. But that
copy lives **on the VM itself**; it does not replace the off-machine copy
above.

Treat that automatic backup as a seatbelt, not a parachute. It saves you from a
mistyped command five minutes later. It saves you from nothing at all once the
VM is gone.

**And write down `.env.local` now**, while it still exists:

```bash
cat .env.local
```

**You should see** your three lines back:

```
CERT_SOURCE=<cert-store-path>
CERT_HOSTNAME=<vm-hostname>
USE_HTTPS=true
```

**What it means:** that is the entire irreplaceable configuration of this
machine. Paste it somewhere you will still have after the VM is decommissioned
— a password manager, a note, an email to yourself. Section 6 recreates it from
exactly these lines.

---

## 2. Preview first (always safe)

**Time:** ~1 minute. Skipping this saves you sixty seconds and can cost you a
morning.

```bash
./uninstall.sh --dry-run
# Lists exactly what would be removed — including any systemd user unit
# (~/.config/systemd/user/container-crucible-py.service), Quadlet file
# (~/.config/containers/systemd/crucible-py.container), and legacy system
# unit. Makes NO changes.
```

**Dry run** — a rehearsal. The script does every bit of its thinking, finds
everything it would touch, prints the list, and then deliberately does nothing.
Reading that list is how you catch the surprise (a second checkout, a cron entry
someone else added, a PostgreSQL container you forgot about) *before* it becomes
a problem rather than after.

The three things it looks for are the server-only pieces the install created:

**systemd user unit** ([glossary](GLOSSARY.md#the-container-words)) — a recipe
card in your personal copy of the machine's start-up manager, telling it to
start the container at boot. A file at
`~/.config/systemd/user/container-crucible-py.service`.

**Quadlet file** ([glossary](GLOSSARY.md#the-container-words)) — the newer,
shorter way of writing that same recipe: a `.container` file that podman
translates into a real unit at boot. A file at
`~/.config/containers/systemd/crucible-py.container`. You will have one or the
other, rarely both.

**Legacy system unit** — an older arrangement where the unit lived in the
*machine-wide* systemd (`/etc/systemd/system/`) rather than your personal one,
and needed `sudo` to touch. Present only on VMs set up before the rootless
approach; the script checks in case yours is one.

**You should see:**

```
DRY RUN — no changes will be made
[would remove] container: crucible-py
[would remove] image: localhost/crucible-py:latest
[would remove] cron entries: 3 matching (monitor.sh, cert-expiry-check.sh, backup)
[would remove] logs: /tmp/crucible-monitor.log, ~/crucible-cert.log, ~/crucible-backup.log
[would remove] certs/
[would remove] systemd user unit: ~/.config/systemd/user/container-crucible-py.service
[keep] data/  (use --full to remove)
```

**What it means:** exactly this list, and nothing else, is what a real run
would touch. Read it line by line. Anything you did not expect is worth
understanding before you continue.

**If instead:** it lists a container or unit name you do not recognise — stop
and find out what it is. Somebody may have deployed something else here.

**If instead:** `[would remove]` lines for cron entries you did not install —
that is normal if a colleague set up the nightly backup. Confirm with them.

**If instead:** the list is empty — Crucible is already uninstalled, or you are
in the wrong folder. `pwd`.

---

## 3. Choose an uninstall mode

**Time:** 2–5 minutes to run.

```bash
./uninstall.sh              # interactive (default): y/N prompt for most steps
                            # (note: rootless systemd/Quadlet units are removed WITHOUT a prompt)
./uninstall.sh --partial    # no prompts — keeps source code and data/
./uninstall.sh --full       # removes EVERYTHING, including data and the project folder
./uninstall.sh --help
```

Pick one; they are alternatives, not a sequence.

- **No flag (interactive)** — the script asks before most steps, so you can say
  no to individual pieces. The safe default when you are not certain what you
  want. Note the parenthesis: the systemd and Quadlet units are removed
  *without* asking, because leaving a start-up recipe pointing at a container
  that no longer exists produces failing units at every boot and confuses
  everyone who inherits the machine.
- **`--partial`** — the everyday choice. Removes the *running* parts and leaves
  the *irreplaceable* parts. Use it when you intend to reinstall: rebuilding
  from a clean image while keeping your data intact.
- **`--full`** — decommissioning. Removes the data and the project folder too.
  Only after section 1's off-machine backup.
- **`--help`** — prints the options and exits, changing nothing.

**`y/N` prompts:** the capital letter is the default, so pressing Enter alone
means *No*. To agree, type `y` and press Enter.

What each mode removes:

| Removed | `--partial` | `--full` |
|---|---|---|
| `crucible-py` container + image (and dangling images) | ✅ | ✅ |
| All crucible cron entries (`monitor.sh`, `cert-expiry-check.sh`, nightly backup) | ✅ | ✅ |
| Their logs (`/tmp/crucible-monitor.log`, `~/crucible-cert.log`, `~/crucible-backup.log`) | ✅ | ✅ |
| `certs/` directory | ✅ | ✅ |
| `client/node_modules`, `client/dist`, `backend/.venv`, Python caches | ✅ | ✅ |
| Base images (`python:3.12-slim`, `node:18-alpine`) | ❌ kept | ✅ (re-downloaded on next build) |
| systemd user unit + Quadlet file (with `daemon-reload`) | ❌ | ✅ |
| `data/` (SQLite DB) and `backups/` | ❌ kept | ✅ (after a final safety backup to `~/crucible-backups/`) |
| The whole project directory | ❌ kept | ✅ (separate "Are you absolutely sure?" confirmation) |

Reading the table:

- **Container + image** — the container is the running instance, the image is
  the recipe it was made from. **Dangling images** are leftover intermediate
  layers from previous builds, belonging to nothing and quietly occupying
  gigabytes; removing them is pure gain.
- **Cron entries** ([glossary](GLOSSARY.md#the-container-words)) — the alarm
  clock's list of scheduled commands. Removing the app without removing these
  leaves alarms firing every five minutes at an app that no longer exists,
  filling logs with failures forever. Both modes clean them up.
- **`node_modules`, `dist`, `.venv`, caches** — downloaded libraries and build
  output. Large, entirely regenerable, never worth keeping.
- **Base images** — `python:3.12-slim` and `node:18-alpine`, the foundations
  our image is built on top of. `--partial` keeps them so your next build is
  fast; `--full` removes them, and the next build re-downloads them.
- **`daemon-reload`** — after deleting a unit file you must tell systemd to
  re-read its recipe box, or it keeps acting on the copy it memorised. The
  script does this for you.
- **The separate "Are you absolutely sure?"** — deleting the project directory
  is the one step that cannot be walked back, so it is confirmed on its own
  even in `--full`.

> **A reinstall does not bring these back.** `./setup-after-clone-py.sh` rebuilds
> the container image, which is all the *application* needs. It does not recreate
> `backend/.venv` (only needed for running tests) or `client/node_modules` (only
> needed for frontend development) — recreate those by hand if you want them. See
> [Why this project has no virtual environment](GLOSSARY.md#the-container-words).


**You should see** from `--partial`:

```
==> Stopping and removing container crucible-py ... done
==> Removing image localhost/crucible-py:latest ... done
==> Removing 4 dangling images ... done
==> Removing crucible cron entries (3) ... done
==> Removing logs ... done
==> Removing certs/ ... done
==> Removing build artifacts ... done
==> Keeping data/ and backups/ (use --full to remove)
✅ Uninstall (partial) complete.
```

**What it means:** the running deployment is gone; your data and source remain.
Go to section 5 and verify.

**If instead:** `Error: container is in use` — something is still holding it.
`./container-py.sh stop` first, then re-run.

**If instead:** `image is in use by container` — a container (perhaps
`crucible-db`) still references it. Section 4 handles the PostgreSQL leftovers.

**If instead:** the script exits immediately with a usage message — you
mistyped a flag. They take two leading dashes.

> 💡 Certs can be re-copied from the corporate store afterwards via
> `./setup-after-clone-py.sh` (needs `.env.local` — see
> [INSTALL-RHEL8.md §3](INSTALL-RHEL8.md#3-https-with-corporate-certificates)).
>
> Which is the whole reason `certs/` can be deleted without ceremony: the
> certificate ([glossary](GLOSSARY.md#the-web-and-api-words)) and its private
> key are copies, and the corporate store still holds the originals. Provided,
> of course, that you still have `.env.local` telling you *where* that store is
> — section 1 again.

---

## 4. Manual cleanup the script does not do

**Time:** ~5 minutes, and mostly optional.

`uninstall.sh` handles the container, images, cron entries, logs, and rootless
systemd units. What remains manual:

Three things are left to you, each for a deliberate reason: one because it
would delete data, one because it needs `sudo`, and one because removing it is
usually wrong.

### 4.1 PostgreSQL artifacts

```bash
# ESSENTIAL after --full: your shell is standing in the folder that was just
# deleted, and podman refuses to start from a directory that no longer exists.
cd ~

# PostgreSQL artifacts (only if you ever used USE_POSTGRES=true — kept manual
# because removing the crucible-pgdata volume deletes PostgreSQL DATA)
podman rm -f crucible-db
podman volume rm crucible-pgdata
podman network rm crucible-net
```

**Skip this entirely unless you ran `USE_POSTGRES=true`.** The default
deployment uses SQLite and never creates any of these.

**Podman volume** ([glossary](GLOSSARY.md#the-container-words)) — a storage
locker managed by podman, living outside any container so that data survives
when containers come and go. That is exactly why it is not deleted
automatically: `podman volume rm crucible-pgdata` destroys the entire
PostgreSQL database in one command, with no prompt and no undo. Take a
PostgreSQL dump first if there is anything in it you want.

**Podman network** ([glossary](GLOSSARY.md#the-container-words)) — a private
virtual network letting containers find each other by name. `crucible-net` is
how the app container reached the database container. Harmless to leave, tidy
to remove.

`-f` on the first line is *force*: remove the container even if it is running,
rather than refusing.

**You should see** each command echo back the name it removed:

```
crucible-db
crucible-pgdata
crucible-net
```

**What it means:** all three are gone. Podman confirms a removal by printing
the name.

**If instead:** `Error: no container with name or ID "crucible-db"` — it was
never created, because you never used PostgreSQL. Nothing to do; skip the rest
of this subsection.

**If instead:** `volume is being used by container` — remove the container
first (the order above matters).

### 4.2 Firewall rule

```bash
# Firewall rule (whichever case applied at install time)
sudo firewall-cmd --permanent --remove-port=49160/tcp && sudo firewall-cmd --reload
# or: sudo iptables -D INPUT -p tcp --dport 49160 -j ACCEPT && sudo service iptables save
```

**Firewall rule** ([glossary](GLOSSARY.md#the-container-words)) — one
instruction to the doorman standing in front of the machine's numbered doors.
At install time you told it *let visitors through door 49160*; you are now
withdrawing that instruction so the door is closed again.

Use the line matching what you found in
[INSTALL-RHEL8.md §1](INSTALL-RHEL8.md#1-prerequisites-one-time-vm-setup): the
`firewall-cmd` line if firewalld was in charge, the `iptables` line if plain
iptables was, and neither if there was no firewall at all. `--remove-port`
undoes `--add-port`; `-D` (delete) undoes `-I` (insert). Both need the change
written to disk — `--reload` for firewalld, `service iptables save` for
iptables — or a reboot brings the old rule back.

This is `sudo` work, which is precisely why the script does not do it: an
uninstaller that quietly rewrites a production machine's firewall would be a
poor citizen.

**You should see** from the firewalld pair:

```
success
success
```

**What it means:** the rule is removed from the permanent configuration, and
the reload applied it to the live one. Two `success` lines, one per command.

**If instead:** `Warning: NOT_ENABLED: 49160:tcp` — the rule was not there.
Fine; nothing to remove.

**If instead:** `sudo: firewall-cmd: command not found` — firewalld is not
installed, so you were **Case C**: there was no host firewall, no rule was ever
added, and there is nothing here to remove. Skip this section entirely. Confirm
with `sudo iptables -S INPUT 2>/dev/null | grep 49160`, which should print
nothing. This is the common answer on an internal VM, and it is why external
access worked at install time without you configuring anything.

**If instead:** `FirewallD is not running` — you were Case B or Case C at
install time. Use the iptables line, or nothing.

**If instead:** `iptables: Bad rule (does a matching rule exist in that chain?)`
— same story: nothing to delete.

### 4.3 Lingering

```bash
# Lingering (uninstall.sh leaves it enabled on purpose)
sudo loginctl disable-linger $USER
```

**Lingering** ([glossary](GLOSSARY.md#the-container-words)) — permission for
your background programs to keep running after you log out. Normally the
machine tidies everything of yours away when your last session ends; lingering
tells it not to. Crucible needed it so the container survived logout and
reboot.

**Leave it enabled unless you have a specific reason.** The uninstaller does,
deliberately, on the grounds that it is a *user* setting rather than a Crucible
one: another tool of yours on this VM may depend on it, and switching it off
would stop that tool with no obvious connection to what you just did. Disable
it only if you are handing the account back or you know nothing else needs it.

**You should see:** nothing at all. (Silence = success.)

**What it means:** your background programs will now stop when you log out.
Confirm with `loginctl show-user $USER | grep Linger`, which should print
`Linger=no`.

> ⚠️ **If you disable it here, you must re-enable it when you reinstall.**
> `sudo loginctl enable-linger $USER` — it is step
> [R6](#r6-re-enable-lingering). This is easy to lose, because lingering is set
> up in a section of the install guide called *"Prerequisites (one-time VM
> setup)"*, which a reinstaller reasonably treats as already done. It is not
> done any more: you undid it right here. The consequence surfaces late and
> looks unrelated — the systemd unit enables without complaint, reports
> `active (running)`, and then the app does not come back after the next
> reboot.

**If instead:** `Failed to disable linger: Interactive authentication required.`
— you dropped the `sudo`.

**If instead:** something else of yours on the VM stops working after your next
logout — this was why. Re-enable with `sudo loginctl enable-linger $USER`.

---

## 5. Verify removal

**Time:** ~2 minutes.

Each line asks a different question, and the expected answer is written beside
it. The pattern `command | grep crucible` means *run the command and show me
only the lines mentioning crucible* — so **no output is the good result**.
Silence here is not a failed command; it is the absence of what you removed.

```bash
cd ~                                              # ESSENTIAL — see the note below
podman ps -a | grep crucible                      # → no output
podman images | grep crucible                     # → no output
podman volume ls | grep crucible                  # → no output
podman network ls | grep crucible                 # → no output
crontab -l | grep -iE 'crucible|monitor.sh|cert-expiry' # → no output
ls ~/crucible-cert.log ~/crucible-backup.log 2>/dev/null # → no output
systemctl --user list-units | grep crucible       # → no output
ss -tlnp | grep 49160                             # → no output
sudo firewall-cmd --list-ports 2>/dev/null        # → 49160/tcp gone (if firewalld)
ls ~/crucible-backups/                            # final data backup, if you ran --full
```

> ### Two results that look like failures but aren't
>
> **`error getting current working directory: No such file or directory`** —
> you skipped the `cd ~`. After `--full`, the project folder you were standing
> in no longer exists, so the shell has nowhere to run commands *from*. Nothing
> is broken; podman simply refuses to start. **Every `podman` check above did
> not actually run** — the silence you are looking at is the command failing,
> not the absence of what you removed. `cd ~` and run the block again.
>
> Note that `pwd` still prints the deleted path and `ls` prints nothing, both
> without complaint: the shell remembers where it was, so it looks like an empty
> folder rather than a missing one. That is what makes this easy to miss.
>
> **`container-crucible-py.service   not-found failed failed`** — read the first
> column: `not-found` means systemd cannot find the unit file, i.e. **it was
> deleted successfully**. What lingers is only systemd's in-memory record that
> the unit failed once. Clear it:
>
> ```bash
> systemctl --user reset-failed container-crucible-py.service
> systemctl --user list-units --all | grep crucible    # → now genuinely nothing
> ```
>
> `uninstall.sh` now does this for you; older runs left the residue behind.


Line by line, what each one is actually asking:

- **`podman ps -a`** — list containers, `-a` meaning *including stopped ones*
  (plain `ps` shows only running). A stopped container is still a container and
  still holds disk space and settings, so this must be silent too.
- **`podman images`** — is the `crucible-py` image gone?
- **`podman volume ls`** — any storage lockers left? (Only relevant if you used
  PostgreSQL.)
- **`podman network ls`** — any private virtual networks left? Same caveat.
- **`crontab -l`** — print your scheduled commands. `grep -iE` is
  case-**i**nsensitive and takes an **E**xtended pattern, where `|` means *or* —
  so this catches all three crucible cron entries whatever their exact spelling.
- **`ls ~/crucible-cert.log ~/crucible-backup.log 2>/dev/null`** — do the log
  files still exist? `2>/dev/null` throws away the error stream, so that
  "No such file or directory" — which is the *desired* outcome — does not clutter
  the screen. Genuine silence means both are gone.
- **`systemctl --user list-units`** — list what your personal systemd is
  managing. Nothing crucible-shaped should remain.
- **`ss -tlnp`** — *socket statistics*: `-t` TCP, `-l` listening, `-n` numeric
  ports rather than names, `-p` which program. In plain words: *which doors are
  currently open, and who is standing behind them?* Silence means nothing is
  listening on 49160 any more. This is the strongest single check, because it
  tests reality rather than configuration.
- **`sudo firewall-cmd --list-ports`** — the doorman's remaining instructions.
  Unlike the others this one *does* print output (any other open ports); what
  matters is that `49160/tcp` is not among them. On a machine without firewalld
  it prints nothing, which is also correct.
- **`ls ~/crucible-backups/`** — the opposite of all the others: here you
  *want* output, a `crucible-final-<stamp>.db` file, if you ran `--full`. It is
  the automatic safety backup. Empty or missing after a `--full` deserves
  investigation — though if you followed section 1 you already have the real
  copy on another machine.

**If instead:** `podman ps -a` still lists `crucible-py` with status `Exited` —
the container was stopped but not removed. `podman rm crucible-py`.

**If instead:** `ss` shows something on 49160 that is not podman — another
program has taken the door since. Not your concern, but worth knowing before
you reinstall.

**If instead:** `crontab -l` reports `no crontab for <your-user>` — every entry
is gone, including any unrelated ones you had. That is expected only if
crucible's were your only entries.

**If instead:** `systemctl --user list-units` shows a unit in `failed` state —
the unit file was deleted but systemd still remembers it. Run
`systemctl --user daemon-reload` and `systemctl --user reset-failed`.

---

## 6. Reinstalling later

**Time:** ~15 minutes, plus the image build.

Nine steps, in order. R1–R5 are written out below; R6–R9 are short steps whose
detail is owned by the install guide, linked per row. Work down the list — the
order matters in three places, noted where it does.

| # | Step | Detail |
|---|---|---|
| **R1** | Find your `CERT_SOURCE` — the one value nothing can restore | [below](#r1-find-your-cert_source) |
| **R2** | Clone the private repo into the **production** folder | [below](#r2-clone) |
| **R3** | Create `.env.local` — **before** any script runs | [below](#r3-recreate-envlocal-first) |
| **R4** | `./setup-after-clone-py.sh` | [below](#r4-install) |
| **R5** | Restore the database from your backup | [below](#r5-restore-your-data) |
| **R6** | **Re-enable lingering** — section 4.3 turned it off | [INSTALL §1.3](INSTALL-RHEL8.md#13-lingering) |
| **R7** | Re-create the systemd user unit | [INSTALL §4.2](INSTALL-RHEL8.md#42-generate-and-enable-the-unit) |
| **R8** | Re-create **both** cron jobs — health monitor *and* cert-expiry | [INSTALL §4.3](INSTALL-RHEL8.md#43-health-monitoring) · [§3.4](INSTALL-RHEL8.md#34-switching-modes-and-keeping-an-eye-on-expiry) |
| **R9** | Walk the V1–V9 checklist, ending with a real reboot | [INSTALL §5](INSTALL-RHEL8.md#5-verification-checklist) |

> ### The two steps people miss
>
> **R6 and R8**, and both fail quietly.
>
> **Lingering** lives in the install guide's section 1, titled *"Prerequisites
> (one-time VM setup)"* — which a reinstaller sensibly skips as already done.
> It is not done: section 4.3 of *this* guide switched it off. Skip R6 and the
> systemd unit in R7 will enable cleanly, report `active (running)`, and then
> fail to come back after the next reboot. That is precisely what V9 tests, and
> it is the last thing you find out.
>
> **Two cron jobs were removed, not one.** The health monitor is re-created for
> you by R4's prompt; the weekly certificate-expiry check is not, and it lives
> in a different section of the install guide (§3.4, not §4). Miss it and the
> certificate expires one day with no warning having been issued.
>
> Neither produces an error. Both leave you with an app that works today.

**The firewall is conditional.** If section 4.2 found firewalld or real
iptables rules and you removed the port, re-open it now
([INSTALL §1.4](INSTALL-RHEL8.md#14-firewall)). If `firewall-cmd` was not
installed — Case C, the common answer on an internal VM — there is nothing to
re-open and no row for it here.

### R1. Find your `CERT_SOURCE`

A gate, not a task: **do you know the path to your certificate store?**

- **Yes** — carry on to R2.
- **No** — recover it *now*. R3 cannot be written without it, and R4 will
  cheerfully start the app on plain HTTP if R3 is wrong. The recovery
  procedure — where to look, how to verify a candidate is the right
  certificate, and what to do if it is gone entirely — is the callout at the
  end of [R3](#r3-recreate-envlocal-first).

It is first in the list because it is the only step here that can fail in a way
you cannot fix from this machine.

### R2. Clone

```bash
# Fresh clone of the PRIVATE repo (RHEL8 VM)
# The cd is not optional: after --full your shell is still standing in the
# deleted folder, and it must land in the PRODUCTION folder's parent — not the
# mirror's. Adjust the path if your layout differs.
cd ~/work/Pandora_toolbox
git clone https://github.com/nestle-it/nr-nips-crucible.git
cd nr-nips-crucible
pwd                                    # confirm before going further
```

**Clone** ([glossary](GLOSSARY.md#the-git-words)) — download a complete copy of
the project's source and history. This restores every tracked file exactly as it
was. What it cannot restore is anything that was never tracked — which is the
entire subject of the next block.

**You should see** the familiar `Cloning into 'nr-nips-crucible'...` followed by
object counts, then silence from `cd`.

**If instead:** `Repository not found` — an access problem in disguise; GitHub
reports private repos you cannot see as missing. Check your organisation
membership and that your Personal Access Token carries `repo` scope.

### R3. Recreate `.env.local` (FIRST)

```bash
# Recreate .env.local FIRST — a full uninstall deleted it, and without it the
# app comes up HTTP with no certificates (see INSTALL-RHEL8.md §3):
cat > .env.local <<'EOF'
CERT_SOURCE=<cert-store-path>
USE_HTTPS=true
EOF
```

**FIRST is doing real work in that comment.** `setup-after-clone-py.sh` reads
`.env.local` when it starts. Create the file afterwards and the script has
already made its decisions: no certificate store known, so no certificates
copied, so no TLS, and the app comes up on plain HTTP — apparently working,
quietly unencrypted, and reachable at a URL nobody expects. Write the file,
then run the script.

The `cat > file <<'EOF' … EOF` shape is a **heredoc**: every line between the
two `EOF` markers is written into the file verbatim. Finish with `EOF` alone on
its own line. If that feels fiddly, `vi .env.local` or `nano .env.local` and
type the two lines by hand — the result is identical.

`CERT_HOSTNAME` is absent here because it is optional: left out, the setup
script uses `hostname -f`, which on this VM already resolves to the right name.
Add it back if the certificate filenames in the store use a different spelling.

> **If you no longer know your `CERT_SOURCE`.** It is the one value a full
> uninstall destroys that no clone and no document can give back — `.env.local`
> is untracked, and every guide writes the path as `<cert-store-path>` on
> purpose. The certificate *store* itself is untouched by uninstalling (step 5
> removes only the copies inside the project), so find it again:
>
> ```bash
> sudo find /etc/pki /etc/ssl /opt -name '*.crt' -newermt '2024-01-01' 2>/dev/null | head -20
> ```
>
> Look for the directory holding a `.crt` and a matching `.key` named for this
> host. Verify before trusting it — `openssl x509 -in <file> -noout -subject -dates`
> should show your hostname and an expiry still in the future. Failing that, any
> off-machine backup of the pair works: copy the two files into a directory of
> your own and point `CERT_SOURCE` at that. **Record the path somewhere outside
> the project once you have it** — you will need it again after the next
> `--full`.

**You should see:** nothing. (Silence = success.)

**What it means:** the file exists. Confirm with `cat .env.local` — you should
get your lines back. If this is a different VM from the one you uninstalled,
the values may need updating.

**If instead:** the shell sits there showing `>` and will not return — it is
still waiting for the closing `EOF`. Type `EOF` and press Enter.

### R4. Install

```bash
./setup-after-clone-py.sh
```

One command: copies and verifies the certificates, builds the image, starts the
container in HTTPS mode, checks the API answers, and offers to install the
health-monitoring cron.

**You should see** a long build (5–15 minutes on a fresh machine — the base
images were re-downloaded if you used `--full`), then:

```
    ✅ API responded: {"chemicals": 0, "samples": 0, ...}
==> Install the health-monitoring cron job? [y/N]
```

**What it means:** the app is running — with an **empty** database, since this
is a fresh install. Zeros are correct at this point. The next command fixes
that.

**If instead:** it starts in HTTP mode — `.env.local` was missing or has a bad
`CERT_SOURCE`. Fix it and re-run.

### R5. Restore your data

```bash
# Restore data if you kept a backup
./container-py.sh restore ~/crucible-backups/crucible-final-<stamp>.db
```

Replace `<stamp>` with the real timestamp — `ls ~/crucible-backups/` shows it.
If your only copy is the one on your laptop from section 1, send it back the
way it came first: from your laptop, `scp ~/crucible-<stamp>.db <your-user>@<vm-hostname>:~/`,
then restore from `~/crucible-<stamp>.db` instead.

**You should see:**

```
⚠️  This will REPLACE the current database. Continue? [y/N] y
✅ Restored from ~/crucible-backups/crucible-final-20260824-150211.db
```

**What it means:** your data is back. Confirm it with
`curl --noproxy '*' -sSk https://localhost:49160/api/stats` — the counts should
match what the app held before the uninstall, not zeros. (`--noproxy '*'` tells
curl to bypass the corporate proxy, which would otherwise intercept a request
to your own machine and fail confusingly.)

**If instead:** `No such file or directory` — the backup path or `<stamp>` is
wrong. `ls ~/crucible-backups/`.

**If instead:** the API still shows zeros afterwards — the restore wrote the
file but the app is holding the old one. `./container-py.sh restart`, then
check again.

**The app is now running with your data.** It is not yet a deployment: nothing
restarts it after a reboot, and nothing is watching it. That is R6–R9.

### R6. Re-enable lingering

```bash
sudo loginctl enable-linger $USER
loginctl show-user $USER | grep Linger      # → Linger=yes
```

Section 4.3 of this guide turned this off. Do it **before** R7 — the unit will
enable either way, so a missing `Linger=yes` costs you nothing visible until the
reboot in R9. Why it is needed, and what to do if it refuses:
[INSTALL §1.3](INSTALL-RHEL8.md#13-lingering).

### R7. Re-create the systemd user unit

The container must be **running** for this to work — `generate systemd`
describes a container that exists.

```bash
mkdir -p ~/.config/systemd/user
podman generate systemd --new --name crucible-py --files
mv container-crucible-py.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now container-crucible-py.service
systemctl --user status container-crucible-py.service
```

You need **both** `enabled` on the Loaded line and `active (running)` on the
Active line. `active` alone means it runs today and vanishes at the next boot.
The Quadlet variant, the expected output in full, and every way this fails:
[INSTALL §4.2](INSTALL-RHEL8.md#42-generate-and-enable-the-unit).

### R8. Re-create both cron jobs

Two were removed by the uninstall. R4 offered to restore only the first.

```bash
# 1. Health monitor — let the script write the line; it fills in the
#    USER= / XDG_RUNTIME_DIR= prefix that rootless podman needs under cron.
SETUP_MONITOR=y ./setup-after-clone-py.sh

# 2. Certificate expiry — not offered by any script; add it by hand.
crontab -e
# 0 8 * * 1 cd <THIS folder, from pwd> && ./cert-expiry-check.sh >> ~/crucible-cert.log 2>&1

crontab -l | grep -iE 'monitor.sh|cert-expiry'    # → two lines, not one
./cert-expiry-check.sh                            # prove it works: exit 0 = not expiring
```

⚠️ **The cert-expiry `cd` must point at this production checkout**, the one
whose `certs/` holds the live certificate. Pointed at any other clone it finds
no certificate, treats that as nothing-wrong, and reports "OK" every Monday
without ever inspecting anything. Run `pwd` here and paste *that* path.
Details: [INSTALL §4.3](INSTALL-RHEL8.md#43-health-monitoring) (monitor) and
[INSTALL §3.4](INSTALL-RHEL8.md#34-switching-modes-and-keeping-an-eye-on-expiry)
(expiry).

### R9. Verify — V1 through V9

Run the full [V1–V9 checklist](INSTALL-RHEL8.md#5-verification-checklist). A
reinstall deserves the same verification as a first install, and arguably more,
because you now have expectations about what the numbers should say — V1's
counts should match the data you restored, not zeros.

**V9 is the one that matters here, and it requires an actual reboot.** Reboot
the VM, wait two minutes, and — *without logging in first* — run V1 and
`systemctl --user status container-crucible-py.service` from a fresh session.
Not logging in first is the whole point: it is what proves R6 took. Checking
the unit while your login session is open tells you nothing about boot.

---

**Last Updated:** August 24, 2026

---

**Next:** [RHEL8 install guide](INSTALL-RHEL8.md) — the full production setup, from packages to reboot survival.
