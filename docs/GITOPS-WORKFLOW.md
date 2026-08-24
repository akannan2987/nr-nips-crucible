[← README](../README.md) · [All docs in order](../README.md#the-documentation-in-order) · [Glossary](GLOSSARY.md)

# GitOps Workflow - Crucible: Pandora Toolbox Enhancement (v2.0)

How to make changes to this project across **two repositories** and **two machines**
without leaking internal data into the public mirror.

Every command below is labelled with **which machine and which folder** it runs in.
Start at section 2 if you are setting up a machine for the first time.

## Table of Contents

- [1. The two repositories](#1-the-two-repositories)
- [2. One-time setup](#2-one-time-setup)
  - [2.1 Mac - the authoring folder](#21-mac---the-authoring-folder)
  - [2.2 VM - the mirror folder](#22-vm---the-mirror-folder)
  - [2.3 VM - the production folder](#23-vm---the-production-folder)
- [3. Golden rules](#3-golden-rules)
- [4. Flow A - a change from start to finish](#4-flow-a---a-change-from-start-to-finish)
- [5. Flow B - a fix discovered on the VM](#5-flow-b---a-fix-discovered-on-the-vm)
- [6. Checking the two repos are in sync](#6-checking-the-two-repos-are-in-sync)
- [7. Why the histories differ, and why that is fine](#7-why-the-histories-differ-and-why-that-is-fine)

---

## 1. The two repositories

| | **Private** | **Public** |
|---|---|---|
| URL | `github.com/nestle-it/nr-nips-crucible` | `github.com/akannan2987/nr-nips-crucible` |
| Role | Source of truth; deployment source | Sanitized mirror (AI assistance, sharing) |
| History | Full, real | Short, starts from a clean snapshot |
| Real lab data | Yes - tracked, appropriately | **Never** |
| Internal hostnames / usernames | Yes, in older commits | **Never** |

Three folders, each with a fixed purpose:

| # | Machine | Folder | `origin` remote | Extra remote | Purpose |
|---|---------|--------|-----------------|--------------|---------|
| 1 | Mac | `~/Documents/Work/pandora_toolbox/nr-nips-crucible` | **public** | none | Write and test changes |
| 2 | VM | `~/crucible-mirror` | **private** | `public` (fetch only) | Copy content public -> private |
| 3 | VM | `~/work/Pandora_toolbox/nr-nips-crucible` | **private** | none | Run the live application |

> **One remote per purpose.** The Mac folder has no private credentials, so it
> *cannot* accidentally push to the private repo. The production folder never
> touches the public repo. Only the mirror folder sees both - and it only ever
> **fetches** from public, never pushes to it.

---

## 2. One-time setup

Do this once per machine. Skip any folder that already exists.

### 2.1 Mac - the authoring folder

```bash
# ▶ MAC
cd ~/Documents/Work/pandora_toolbox
git clone https://github.com/akannan2987/nr-nips-crucible.git
cd nr-nips-crucible
git switch develop

# Confirm: origin must be the PUBLIC repo, and nothing else
git remote -v
```

Expected:

```
origin  https://github.com/akannan2987/nr-nips-crucible.git (fetch)
origin  https://github.com/akannan2987/nr-nips-crucible.git (push)
```

Then set the app up locally - see [INSTALL-MACOS.md](INSTALL-MACOS.md).

### 2.2 VM - the mirror folder

This is the folder that moves content from the public repo into the private one.
It is **not** the production folder and never runs the application.

```bash
# ▶ VM
cd ~
git clone https://github.com/nestle-it/nr-nips-crucible.git crucible-mirror
cd ~/crucible-mirror
git switch develop

# Add the PUBLIC repo as a second remote named "public".
# This is the step that makes `git fetch public` work later.
git remote add public https://github.com/akannan2987/nr-nips-crucible.git
git fetch public

# Confirm both remotes are present
git remote -v
```

Expected:

```
origin  https://github.com/nestle-it/nr-nips-crucible.git (fetch)
origin  https://github.com/nestle-it/nr-nips-crucible.git (push)
public  https://github.com/akannan2987/nr-nips-crucible.git (fetch)
public  https://github.com/akannan2987/nr-nips-crucible.git (push)
```

> Git adds `public` for both fetch and push, but **never push to it from here.**
> This folder contains the private history; pushing it to the public repo would
> publish the internal hostname, your corporate username, and the real lab data
> that older commits still contain. Treat `public` as fetch-only.
>
> If the VM cannot reach the public repo (corporate proxy), see
> [section 5](#5-flow-b---a-fix-discovered-on-the-vm) for the offline patch route.

### 2.3 VM - the production folder

This is the running deployment; it almost certainly already exists.

```bash
# ▶ VM
cd ~/work/Pandora_toolbox/nr-nips-crucible     # adjust to your actual path
git remote -v                                  # must show ONLY the private repo
```

If you ever need to recreate it, clone the private repo and follow
[INSTALL-RHEL8.md](INSTALL-RHEL8.md). Do **not** add a `public` remote here.

---

## 3. Golden rules

1. **Author changes on the Mac** (public checkout). Content written there is
   sanitized by construction - you use `<vm-hostname>` and `<cert-store-path>`
   placeholders, never real values.
2. **Content flows public -> private.** Never the other way through git.
3. **Never push the private repo's history to the public repo.** Publishing
   history is irreversible.
4. **Run `./check-public-safe.sh` before every public push.** Exit 0 = safe.
5. **Real values live in `.env.local`** on the VM - gitignored, never committed.
6. **Sync is selective.** The private repo legitimately holds files the public one
   must never have. Never mirror private -> public wholesale.

---

## 4. Flow A - a change from start to finish

The complete path for a normal change: you edit something on the Mac, and finish
with **both repositories' `develop`, `beta`, and `master` branches in sync** and
the VM redeployed.

### Step 1 - Make and test the change

```bash
# ▶ MAC — ~/Documents/Work/pandora_toolbox/nr-nips-crucible
git switch develop
git pull --ff-only origin develop        # start from the latest

# ... edit files ...

cd backend && .venv/bin/pytest && cd ..  # tests must pass
./container-py.sh rebuild                # run it for real
curl --noproxy '*' -sS http://localhost:49160/api/stats
```

### Step 2 - Safety gate

```bash
# ▶ MAC
./check-public-safe.sh
```

Must print **`✓ SAFE TO PUSH`**. If it fails, fix what it lists - do not continue.

### Step 3 - Commit

```bash
# ▶ MAC
git add -A
git status                               # review before committing
git commit -m "<what changed>"
```

### Step 4 - Push to the public repo (all three branches)

```bash
# ▶ MAC
git fetch origin                         # confirm nobody else pushed
git push origin develop develop:beta develop:master
```

This sends your local `develop` to the remote `develop`, `beta`, **and** `master` -
one commit ID across all three, fast-forward, no merge commits.

### Step 5 - Level your local master

```bash
# ▶ MAC
git switch master
git pull --ff-only origin master
git switch develop
```

### Step 6 - Copy the content into the private repo

```bash
# ▶ VM — ~/crucible-mirror
cd ~/crucible-mirror
git switch develop
git fetch origin && git status           # expect "up to date with origin/develop"
git fetch public                         # pull in your new public commit

git checkout public/develop -- .         # copy CONTENT (note the trailing "-- .")
```

> ⚠️ The `-- .` is essential. Without it, `git checkout public/develop` switches
> you onto the public commit (detached HEAD) instead of copying files in.

### Step 7 - Review what will be committed

```bash
# ▶ VM — ~/crucible-mirror
git status
git diff --cached --summary | grep -i mode
```

Read the mode output like this:

| Line | Meaning | Action |
|------|---------|--------|
| `create mode 100644 <file>` | New regular file (docs, templates, data) | ✅ normal |
| `create mode 100755 <file>` | New **executable script** (`./name.sh`) | ✅ normal and required |
| `mode change 100755 => 100644` | An existing file **lost** its executable bit | ⚠️ fix before committing |

Only the last one is a problem. `create mode` lines just record a new file's type -
`100755` is correct for anything you run as `./something.sh`, `100644` for
everything else.

> ⚠️ If you see `mode change 100755 => 100644`, a file lost its executable bit in
> transit (this happens when files are copied or downloaded rather than cloned).
> Restore it instead of committing the change - this keeps the content change while
> fixing the permission:
> ```bash
> chmod +x <the files>
> git add <the files>
> ```
> Then re-run the mode check; the `mode change` line should be gone.

### Step 8 - Commit and push to the private repo (all three branches)

```bash
# ▶ VM — ~/crucible-mirror
git commit -m "<what changed>"
git push origin develop develop:beta develop:master
```

### Step 9 - Level the mirror's local master

```bash
# ▶ VM — ~/crucible-mirror
git switch master
git pull --ff-only origin master
git switch develop
```

At this point **both repositories are in sync on all three branches.**

### Step 10 - Deploy to production

```bash
# ▶ VM — production folder
cd ~/work/Pandora_toolbox/nr-nips-crucible
./container-py.sh backup                        # consistent snapshot → backups/
# Copy that snapshot OUT of the project folder — backups/ lives inside it
# and would be destroyed by a --full uninstall:
cp "$(ls -t backups/crucible-*.db | head -1)" ~/data-backup-$(date +%Y%m%d).db
git pull
./container-py.sh rebuild                       # preserves HTTP/HTTPS mode
curl --noproxy '*' -sSk https://localhost:49160/api/stats   # -k: the cert names the VM's FQDN, not localhost
```

> **Why not just `cp -r data`?** Because the app is still running. Copying a live
> SQLite file with `cp` can catch it mid-write and produce a file that opens
> perfectly and is quietly corrupt — the worst kind of broken backup, since you
> only discover it when you try to restore. `./container-py.sh backup` uses
> SQLite's online-backup mechanism to take a coherent snapshot while the app
> keeps serving. Always take the snapshot, then copy *that*.

### Step 11 - Confirm

```bash
# ▶ VM — ~/crucible-mirror
git diff --stat public/develop develop
```

Expect **only** the private-only files: the 6 real-data workbooks under
`docs/excel-templates/` and the old `crucible-costar-prompt.md` the private repo
kept from its earlier history (see
[section 6](#6-checking-the-two-repos-are-in-sync)).

---

## 5. Flow B - a fix discovered on the VM

Sometimes a problem only appears on the server. **Do not push from the VM to the
public repo** - the mirror folder carries the private history.

Carry the change back to the Mac as a patch instead:

```bash
# ▶ VM — with your fix applied but NOT committed
cd ~/crucible-mirror
git diff > ~/fix.patch
```

```bash
# ▶ MAC
scp <your-user>@<vm-hostname>:~/fix.patch .
git apply fix.patch
git diff                                 # review what it changed
rm fix.patch
```

Then run **Flow A from Step 1**. The fix is now authored on the Mac and travels the
normal one-way route - no exceptions to the rules.

A similar scp-based route (this time with `git bundle`) covers the opposite
problem - the VM cannot reach the public repo at all:

```bash
# ▶ MAC
git bundle create ~/crucible-develop.bundle develop
scp ~/crucible-develop.bundle <your-user>@<vm-hostname>:~/
```

```bash
# ▶ VM — ~/crucible-mirror   (use the bundle instead of the public remote)
git remote add public ~/crucible-develop.bundle     # if "public" was never added
# ...or, if §2.2 already added "public" pointing at GitHub:
git remote set-url public ~/crucible-develop.bundle
git fetch public
git checkout public/develop -- .
# To point it back at GitHub later:
# git remote set-url public https://github.com/akannan2987/nr-nips-crucible.git
```

---

## 6. Checking the two repos are in sync

```bash
# ▶ VM — ~/crucible-mirror
cd ~/crucible-mirror
git fetch origin && git fetch public
git diff --stat public/develop develop
```

**Expected:** only the private-only files - the 6 real-data workbooks under
`docs/excel-templates/` and the old `crucible-costar-prompt.md` retained from
the private repo's earlier history. That difference is correct and permanent.

**Anything else = drift.** Re-run Flow A steps 6-8 to bring them back in line.

As a plain file list:

```bash
# ▶ VM — ~/crucible-mirror
git diff --name-status public/develop develop
```

---

## 7. Why the histories differ, and why that is fine

The public repo was created from a **download** of the project, not a clone, so it
began with a fresh history. The private repo holds the complete engineering record.
The two therefore have unrelated histories - no shared ancestor - and always will.

One hard consequence follows:

> **`git push` between them is impossible without `--force`, and forcing it would
> destroy the target repo's history.** That is why we copy *content*
> (`git checkout public/develop -- .`) instead of pushing branches between them.

This is not a defect. The repositories are in sync in the way that matters - **the
sanitized content is identical** - while each keeps the history appropriate to its
purpose. What protects the public repo is the redaction and `.gitignore`, not the
short history.

If you want full history on the Mac for `git log` / `git blame`, clone the private
repo into a **separate folder** with only the private remote. Do not merge it with
the authoring folder.

---

**See also:** [Contributing](../CONTRIBUTING.md) ·
[macOS install](INSTALL-MACOS.md) · [RHEL8 install](INSTALL-RHEL8.md) ·
[Deployment reference](../DEPLOYMENT.md)

**Last Updated:** August 7, 2026
