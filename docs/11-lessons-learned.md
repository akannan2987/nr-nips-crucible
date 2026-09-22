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


**29. A comment stated what a platform does, without checking.** The first
CI workflow said in its header that the private repository "does not run
workflows", and ran the publication gate unconditionally. The private
repository does run workflows; its first run failed at the gate, which
refused the six real workbooks that repository carries on purpose. The gate
was right; the assumption was wrong. The gate is now conditional on the
repository name, and everything else runs on both sides. *Lesson: a sentence
that describes what another system will do is a claim, and a claim about a
system you can push to is one push away from being tested.*


**30. A script that had only ever met the data it had.** The removal script
read a `chemical_id` column on every kind of row. Samples have no such
column — a sample points at *many* chemicals, through a list inside its
document — so the script would have crashed on the first sample it met. It
never had, because production holds no samples. The script's first
automated test seeded one, and found it in a minute. *Lesson: a tool
exercised only on the data you happen to have has been tested for the
absence of the data you do not.*


**31. A check that passed only in the shell it was written in.** The
post-deploy verification used a curl option added in curl 7.71. On the VM it
passed for weeks — because the shell it ran from had a conda environment
active, with a newer curl. Run from a plain login shell, RHEL 8's system curl
(7.61) rejected the option, every request failed, and the script reported
thirteen failures against a deployment that was fine, including "a write was
not refused". The script now retries by hand and works with the oldest curl
in use. *Lesson: a verification script must run with the tools the machine
actually has, not the ones your shell happens to add; and a check whose
failure mode looks like a security failure must fail loudly about itself
first.*

---

**32. A tag with the right name on the wrong commit.** The first release tag
was made on the development machine and pushed to the public repository. On the VM, the
mirror's `git fetch public` copied that tag along with the commits, so
`git tag -a v2.10.1` on the mirror's own commit failed with "already
exists" — and the next command pushed the *copied* tag, pointing at the
public commit, into the private repository, dragging 839 objects of public
history with it. The private release page then showed a commit on no
private branch and "71 commits since this release", a comparison between
two unrelated histories. Nothing secret moved, because public content is a
subset of private, but the tag was wrong and had to be deleted, on the
host and in git, and remade on the private commit. *Lesson:* the two
repositories share tag *names* and nothing else; the mirror now fetches
the public remote with tags switched off (`remote.public.tagOpt
--no-tags`), Step 8b checks which commit the tag points at before pushing,
and the setup section says why. *The shape:* an instruction that worked on
one machine, given for the other without asking what else the same
command does there.

---

**33. A cache keyed on a count cannot see an update.** The registry's
column list — every column the entries have — is discovered by reading
every entry, so the answer was cached and rebuilt only when the number of
entries changed. Then the export was re-imported on production to pick up
the batch values a fix had started keeping: 12,539 entries updated, none
added. The count did not move; the cache did not move; the page went on
showing 10 batch columns where 34 had just been written, and would have
until the next restart. The first fix — key the cache on the newest
`updated_at` as well — was right and cost a full scan of every document on
every call, a second on this registry, which is worse than the bug. The
cache is now invalidated by any write through the chemicals API and expires
after thirty seconds for writes made from outside the process, which the
import script is. Found because the deploy check's question was asked
again after the import: "how many batch columns?" *Lesson: a cache key must
change with everything the cached answer depends on, not with the one
thing that is cheap to ask; and where a writer exists that the cache cannot
see, the cache must expire on its own.* *The shape:* a status that cannot
change.

---

**34. Three answers per click, and the last one to arrive wins.** The
registry page asked the server three questions on every click — the rows,
the notices, the new counts — and two of the three recount all 12,539
entries. Nobody noticed on the test data; on the real registry, four quick
clicks queued twelve requests, the browser waited seconds for each, and
the answers came back in whatever order the server finished them. The
page applied each as it arrived, so an older, slower answer overwrote a
newer one and the table showed a state no button described: "Showing 0 of
0" under buttons that said otherwise. The owner reported it as "nothing I
click works", which was exactly true. The fix was three small things —
count once instead of on every click, drop an answer that is no longer
the latest and cancel the request behind it, cache the whole-registry
answers on the server — and none of them was visible in the code until a
browser was driven against the real data with a log of every request.
*Lesson: a page that fires a request per click must expect the answers in
any order, and a count that reads everything must not be asked for on
every click; and the only way to see either is to drive the page as a
person does, against data of the real size.* *The shape:* an operation
reporting one thing (the buttons) while showing another (the answer to an
earlier click).

