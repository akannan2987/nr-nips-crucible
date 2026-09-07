[← README](../README.md) · [Handbook](HANDBOOK.md) · [Glossary](00-glossary.md)

# Lessons learned — the bugs that real verification found, and what each taught

**What this is:** every bug found by *following a written procedure literally*
on a real machine rather than by reading the code. They are recorded because
the lesson generalises, and because a project that lists no mistakes is a
project that has not been verified.
**The shape to look for:** almost every entry is **an operation reporting one
thing while doing another** — a dry run that wrote, a status that could not
fail, a verification that could not run and printed what a pass looks like, a
list treated as ranked. When you review code or documentation on this project,
look for that shape first.

*Everyday version:* a smoke alarm with a flat battery. It hangs on the ceiling
looking exactly like a working one; the only way to know is to press the test
button. Every entry below is a test button that was pressed.

---

## Contents

- [From walking the install and uninstall guides](#from-walking-the-install-and-uninstall-guides)
- [From loading real laboratory data](#from-loading-real-laboratory-data)
- [From identifying and auditing compounds](#from-identifying-and-auditing-compounds)
- [The one rule they add up to](#the-one-rule-they-add-up-to)

---

## From walking the install and uninstall guides

**1. The update command silently downgraded HTTPS to HTTP.** `rebuild` — the exact
command the update instructions tell you to run — brought the app back on plain
HTTP. Nothing failed, nothing logged a warning; the padlock just quietly went
away. *Lesson: a command that "restarts things" must preserve every mode the
old process was running in, and the ones you forget are the invisible ones.*

**2. `status` reported nothing at all in TLS mode**, because it probed `http://`
against an HTTPS listener. The healthcheck was structurally incapable of
succeeding on the production configuration.

**3. `start` printed the port you asked for**, not the port actually being served,
when it reused an existing container. The output was confident and wrong, which
is worse than no output.

**4. `.env.local` was ignored on a fresh install.** `USE_HTTPS=true` was only
honoured if a container already existed to copy the setting from — so the first
start after an uninstall came up unencrypted, at the moment nobody was
watching.

**5. `uninstall.sh` aborted halfway through, reporting success.** Six functions
ended with `[ "$found" -eq 0 ] && { ...; }`. When something *was* found, that
expression evaluated false, the function returned non-zero, and `set -e` killed
the script — so the image was never removed. *Lesson: under `set -e`, never end
a bash function with a bare `[ ... ] && { ... }`. Use `if ... fi`.*

**6. A clean uninstall looked like a failed one.** Removing a systemd unit file
leaves an in-memory record that prints as `not-found failed failed`. Everything
had worked; the output said otherwise. The script now calls `reset-failed`.

**7. The docs said `cp -r data/` immediately after taking a proper backup.** A
plain copy of a live SQLite file can be quietly corrupt — it opens fine and
fails much later. The guides now copy the snapshot out of `backups/` instead.

**8. Thirty-five verification commands used `curl -s`.** With `-s`, a failed
request prints *nothing* — indistinguishable from a successful silent one. Every
one became `-sS`. *Lesson: in a document that teaches, a command that can fail
invisibly is worse than no command at all.*

**9. A weekly certificate check reported "OK" for months without ever looking at a
certificate.** Its cron line pointed at a second checkout that has no `certs/`
directory, and "no certificate present" was being treated as "nothing wrong".
*Lesson: a monitor that cannot fail is not a monitor.*

**10. The macOS monitoring cron never ran once.** Two independent causes stacked:
cron's minimal `PATH` excludes the podman install location, and macOS blocks
cron from reading `~/Documents` without Full Disk Access. Neither produced an
error anybody saw.

**11. Verification commands that could not run looked exactly like passing ones.**
After a full uninstall deletes the project directory, the shell is left standing
in a folder that no longer exists, and every `podman` command fails with
`error getting current working directory`. Run as `podman … | grep crucible`,
that failure prints nothing — which is precisely what the guide says a pass
looks like. The uninstall guide now starts those blocks with `cd ~`.



**12. HTTPS against `localhost` could never validate on the VM.** The
certificate's subject alternative names list only the machine's full
hostname, so a `curl https://localhost:…` without `-k` fails the check every
time, and a guide that used it looked broken on a working server. The guides
now show the full-hostname form for validation and `-k` for the local probe.
*Lesson: a check must be written for the name the certificate actually
carries.*

**13. The reinstall path silently dropped two steps.** Lingering (which lets
rootless containers survive logout) and the certificate-expiry cron both sit
inside a section headed "one-time prerequisites" — which a reinstaller
skips, reasonably, having done it once. The reinstall walk lost both. Fixed
with an R1–R9 reinstall checklist. *Lesson: a cross-reference is not a
step.*

**14. The monitor restarted a healthy server every five minutes, reporting
success.** `monitor.sh` defaults to `http://`; on an HTTPS-only server that
request is refused, the script concludes the app is dead, restarts it, and
logs a recovery. In cron, forever. The RHEL 8 checklist now leads with
`API_URL=https://…` and checks the installed cron line. *Lesson: a monitor
whose default cannot succeed on the production configuration is an outage
generator.*

**15. A placeholder was pasted literally into a cron line.** The guide said
`cd <THIS folder, from pwd>`; an operator pasted it as written; `sh` read
`<THIS` as a redirection and the weekly certificate check never ran, quietly.
The second time this check failed invisibly. Every home for that line now
*generates* it with the absolute path filled in. *Lesson: never ask an
operator to paste a path into a command you could substitute for them.*

**16. Stale expected output in the checklists.** One guide promised
`147 passed`, another `214 passed`; the suite had 47 tests (90 since phase
04). A reader who trusts the number and gets a different one cannot tell a
drift in the docs from a failure in the code. *Lesson: an expected output is
a claim; review it against the code whenever a verification walk is done.*

---

## From loading real laboratory data

**17. A "dry run" that wrote to the database.** The preview mode of a linking job
reported *"Dry run — nothing written"* and had already written 1,897 rows. It
recorded each link through a helper that commits on every call, so the closing
rollback had nothing left to undo. *Lesson: a rollback cannot undo a function
that already committed — check what the helpers do, not what the flag says.*

**18. A job that looked hung was doing ten thousand disk commits.** The same helper
meant one transaction per row against a 116 MB file. No output for minutes,
indistinguishable from a crash. *Lesson: batch writes, and print progress often
enough that a slow network cannot be mistaken for a dead process.*

**19. A cache keyed on a number that never stopped moving.** The column metadata was
cached against the count of registered compounds, so that a "how many are
identified" figure stayed fresh. During identification that count changes every
few seconds, so the cache never once hit, and every request re-read all 49,000
records while competing with the job for the database. It surfaced as dropped
connections.

**20. A feature that had shipped, reported missing.** `index.html` was served with
no cache headers. It names a content-hashed script bundle, so a cached copy
pinned the browser to an old build no matter how many times it was reloaded.

**21. `cut -d,` on a file full of commas.** A report summarised with `cut` turned
`Phenol, 2,4-di-tertiobutyl` into fragments and produced a meaningless summary.
*Lesson: CSV has quoting rules; parse it with something that knows them.*

**22. Deleting a compound left its measurements pointing at nothing.** The delete
endpoint removes the entry without unlinking the rows that reference it. Fixed
with a tool that unlinks first — but the endpoint still behaves that way, which
is recorded rather than hidden.

---

**23. One substance registered twice.** Keying the registry on the CAS
number alone let one compound register under two different numbers, both
pointing at the same public-database identifier. The linker now keys on the
compound identifier too. The opposite mistake was also made and walked
back: a *shared name* with different CAS numbers and different compounds is
not a duplicate. *Lesson: "same thing" needs a definition before a check can
enforce it.*

**24. A verification command that could not run, reported as a pass.** A
check for a running background job used `ps` inside the container; the slim
image has no `ps`, so the command failed, and `grep -c` on the failure
printed `0` — exactly what "not running" looks like. `podman top` from the
host is the reliable way. *Lesson: a tool that is absent fails in the same
voice as a tool that found nothing.*

---

## From identifying and auditing compounds

**25. Position zero in a list nobody ranked.** Looking a compound up by its registry
number used an endpoint that returns *every* compound referencing that number,
ordered by internal identifier. The code took the first. For one number that is
the right substance; for the next it is an unrelated one that merely mentions
it. Nineteen compounds were registered holding another substance's formula —
a food antioxidant carrying nicotine's chemistry — while every registry number
in the source file was correct. *Lesson: an interface returning a list has not
thereby ranked it.*

**26. Two audit heuristics that had to be thrown away.** The first compared the
laboratory's name for a compound against the public database's and flagged
disagreement; but `Monostearin` and `Glycerol, 1-monooctadecanoate` are one
substance sharing no words, so it flagged correct entries. The second assumed a
name containing "ester" implied a heavy molecule; ethyl acetate is an ester at
88 g/mol, and it produced 28 false alarms out of 41. Only checkable chemistry
worked — a carbon chain the formula cannot hold, an element the name never
mentions. *Lesson: a check that cries wolf is worse than no check, because it
teaches the reader to skim.*

**27. An audit that examined the wrong half of the data.** It read one field, which
only one of the two import paths writes. Of 686 records it checked 367 — and the
319 it skipped were precisely the ones that had never been reviewed.


**28. The gate passed on a file it could not see.** The public-safety gate
searched *tracked* content for internal identifiers. New figures were run
past it while still untracked, it reported safe, the files were committed and
pushed, and only the next run — with the files now tracked — found a real
workbook code in an example row. The gate now searches untracked files too.
*Lesson: a check that runs before `git add` must look at the working tree,
not the index; otherwise "new" is exactly the case it misses.*

---

## The one rule they add up to

Documentation detailed enough to be followed literally is documentation
detailed enough to be *tested* — and an instruction nobody can test is just a
hope. Every guide in this repository therefore shows the output a command
should produce and names the likely mistakes, so that the next person who
presses the test button finds a working alarm.

Where each fix landed: the container script, the uninstall script and the
guides are described as they now are in [`07-operations.md`](07-operations.md)
and the setup guides; the identification rules and the audit are in
[`09-chemical-identification.md`](09-chemical-identification.md); the remaining
open behaviour (the delete endpoint) is on the [roadmap](05-roadmap.md).

**Last Updated:** September 7, 2026
