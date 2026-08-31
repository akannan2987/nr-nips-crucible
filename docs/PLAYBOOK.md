[← README](../README.md) · [All docs in order](../README.md#the-documentation-in-order) · [Glossary](GLOSSARY.md)

# The Playbook — running Crucible, start to finish

**Prerequisites:** none. No chemistry, no databases, no command line experience.
**Learning goal:** after this you will understand what this system is *for*, and
be able to load a laboratory file into it, check the result, correct what is
wrong, answer your own questions, and publish a change — knowing at each step
why you are doing it and how to tell whether it worked.
**Time:** an hour to read. The tasks themselves are mostly minutes, with two
long-running jobs flagged where they appear.

> ### How to use this
>
> The other guides answer *"how does X work?"*. This one answers **"what do I do,
> and in what order?"** — the whole sequence, once, with the reasoning attached.
> Where a topic has its own guide, this points at it rather than repeating it.
>
> **Grey boxes are commands.** Type or paste them into a terminal.
> **You should see** is roughly what appears. **What it means** is one sentence
> of translation. **If instead** covers the likely ways it goes wrong.
>
> Words in **bold with an em-dash** are being defined as they first appear, with
> an everyday comparison. Every term is also in the
> [Glossary](GLOSSARY.md).

## Table of Contents

- [Part 0 — What this thing is](#part-0--what-this-thing-is)
- [Part 1 — Get it running](#part-1--get-it-running)
- [Part 2 — Put a laboratory file in](#part-2--put-a-laboratory-file-in)
- [Part 3 — Look at what arrived](#part-3--look-at-what-arrived)
- [Part 4 — Give the compounds an identity](#part-4--give-the-compounds-an-identity)
- [Part 5 — Check what you registered](#part-5--check-what-you-registered)
- [Part 6 — Correct what is wrong](#part-6--correct-what-is-wrong)
- [Part 7 — Ask your own questions](#part-7--ask-your-own-questions)
- [Part 8 — Change something and publish it](#part-8--change-something-and-publish-it)
- [Part 9 — What to run, and when](#part-9--what-to-run-and-when)
- [Part 10 — When something goes wrong](#part-10--when-something-goes-wrong)

---

# Part 0 — What this thing is

## The problem, before any software

A laboratory tests packaging. It puts a plastic bottle in contact with a liquid,
waits, then measures which chemicals moved out of the plastic and into the
liquid. Each test produces a spreadsheet row: *this sample, this compound, this
much*.

Do that for a year and you have fifty thousand rows across dozens of
spreadsheets. Now someone asks a reasonable question:

> *"How much of this substance have we found across all our packaging?"*

And you cannot answer it. Not because the data is missing — because the same
substance is written down eleven different ways:

```
EICOSANE (POSH)      Eicosane (POSH)     EICOSANE
EICOSANE (posh)      Eicosane (posh)     EICOSANE POSH)     ← someone missed a bracket
Eicosane             EICOSANE (POSh)     …and three more
```

Every one of those is the same chemical. Your spreadsheet does not know that.
Sort by name and you get eleven groups. Total them and you get eleven totals.

**That is the problem this application exists to solve.** Everything else —
the tables, the filters, the exports — is in service of it.

## Four words you will meet constantly

Think of a laboratory as a kitchen, and these as the four things it writes down:

- A **chemical** is a substance on paper — a name, a formula, an identifier. Like
  an entry in a recipe book: "butter". It is the *idea* of the thing.
- A **sample** is a physical quantity of something, sitting in a vial with a
  label. Like the actual pack of butter in your fridge: a specific one, bought
  on a specific day.
- **Screening** is the fast, broad first test — run the sample past an
  instrument and record everything it detects. Like glancing in the fridge and
  listing what is there.
- A **toxicology study** is the slow careful one that follows: how much of it is
  safe. Like reading the label properly.

Crucible holds all four, and links them together.

## The CAS number — a passport for a chemical

A **CAS number** — a chemical's internationally agreed identifier, written like
`112-95-8`. Every laboratory on earth uses the same number for the same
substance.

Think of it as a passport number. Your name might be written *Smith, John*,
*John Smith*, or *SMITH J.* on different forms. The passport number is the same
on all of them, and it is what proves they are one person.

That is exactly its job here. Those eleven spellings of eicosane all carry
`112-95-8`, and that number is what lets the software know they are one
substance.

**Roughly three quarters of the rows in a real laboratory file have no CAS
number at all.** That is not a fault in this software; it is what the instrument
produced. It sets a ceiling on what any tool can identify, and it is worth
knowing before you start.

## How the software is put together

Three pieces, and it helps to know which is which when something misbehaves:

- **The container** — a sealed lunchbox holding the application and everything it
  needs to run: its own Python, its own libraries, its own miniature operating
  system. It runs on the server but does not mix with it. Delete the lunchbox
  and every trace of the app goes with it.
- **The database** — one file, `data/crucible.db`. Not a server, not an account,
  no password. Copying that one file copies everything, which is exactly what
  the backup command does.
- **The web interface** — what you see in a browser, served by the same program
  that holds the data.

## The one design decision worth knowing

Each record is stored **whole**, exactly as it arrived, as a single block of
text — plus a handful of separate columns used for finding it quickly.

The everyday version: most systems file your data into pre-printed forms with
fixed boxes, and anything that does not fit a box is thrown away. This one keeps
the original document in the folder, and writes a few index cards to find it
by.

That is why a spreadsheet with columns nobody anticipated can be loaded without
losing anything, and why adding a field later breaks nothing. The cost is that
searching an un-indexed field means reading every document — which is fine at
this scale and is the next planned piece of work.

The consequence you will actually notice: **nothing is ever silently discarded.**
When cleaning changes a value, the original is kept beside it.

---

# Part 1 — Get it running

If somebody has already set this up for you and given you a URL, skip to
[Part 2](#part-2--put-a-laboratory-file-in).

## Which guide

| You are on | Follow | Why |
|---|---|---|
| Your own Mac, to try things | [macOS Install](INSTALL-MACOS.md) | Runs on `localhost`, nobody else can reach it |
| The RHEL8 server, for real use | [RHEL8 Install](INSTALL-RHEL8.md) | HTTPS, real certificates, survives a reboot |

Both come down to one command, `./setup-after-clone-py.sh`, but the guides walk
every step and name the likely mistakes. **Follow the guide the first time.**

## Confirming it works

```bash
cd ~/work/Pandora_toolbox/nr-nips-crucible
curl --noproxy '*' -sSk https://localhost:49160/api/stats
```

**You should see** a line of counts:

```json
{"chemicals":{"total":664,...},"screening":{"total":49065},...}
```

**What it means:** the application is running and can read its database. This is
the single most useful check in the whole system — if it answers, everything
underneath is working.

**If instead** `curl: (7) Failed to connect` — nothing is listening. Start it
with `./container-py.sh start-ssl`.

**If instead** `curl: (52) Empty reply from server` on an `http://` address —
that is *correct* on a server configured for HTTPS. Use `https://`.

> **Two flags that always appear.** `--noproxy '*'` stops a corporate proxy
> intercepting a request to your own machine. `-sS` shows errors but hides the
> progress bar — never use plain `-s`, which hides failures too and makes a
> broken command look like a silent success.

## The one-command health check

```bash
./verify-deploy.sh https://localhost:49160
```

**You should see** sixteen lines of `PASS` and `Everything checks out.`

**What it means:** every feature has been exercised — the table loads, filters
work, sorting works, exports work, the query console refuses to write, no
compound record is broken. Run this after any change.

---

# Part 2 — Put a laboratory file in

## What happens to your file

Four stages, and understanding them makes the rest obvious:

```
   your spreadsheet
         │
         ▼
   ┌───────────────┐   Is this a file shape I recognise?
   │  Recognise    │   Matched by its column headings.
   └───────┬───────┘
           ▼
   ┌───────────────┐   Fix the mess: encoding, error cells,
   │  Clean        │   repeated headings, odd spellings of "nothing".
   └───────┬───────┘
           ▼
   ┌───────────────┐   Store the tidy version AND the original row.
   │  Store        │   Nothing is discarded.
   └───────┬───────┘
           ▼
   ┌───────────────┐   Point each row at a known compound,
   │  Link         │   where one is already registered.
   └───────────────┘
```

## The mess it expects to find

Real exports are not tidy. A genuine 49,000-row file contained all of this:

| What was in the file | Why it is a problem | What happens now |
|---|---|---|
| `#DIV/0!` and `#VALUE!` | Excel failed to calculate something. Not a measurement | Stored as empty, counted and reported |
| `NA`, `N/A`, `-`, blank | Four spellings of "nothing" | All treated as no value |
| `No compounds found above 0.01 mg/kg` | A sentence where a number goes | Recognised as *a clean sample* — a real result, flagged as such |
| Column headings repeated in the middle | Several exports were pasted together | Those rows are dropped |
| `°C` in an unusual encoding | Written by Excel on Windows | Detected and read correctly |
| Two CAS numbers in one cell | The instrument could not choose between two candidates | Shown exactly as written; neither is invented |

**The distinction that matters most:** an empty cell means *nobody measured
this*. `#DIV/0!` means *a calculation failed*. "No compounds found" means *we
looked and it was clean*. Those are three different facts and the system keeps
them apart.

## Uploading

In the browser: **Screening → Upload Screening (ELN)**, choose your file.

**You should see** a summary when it finishes:

```
Imported 49,065 screening records from Cergy packaging migration screening.
0 linked to registered chemicals; 49,065 await identification.

Recognised as cergy_screening · tagged Cergy_data · read as cp1252
Rows read 49,068      Records stored 49,065
Formula errors → empty 6,321    Repeated headers dropped 3
Below detection limit 20        Duplicate groups flagged 1,218
```

**What it means:** the file was recognised, cleaned, and stored. Read that
report — it is the honest account of what the cleaning did. If 6,321 cells
became empty, you should know that rather than discover it later.

**"0 linked to registered chemicals" is expected** on a fresh system. Linking
compounds is [Part 4](#part-4--give-the-compounds-an-identity); it is a separate
step by design.

**If instead** the upload is rejected as an unrecognised format, the file's
column headings do not match any template the system knows. Adding a template is
a small change — see
[Architecture](architecture.md) — but it is a developer task, not a
configuration setting.

---

# Part 3 — Look at what arrived

Open **Screening → View Screening Data**.

## The table is built from your file

The column headings are **your** headings, converted to a consistent style:
`lims`, `name`, `cas`, `mg_kg_food`. Including the typo — the file says
`additionnal information` with two Ns, and so does the table. Correcting it
silently would make the two harder to reconcile.

Columns marked **+** are ones the application added. Click *"What are the N
columns marked +?"* above the table to see what each means.

## Two views

- **Raw view** — every column, in the order your file had them. This is the
  spreadsheet, on screen.
- **Choose columns** — pick the ones you care about. The list shows how well
  populated each column is, so you can tell a column that is always empty from
  one that matters.

## Finding things

| To do this | Use |
|---|---|
| Find a word anywhere in any record | The search box |
| Narrow one column | The `filter…` box under its heading |
| Combine conditions | Several filter boxes at once — they add up |
| Sort | Click a heading. Click again to reverse |
| Show only one data source | The **All sources** dropdown |

Filters are *contains*, not *exact* — typing `ethanol` finds `ethanol 95%` and
`Ethanol 20%`. Free-typed laboratory text almost never matches exactly, so exact
matching would find nothing.

## The coloured rows

Some rows are shaded, and the legend above the table explains them:

- **Amber — an exact copy.** Every column matches another row. The same row
  present twice, usually because several exports were combined.
- **Blue — a repeat measurement.** Same sample, same compound, same conditions,
  but **different measured values**. The substance was measured more than once
  and the results differ.

**These are not the same thing, and the difference matters.** In one real file
there were 1,482 exact copies and 1,002 repeat measurements. Deleting "duplicates"
without that distinction would have destroyed a thousand genuine results.

The dropdown lets you show: all rows, unique rows only (hiding exact copies but
**keeping** repeat measurements), only the exact copies, only the repeats, or
anything flagged.

## Getting data out

**Export** gives you CSV, TSV, Excel or JSON. Two things worth knowing:

- It exports **everything matching your current filters**, not just the page on
  screen.
- **Raw export** gives the original values exactly as your file had them —
  `#DIV/0!` and all. That is what you want when reconciling against the source.

---

# Part 4 — Give the compounds an identity

## Why bother

Remember the eleven spellings of eicosane. **Identification** is the step that
collapses them onto one entry, and attaches chemistry your file never contained
— molecular formula, weight, structure.

The phone analogy, because it is exact:

| On your phone | Here |
|---|---|
| Three conversations from one person | Eleven spellings, one compound |
| Their phone number | The CAS number |
| Saving them as a contact | Registering the compound |
| Photo, address, birthday | Formula, weight, structure |
| Your address book | **PubChem**, a free public chemical database |

Saving a contact does two things: three conversations become one person, and you
gain details the messages never held. Identification does exactly those two
things.

> **It is optional.** Everything in Part 3 works without it. Unidentified rows
> simply show the compound name your file recorded. Identification adds
> cross-referencing; it is not a prerequisite for using your data.

## How a compound gets identified

Two stages, tried in order. **The second only runs if the first finds nothing.**

| Stage | When | Rule | Network? |
|---|---|---|---|
| 1. Your own registry | At upload, instantly | **EITHER** the CAS **or** the name matches | No |
| 2. PubChem | A background job | **BOTH** must point at the same compound | Yes |

**The two stages use opposite rules, deliberately.** Your registry is curated by
you — if you entered a CAS number against a compound, you meant it, and one
match is enough to trust. PubChem is an outside database you are *guessing*
from, so you demand two independent identifiers agree.

The everyday version: you will merge two contacts if you recognise the person.
You would want the name *and* the number to match before merging two strangers'
contacts that a website suggested.

**Practical consequence: upload your own chemicals list first if you have one.**
Everything it covers links instantly, with no network and no strict rule to
satisfy, because you vouched for it.

## Running stage 2

This is a long job — roughly an hour for a few thousand compounds — because
PubChem asks callers not to exceed five requests a second. That is a politeness
limit, not slow code.

```bash
cd ~/work/Pandora_toolbox/nr-nips-crucible

# 1. Always back up before a bulk write
./container-py.sh backup

# 2. Preview. Writes nothing.
podman exec crucible-py python /app/backend/scripts/link_pubchem.py --limit 60
```

**You should see** progress every five compounds, then a breakdown by reason.

```bash
# 3. The real run, detached, keeping a log and a report
podman exec -d crucible-py sh -c \
  'python /app/backend/scripts/link_pubchem.py --apply \
     --report /app/backend/unlinked.csv > /app/backend/link.log 2>&1'
```

Check on it whenever you like — the app works normally throughout:

```bash
podman top crucible-py | grep link_pubchem      # a line = running, empty = finished
podman exec crucible-py tail -5 /app/backend/link.log
sqlite3 data/crucible.db "SELECT COUNT(*) FROM chemicals;"
```

> **Do not use `ps` inside the container.** The image is a minimal one and has no
> `ps`; piping the failure into `grep -c` prints `0`, which reads exactly like
> "not running". `podman top` runs on the host and is reliable. This has already
> wasted somebody's afternoon once.

## Reading the outcome

```bash
podman cp crucible-py:/app/backend/unlinked.csv ./unlinked.csv
python3 -c "
import csv, collections
rows = list(csv.DictReader(open('unlinked.csv')))
print(f'{len(rows)} unlinked compounds\n')
for reason, n in collections.Counter(
        ('name/CAS disagree' if (r['reason'] or '').startswith('name=CID') else r['reason'])
        for r in rows).most_common():
    print(f'{n:6}  {reason}')
"
```

**You should see** something like:

```
2942 unlinked compounds

  2278  no CAS to corroborate the name
   456  name not in PubChem
   147  name/CAS disagree
    42  neither found
    19  CAS not in PubChem
```

**What each line means:**

- **no CAS to corroborate the name** — the biggest group, and the real ceiling.
  The row named a compound but gave no identifier, so there is nothing to check
  the name against. Only the laboratory can fix this, by putting CAS numbers in
  the export.
- **name not in PubChem** — the CAS is fine; the *name* is written in a house
  style PubChem does not recognise, like `Phenol, 2,4-di-tertiobutyl` for
  2,4-di-tert-butylphenol. **These are recoverable** — see below.
- **name/CAS disagree** — the check earning its keep. The name and the number
  point at genuinely different substances. Each deserves a human look.

> **Do not use `cut -d,` on that file.** Compound names contain commas, and
> `cut` does not understand quoting — it will turn `Phenol, 2,4-di-tertiobutyl`
> into fragments and give you a meaningless summary. Use the Python above.

## Recovering the ones rejected on their name

The `name not in PubChem` group are real compounds with correct identifiers,
rejected only over spelling. `propose_chemicals.py` prepares them for your
judgement:

```bash
podman cp unlinked.csv crucible-py:/app/backend/unlinked.csv
podman exec crucible-py python /app/backend/scripts/propose_chemicals.py \
  /app/backend/unlinked.csv -o /app/backend/proposed.xlsx
podman cp crucible-py:/app/backend/proposed.xlsx ./proposed.xlsx
```

Open it. Each row has **your** name for the compound and **PubChem's** name side
by side.

> ⚠️ **Review it before uploading. This is the most important instruction in
> this document.**
>
> The script registers nothing. Uploading the file is *you vouching* for those
> compounds — which is exactly the corroboration the automated rule could not
> obtain. Compare the two name columns and delete any row where they do not
> describe the same substance.
>
> This is not a formality. On one occasion the file was uploaded unreviewed and
> **19 compounds went in carrying another substance's chemistry** — a food
> antioxidant holding nicotine's formula. Finding and undoing that took most of
> a day.

Then upload via **Chemicals → Upload Chemicals (ELN)**, and re-link:

```bash
podman exec crucible-py python /app/backend/scripts/link_pubchem.py --apply
```

**You should see** `Re-linked N rows to compounds registered by an earlier run.`
— your new compounds being matched by CAS, with no PubChem involved.

---

# Part 5 — Check what you registered

## Why this step exists

When a compound is registered from a proposal file, it carries **two halves from
two different places**:

- the **name**, from your laboratory's file
- the **chemistry** — formula, weight, structure — fetched from PubChem using
  the CAS number

If the wrong compound gets fetched, the entry keeps the right name and acquires
somebody else's chemistry. And every screening row pointing at it inherits that.

It is like saving a contact correctly named "Mum" and attaching a stranger's
photo and address. The name looks right in your contacts list. Everything you do
*with* it is wrong.

## Run the audit

```bash
podman exec crucible-py python /app/backend/scripts/audit_chemicals.py
```

**You should see:**

```
664 entries checked (0 skipped for having no formula).
0 look doubtful.
```

**What it means:** every registered compound whose chemistry can be compared
against its own name agrees with it.

**If instead** entries are listed, each says why:

```
  ??  CHEM-000413
        yours   : Glycerol, 2-monohexadecanoate
        pubchem : 2-Methoxyaniline
        cas=23470-00-0  formula=C7H9NO  mw=123.15
        -> name says 'hexadec…' (16 carbons) but the formula has 7
```

## What it checks, in plain terms

**A chain the formula cannot hold.** Chemical names are partly arithmetic: a
name containing *hexadecanoate* is claiming a sixteen-carbon chain, the way
*hexagon* claims six sides. If the formula only has seven carbons, the two
statements contradict each other and no naming convention explains it.

**An element the name never mentions.** An ester, a diol or a benzoate is built
from carbon, hydrogen and oxygen. If the formula also contains nitrogen or
chlorine, the name has to earn it — with a word like *amide*, *chloro* or
*phosph*. `Carbamic acid, butyl ester` contains nitrogen and says *carbam*, so it
passes. `Dipropylene glycol dibenzoate` contains nitrogen and explains none of
it, so it does not.

Two exemptions stop it crying wolf:

- **Both names agreeing.** If your name and PubChem's are the same word, there is
  nothing to investigate whatever the elements. `Caffeine` cannot possibly hint
  at its own nitrogen, and PubChem agreeing with it is better evidence than any
  word list.
- **Two compounds in one cell.** `Acrylic acid, diester with tetraethyleneglycol
  + Eicosane (POSH)` describes two peaks that came out together. A chain named by
  the second is not evidence against the first.

> ⚠️ **A clean result is not a guarantee.** These checks catch contradictions
> that can be *measured*. A wrong CAS pointing at a compound of similar
> composition leaves nothing to measure. Three such entries were found only by
> reading the pairs by eye. To read them all:
>
> ```bash
> podman exec crucible-py python /app/backend/scripts/audit_chemicals.py --all | less
> ```

## Why this happened at all

Worth understanding, because it explains why the rules are as strict as they
are.

Looking a compound up by its CAS number used a PubChem endpoint that returns
**every compound whose record mentions that number** — ordered by internal
identifier, not by relevance. The code took the first one.

```
CAS 95-47-6  →  [4831, 7237, 12245919]
                 └ Pipemidic Acid    └ o-Xylene, the correct answer
```

An antibiotic came back before o-xylene, so o-xylene got the antibiotic's
chemistry. Caffeine happened to be first in its own list and came out right — by
luck.

Fixed by checking which candidate lists that CAS among its *own* synonyms. The
compound that owns a number says so; the ones merely mentioning it do not.

**And note what was unaffected:** the identification job in
[Part 4](#part-4--give-the-compounds-an-identity) requires a compound's name and
its CAS to point at the same substance. When the CAS lookup went astray, the
name lookup did not, they disagreed, and the entry was rejected. **The strict
rule kept 367 compounds clean while this bug was live.** Only the proposal path,
which uses the CAS alone, let it through.

That is the argument for the strict rule, and it is why you should be wary of
anyone offering to relax it.

---

# Part 6 — Correct what is wrong

## The rule that matters

**Never delete a compound through the web interface or the API.**

Neither unlinks the measurements first. You end up with rows pointing at
something that no longer exists — a page reference to a page that has been torn
out. This has already happened once, to 1,897 rows.

Use the script. It unlinks first, deletes second, and reports before it writes.

## Removing wrong entries

```bash
cd ~/work/Pandora_toolbox/nr-nips-crucible
./container-py.sh backup
```

Write the identifiers into a file, one per line:

```bash
cat > bad-ids.txt <<'EOF'
CHEM-000413
CHEM-049196
EOF
```

Then report, read, and only then apply:

```bash
podman cp bad-ids.txt crucible-py:/app/backend/bad-ids.txt
podman exec crucible-py python /app/backend/scripts/remove_chemicals.py \
  --from-file /app/backend/bad-ids.txt
```

**You should see** each entry named, and how many measurements point at them:

```
22 chemical entries to remove
  CHEM-000413  Glycerol, 2-monohexadecanoate   cas=23470-00-0
  …
232 rows point at them and will be unlinked:
  screening    232
Report only — nothing written. Re-run with --apply.
```

**Check the names are the ones you meant**, then:

```bash
podman exec crucible-py python /app/backend/scripts/remove_chemicals.py \
  --from-file /app/backend/bad-ids.txt --apply
```

**What happens to the measurements:** nothing is deleted. They lose their link
and go back to showing the compound name your file recorded — *unidentified*
rather than *wrongly identified*, which is the honest state.

## Merging two entries for one substance

Two different CAS numbers can point at one compound — a substance and a variant
of it. Production held `1-Docosanol` twice.

```bash
podman exec crucible-py python /app/backend/scripts/merge_duplicate_chemicals.py
podman exec crucible-py python /app/backend/scripts/merge_duplicate_chemicals.py --apply
```

It keeps the older entry, copies over any detail only the duplicate had,
repoints every measurement, and deletes only then.

**A shared name is not enough to merge on.** Two entries with different CAS
numbers *and* different PubChem compounds are different substances that happen
to share a label — isomers, or a name truncated in the source. Merging those
would destroy a real distinction, so the tool does not.

## Confirming

```bash
podman exec crucible-py python /app/backend/scripts/audit_chemicals.py
./verify-deploy.sh https://localhost:49160
```

**You should see** `0 look doubtful`, and among the sixteen passes,
`no dangling chemical links` — confirming nothing was left pointing at a deleted
entry.

## Getting them back

A removed compound is usually a real substance whose *lookup* failed, not bad
source data. Re-propose it (Part 4), **review the file**, upload, re-link.

---

# Part 7 — Ask your own questions

Some questions have no button. *"Which simulant gives the highest migration?"*
*"Which compounds appear in more than twenty samples?"* The **Query** tab
answers those.

## Why queries look odd here

Because of the design decision in Part 0: each record is stored whole, as one
block, rather than spread across fixed columns. To read a field you reach inside
it:

```sql
json_extract(doc, '$.compound_name')
```

Read that as: *from the record, take the field called `compound_name`*.

Two consequences worth knowing before you write anything:

**Everything comes out as text.** Sorting without converting gives nonsense —
`9.9` sorts above `10000`, exactly as *apple* sorts above *banana*. Convert
first:

```sql
CAST(json_extract(doc, '$.mg_per_kg_food') AS REAL)
```

**A few fields are real columns** — `id`, `chemical_id`, `created_at`. Use those
directly and they are much faster.

## Safety

It is **read-only, enforced by the database itself** — the connection is opened
in read-only mode, so `DROP`, `DELETE` and `UPDATE` are refused before this
application gets a say. You cannot break your data from this page.

> ⚠️ The API has no login. Anyone who can reach the port can run queries and
> read everything. That is the same exposure every other part already has, but a
> query console makes it obvious. It is the first item on the roadmap.

## Getting started

The Query page has seven worked examples down the right-hand side — click one to
load it, then edit. **Show tables & fields** lists what is actually stored.

Recipes and a troubleshooting section: [Query Cookbook](QUERY-COOKBOOK.md).

---

# Part 8 — Change something and publish it

## Three folders, three jobs

The everyday version:

| Folder | Like | What it is for |
|---|---|---|
| Your Mac | Your desk | Where you write and test. Cannot reach the private repository — deliberately |
| The VM mirror | The post room | Copies work from the public repository into the private one |
| The VM production folder | The noticeboard | What people actually use. Only ever receives; never sends |

Work flows **one way**: desk → post room → noticeboard. Never backwards.

## The sequence

**1. On your Mac — write and check:**

```bash
cd ~/Documents/Work/pandora_toolbox/nr-nips-crucible
cd backend && .venv/bin/pytest && cd ..     # must pass
./check-public-safe.sh                       # must print SAFE TO PUSH
```

**`check-public-safe.sh` is not optional.** The public repository is visible
outside the company; this checks no internal hostname, username, path,
certificate or real laboratory data is about to be published.

**2. Commit and push:**

```bash
git add -A
git status                                   # read this before committing
git commit -m "<what changed>" -m "<why, one point per line>"
git push origin develop develop:beta develop:master
git switch master && git pull --ff-only origin master && git switch develop
```

**3. On the VM, in the mirror — copy public into private:**

```bash
cd ~/work/Pandora_toolbox/crucible-mirror
git switch develop
git fetch origin && git status
git fetch public
git checkout public/develop -- .
git status
git diff --cached --summary | grep -i mode
git commit -m "<same subject>" -m "Mirrors public commit: <one line>."
git push origin develop develop:beta develop:master
git switch master && git pull --ff-only origin master && git switch develop
```

> **The trailing `-- .` is essential.** `git checkout public/develop` without it
> moves you onto the public commit instead of copying files in.
>
> **`mode change 100755 => 100644`** means a script lost permission to run.
> Fix with `chmod +x <file>` and `git add <file>` before committing.

**4. On the VM, in production — deploy:**

```bash
cd ~/work/Pandora_toolbox/nr-nips-crucible
git switch master
git pull --ff-only origin master
git log --stat -1          # what actually changed?
```

**Does it need a rebuild?** This trips people up:

| Changed | Rebuild? | Why |
|---|---|---|
| `backend/app/`, `backend/scripts/` | **Yes** | Baked into the container |
| `client/` | **Yes** | Compiled into the container |
| `docs/*.md`, `README.md` | No | Read from disk |
| `*.sh` in the repository root | No | Read from disk |

The catch: helper scripts in the **root** update with a pull, but scripts in
**`backend/scripts/`** live inside the container and need a rebuild.

```bash
./container-py.sh backup
./container-py.sh rebuild
./verify-deploy.sh https://localhost:49160
```

Watch the rebuild output. If your change was to `backend/scripts/` and the line
`COPY backend/scripts` says `Using cache`, **your change is not in the image** —
the pull did not bring it.

**5. Confirm the two repositories agree:**

```bash
cd ~/work/Pandora_toolbox/crucible-mirror
git fetch origin && git fetch public
git diff --stat public/develop develop
```

**You should see** only the six real-data workbooks. Anything else means step 3
did not take.

The reference version of all this: [GitOps Workflow](GITOPS-WORKFLOW.md).

---

# Part 9 — What to run, and when

## After any code change

| Step | Command |
|---|---|
| Tests | `cd backend && .venv/bin/pytest` |
| Safety gate | `./check-public-safe.sh` |
| Publish | Part 8, all five stages |
| Verify | `./verify-deploy.sh https://localhost:49160` |

## After loading a new laboratory file

1. Read the import report on screen — do the counts look plausible?
2. `./verify-deploy.sh` — 16 passes
3. Run identification (Part 4) — an hour, in the background
4. Read the unlinked report — how much could not be identified, and why
5. Propose the recoverable ones, **review**, upload, re-link
6. **Audit** (Part 5)
7. Remove what is wrong (Part 6)
8. Audit again — expect `0 look doubtful`

## Periodically

| How often | What | Why |
|---|---|---|
| Before any bulk write | `./container-py.sh backup` | Cheap; the alternative is not |
| After each deploy | `./verify-deploy.sh` | Sixteen checks, twenty seconds |
| After any registry change | `audit_chemicals.py` | Catches wrong chemistry early |
| Weekly, automatic | Certificate expiry cron | Warns before HTTPS lapses |
| Every five minutes, automatic | Health monitor | Restarts the app if it stops answering |

## Two habits worth forming

**Always run the report before the `--apply`.** Every destructive tool here
reports first and writes only when asked. Read the report. It takes seconds and
it is the difference between removing 22 entries and removing 220.

**Back up before anything bulk.** `./container-py.sh backup` takes a consistent
copy while the app keeps running. Never copy the database file directly with
`cp` while the app is running — it can catch it mid-sentence and the result
opens fine and is quietly corrupt.

---

# Part 10 — When something goes wrong

## First, three questions

1. **Is it running?** `./container-py.sh status`
2. **Does it answer?** `curl --noproxy '*' -sSk https://localhost:49160/api/stats`
3. **What does it say?** `./container-py.sh logs` — the real error is usually in
   the last twenty lines. `Ctrl-C` stops watching; it does not stop the app.

## The failure this project keeps having

Nearly every difficult bug here has had the same shape: **an operation reporting
one thing while doing another.** A dry run that had already written. A monitor
that reported healthy while checking nothing. A check that printed `0` because
the command failed to start.

So when something looks wrong, ask not only *"did it fail?"* but **"could this
have failed in a way that looks like success?"**

Concretely: `command | grep something` prints nothing both when there is no
match *and* when the command never ran. Run the command by itself first.

## Specific things you may hit

**A change you deployed is not visible in the browser.** Hard-refresh once
(`Cmd/Ctrl + Shift + R`). The page shell is now sent uncached, but a copy from
before that fix may still be held.

**A long job seems stuck.** Check it is alive with
`podman top crucible-py | grep <script>`, then watch the numbers rather than the
process:

```bash
sqlite3 data/crucible.db "SELECT COUNT(*) FROM chemicals;"
```

Run it twice a minute apart. Moving means working.

**PubChem stops answering.** It throttles under sustained load. The client backs
off and reports how often it happened. Compounds it refused are recorded as *not
found* but were never actually asked — **re-run**, which skips everything
already registered.

**A verification command "passes" suspiciously.** After a full uninstall the
shell may be standing in a deleted folder, and every container command fails
with `error getting current working directory` — printing nothing, which reads
exactly like success. `cd ~` first.

## Where to look next

| Question | Guide |
|---|---|
| What does this word mean? | [Glossary](GLOSSARY.md) |
| How do I install or remove it? | [macOS](INSTALL-MACOS.md) · [RHEL8](INSTALL-RHEL8.md) · [Uninstall](UNINSTALL-RHEL8.md) |
| How does identification decide? | [Chemical Identification](CHEMICAL-IDENTIFICATION.md) |
| How do I write a query? | [Query Cookbook](QUERY-COOKBOOK.md) |
| How do I call the API? | [API Cookbook](API-COOKBOOK.md) |
| How is it built, and why? | [Architecture](architecture.md) |
| How do I publish a change? | [GitOps Workflow](GITOPS-WORKFLOW.md) |
| What broke before, and what was learned? | [README → Bumps hit along the way](../README.md#bumps-hit-along-the-way-kept-on-purpose) |

---

**Last Updated:** August 31, 2026
