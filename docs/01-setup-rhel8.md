[← README](../README.md) · [Handbook](HANDBOOK.md) · [Glossary](00-glossary.md)

# RHEL8 Install & Run — Crucible: Pandora Toolbox Enhancement (v2.0)

**Prerequisites:** SSH access to the RHEL8 VM, permission to install packages, git access to the private repo, and about 45 minutes.
**Learning goal:** after this guide you will understand why a server deployment differs from a laptop one — rootless containers, SELinux labels, firewalls, HTTPS with real certificates, and surviving a reboot — and you will have the app running in production.
**Time:** ~45 minutes, plus the first image build.

Step-by-step guide to install, run, and verify Crucible on the **RHEL8 VM**
(production, rootless podman, HTTPS with corporate certificates). Companion
documents: [RHEL8 Uninstall](01-uninstall-rhel8.md) ·
[macOS Install & Run](01-setup-macos.md) · [macOS Uninstall](01-uninstall-macos.md).

> **Repository for RHEL8:** clone from the **private** Nestlé repo
> `https://github.com/nestle-it/nr-nips-crucible` (requires a Personal Access
> Token over HTTPS, or an SSH key: `git@github.com:nestle-it/nr-nips-crucible.git`).
> A development machine uses the public repo instead — see
> [01-setup-macos.md](01-setup-macos.md) or [01-setup-windows.md](01-setup-windows.md).
>
> This guide uses placeholders for internal values — `<vm-hostname>` for the
> VM's FQDN and `<cert-store-path>` for the corporate certificate store. No
> internal values are hardcoded anywhere: on the VM you configure them **once**
> in an untracked `.env.local` file (section 3), or pass `CERT_SOURCE=` /
> `CERT_HOSTNAME=` as environment variables. The full runbook with
> troubleshooting is
> **[docs/07-operations.md → Runbook C](07-operations.md#runbook-c--rhel8-vm-podman)**.

> ### How to read this doc
>
> **Every command in this guide runs on the RHEL8 VM**, in a terminal you have
> opened over **SSH** ([glossary](00-glossary.md#the-container-words)) — *secure
> shell*, a way of typing into a distant machine's keyboard from your own desk.
> You log in with something like `ssh <your-user>@<vm-hostname>` and from then
> on every character you type is executed **there**, not on your laptop. If a
> command ever misbehaves, the first question is always: *am I on the VM or on
> my own machine?* (`hostname -f` answers it.)
>
> Notation used throughout:
>
> - Grey boxes are commands. Type them one at a time; do not paste a whole box
>   at once until you have read what each line does.
> - `# lines starting with a hash` inside a box are **comments** — notes for
>   humans. The shell ignores them. Pasting them is harmless.
> - Angle brackets like `<vm-hostname>` are **placeholders**: replace them,
>   brackets and all, with your real value. They are deliberately blank here
>   because the real values are internal to the company.
> - **You should see:** shows the literal output you can expect.
> - **What it means:** translates that output into one plain sentence.
> - **If instead:** covers the plausible ways a step goes sideways.
> - `$` is never part of a command — if you see one in output examples, it is
>   the shell's prompt, waiting for you.
>
> **A word about "production".** This VM is the real one. Real people open the
> app in a browser and rely on the numbers it shows them. That does not make
> the steps below dangerous — almost everything here is additive — but it does
> mean you should read each section before running it, and take the backup in
> section 6 seriously.

> **Where do all the packages go?** Nowhere on your computer. Python, FastAPI,
> RDKit and the rest live *inside* the container image, not in your system
> folders — which is why this project needs no virtual environment, and why an
> uninstall can remove every trace. If that raises questions, the glossary
> answers them in one place:
> **[Why this project has no virtual environment](00-glossary.md#the-container-words)**.

## Table of Contents

- [Before anything: what are we actually installing?](#before-anything-what-are-we-actually-installing)
- [1. Prerequisites (one-time VM setup)](#1-prerequisites-one-time-vm-setup)
- [2. Install and run](#2-install-and-run)
- [3. HTTPS with corporate certificates](#3-https-with-corporate-certificates)
- [4. Auto-start on boot and monitoring](#4-auto-start-on-boot-and-monitoring)
- [5. Verification checklist](#5-verification-checklist)
- [6. Day-2 operations](#6-day-2-operations)
- [What you have now](#what-you-have-now)
- [7. RHEL8-specific gotchas](#7-rhel8-specific-gotchas)
- [8. A second instance for user testing (beta)](#8-a-second-instance-for-user-testing-beta)

---

## Before anything: what are we actually installing?

![The same container image runs on macOS, Windows and RHEL 8; the database, certificates and settings are mounted in from the host and answers come out on port 49160](img/fig_container_lunchbox.svg)

Skip this if you already know. It costs two minutes and saves twenty.

**Crucible** is a web application for laboratory data — chemicals, samples,
screening results, toxicology. It has two halves: a **backend**
(the part that stores and calculates, written in Python) and a **frontend**
(the part you look at, written in React and rendered by your browser). Both
halves are packed into a single **container**.

**Container** ([glossary](00-glossary.md#the-container-words)) — a sealed lunchbox
holding an application plus every library it needs. It runs on your machine but
brings its own private idea of what "the filesystem" contains, so it behaves
identically on a development laptop and on this RHEL8 server. Nothing inside can see
your machine's files unless you deliberately hand a folder in.

**Image** ([glossary](00-glossary.md#the-container-words)) — the recipe-plus-
ingredients the lunchbox is packed from. You *build* an image once; you *run*
containers from it many times. Ours is called `crucible-py:latest`.

**Podman** ([glossary](00-glossary.md#the-container-words)) — the program that
builds images and runs containers. (If you have heard of Docker: podman does
the same job, with the same commands, and is what Red Hat ships.)

**Port** ([glossary](00-glossary.md#the-container-words)) — a machine has one
address but thousands of numbered doors. A program listening on a port has
claimed one door; another program can use a different door at the same time
without either noticing. Crucible uses door **49160**, and only that one.

So: we will install podman, fetch the source code, build one image, run one
container listening on port 49160, wrap it in HTTPS with real corporate
certificates, and then arrange for all of that to come back by itself after a
reboot.

---

## 1. Prerequisites (one-time VM setup)

**Time:** ~10 minutes. Everything in this section is done **once per VM**, ever.
If someone set this VM up before you, run the checks anyway — they are all
read-only until you hit a step that reports something missing.

Two things about servers that trip up everyone arriving from a laptop:

**`sudo`** — *substitute user do*. It runs one command as the machine's
administrator (`root`). On your own laptop you are effectively the
administrator all the time; on a shared server you are not, and you borrow that
power one command at a time. Every `sudo` line below may ask for your password.
Lines without `sudo` run as ordinary you.

**Rootless podman** ([glossary](00-glossary.md#the-container-words)) — containers
running as *ordinary you*, not as the administrator. Think of cooking in your
own kitchen instead of taking over the restaurant's: you can make whatever you
like, and if you set fire to a pan, only your kitchen is affected. This is the
safer default and the one we use. It has two consequences you will meet in a
moment — you cannot claim door numbers below 1024, and your containers stop
when you log out unless you ask otherwise.

### 1.1 Packages

```bash
# 1. Packages (curl/openssl are normally present already)
sudo dnf install -y git podman
podman --version                          # any 4.x / 5.x is fine
```

`dnf` is RHEL's app store, driven from the keyboard; `-y` answers "yes" to its
questions in advance. `git` fetches source code, `podman` runs containers.

**You should see:** a wall of package names scrolling past, ending in
`Complete!`, and then from the second command:

```
podman version 4.9.4
```

**What it means:** podman is installed and can talk to you. Any 4.x or 5.x
version is fine; the exact number does not matter.

**If instead:** `Nothing to do.` — the packages were already there. Perfect,
carry on.

**If instead:** `Error: This command has to be run with superuser privileges` —
you dropped the `sudo`.

**If instead:** `command not found: podman` after a successful install — log
out of the SSH session and back in, so your shell picks up the new program.

### 1.2 Rootless user namespaces (subuid/subgid)

```bash
# 2. Rootless user namespaces (normally provisioned by the podman package)
grep $USER /etc/subuid /etc/subgid        # should print a range for your user
# If missing:
#   sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 $USER
#   podman system migrate
```

**subuid / subgid** ([glossary](00-glossary.md#the-container-words)) — a block of
*pretend* user-ID numbers the system lends you. Inside its lunchbox a container
wants to have its own administrator, its own "user 0". Those pretend IDs let it
have one: the container's "root" is quietly mapped to some harmless number like
100000 on the real machine, which owns nothing and can do nothing. It is a
stage crown — convincing inside the play, worthless outside it. Without this
lending range, rootless podman cannot start containers at all.

**You should see:**

```
/etc/subuid:<your-user>:100000:65536
/etc/subgid:<your-user>:100000:65536
```

**What it means:** you have been lent 65536 pretend IDs starting at 100000.
That is all podman needs. Move on.

**If instead:** no output at all (silence) — the range is missing. Run the two
commented lines above without the leading `#`, then log out and back in, then
re-run the `grep` to confirm.

**If instead:** `grep: /etc/subuid: No such file or directory` — the file does
not exist yet; `usermod --add-subuids` creates it.

### 1.3 Lingering

```bash
# 3. Lingering — required so the container survives logout/reboot
sudo loginctl enable-linger $USER
```

**Lingering** ([glossary](00-glossary.md#the-container-words)) — normally the
machine tidies up after you: when your last login session ends, everything you
started is shut down with it. Sensible on a shared machine, catastrophic for a
server application, because closing your SSH window would take the website down
with it. `enable-linger` tells the system: *this user's programs are allowed to
stay behind after they leave.* Like paying to keep the lights on in your office
overnight.

**You should see:** nothing at all. (Silence = success.)

**What it means:** your background programs will now outlive your login. This
setting persists across reboots; you never need to run it again.

**If instead:** `Failed to enable linger: Interactive authentication required.`
— you dropped the `sudo`.

You can confirm it took effect at any time with `loginctl show-user $USER | grep Linger`,
which should print `Linger=yes`.

### 1.4 Firewall

```bash
# 4. Firewall — diagnose FIRST, then open port 49160 for the case that applies
rpm -q firewalld iptables-services
sudo iptables -L INPUT -n | head
# Case A — firewalld running:
#   sudo firewall-cmd --permanent --add-port=49160/tcp && sudo firewall-cmd --reload
# Case B — plain iptables with real rules:
#   sudo iptables -I INPUT -p tcp --dport 49160 -j ACCEPT && sudo service iptables save
# Case C — no host firewall (common on internal VMs): nothing to do.
#   Do NOT install firewalld just for this — it would impose default-deny.
```

**Firewall** ([glossary](00-glossary.md#the-container-words)) — a doorman standing
in front of all those numbered doors, deciding which ones accept visitors from
outside. Your program can be listening perfectly on door 49160 and still be
unreachable, because the doorman is turning everyone away before they knock.

**firewalld** and **iptables** are two different doormen. `iptables` is the
older one: a plain list of rules, enforced by the kernel. `firewalld` is a
management layer that sits on top and writes those rules for you. A machine may
have one, the other, or neither — hence the "diagnose first" instruction.

The first command asks the package database which doormen are even installed;
the second prints the current rule list (`head` trims it to the first ten
lines).

**You should see** one of three shapes.

*Case A — firewalld is in charge:*

```
firewalld-0.9.11-4.el8.noarch
package iptables-services is not installed
Chain INPUT (policy ACCEPT)
target     prot opt source               destination
INPUT_direct  all  --  0.0.0.0/0            0.0.0.0/0
...
```

**What it means:** the `_direct` / `_ZONES` chain names are firewalld's
fingerprints. Run the **Case A** line: it adds the rule permanently
(`--permanent` = survive reboots) and then `--reload` applies it now.

*Case B — plain iptables with real rules:*

```
package firewalld is not installed
iptables-services-1.8.5-11.el8.x86_64
Chain INPUT (policy DROP)
target     prot opt source               destination
ACCEPT     tcp  --  0.0.0.0/0            0.0.0.0/0            tcp dpt:22
```

**What it means:** rules exist and the default policy is `DROP` (turn everyone
away). Run the **Case B** line: `-I INPUT` inserts an allow-rule at the top of
the list, and `service iptables save` writes it to disk so a reboot does not
forget it.

*Case C — no doorman at all:*

```
package firewalld is not installed
package iptables-services is not installed
Chain INPUT (policy ACCEPT)
target     prot opt source               destination
```

**What it means:** an empty chain with `policy ACCEPT` = nobody is being turned
away. Common on internal VMs that sit behind a network firewall already. Do
nothing.

> ⚠️ **Do not install firewalld "to be safe".** Installing it does not add a
> single rule — it adds an entire doorman whose default instruction is *turn
> everyone away* (`default-deny`). On a working VM that means you take the
> application, and possibly your own SSH session, off the air in one command.
> If there is no firewall, that is the answer, not a problem to fix.

**If instead:** `-bash: rpm: command not found` — you are not on a RHEL-family
machine. Check `hostname -f`; you are probably still on your laptop.

### 1.5 The rest

Also required: git access to the **private** repo (PAT or SSH key), outbound
internet during the image build, and — for HTTPS — read access to the corporate
certificate store on the VM.

In plain words:

- **PAT** (Personal Access Token) — a long random password you generate on
  GitHub and use *instead of* your real password, so that a machine can fetch
  code without ever holding your actual credentials. Revocable on its own,
  which is the whole point.
- **SSH key** — the same idea in a different shape: a matched pair of files,
  one secret and one public. You hand GitHub the public half; the secret half
  never leaves the VM. Nothing to type, nothing to expire.
- **Outbound internet during the build** — building the image downloads Python
  and Node packages. After the build, the running app needs no internet at all.
- **Read access to the certificate store** — a folder on the VM where your
  organisation keeps the machine's official HTTPS credentials. Section 3.

---

## 2. Install and run

**Time:** ~5 minutes of typing, plus 5–15 minutes of watching the first build.

### 2.1 Clone the repository

```bash
# 1. Clone the PRIVATE repository
git clone https://github.com/nestle-it/nr-nips-crucible.git
cd nr-nips-crucible
chmod +x *.sh                             # first time only (all helper scripts)
```

**Clone** ([glossary](00-glossary.md#the-git-words)) — download a complete copy of
a project's source code *and its entire history*, so your copy is a full
independent replica rather than a snapshot. `cd` then walks into the new
folder. `chmod +x *.sh` marks every `.sh` script as *executable* — permission
to be run as a program rather than merely read as text. Files arriving from a
clone sometimes lack that flag, and the symptom is a baffling
`Permission denied` on a script that is plainly right there.

**You should see:**

```
Cloning into 'nr-nips-crucible'...
Username for 'https://github.com':
```

— then, after you supply your username and paste your PAT as the password:

```
remote: Enumerating objects: 4127, done.
remote: Counting objects: 100% (4127/4127), done.
Receiving objects: 100% (4127/4127), 12.4 MiB | 8.20 MiB/s, done.
Resolving deltas: 100% (2611/2611), done.
```

and then silence from `cd` and `chmod`.

**What it means:** the code is on the VM and the scripts are runnable.

**If instead:** `Repository not found.` — this is nearly always an access
problem wearing a disguise. GitHub reports a private repo you cannot see as
non-existent rather than admitting it exists. Check that your account is a
member of the `nestle-it` organisation and that your PAT carries `repo` scope.

**If instead:** `Support for password authentication was removed` — you typed
your GitHub account password. It must be a PAT.

**If instead:** `Permission denied (publickey)` on the SSH URL — the VM's
public key is not registered with your GitHub account.

### 2.2 One-shot setup

Before running this, read section 3 if you want HTTPS from the very first
start — the certificate settings belong in `.env.local` *before* this script
runs, not after.

```bash
# 2. One-shot setup: copy + verify certs, build, start (HTTPS when certs
#    exist), verify the API, optionally install the monitoring cron
./setup-after-clone-py.sh
#    Non-interactive: SETUP_MONITOR=y ./setup-after-clone-py.sh
#    For HTTPS, configure the cert store FIRST via .env.local (see section 3),
#    or one-off: CERT_SOURCE=<cert-store-path> ./setup-after-clone-py.sh
```

The `./` prefix means *the script in this very folder* — without it the shell
searches its usual list of program directories, finds nothing, and says
`command not found`.

`SETUP_MONITOR=y ./setup-after-clone-py.sh` sets an **environment variable**
([glossary](00-glossary.md#the-container-words)) for the duration of that one
command. An environment variable is a named value a process carries, inherited
at birth from its parent and from nowhere else. Setting it on the same line as
the command hands the value to that command only — nothing is changed
permanently, and the next command you type will not see it.

**You should see** (this takes a while — see below):

```
==> Checking prerequisites ...
    podman 4.9.4 found
==> Certificates: copying from <cert-store-path> ...
    certs/server.crt, certs/server.key installed (modulus match OK)
==> Building image crucible-py:latest ...
STEP 1/14: FROM node:18-alpine AS frontend
...
STEP 14/14: CMD ["python", "-m", "uvicorn", ...]
COMMIT crucible-py:latest
==> Starting container (HTTPS) ...
==> Verifying API ...
    ✅ API responded: {"chemicals": 0, "samples": 0, ...}
==> Install the health-monitoring cron job? [y/N]
```

**What it means:** image built, container running, the app answered a real
request. Answer `y` at the prompt to install health monitoring now (section 4
explains what that is), or `N` and do it later.

> **The first build is slow, and that is normal.** Five to fifteen minutes,
> sometimes more on a busy VM. It is downloading a Python base image, a Node
> base image, and every library the app depends on. The screen will fill with
> `STEP 7/14`, package names, and progress bars, and it will look like it has
> hung during the npm install step. It has not. Later builds reuse everything
> unchanged and finish in well under a minute. Do not interrupt this one.

```bash
# ✅ The script polls the API for up to 60 s and exits non-zero (with a
#    pointer to ./container-py.sh logs) if the app never answers.
```

"Exits non-zero" is how a Unix program says *this failed*: it hands back a
number when it finishes, `0` for success and anything else for trouble. You can
see the last one with `echo $?`.

**If instead:** `❌ API did not respond within 60s` — the container is probably
running but unhappy. Run `./container-py.sh logs` and read the last twenty
lines; the real error is almost always there in plain English.

**If instead:** `Permission denied` running the script — the `chmod +x *.sh`
step was skipped.

**If instead:** the build fails on a network timeout — check that the VM has
outbound internet, and whether it needs proxy environment variables set.

### 2.3 The manual alternative

Manual alternative (what the one-shot script does internally):

```bash
./container-py.sh build       # podman build --format docker … → crucible-py:latest
./container-py.sh start-ssl   # HTTPS (needs certs/ — see section 3), or:
./container-py.sh start       # HTTP on 0.0.0.0:49160
```

Useful when something has gone wrong and you want to do one thing at a time.
`build` produces the image; `start` or `start-ssl` runs a container from it.

**You should see** from `build`, at the end:

```
COMMIT crucible-py:latest
--> a3f9c1e2b7d4
Successfully tagged localhost/crucible-py:latest
```

and from `start-ssl`:

```
🔒 Starting crucible-py in HTTPS mode on 0.0.0.0:49160
7f3a9b2c8e1d4a6f5b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a
```

**What it means:** that 64-character string is the container's ID. Podman
prints it when a container starts successfully. You will never need to type it
— `crucible-py` is the name, and names are what the scripts use.

### 2.4 Where the app now lives

On Linux the port is published on **0.0.0.0**, so the app is reachable from
other machines once the firewall allows it: `https://<vm-hostname>:49160`.

**`0.0.0.0` versus `127.0.0.1`** — `127.0.0.1` (also called **localhost**) is
this very machine and nowhere else; a program listening there is answering a
door that only opens onto its own hallway. `0.0.0.0` means *every network
address this machine has* — the front door onto the street. On a macOS
development machine the scripts deliberately use `127.0.0.1`, so nobody else can reach it;
on this server we want colleagues to reach it, so we use `0.0.0.0`. This is one
of the genuine differences between a laptop install and a production one.

---

## 3. HTTPS with corporate certificates

**Time:** ~10 minutes.

### 3.1 What a certificate actually is

**HTTPS** ([glossary](00-glossary.md#the-web-and-api-words)) — HTTP with the
conversation sealed in an envelope. Plain HTTP is a postcard: anyone handling
it on the way can read it and, worse, rewrite it. HTTPS wraps the same messages
in **TLS** ([glossary](00-glossary.md#the-web-and-api-words)), which both encrypts
them and proves who you are talking to.

**Private key** ([glossary](00-glossary.md#the-web-and-api-words)) — a secret file
that only this server holds. It is the thing that proves identity. If it leaks,
someone else can impersonate the server, which is why it lives in `chmod 600`
(readable by you and nobody else) and must never, ever be committed to git.

**Certificate** ([glossary](00-glossary.md#the-web-and-api-words)) — the public
half: a document saying *"the holder of the matching private key is
`<vm-hostname>`"*, signed by someone browsers already trust. Think of the key
as your signature and the certificate as your passport — the passport is safe
to show anyone, the signature is not.

**Certificate authority (CA)** ([glossary](00-glossary.md#the-web-and-api-words))
— the passport office. An organisation whose signature browsers accept.
Nestlé runs an internal one, and every managed machine in the company is
configured to trust it.

**Self-signed versus corporate-signed** — a *self-signed* certificate is a
passport you printed yourself. It encrypts traffic perfectly well, but nothing
vouches for it, so browsers throw up a red warning page and `curl` needs `-k`
("I know, ignore it") to proceed. That is fine for a laptop
([01-setup-macos.md](01-setup-macos.md) uses one). A *corporate-signed*
certificate comes from the internal CA, so managed browsers show a clean
padlock and `curl` needs no `-k` at all. **This is why no command in this guide
uses `-k`.** If you find yourself reaching for it, that is a signal something
is wrong with the certificate, not a nuisance to work around.

### 3.2 Configure the certificate source

`./container-py.sh start-ssl` requires `certs/server.crt` **and**
`certs/server.key`. `setup-after-clone-py.sh` places them automatically from
the corporate store once it knows where that store is — configure it **once**
per VM in an untracked `.env.local` file (gitignored, survives `git pull`;
environment variables override it):

**`.env.local`** — this machine's own settings file. Same idea as the label on
the back of a piece of office equipment: it records the facts that are true for
*this one unit* and no other. Everything in the repository is identical on every
machine; `.env.local` is where a machine keeps what makes it different. It is
listed in `.gitignore` ([glossary](00-glossary.md#the-git-words)), which means git
is under instructions to pretend it does not exist — so it is never committed,
never pushed, never leaked into the repository, and never overwritten by a
`git pull`.

```bash
cat > .env.local <<'EOF'
CERT_SOURCE=<cert-store-path>
CERT_HOSTNAME=<vm-hostname>
USE_HTTPS=true
EOF
# CERT_SOURCE / CERT_HOSTNAME → where setup-after-clone-py.sh copies certs
#   from (CERT_HOSTNAME is optional — defaults to `hostname -f`, which on the
#   VM already resolves to the right FQDN; the store must contain
#   <vm-hostname>.cer and <vm-hostname>.key).
# USE_HTTPS=true → makes plain `./container-py.sh start` and `rebuild` come up
#   HTTPS even when no container exists yet (fresh install, or right after an
#   uninstall). Without it, `rebuild` can only preserve the mode of an
#   EXISTING container — from scratch it would default to HTTP.
# AUTH_MODE / CRUCIBLE_TOKEN → the login, two more lines once you turn it on
#   (off by default; docs/13-authentication.md, phase SH-3a Step 7);
#   AUTH_MODE=local / SESSION_SECRET → accounts with roles instead of the
#   shared token, once the accounts exist (phase SH-3b Step 9).
./setup-after-clone-py.sh
```

That `cat > file <<'EOF' … EOF` construction is a **heredoc**: everything
between the first `EOF` and the last one is written into the file verbatim.
Type the lines exactly, ending with `EOF` alone on its own line. The quotes
around `'EOF'` matter — they stop the shell from trying to interpret anything
inside as a variable. If heredocs make you uneasy, open the file in an editor
(`vi .env.local` or `nano .env.local`) and type the three lines by hand; the
result is identical.

**FQDN** — *fully qualified domain name*: a machine's complete address
including every domain suffix (`host.department.company.com`), as opposed to
the bare nickname (`host`). `hostname -f` prints it.

**You should see:** nothing from the heredoc (silence = success), then the
setup script's output as in section 2.2, this time including the certificate
lines:

```
==> Certificates: copying from <cert-store-path> ...
    certs/server.crt, certs/server.key installed (modulus match OK)
```

**What it means:** the certificate and key are in place, and their modulus
check passed — see 3.3 for what that check is.

Verify the file landed correctly with `cat .env.local`; you should get your
three lines back.

**If instead:** `No certificate store found` — `CERT_SOURCE` points somewhere
that does not exist, or you lack read permission on it. `ls <cert-store-path>`
tells you which.

**If instead:** the store exists but the script says the expected files are
missing — it looks specifically for `<vm-hostname>.cer` and `<vm-hostname>.key`.
If the real filenames use a different hostname spelling, set `CERT_HOSTNAME`
explicitly to match.

> **Treat `.env.local` as a VM prerequisite.** It is untracked (gitignored),
> survives `git pull`, and is the one piece a fresh clone or full uninstall
> cannot restore — recreate it before anything else.
>
> That is worth reading twice. Every other file on this VM can be rebuilt from
> the repository. This one cannot, because it deliberately was never put in the
> repository. Keep a note of its three lines somewhere you will still have
> after the VM is gone.

### 3.3 Manual placement

Manual placement (what the script does internally):

```bash
mkdir -p certs
cp <cert-store-path>/<vm-hostname>.cer certs/server.crt
cp <cert-store-path>/<vm-hostname>.key certs/server.key
chmod 600 certs/server.key
chmod 644 certs/server.crt
```

`mkdir -p` creates the folder and stays quiet if it already exists. The two
`chmod` numbers are Unix permissions in shorthand: **600** = the owner may read
and write, everyone else gets nothing — correct for a secret. **644** = the
owner may read and write, everyone else may read — correct for a passport you
are going to show people anyway.

**You should see:** nothing from any of the four commands. (Silence = success.)

**What it means:** both files are in `certs/` with the right permissions.
Confirm with `ls -l certs/`, which should show `-rw-------` for `server.key`
and `-rw-r--r--` for `server.crt`.

**If instead:** `cp: cannot stat '<cert-store-path>/...': No such file or directory`
— the source path or the hostname in the filename is wrong. `ls <cert-store-path>`
lists what is actually there.

```bash
# Verify the pair matches — both commands MUST print the same MD5 hash
openssl x509 -noout -modulus -in certs/server.crt | openssl md5
openssl rsa  -noout -modulus -in certs/server.key | openssl md5
```

A certificate and a key are two halves of one mathematical object, and it is
entirely possible to end up holding halves from different pairs — the files
look fine, they are individually valid, and the server simply refuses to start.
The *modulus* is a large number both halves share. Piping it through `md5`
shortens it to a fingerprint short enough to compare by eye.

**You should see** two lines that are character-for-character identical:

```
(stdin)= 4a7bd3e6f2c891a05b4e7d9c3f1a8b62
(stdin)= 4a7bd3e6f2c891a05b4e7d9c3f1a8b62
```

**What it means:** the key belongs to the certificate. Continue.

**If instead:** the two hashes differ — you have a mismatched pair. Do not
proceed; re-copy both files together from the store. Copying only one of them
is the usual cause.

**If instead:** `unable to load Private Key` — the key file is in a format
`openssl rsa` does not recognise (modern keys are sometimes PKCS#8).
`openssl pkey -noout -modulus -in certs/server.key | openssl md5` reads both
formats and produces a comparable hash.

```bash
# Start in TLS mode (always recreates the container; no rebuild needed —
# certs are runtime-mounted read-only, never baked into the image)
./container-py.sh start-ssl
```

"Runtime-mounted read-only" means the `certs/` folder is handed to the
container as it starts, and handed in as look-but-do-not-touch. The secret is
therefore never *inside* the image — which matters, because images get copied
around, and an image with a private key baked into it is a private key with
legs.

**You should see:**

```
🔒 Starting crucible-py in HTTPS mode on 0.0.0.0:49160
7f3a9b2c8e1d...
```

**What it means:** running, listening, encrypted.

**If instead:** `certs/server.crt not found` — you are in the wrong directory.
`pwd` should end in `/nr-nips-crucible`.

```bash
# ✅ Full verification — ask for the machine's REAL name, not "localhost".
#    This validates the certificate chain as a browser would:
curl --noproxy '*' -sS https://<vm-hostname>:49160/api/stats

# ✅ Quick local probe — needs -k. Not a problem: the certificate is issued
#    to <vm-hostname>, so asking for "localhost" is a name mismatch by design.
curl --noproxy '*' -sSk https://localhost:49160/api/stats
```

> **Why `localhost` needs `-k` even with a perfectly good certificate.** A
> certificate lists the names it is valid for (its *Subject Alternative Names*).
> The corporate one carries exactly one: `<vm-hostname>`. It says nothing about
> `localhost`, so a client asking for `localhost` is right to object — that is
> hostname checking doing its job, not a fault. Use the FQDN when you want to
> prove the certificate is genuinely good; use `-k` when you just want to know
> the app is alive. Both are shown above because they answer different
> questions.

`curl` is a browser with no windows — it fetches a URL and prints what comes
back. `-s` is *silent*: suppress the progress meter, print only the answer.

**`--noproxy '*'` and the corporate proxy** ([glossary](00-glossary.md#the-web-and-api-words))
— a **proxy** is a middleman your organisation puts between its machines and
the internet, so that all outbound traffic can be inspected and logged. The VM
is configured to send web requests through it. That is fine for the internet
and absurd for `localhost`: asking a middleman across the network to fetch a
page from *the machine you are already standing on* means the request leaves,
gets refused or mangled by a proxy that has never heard of `localhost`, and
comes back as a baffling failure. `--noproxy '*'` means *for these hosts, do
not use the proxy* — and `'*'` means *all of them*. The quotes stop the shell
from expanding `*` into a list of filenames first.

This is why every `curl` in this guide carries `--noproxy '*'`. Drop it and
localhost checks fail for reasons that have nothing to do with your app.

**You should see:**

```json
{"chemicals":1247,"samples":389,"screening_results":15302,"tox_records":88}
```

(Your numbers will differ. A fresh database prints zeros.)

**What it means:** the **API** ([glossary](00-glossary.md#the-web-and-api-words))
answered over HTTPS, with a valid certificate, without `-k`. An API is simply
the machine-readable version of the app — the same data the web page shows, in
a form other programs can read. Getting real **JSON** back is the single
strongest signal that everything below it works: container, port, TLS,
certificates, backend, and database, all confirmed by one line.

**If instead:** `curl: (60) SSL certificate problem: ...` — read the rest of the
line, because the two variants mean opposite things:

- **`... self signed certificate`** — the certificate in `certs/` really is a
  self-signed one, not the corporate pair. Re-copy from the store (§3.1).
- **`... unable to get local issuer certificate`** — the certificate is fine.
  **Your `curl` does not trust the authority that signed it.** This is a client
  problem, not a server problem: the app is serving the right certificate, and
  `./container-py.sh status` (which uses `-k`) will happily return JSON while
  this command fails.

  The usual cause here is **conda**. If your prompt starts with `(base)` you are
  inside a conda environment, and conda ships its own `curl` with its own list of
  trusted authorities — public CAs only, not the corporate one. The system
  `curl` normally does trust it:

  ```bash
  which curl                                                        # conda's, or /usr/bin/curl?
  /usr/bin/curl --noproxy '*' -sS https://<vm-hostname>:49160/api/stats  # system curl, real name
  curl --noproxy '*' -sS -k https://localhost:49160/api/stats        # or skip verification
  ```

  Use `/usr/bin/curl` for the honest check. `-k` is acceptable on a localhost
  probe where you are both the server and the client — it is what
  `container-py.sh` does internally — but never make it a habit against a remote
  host: it disables the one check that would catch an impostor. The browser test
  (V8) is the more meaningful verification anyway, since a corporate workstation
  trusts the internal CA and will show the padlock without complaint.

**If instead:** `curl: (7) Failed to connect to localhost port 49160` — nothing
is listening. `./container-py.sh status` and then `./container-py.sh logs`.

**If instead:** an HTML page about proxy authentication comes back — the
`--noproxy '*'` was omitted or mistyped.

### 3.4 Switching modes, and keeping an eye on expiry

HTTPS **replaces** HTTP on port 49160. Switch back with
`./container-py.sh stop && podman rm crucible-py && ./container-py.sh start`.

There is one door and one protocol at a time. `stop` halts the container,
`podman rm` deletes the stopped container (not the image, and not your data —
those live in the bind-mounted `data/` folder on the host), and `start` creates
a fresh one in HTTP mode.

Certificate expiry monitoring (warns when < 30 days remain):

Certificates expire, usually after a year, and always at the least convenient
moment. When one does, the site does not degrade gracefully — every browser
refuses it outright. Thirty days of warning is enough to get a renewal through
whatever process your organisation uses.

```bash
./cert-expiry-check.sh                    # manual check, exit 1 = expiring/expired
```

**You should see:**

```
Certificate for <vm-hostname> expires 2027-03-14 (202 days remaining) — OK
```

**What it means:** more than 30 days left; nothing to do.

**If instead:** `⚠️ expires in 12 days` and the script exits 1 — start the
renewal now. Rotation instructions are below.

**If instead:** `No certificate present` — you are in a checkout without a
`certs/` folder. See the warning after the cron setup; this is exactly the trap
it describes.

```bash
# Print the exact line to paste, with your real paths already filled in.
# Run this from the production checkout — the one whose certs/ holds the live
# certificate — so that $(pwd) expands to the right place.
echo "0 8 * * 1 CERT_FILE=$(pwd)/certs/server.crt $(pwd)/cert-expiry-check.sh >> ~/crucible-cert.log 2>&1"

crontab -e   # paste the line that just printed, verbatim (Mondays 08:00)
```

**Let the `echo` write the line; do not retype it.** Every character of the
path is substituted for you, so there is nothing left to fill in and nothing to
mistype. A placeholder accidentally left in place — `/path/to/crucible`, or
anything with angle brackets — does not fail loudly: the shell chokes on the
`cd`, `&&` short-circuits, and the check simply never runs, silently, every
Monday.

Passing `CERT_FILE` as an absolute path is deliberate too. It removes the
working directory from the equation altogether, which is the thing that broke
this check before (see the warning below).

**cron** ([glossary](00-glossary.md#the-container-words)) — the machine's alarm
clock. It holds a list of *"at this time, run this command"* instructions and
carries them out whether or not anyone is logged in. Your personal list is
called your **crontab**, and `crontab -e` opens it in an editor. (If that
editor turns out to be `vi` and you are stranded: press `i` to type, then
`Esc`, then `:wq` and Enter to save and quit. `export EDITOR=nano` before
`crontab -e` avoids the whole experience.)

Each line begins with five fields saying *when*:

| Field | Position | Range | In `0 8 * * 1` | Meaning |
|---|---|---|---|---|
| Minute | 1st | 0–59 | `0` | on the hour |
| Hour | 2nd | 0–23 | `8` | 08:00, 24-hour clock |
| Day of month | 3rd | 1–31 | `*` | every day of the month |
| Month | 4th | 1–12 | `*` | every month |
| Day of week | 5th | 0–7 (0 and 7 = Sunday) | `1` | Monday |

`*` means *every*. Read together: **every Monday at 08:00.** The other pattern
you will meet in this guide is `*/5 * * * *` — the `*/5` means *every 5th
minute*, so: every five minutes, all day, forever.

After the five fields comes the command. `>>` appends its output to a log file
instead of throwing it away, and `2>&1` adds error messages to the same file
(stream `2` is errors, stream `1` is normal output — this says *send 2 wherever
1 goes*). Without those, cron mails its output into a void nobody reads.

**You should see** after saving:

```
crontab: installing new crontab
```

**What it means:** the alarm is set. Confirm with `crontab -l`, which prints
your list.

**If instead:** `crontab: no crontab for <your-user>` from `crontab -l` — the
save did not happen. Re-run `crontab -e`.

> ⚠️ **`CERT_FILE` must resolve to the certificate this server is actually
> serving** — the one in the **production checkout**. Point it at another clone
> (e.g. `~/work/Pandora_toolbox/crucible-mirror`, which has no `certs/`) and the
> check reports "no cert present = OK" every week while never inspecting the
> real certificate.
>
> A **checkout** is one folder containing one copy of the code. It is entirely
> normal for a VM to hold several. This warning describes a real failure that
> has actually happened, twice, in different disguises: once as a `cd` pointing
> at a clone with no `certs/`, and once as a placeholder left unsubstituted in
> the cron line so the command never ran at all. Both reported nothing wrong
> for months. **A monitor that cannot fail is not a monitor.**
>
> This is why the `echo` above builds the line for you, and why `CERT_FILE` is
> absolute: neither the working directory nor your typing is left in the loop.
>
> Prove it once, and read the output rather than the exit code:
>
> ```bash
> CERT_FILE="$(pwd)/certs/server.crt" ./cert-expiry-check.sh
> ```
>
> A real expiry date means it is genuinely reading your certificate.
> `no certificate at … — nothing to check` means it is not — and note that
> this message **exits 0**, so anything watching only the exit status will call
> it a pass.

Certificate rotation (renewal or reissue): see
[docs/07-operations.md → Maintenance](07-operations.md#maintenance-and-operational-tasks).
Shortcut — **remove the old pair first** (the setup script keeps existing
certs and skips the copy if `certs/` is already populated):
`rm certs/server.crt certs/server.key && CERT_SOURCE=/path/to/new ./setup-after-clone-py.sh`,
then `./container-py.sh start-ssl`.

The "remove first" is not fussiness. The script's rule is *never clobber
certificates that are already there* — sensible protection, and the exact
reason a rotation appears to succeed while leaving the expired certificate in
place. Delete, then copy, then restart.

> ⚠️ **Never commit certificates** — `certs/`, `*.key`, and `*.crt` are
> `.gitignore`d. The private key must stay `chmod 600`.
>
> **Commit** ([glossary](00-glossary.md#the-git-words)) means recording a change
> into git's permanent history. Permanent is the operative word: a secret
> committed once is in the history forever, on every clone anyone has ever
> made, even if you delete the file in the very next commit. Recovering from
> that means reissuing the certificate, not editing history. The `.gitignore`
> entries make this near-impossible by accident — leave them alone.

---

## 4. Auto-start on boot and monitoring

**Time:** ~10 minutes.

> **The everyday commands** (is it running, stop, start, restart, and what
> the service does at boot) are on one page, [`15-run-stop-status.md`](15-run-stop-status.md).
> This section sets the service up once.

### 4.1 Why a container is not enough

Rootless containers die with your login session — `--restart unless-stopped`
alone does **not** survive a reboot. You need lingering (section 1) plus a
systemd **user** unit:

This trips up nearly everyone. `--restart unless-stopped` sounds like a
promise of immortality; it is not. It means *if this container crashes, start
it again* — and it is enforced by a supervisor that is itself part of your
login session. Reboot the machine and there is no session, no supervisor, and
nothing to restart anything. Two separate pieces are needed:

1. **Lingering** (section 1.3) — permission for your programs to exist while
   you are not logged in.
2. **A systemd user unit** — someone to actually start them at boot.

**systemd** ([glossary](00-glossary.md#the-container-words)) — the program that
brings a Linux machine to life. When the kernel finishes booting it starts
systemd, and systemd starts everything else, in order, in parallel where it
can, restarting things that fall over. It is the machine's stage manager.

**Unit** — one recipe card in systemd's box: *what to run, when to run it, what
must be ready first, what to do if it dies.* A **user unit** is a recipe card
in your own personal box rather than the machine-wide one, so it runs as you,
needs no `sudo`, and cannot affect anyone else. The natural fit for a rootless
container.

**Quadlet** ([glossary](00-glossary.md#the-container-words)) — the modern way to
write that recipe card for a container. Instead of generating a long systemd
file full of podman flags, you write a short `.container` file describing the
container, and podman translates it into a proper unit at boot. Fewer moving
parts, and it does not go stale when the container is recreated.

### 4.2 Generate and enable the unit

```bash
# Quick variant (podman 4.x): generate a user unit from the running container
mkdir -p ~/.config/systemd/user
podman generate systemd --new --name crucible-py --files
mv container-crucible-py.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now container-crucible-py.service
```

Line by line: create the folder where personal unit files live (`~` is your
home directory); ask podman to write a unit describing the running
`crucible-py` container (`--new` makes it recreate the container from the image
each boot rather than depending on one specific existing container — sturdier);
move the generated file into place; tell systemd to re-read its recipe box; and
finally `enable --now`, which does two jobs at once — `enable` means *start
this at every boot from now on*, `--now` means *and also start it this second.*

**You should see:**

```
/home/<your-user>/container-crucible-py.service
```

from the generate step (it prints the path of the file it wrote, into the
current directory — hence the `mv`), then silence from `mv` and
`daemon-reload`, then from the last command:

```
Created symlink /home/<your-user>/.config/systemd/user/default.target.wants/container-crucible-py.service → /home/<your-user>/.config/systemd/user/container-crucible-py.service.
```

**What it means:** the symlink *is* the enablement — systemd records "start
this at boot" by linking the unit into a `.wants` folder. Seeing it is
confirmation. Check the result with `systemctl --user status container-crucible-py.service`,
which should say `active (running)`.

**If instead:** `Failed to connect to bus` — this is the classic rootless-over-SSH
error. Your systemd user session is not reachable. Confirm lingering is on
(`loginctl show-user $USER | grep Linger` → `Linger=yes`), log out fully, log
back in, and retry.

**If instead:** `Error: no container with name or ID "crucible-py"` — the
container must be **running** for `generate systemd` to describe it. Start it
first.

**If instead:** `Unit container-crucible-py.service not found` after
`daemon-reload` — the `mv` put the file somewhere else. `ls ~/.config/systemd/user/`.

The preferred **Quadlet** variant (podman ≥ 4.4) and the full unit content are
in [docs/07-operations.md → Auto-start on boot](07-operations.md#auto-start-on-boot-systemd).
**One unit per instance:** if this VM also runs the beta instance
(section 8), repeat these commands in that folder with `--name crucible-py-beta`;
the unit is then `container-crucible-py-beta.service`.
If you use the Quadlet file, **adjust its `Volume=` path** to your actual
checkout or the app starts with an empty database.

That last sentence describes the most alarming five minutes a new operator can
have. A **volume** here means a **bind mount** — a folder on the host handed
into the container so the two share it. `Volume=/home/you/nr-nips-crucible/data:/app/data:Z`
says *my `data` folder appears inside the container as `/app/data`*. The
database file lives there, on the host, which is precisely why deleting a
container never deletes your data. Point that path at a folder that does not
exist and podman helpfully creates an empty one — so the app starts perfectly,
in HTTPS, with zero chemicals, and looks for all the world as though your data
has been destroyed. It has not. Fix the path, restart, and everything is back.

### 4.3 Health monitoring

Health monitoring (auto-restart on failed health checks):

A **health check** is a small program that asks the app *are you all right?*
every so often. Ours calls the API and looks for a sensible answer. A process
can be running and yet useless — deadlocked, out of memory, wedged on a
connection — and "is the process alive?" will cheerfully report yes. The
monitor asks the better question, and restarts the container when the answer is
no.

```bash
SETUP_MONITOR=y ./setup-after-clone-py.sh     # installs/refreshes THIS folder's cron line
crontab -l | grep monitor.sh                  # verify; the installed entry is ONE line per instance:
# */5 * * * * cd <repo> && USER=<user> XDG_RUNTIME_DIR=/run/user/<uid> CONTAINER_NAME=crucible-py API_URL=https://localhost:49160/api/health ./monitor.sh
tail -5 /tmp/crucible-monitor.log
```

(With the beta instance of section 8 installed there is a second line
ending `CONTAINER_NAME=crucible-py-beta API_URL=https://localhost:49161/api/health ./monitor.sh`,
and a second log, `/tmp/crucible-monitor-beta.log`. Re-running the setup in
one folder replaces only that folder's line.)

`grep` filters lines, keeping only those containing the text you gave it —
here, printing just the monitor line out of a possibly long crontab. `tail -5`
shows the last five lines of a file, which for a log is the interesting end.

**You should see** from the `grep` a single long line beginning `*/5 * * * *`
(every five minutes — see the cron table in section 3.4), and from `tail`:

```
[2026-08-24 14:35:01] OK - API responding
[2026-08-24 14:40:01] OK - API responding
[2026-08-24 14:45:01] OK - API responding
```

**What it means:** the alarm clock is set, and the checks are passing.
Timestamps five minutes apart confirm cron is genuinely firing.

**If instead:** `tail: cannot open '/tmp/crucible-monitor.log'` and you only
just installed the cron — the file appears after the first run. Wait five
minutes and look again.

**If instead:** the log shows `RESTARTING` entries repeatedly — the app is
crashing and being resurrected in a loop. `./container-py.sh logs` has the
reason.

**If instead:** the log stops updating — cron has stopped firing, or the line
was removed. `crontab -l` and check.

> ⚠️ The `USER=… XDG_RUNTIME_DIR=…` prefix is **required** for rootless podman
> under cron — without it podman resolves its storage to a bad path and the
> monitor cannot restart the container. Let the setup script write the line
> rather than copying simplified examples.
>
> The reason: cron does not run your commands in a normal login. It gives them
> a nearly empty set of environment variables — none of the values your shell
> quietly inherits when you log in. Two of those missing values matter to
> rootless podman. `USER` is your username; `XDG_RUNTIME_DIR` is the path to
> your private per-session scratch folder (`/run/user/<your numeric ID>`),
> where podman keeps track of what it is running. Deprived of them, podman does
> not fail loudly — it looks in the wrong place, concludes you have no
> containers at all, and the monitor reports success while monitoring nothing.
> This is the single most common way a "working" cron job turns out to be
> decorative. Let the script generate the line; it fills in your real username
> and numeric ID.

---

## 5. Verification checklist

**Time:** ~5 minutes (V7 adds a few more).

Run this same checklist after every install or redeploy. It mirrors the macOS
checklist in [01-setup-macos.md](01-setup-macos.md#4-verification-checklist),
plus the external-access checks (V8–V9) that only apply to the VM.

Do not skip it because "it obviously worked". Each check exercises a different
layer, and the point is that a failure tells you *which* layer — which is worth
far more than a vague sense that something is wrong.

```bash
# V1. API answers with stats JSON (must contain "chemicals")
curl --noproxy '*' -sS  http://localhost:49160/api/stats     # HTTP mode
curl --noproxy '*' -sS  https://<vm-hostname>:49160/api/stats  # HTTPS, full validation
curl --noproxy '*' -sSk https://localhost:49160/api/stats      # HTTPS via localhost (-k: cert names the FQDN, not localhost)
```

Run the line matching the mode you started in. Only one will answer — HTTPS
replaces HTTP on the same port.

**You should see:**

```json
{"chemicals":1247,"samples":389,"screening_results":15302,"tox_records":88}
```

**What it means:** every layer beneath is working. This is the highest-value
single check in the document.

**If instead:** `curl: (52) Empty reply from server` from the **`http://`**
line — that is the expected answer in HTTPS mode, not a fault. You spoke plain
HTTP to a TLS listener; it closed the connection without replying. Use one of
the `https://` lines. On a correctly deployed VM this is what V1's first line
*should* print, and it is worth recognising, because the same message from a
monitoring script means the same thing (see V5).

**If instead:** empty output with no error at all — the connection was made but
nothing came back; check `./container-py.sh logs`.

**If instead:** `curl: (7) Failed to connect` — nothing is listening on 49160.

**If instead:** `curl: (35) SSL ... wrong version number` — the mirror image:
you asked for `https://` and the container is running in HTTP mode. Try the
other line.

**If instead:** `bash: vm-hostname: No such file or directory` — you pasted the
line literally. `<vm-hostname>` is a placeholder; substitute your real FQDN
(`hostname -f` prints it), angle brackets and all.

```bash
# V2. Container is up and (after ~30 s) healthy. `status` detects HTTP vs
#     HTTPS mode and prints the stats JSON for whichever is in use.
./container-py.sh status
./container-py.sh script healthcheck.py && echo healthy
```

`podman exec` runs a command *inside* the running container — reaching into the
lunchbox and using the tools packed in there. `&& echo healthy` prints the word
only if the command before it succeeded, so a bare `healthy` at the end is your
green light.

**You should see:**

```
Container: crucible-py   STATUS: Up 4 minutes (healthy)
Mode:      HTTPS on 0.0.0.0:49160
API:       {"chemicals":1247,"samples":389,...}
healthy
```

**What it means:** podman's own health checking agrees with the API, from
inside and outside the container.

**If instead:** `(health: starting)` — the check has not run yet. It takes
about 30 seconds after start. Wait, then re-run.

**If instead:** `(unhealthy)` while V1 works — the classic proxy-interception
symptom. See the gotcha in section 7: rebuild to pick up the proxy-bypassing
healthcheck.

**If instead:** `Error: no container with name or ID "crucible-py"` — nothing
is running. `./container-py.sh start-ssl`.

```bash
# V3. UI loads (from the VM)
curl --noproxy '*' -sSk https://localhost:49160/ | grep -o '<title>[^<]*</title>'
```

V1 proved the backend answers. This proves the **frontend** — the actual web
page — is being served too. Rather than dumping a screenful of HTML, it pulls
out just the page title. (`grep -o` prints only the matching part of the line
instead of the whole line.)

**You should see:**

```html
<title>Crucible — Pandora Toolbox</title>
```

**What it means:** the built React frontend is present in the image and being
served. A browser pointed at this URL will get a real page.

**If instead:** no output — the HTML came back but had no `<title>`, or nothing
came back at all. Drop the `| grep …` and look at the raw response.

```bash
# V4. Logs are clean (Ctrl-C to detach)
./container-py.sh logs
```

**Logs** are the application's running commentary about what it is doing. This
command *follows* them — it prints what has happened and then sits there
waiting for more, which is what you want while watching for a problem.

**You should see:**

```
INFO:     Uvicorn running on https://0.0.0.0:49160 (Press CTRL+C to quit)
INFO:     Application startup complete.
INFO:     127.0.0.1:52344 - "GET /api/stats HTTP/1.1" 200 OK
```

**What it means:** `Application startup complete` is the line that matters.
`200 OK` entries are your own successful curl commands from V1 appearing in the
log. **Press Ctrl-C to stop watching** — this detaches your view of the logs
and does *not* stop the container. (That is worth internalising before you
press it.)

**If instead:** `Traceback (most recent call last)` — a Python error. The last
line of the traceback names the actual problem; everything above it is the
route the error travelled.

**If instead:** the same startup lines repeating every few seconds — the app is
crash-looping. Read the lines immediately before each restart.

```bash
# V5. Health monitor runs (logs to /tmp/crucible-monitor.log)
# On this VM the app is HTTPS, so API_URL is REQUIRED — monitor.sh defaults to
# http:// and would otherwise report a healthy app as dead.
API_URL=https://localhost:49160/api/health ./monitor.sh

# Then confirm the installed cron line carries the same URL:
crontab -l | grep monitor.sh
```

This runs one round of the monitor by hand, so you find out now whether it
works rather than discovering at 3 a.m. that it never did.

> ⚠️ **Do not run bare `./monitor.sh` on an HTTPS deployment.** Its built-in
> default is `http://localhost:<port>/api/health`, which a TLS listener refuses —
> so the monitor concludes the app is dead and **restarts your container**. What
> you see is alarming and entirely self-inflicted:
>
> ```
> ⚠️  Health check failed!
> ⚠️  Container unhealthy, restarting...
> ✗ Container restart failed
> ```
>
> The final line is the second HTTP check failing after the restart, not a
> container that refused to start. Nothing was broken; the probe was pointed at
> the wrong protocol. The same mistake **in the cron line** is far worse: it
> restarts production every five minutes, indefinitely, while reporting that it
> is doing its job. That is why the `crontab -l` check above is part of V5 and
> not an afterthought — the installed line must contain
> `API_URL=https://localhost:49160/api/health`.
>
> The monitor already passes `-k`, so the certificate naming the FQDN rather
> than `localhost` is not a problem here.

> **Once section 4.2's systemd unit exists**, note that `monitor.sh` restarts
> the container directly with `podman restart`, while the unit owns it and was
> generated with `--new` (it removes and recreates the container). The two can
> disagree about who is in charge. It resolves itself in practice — systemd
> brings the container back — but if you ever see repeated restart churn in the
> log, this interaction is the first place to look.

**You should see:** little or no output, and a new line in
`/tmp/crucible-monitor.log`:

```
[2026-08-24 14:50:22] OK - API responding
```

**What it means:** the monitor can reach the app and would notice if it
stopped.

**If instead:** the log says the API is not responding while V1 works — the
monitor is checking the wrong URL. In HTTPS mode you must pass
`API_URL=https://...` as shown, because its built-in default is HTTP.

```bash
# V6. Backup / restore round-trip works
./container-py.sh backup     # → backups/crucible-<stamp>.db
```

**Backup** ([glossary](00-glossary.md#the-data-words)) — a copy of the database
taken at a single consistent instant. The `<stamp>` is a timestamp, so backups
never overwrite one another.

**Database** ([glossary](00-glossary.md#the-data-words)) — think: a filing cabinet
for tables. Ours is **SQLite** ([glossary](00-glossary.md#the-data-words)), which
keeps the entire cabinet in one ordinary file inside `data/`. No separate
database server to install or babysit — a large part of why this deployment is
as simple as it is.

**You should see:**

```
✅ Backup written: backups/crucible-20260824-145533.db (4.2 MB)
```

**What it means:** a restorable copy exists. Verify with `ls -lh backups/`.

**If instead:** a size of 0 bytes — something went wrong; check that `data/`
actually contains a database.

**If instead:** `Permission denied` writing to `backups/` — an SELinux or
ownership problem on the folder; `ls -ld backups/`.

```bash
# V7. Backend test suite passes (bare-metal venv; optional on the VM)
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/pytest
```

Optional, and genuinely optional on a production VM — the container has already
proved itself. Run it when you want independent confirmation that the code
itself is sound.

A **venv** (virtual environment) is a private, disposable Python installation
inside the project folder, so the libraries this project needs cannot collide
with the ones the system's own Python depends on. **pytest** is the test
runner; it finds the project's tests and executes them.

**You should see:**

```
==================== 47 passed in 1.81s ====================
```

**What it means:** the backend behaves as its authors specified.

**If instead:** `No matching distribution found for fastapi<1.0,>=0.115`, with
the resolver listing only much older versions — **this is the normal result on
a stock RHEL8 VM, and you should skip V7.** RHEL8 ships Python 3.6 as its
system `python3` (the giveaway is `pip 9.0.3` in the same output), and the
project's dependencies require 3.8+. Nothing is wrong with your deployment: the
container carries its own Python 3.12, which is exactly why the app is running
while this fails. Clean up the unusable venv and move on:

```bash
cd .. && rm -rf backend/.venv
```

Running the suite here would mean installing a newer Python from AppStream
solely to test code the container has already proved. V2's healthcheck is the
check that matters on a server.

**If instead:** `No module named venv` — install `python3-devel` / the
`python3` package that provides it, or simply skip V7 on the VM.

**Remember to `cd ..` afterwards**, since this step left you inside `backend/`.

```bash
# V8. Reachable from a workstation (browser or curl):
#     https://<vm-hostname>:49160  and  https://<vm-hostname>:49160/architecture
```

The first seven checks were all run *on* the VM. This one is different and it
is the one that matters to users: open that URL in a browser **on your own
laptop**. It exercises the whole path — DNS, network, the firewall doorman from
section 1.4, the `0.0.0.0` binding, and the certificate.

**You should see:** the Crucible interface, with a **closed padlock** in the
address bar and no warning page.

**What it means:** the deployment is genuinely live. Colleagues can use it.

**If instead:** the browser hangs and eventually times out — the firewall is
still closed (section 1.4), or the port is bound only to `127.0.0.1`. Check
`HOST_BIND`.

**If instead:** a certificate warning appears — the certificate does not match
`<vm-hostname>` (a `CERT_HOSTNAME` mismatch), or your laptop does not trust the
corporate CA (usually means it is not a managed device).

**If instead:** it works from another Linux box but not your laptop — suspect
your laptop's proxy settings, which browsers apply to internal hostnames too.

```bash
# V9. Survives a reboot (after section 4):
systemctl --user status container-crucible-py.service   # or the Quadlet unit
```

**You should see:**

```
● container-crucible-py.service - Podman container-crucible-py.service
     Loaded: loaded (/home/<your-user>/.config/systemd/user/container-crucible-py.service; enabled; vendor preset: enabled)
     Active: active (running) since Mon 2026-08-24 14:31:07 CEST; 21min ago
```

**What it means:** two words carry the whole check. **`enabled`** on the Loaded
line = it will start at boot. **`active (running)`** = it is up right now. You
need both; `active` alone means it is running today and will vanish at the next
reboot.

`status` pages open in a pager — press `q` to get your prompt back.

**If instead:** `disabled` — run `systemctl --user enable container-crucible-py.service`.

**If instead:** `Failed to connect to bus` — lingering is off, or you need a
fresh login. See section 4.2.

**If instead:** you want to prove it for real — reboot the VM (with whatever
permission your organisation requires), wait two minutes, and run V1 and V9
again without logging in first. That is the only test that truly settles it.

---

## 6. Day-2 operations

"Day 2" is everything after the install: updating, backing up, and the
occasional change of plan. **Time:** varies; the update sequence takes about
5 minutes.

### 6.1 Updating to a new version

```bash
# Update to a new version (field-tested sequence)
cd /path/to/crucible
git switch master        # production tracks master (see 03-git-workflow.md §2.3);
                         # the beta folder of section 8 tracks beta instead, and is updated
                         # first — production only moves by a promotion (03-git-workflow.md Step 11)
./container-py.sh backup                      # consistent snapshot → backups/
# Copy it OUT of the project folder (backups/ is inside it):
cp "$(ls -t backups/crucible-*.db | head -1)" ~/data-backup-$(date +%Y%m%d).db
git pull
./container-py.sh rebuild                     # rebuild + recreate; preserves the
                                              # protocol mode (HTTPS stays HTTPS)
```

The order is the point, and it has been field-tested — meaning someone learned
it the hard way so you do not have to.

`cp -r` copies a folder and everything in it. `$(date +%Y%m%d)` runs `date` and
drops its output straight into the folder name, so you get
`~/data-backup-20260824` without typing today's date. Yes, `./container-py.sh backup`
is the better backup; this is the *additional* one, taken because an upgrade is
the moment you least want to discover your backup routine had a flaw.

**git pull** ([glossary](00-glossary.md#the-git-words)) — fetch the newer commits
from the **remote** (the copy on GitHub) and apply them to your checkout.

`rebuild` then rebuilds the image from the new code and recreates the
container. Crucially it *preserves the protocol mode* — if you were on HTTPS,
you come back on HTTPS. (This is also what `USE_HTTPS=true` in `.env.local`
guarantees when no container exists to inspect.)

**You should see** from `git pull`:

```
Updating a1b2c3d..e4f5g6h
Fast-forward
 backend/app/routers/chemicals.py | 24 +++++++++++++++---
 2 files changed, 20 insertions(+), 4 deletions(-)
```

and from `rebuild`, a build (fast this time — layers are cached) followed by
`🔒 Starting crucible-py in HTTPS mode on 0.0.0.0:49160`.

**What it means:** *Fast-forward* is the happy case — you had no local changes,
so git simply moved you forward.

**If instead:** `Already up to date.` — there was nothing new. Nothing is
wrong; skip the rebuild.

**If instead:** `error: Your local changes ... would be overwritten by merge` —
someone edited a tracked file on the VM. `git status` shows which. Note that
`.env.local` is *never* the cause, because git ignores it.

**If instead:** the app comes back on HTTP after a rebuild — `USE_HTTPS=true`
is missing from `.env.local`. Section 3.2.

Run the section 5 checklist afterwards. Every time.

### 6.2 Backups and restores

```bash
# Backups (safe while running — SQLite online-backup API; never plain-cp a live DB)
./container-py.sh backup
./container-py.sh restore backups/crucible-<stamp>.db
```

That parenthesis deserves unpacking, because it is the difference between a
backup and a file that merely looks like one. A database is being written to
continuously. Copying its file with `cp` while that is happening can catch it
mid-write, producing a copy that is internally inconsistent — and it will
usually *open* fine, which is the cruel part; you find out it is broken when
you need it. SQLite's online-backup API takes a copy that is coherent as of a
single instant, safely, with the app still running. `./container-py.sh backup`
uses it. Please use the script.

**restore replaces the current database.** Take a backup immediately before
restoring one, so that a mistaken restore is itself reversible.

**You should see** from `restore`:

```
⚠️  This will REPLACE the current database. Continue? [y/N] y
✅ Restored from backups/crucible-20260824-145533.db
```

**What it means:** the database is now the backup's contents. Run V1 to confirm
the app is happy with it.

### 6.3 Nightly backups

```bash
# Recommended nightly backup cron (02:00, keep last 14).
# NOTE: a crontab entry must be a single line — paste the following as ONE line:
# 0 2 * * * cd /path/to/crucible && USER=$(id -un) XDG_RUNTIME_DIR=/run/user/$(id -u) ./container-py.sh backup >> ~/crucible-backup.log 2>&1 && ls -t backups/crucible-*.db | tail -n +15 | xargs -r rm
```

`0 2 * * *` — read with the table from section 3.4: minute 0, hour 2, every
day. Two in the morning.

Note the `USER=… XDG_RUNTIME_DIR=…` prefix again, for exactly the reason given
in section 4.3: cron's environment is nearly empty, and rootless podman needs
those two values to find its own containers.

The tail end is a self-pruning trick worth understanding: `ls -t` lists the
backups newest-first; `tail -n +15` prints from the 15th onward — i.e. every
file *except* the newest fourteen; `xargs -r rm` deletes exactly those, and the
`-r` means *if the list is empty, do nothing at all* (without it, `rm` would be
run with no arguments and complain nightly). Result: fourteen days of backups,
maintained forever, with no disk-space surprise.

**The single-line warning is not decoration.** A crontab entry that spans two
lines is not one long instruction — it is one broken instruction followed by
garbage. Your editor may soft-wrap it across the screen; that is fine, so long
as you never press Enter in the middle.

**You should see** the next morning, in `~/crucible-backup.log`:

```
✅ Backup written: backups/crucible-20260825-020007.db (4.2 MB)
```

**What it means:** the nightly backup ran. Check it once, a day after setting
it up. An unverified backup schedule is a hope, not a schedule.

### 6.4 PostgreSQL (optional)

```bash
# Optional PostgreSQL instead of SQLite
./container-py.sh db-start
USE_POSTGRES=true ./container-py.sh start-ssl
```

**PostgreSQL** ([glossary](00-glossary.md#the-data-words)) — a full database
*server*: a separate program, in its own container, that other programs connect
to over the network. Where SQLite is a filing cabinet in your own office,
PostgreSQL is the central records department. It handles many simultaneous
writers better; it also becomes a second thing to run, monitor, and back up.
The default SQLite setup is right for this deployment unless you have a
specific reason. If you turn it on, note that it adds artifacts (a container, a
volume, a network) that the uninstaller deliberately leaves alone — see the
[uninstall guide](01-uninstall-rhel8.md#4-manual-cleanup-the-script-does-not-do).

### 6.5 The environment variables worth knowing

Key environment variables (full table in [docs/07-operations.md](07-operations.md)):
`CRUCIBLE_PORT` (`container-py.sh`'s only port override — it deliberately
ignores a generic `PORT` shell variable, which matters on shared VMs; note
`monitor.sh` **does** read `PORT`, so on a non-default port set
`API_URL=...` for the monitor explicitly), `CRUCIBLE_INSTANCE` (names a
second instance run from another folder — section 8), `HOST_BIND` (default
`0.0.0.0` on Linux), `USE_POSTGRES`, `DATABASE_URL`, `CERT_SOURCE` /
`CERT_HOSTNAME` (setup script).

The `PORT` asymmetry is deliberate and worth a sentence. On a shared VM, some
other tool may well have exported a `PORT` variable into your shell for its own
reasons. If `container-py.sh` honoured it, Crucible would silently move to a
different door and everything would break in a way nobody would guess. So it
ignores `PORT` and reads only `CRUCIBLE_PORT`. `monitor.sh` predates that
decision and still reads `PORT` — hence the note: if you ever move off 49160,
tell the monitor explicitly with `API_URL=`.

---

## What you have now

![Set up once: runtime, clone, one command, checklist; then the loop: edit, test, rebuild, verify, publish](img/fig_setup_flow.svg)

If the section 5 checklist passed, here is what is actually running on this VM —
worth reading once, because it is the mental model you will debug against later.

**The application.** One container named `crucible-py`, built from the image
`crucible-py:latest`, running as *you* rather than as root, listening on port
**49160** on `0.0.0.0` — every network interface the VM has.

**The data.** A single SQLite file in `data/` on the host, bind-mounted into
the container. It is *outside* the container on purpose: containers are
disposable, and yours can be deleted and recreated a hundred times without
touching a row.

**The encryption.** Corporate-signed certificate and private key in `certs/`,
mounted read-only at runtime and never baked into the image. Browsers show a
padlock with no warning; `curl` needs no `-k`.

**The site-specific settings.** `.env.local`, untracked, holding `CERT_SOURCE`,
optionally `CERT_HOSTNAME`, and `USE_HTTPS=true`. The one file no clone and no
backup will restore for you.

**Survival.** Lingering is enabled, so your programs outlive your logout. A
systemd user unit is enabled, so the container comes back after a reboot without
anyone logging in; the script rewrites that unit after every container it
creates and hands the container to it, so what boots is what runs
([`15-run-stop-status.md`](15-run-stop-status.md)).

**Watchfulness.** A cron entry every five minutes checking the app's health and
restarting it if it has wedged; another every Monday at 08:00 warning you a
month before the certificate expires; optionally a third at 02:00 taking a
nightly backup and keeping the last fourteen.

**The doorman.** Whatever firewall arrangement section 1.4 revealed, with 49160
open if there was a doorman to tell.

**Optionally, a second instance.** Since v2.20.0 the same VM can also run
the **beta instance** — a second folder, container and port (49161) with
its own copy of the data, where end users test and where every change
lands before it is promoted to production. Section 8 sets it up; it adds
a second unit, a second monitor line and a second log, and nothing else
above changes.

What you do *not* have: a load balancer, redundancy, or a second machine. This
is a single-VM deployment and it is honest about that. If the VM goes down, the
app goes down — which is exactly why the off-machine backup step in the
[uninstall guide](01-uninstall-rhel8.md#1-before-you-start) matters more than it
looks like it should.

---

## 7. RHEL8-specific gotchas

These are the traps specific to this platform. Each has bitten someone
already — that is how it earned its place on the list.

- **SELinux** ([glossary](00-glossary.md#the-container-words)): every bind mount
  must carry the `:Z` suffix (the scripts already
  do: `data/ → /app/data:Z`, `certs/ → /app/certs:Z,ro`). Running `podman run`
  manually without `:Z` yields `Permission denied` / an empty `/app/data`.

  **SELinux** is a security guard who works by labels. On top of ordinary file
  permissions (who owns it, who may read it), SELinux gives every file and every
  process a *label*, and enforces rules about which labels may touch which. A
  process labelled "container" is not permitted to read files labelled "ordinary
  home directory stuff", no matter what the file permissions say — which is
  precisely the point, since it means a compromised container cannot rummage
  through your home directory.

  The catch: your `data/` folder is ordinary home-directory stuff, and you *do*
  want the container to read it. **`:Z`** is how you say so. Appended to a bind
  mount, it tells podman to relabel that folder as container content, so the
  guard permits access. (Capital `Z` means *private to this container*;
  lowercase `z` would share it between several.) The scripts do this already. It
  only bites when you improvise a `podman run` by hand — and the symptom is
  cruel, because `Permission denied` or a silently empty `/app/data` looks like a
  broken mount rather than a security policy. If a bind mount seems to have
  produced an empty folder, check for `:Z` first.

- **Rootless limits**: ports < 1024 cannot be bound (49160 is fine); containers
  need lingering + a systemd user unit to survive reboots.

  Ports below 1024 are *privileged*, reserved by ancient and still-sensible
  convention for services that the administrator sanctioned — 22 for SSH, 80 for
  HTTP, 443 for HTTPS. A non-root user cannot claim one. This is a large part of
  why Crucible uses 49160: it is comfortably in the range any user may bind, and
  unlikely to collide with anything.

- **Corporate proxy**: always `curl --noproxy '*'` for localhost checks — the
  proxy otherwise intercepts them. The in-container healthcheck already
  bypasses the proxy; if `status` ever shows *unhealthy* while curl works,
  rebuild to pick up the proxy-bypassing healthcheck.

  That last clause describes a real production bug and its fix. An older image
  contained a healthcheck that did not bypass the proxy, so podman's health
  probe was intercepted and failed, while an ordinary `curl --noproxy '*'`
  succeeded — a container marked `unhealthy` that was in perfect health, and a
  monitor dutifully restarting a working app. If you ever see that combination,
  the answer is `./container-py.sh rebuild`, not investigation.

- **`podman build` needs `--format docker`** (the script adds it): podman's
  native OCI format silently drops the Dockerfile `HEALTHCHECK`.

  There are two formats an image can be written in. Podman's native OCI format
  has no place to record a `HEALTHCHECK` instruction — so it discards it,
  without a warning, and you get an image whose health can never be known.
  `--format docker` keeps it. Another reason to build via `./container-py.sh
  build` rather than by hand.

- **`start` reuses an existing container as-is** — env/port changes need
  `rebuild` (or `stop` + `rm` + `start`); the script warns and prints the port
  actually in use when it differs from the one requested. `start-ssl` always
  recreates.

  A container's settings — ports, environment variables, mounts — are fixed at
  the moment it is created and cannot be edited afterwards. `start` on an
  existing container therefore starts it *with its original settings*, and your
  new `CRUCIBLE_PORT=` is quietly ignored. It is not a bug; a container is a
  cast object, not a configurable one. To change settings you must create a new
  one, which is what `rebuild` and `start-ssl` do.

- **Custom port**: `setup-after-clone-py.sh`'s verify loop hardcodes 49160 — with
  `CRUCIBLE_PORT=<other>` the container is fine but the script's verification
  falsely fails; verify manually instead.

  An honest limitation, documented rather than hidden. If you run on a custom
  port, expect the setup script to end with a verification failure, and confirm
  by hand with `curl --noproxy '*' -sS https://localhost:<your-port>/api/stats`.

- **Cron + rootless podman on a network-mounted home directory**: any cron
  line invoking podman needs the `USER=… XDG_RUNTIME_DIR=…` prefix (see
  section 4).

  A **network-mounted home directory** is one that lives on a file server and
  appears on the VM over the network (NFS and friends) — common in corporate
  environments, so that your files follow you between machines. It makes
  podman's storage path resolution more fragile still, and turns the missing
  environment variables from "usually survivable" into "reliably broken".

---

**See also:** [RHEL8 Uninstall](01-uninstall-rhel8.md) ·
[Full deployment guide](07-operations.md) · [Project README](../README.md)


---

## 8. A second instance for user testing (beta)

**Time:** ~15 minutes, plus one image build (fast: every layer is already on
this VM). **Prerequisites:** sections 1–5 done, production running on 49160.
**Why:** end users are going to test the application, and the login is going
to be rehearsed. Neither should touch the laboratory's registry. The design
and the decisions behind it are [`14-beta-instance.md`](14-beta-instance.md)
and [ADR 0002](adr/0002-beta-instance.md); the phase that built it, with a
test for every route, is [phase SH-12](04-phase-tutorials/phase-sh-12-beta-instance.md).

![Production and beta on one server: two folders, two containers, two ports; publish reaches beta, promotion reaches production, data is copied one way on request](img/fig_two_instances.svg)

**Instance** ([glossary](00-glossary.md#the-container-words)) — one running
copy of the application: a folder, a container, a port, a database. You
have one; this section adds a second, called **beta**, that shares nothing
with the first at run time. *Everyday version:* a practice kitchen next to
the restaurant kitchen — same equipment, a copy of tonight's ingredients,
and whatever a trainee burns there, no customer eats.

Everything in this section runs **on the VM**, in the **new** folder unless
a comment says otherwise. Nothing here changes production.

### 8.1 Clone the private repository a second time, on the `beta` branch

```bash
# ▶ VM
cd ~/work/Pandora_toolbox
git clone https://github.com/nestle-it/nr-nips-crucible.git nr-nips-crucible-beta
cd nr-nips-crucible-beta
git switch beta
git branch -d master 2>/dev/null; git branch -d develop 2>/dev/null   # keep only beta here
chmod +x *.sh
git branch --show-current && git remote -v
```

**Why a second folder.** A folder holds one checkout of one branch, one
`data/`, one `certs/` and one `.env.local`. Two instances need two of each,
and beta must be able to run a commit production does not have yet. The
folder name ends in `-beta` so that `pwd` always tells you where you are.

**Why the `beta` branch.** It has existed in both repositories all along
and, until v2.20.0, always equalled `master`. It now means "what the beta
instance runs": every publish moves it; production's `master` moves only by
a promotion ([`03-git-workflow.md` → Flow A](03-git-workflow.md#4-flow-a---a-change-from-start-to-finish)).

**You should see:** `beta` from the first command and the private repository
twice (fetch and push) from the second — and **no** `public` remote.

**If instead:** `fatal: destination path 'nr-nips-crucible-beta' already exists` —
a previous attempt; `ls` it, and if it is empty or half-cloned, `rm -rf` it
and clone again. If it holds a `data/` folder, stop and look before deleting.

### 8.2 Write the three lines that make it beta

```bash
# ▶ VM — beta folder
cat > .env.local <<'EOF'
CERT_SOURCE=<cert-store-path>
USE_HTTPS=true
CRUCIBLE_INSTANCE=beta
CRUCIBLE_PORT=49161
EOF
./container-py.sh help | grep Usage
```

Replace `<cert-store-path>` with the same value production's `.env.local`
has (`cat ../nr-nips-crucible/.env.local` shows it). If production also sets
`CERT_HOSTNAME`, copy that line too.

**Why a file.** Every script — the container script, the setup, the
monitor, the uninstaller, and the cron job and service unit that run
without you — reads this file from the folder it is in. Nobody has to
remember a flag, and the day someone forgets it nothing is replaced by
mistake. The environment still wins over the file for a one-off command.

**Why the same certificate.** It names the host, not the port; one
certificate serves `:49160` and `:49161`. The setup script copies the same
pair into this folder's `certs/`.

![The three lines of the beta folder's .env.local fan out to the image, container, service unit, monitor log, cron line and address](img/fig_instance_name.svg)

**You should see:**

```
Usage: ./container-py.sh [command]        (runtime: podman · instance: beta → crucible-py-beta, port 49161)
```

**What it means:** every command run from this folder now names
`crucible-py-beta` on 49161. Production's folder still prints
`instance: default → crucible-py, port 49160`.

**If instead:** `✗ CRUCIBLE_INSTANCE='…' must be lowercase letters, digits and hyphens` —
the name is used inside container and file names; `beta` is the one this
guide assumes.

### 8.3 Run the one-shot setup — for the beta instance

```bash
# ▶ VM — beta folder
SETUP_MONITOR=y ./setup-after-clone-py.sh
```

**You should see** it open with

```
Instance: beta — image and container crucible-py-beta, port 49161
          (from .env.local or the environment; docs/14-beta-instance.md)
Step 1: SSL certificates
  ✓ Nestlé certificates copied and verified
Step 2: Building the crucible-py-beta image (first build takes a few minutes)...
```

— the build is quick here, every layer is already on the VM from
production's image — then

```
Step 3: Starting the container...
✓ Container started with HTTPS
  instance: beta · container: crucible-py-beta · image: crucible-py-beta:latest
Step 4: Verifying the API...
  ✓ API is answering:
{"chemicals":{"total":0,"max":15000},...
Step 5: Health monitoring (cron job, every 5 minutes)
  ✓ Monitoring cron installed (old monitor.sh entries replaced):
    */5 * * * * cd /home/<your-user>/work/Pandora_toolbox/nr-nips-crucible-beta && ... CONTAINER_NAME=crucible-py-beta API_URL=https://localhost:49161/api/health ./monitor.sh
```

**What it means:** two containers now run on this VM. Beta is **empty**
(`"total":0`) — a fresh instance, like production was on day one. The cron
line names this folder, this container and this port; production's line is
still there (`crontab -l | grep monitor.sh` prints two lines).

**If instead:** `Step 2: Building the crucible-py image` (no `-beta`) — the
`.env.local` is not in this folder or is misspelt. `cat .env.local`, fix,
run again.

**If instead:** `address already in use` — `CRUCIBLE_PORT` is missing and
both instances asked for 49160. Add the line and `./container-py.sh rebuild`.

### 8.4 Give beta a copy of production's data

```bash
# ▶ VM — production folder: a consistent snapshot while it keeps running
cd ~/work/Pandora_toolbox/nr-nips-crucible
./container-py.sh backup

# ▶ VM — beta folder: take production's NEWEST backup (a folder, so no timestamp to copy)
cd ~/work/Pandora_toolbox/nr-nips-crucible-beta
./container-py.sh restore ../nr-nips-crucible/backups
curl --noproxy '*' -sSk https://localhost:49161/api/stats | head -c 80; echo
curl --noproxy '*' -sSk https://localhost:49160/api/stats | head -c 80; echo
```

**Why a backup and not `cp`.** The database is in use; a plain copy of a
live SQLite file can be quietly corrupt. `backup` takes a coherent snapshot
inside the running container ([`07-operations.md` → Backup and restore](07-operations.md#backup-and-restore)).

**Why one way.** The restore runs in beta's folder against beta's `data/`.
Nothing writes into production's `data/` from anywhere but production's own
folder. Run the same two commands whenever the testers should start again
from a clean copy.

**You should see:** `Newest backup in ../nr-nips-crucible/backups: crucible-<stamp>.db`,
`✓ Restored … (instance: beta)`, the container starting again, and then two
identical stats lines — `"chemicals":{"total":12539` on both ports.

Open **`https://<vm-hostname>:49161`** in a browser: the same application,
the same 12,539 compounds, an amber **Beta** pill next to the title on a
pale amber bar (from v2.21.0), `[Beta]` at the start of the tab's title,
and in the right-hand corner **Running on port 49161**. Production's tab
shows an indigo **Prod** on a white bar. That is how a tester knows which
instance a tab shows ([phase SH-13](04-phase-tutorials/phase-sh-13-instance-label.md)).

### 8.5 Make it survive a reboot

```bash
# ▶ VM — beta folder, with crucible-py-beta running
mkdir -p ~/.config/systemd/user
podman generate systemd --new --name crucible-py-beta --files
mv container-crucible-py-beta.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now container-crucible-py-beta.service
systemctl --user status container-crucible-py-beta.service | head -3
```

The same three ideas as section 4.2 — lingering, a user unit, `enable --now` —
with the beta container's name. **You should see** `active (running)` and
`enabled`. Section 4.2's *If instead* notes apply unchanged.

### 8.6 Verify both instances

```bash
# ▶ VM — from any folder
podman ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
crontab -l | grep monitor.sh | sed 's/.*CONTAINER_NAME=/CONTAINER_NAME=/'
systemctl --user list-units 'container-crucible-py*' --no-legend
(cd ~/work/Pandora_toolbox/nr-nips-crucible-beta && ./verify-deploy.sh https://localhost:49161 | tail -2)
(cd ~/work/Pandora_toolbox/nr-nips-crucible      && ./verify-deploy.sh https://localhost:49160 | tail -2)
```

**You should see:**

```
NAMES             STATUS                  PORTS
crucible-py       Up 3 days (healthy)     0.0.0.0:49160->49160/tcp
crucible-py-beta  Up 5 minutes (healthy)  0.0.0.0:49161->49161/tcp, 49160/tcp
CONTAINER_NAME=crucible-py API_URL=https://localhost:49160/api/health ./monitor.sh
CONTAINER_NAME=crucible-py-beta API_URL=https://localhost:49161/api/health ./monitor.sh
container-crucible-py.service       loaded active running ...
container-crucible-py-beta.service  loaded active running ...
  16 passed, 0 failed
  Everything checks out.
  16 passed, 0 failed
  Everything checks out.
```

**What it means:** two of everything — container, port, unit, monitor line —
and sixteen checks passing on each. The bare `49160/tcp` in beta's `PORTS`
column is the port the image *declares*; beta does not publish it
(`podman port crucible-py-beta` prints only `49161/tcp -> 0.0.0.0:49161`).

**If instead** `list-units` shows only one of the two units: that command
hides *inactive* units. Since v2.21.2 a unit is active whenever its
application runs, because every script command hands the container to
the service; an inactive unit beside a running container means an older
version started it, and `./container-py.sh start` in that folder hands it
over. Only `failed`, or a unit missing from
`systemctl --user list-units --all 'container-crucible-py*'`, needs action:
`reset-failed`, or section 4.2 again. The full table of what you can see
and what to do is in [`15-run-stop-status.md`](15-run-stop-status.md#when-something-looks-wrong).

**If instead** the restore's final lines said `http://localhost:49161`: the
container it restarted still serves HTTPS — `curl -k https://…` proves it —
and the message was wrong before v2.20.2, which reads the scheme from the
container.

### 8.7 Day 2 for the beta instance

| I want to… | Command (beta folder) |
|---|---|
| Update beta to what was just published | `git pull --ff-only origin beta`, then `./container-py.sh rebuild` if code changed — [`03-git-workflow.md` Step 10](03-git-workflow.md#step-10---deploy-to-the-beta-instance). The rebuild stops the service if it is active, rewrites the unit from the new container and hands the container to the service ([why](07-operations.md#auto-start-on-boot-systemd)) |
| Check it, stop it, start it, restart it | `./container-py.sh status` · `stop` · `start` · `restart` in this folder, or `systemctl --user … container-crucible-py-beta.service` from anywhere; both agree — [`15-run-stop-status.md`](15-run-stop-status.md) |
| Give the testers a fresh copy of production | the two commands of 8.4 |
| See what beta has that production does not | `git log --oneline origin/master..origin/beta` (after `git fetch origin`) |
| Promote it to production | not from here — [`03-git-workflow.md` Step 11](03-git-workflow.md#step-11---promote-to-production-when-the-testers-agree), from the development machine and the mirror folder, then production's own folder |
| Turn the login on (since v2.22.0) | two lines in this folder's `.env.local`, then `./container-py.sh stop` and `start` — [phase SH-3a, Step 7](04-phase-tutorials/phase-sh-3a-token-gate.md#step-7--turn-it-on-beta-first); the testers get the token out of band |
| Give each tester an account (since v2.23.0) | `./container-py.sh users add <name> --role viewer\|editor\|admin` in this folder, then `AUTH_MODE=local` and a `SESSION_SECRET` in `.env.local`, `stop` and `start` — [phase SH-3b, Step 9](04-phase-tutorials/phase-sh-3b-local-accounts.md#step-9--turn-it-on-beta-first); each tester gets a temporary password out of band and changes it in the page; on production the accounts are created first and the token stays until the announced switch ([Step 10, in two moments](04-phase-tutorials/phase-sh-3b-local-accounts.md#step-10--production-in-two-moments-the-accounts-then-the-switch)) |
| Remove the beta instance | `./uninstall.sh --dry-run` here first: it opens with `Instance: beta` and lists only beta's container, image, unit and cron line; then the mode you mean. Production is not listed and not touched |

The weekly certificate check (section 3.4) and the nightly backup (6.3)
stay in production's folder: the certificate is the same file, and beta's
data is a copy that 8.4 recreates in two commands.

**Last Updated:** September 23, 2026

---

**Next:** [RHEL8 uninstall guide](01-uninstall-rhel8.md) — clean removal, including the server-only pieces.