**35. "The" container, when there are two.** Every script that managed the
application knew one container by name: `crucible-py`. That was true for
as long as there was one. The moment a second checkout was to run beside
it, three scripts that had never been wrong became dangerous without a
line of them changing: the setup removed *every* monitor line from the
crontab before writing its own, so installing beta would have silently
stopped watching production; the uninstaller removed *every* crucible cron
line and *the* unit, so `./uninstall.sh --partial` in the beta folder
would have stopped production; and the monitor, run by hand in the beta
folder, would have restarted production. All three were found on a
laptop, with two containers and a fake crontab, before the server had a
second folder. The fix that took longest to get right was the smallest:
scoping a cron line to its folder by path — because `…/nr-nips-crucible-beta`
*begins with* `…/nr-nips-crucible`, a plain prefix match from the
production folder would have removed beta's lines too. The path is now
matched with what follows it. *Lesson: a name that was never a variable is
a hidden assumption that there will only ever be one; and when a path is
used as a key, match its boundary, not its prefix.* *The shape:* an
operation reporting one thing (cleaning up after itself) while doing
another (cleaning up after its neighbour).

**36. Two supervisors, one container.** The beta instance had a systemd
unit, made the way the guide says, and the unit was active because it had
started the container that morning. Then the first rebuild since arrived
with two new environment variables. The script stopped the container,
removed it and started a new one with the variables, and printed the
right instance name. Seconds later the unit, whose job is to restart the
container when it dies, ran the command it had recorded the day before
and replaced the script's container with one that had no name. The page
on port 49161 said *Prod*. Every command had done exactly what it was
written to do; the two of them had never been told about each other. The
diagnosis took three read-only commands: the container's creation time
matched the unit's start time, not the script's, and its environment had
no name. The fix is in the script, not in a warning: it stops an active
unit before it touches the container and rewrites the unit from the
container it created, so the boot-time recipe is never older than what
runs. *Lesson: when two things are allowed to start the same process, one
of them must know about the other; a documented rule that a person has to
remember at the right second is not a fix.* *The shape:* an operation
reporting one thing (the script's `instance: beta`) while another does
the opposite (the unit's silent replacement).

**37. A rule a person must remember at the right second is not a fix.**
After lesson 36 the script stopped an active service before touching the
container and rewrote the service's recipe afterwards. Correct, and still
confusing: the service was inactive whenever the script had started the
application, so `systemctl status` said "dead" about an application that
was answering, and whether `stop` worked through the service depended on
who had started it. The owner read the pages that explained this and
could not follow them, and said so. The explanation was accurate and the
design was wrong: two things were allowed to run the same application, so
every honest sentence about it had a condition in it. The fix was to make
one of them the owner. The script now builds, hands the container to the
service, and drives status, stop, start and restart *through* the service;
the service is active whenever the application runs; both doors always
show and change the same thing. Then one page could be written without a
single "it depends", and every other page points to it. *Lesson: when a
document about an everyday task needs a paragraph called "how the two
relate", change the two, not the paragraph.* *The shape:* a status that
reported one thing (`inactive`) while the application did another
(answered).

**38. A monitor that cannot tell "refused" from "dead" restarts a healthy
application forever.** Every probe — the container's own, the cron
monitor, the script's wait-for-ready — asked `/api/stats`. The moment a
login is on, that route answers 401 to a probe with no token, which every
probe would have read as "dead": `unhealthy` in `podman ps`, a restart
every five minutes, and a log saying `✓ Container restarted successfully`
each time. Caught in the design of SH-3a, before the gate was built: one
open route that says only *ok* (`/api/health`), every probe moved to it,
and the monitor trying it first at whatever address its old cron line
names. *The lesson: write the open door before the lock, and make the
watchman check the door that will still open.* *The shape:* a check that
would have reported one thing (dead) while another was true (answering,
and correctly asking for a badge).

**39. A probe at the wrong port restarted a healthy production.** The
evening the login went on for production, `./monitor.sh` was run by hand
in production's folder as a check. The server's shell exports `PORT=3000`
for something else; the container script has ignored a generic `PORT`
since the port clashes of 2026-08, but the monitor still honoured it when
the folder had no `CRUCIBLE_PORT` (beta's has one, production's does not).
It probed port 3000, found nothing, declared the application dead, and
restarted it through its service; the second probe at port 3000 failed
too, so it logged `✗ Container restart failed` about an application that
was up and answering. Two fixes: the monitor derives its port the way the
container script does, and it refuses to restart a container whose
published port is not the one it probed, naming both. *The lesson: every
script that reads a setting must read it the same way, and a watchman must
check that it is looking at the right door before kicking it in.* *The
shape:* a status that reported one thing (dead, restart failed) while
another was true (answering; restarted for nothing).

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

**Last Updated:** September 22, 2026
