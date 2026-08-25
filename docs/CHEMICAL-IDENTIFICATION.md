[← README](../README.md) · [All docs in order](../README.md#the-documentation-in-order) · [Glossary](GLOSSARY.md)

# Chemical identification — turning compound names into a registry

**Prerequisites:** a running instance with screening data loaded. No chemistry
or database knowledge assumed.
**Learning goal:** after this you will understand why screening data needs
compounds to be *identified*, exactly when a row links to a compound you
already have and when it asks an external database, and how to run and read the
identification job.
**Time:** ten minutes to read; the job itself runs in the background.

## Table of Contents

- [The problem, in your own data](#the-problem-in-your-own-data)
- [The everyday version](#the-everyday-version)
- [What identification gets you](#what-identification-gets-you)
- [How a compound gets identified](#how-a-compound-gets-identified)
- [Stage 1 — your own registry](#stage-1--your-own-registry)
- [Stage 2 — PubChem](#stage-2--pubchem)
- [Every scenario, side by side](#every-scenario-side-by-side)
- [Why it will not create duplicates](#why-it-will-not-create-duplicates)
- [Running it](#running-it)
- [Reading the report](#reading-the-report)
- [When something goes wrong](#when-something-goes-wrong)

---

## The problem, in your own data

A screening export records the compound it detected as **free text**, typed by
whoever ran the analysis. Here is one substance, exactly as one real export
spells it:

```
EICOSANE (POSH)      Eicosane (POSH)      EICOSANE
EICOSANE (posh)      Eicosane (posh)      EICOSANE POSH)     <- bracket typo
Eicosane             EICOSANE (POSh)      …and two more
```

**Ten spellings. Six hundred-odd rows. One substance.** Every one of them
carries the same number: `112-95-8`.

It is not an isolated case. In the same file, one compound appears under ten
spellings across 703 rows, and another under eleven across 434.

The file also contains **no chemistry at all** — no molecular formula, no
molecular weight, no structure. It has a name someone typed and, less than half
the time, a registry number.

**Identification** is the step that fixes both: it decides which compound each
row is *about*, and attaches the chemistry the file never had.

---

## The everyday version

Think about the messages on your phone.

Someone texts you from their work phone, their personal phone, and a messaging
app. Your phone shows three separate conversations — *"+41 79 …"*, *"Mum"*,
*"Mother"*. You know they are one person. Your phone does not.

**Saving them as a contact** changes two things:

1. Three conversations become one person, so *"show me everything from Mum"*
   finally works.
2. You gain information the messages never held — a photo, an address, a
   birthday. That came from your address book, not from the texts.

That is exactly this:

| On your phone | In Crucible |
|---|---|
| Ten conversations, one person | Ten spellings, one compound |
| Their phone number | The **CAS number** — a compound's internationally agreed identifier, the same in every laboratory on earth |
| Saving them as a contact | Registering the compound in the Chemicals module |
| Photo, address, birthday | Molecular formula, weight, structure |
| Your address book | **PubChem**, a free public chemical database run by the US National Library of Medicine |

---

## What identification gets you

**Counting becomes possible.** Ask *"how much eicosane migrated across all our
packaging?"* today and you get ten answers, one per spelling — including one for
the bracket typo. Identified, you get one number.

**Chemistry the file does not contain.** Formula, molecular weight, SMILES,
InChIKey. None of it is in the export; it cannot be recovered from the export;
it has to come from somewhere else.

**Later files line up automatically.** When a second laboratory's data arrives
calling the same substance `n-Eicosane`, it resolves to the same compound.
Without a registry you get a second, unconnected pile of rows and no way to
prove they describe one substance. This is the whole premise of the
application — see the README's opening.

**One page per compound.** Click a name in the screening table and see every
result for that compound, across every sample and every simulant.

> **It is optional.** The screening table, its filters, sorting, export and the
> query console all work without any of this. Unidentified rows simply show the
> compound name exactly as the file recorded it. Identification adds
> cross-referencing; it is not a prerequisite for using your data.

---

## How a compound gets identified

Two stages, and they are tried in order. **The second is only reached if the
first finds nothing.**

```
   a screening row
        │
        ▼
   ┌─────────────────────────────────────────┐
   │ STAGE 1  Do we already have this        │   at upload, instantly,
   │          compound registered?           │   no network involved
   │          CAS matches?  → link           │
   │          name matches? → link           │
   └───────────────┬─────────────────────────┘
                   │ nothing matched
                   ▼
   ┌─────────────────────────────────────────┐
   │ STAGE 2  Ask PubChem.                   │   a background job,
   │          Register ONLY if the name AND  │   roughly an hour
   │          the CAS agree on one compound  │
   └───────────────┬─────────────────────────┘
                   │ not confident enough
                   ▼
        row keeps its own name, unlinked
```

**The two stages use deliberately different rules**, and this is the part worth
reading twice:

| Stage | Rule |
|---|---|
| **Your registry** | **EITHER** the CAS **or** the name matches → link |
| **PubChem** | **BOTH** the CAS **and** the name must agree → link |

Why the difference? Your registry is curated by you. If you entered CAS
`100-52-7` against a compound, you meant it, and one match is enough to trust.
PubChem is an outside database you are *inferring* identity from, so you require
two independent identifiers to agree before accepting it.

---

## Stage 1 — your own registry

Runs the moment screening data is uploaded. No network, no waiting.

It tries the **CAS number first**, then the **name**:

```
Registry:  CHEM-000001   name='Our name for it'   cas=100-52-7
           CHEM-000002   name='Testene'           cas=(none)
```

| The screening row says | Result |
|---|---|
| name `Our name for it`, cas `100-52-7` — both match | → `CHEM-000001` |
| name `Totally different`, cas `100-52-7` — **only the CAS matches** | → `CHEM-000001` |
| name `Testene`, no CAS — **only the name matches** | → `CHEM-000002` |
| name `Testene`, cas `999-99-9` — name matches, CAS unrecognised | → `CHEM-000002` |
| name `Brand new thing`, cas `55-55-5` — neither matches | → stage 2 |

Two rules decide the awkward cases:

**If the name and the CAS point at different registered compounds, the CAS
wins.** A CAS number is an internationally agreed identifier; a name is a label
someone typed.

**A name match is refused when the row's CAS contradicts the one on file.** If
your registry records `Alpha` as `100-52-7` and a row claims `Alpha` is
`999-99-9`, those disagree about what the substance *is*. The row is left
unlinked for a person to look at, rather than being attached to a compound it
may not be. This is the same disagreement that causes a rejection in stage 2 —
treating it as a match here would apply opposite rules to identical evidence.

> **Practical consequence: upload your chemicals list first.** Every screening
> row whose compound you already know then links instantly at upload, with no
> network call and no strict rule to satisfy — because you vouched for it.
> PubChem is left to deal only with the genuinely unknown remainder, which is
> both faster and more accurate.

---

## Stage 2 — PubChem

Only compounds that matched nothing in your registry get here.

The rule: **register the compound only when the name and the CAS number both
resolve to the same PubChem compound.**

| The row says | PubChem says | Result |
|---|---|---|
| `Benzaldehyde` + `100-52-7` | both → compound 240 | ✅ registered and linked |
| `Phenol, 2,4-di-tertiobutyl` + `96-76-4` | CAS → 7311, name → *unknown* | ❌ unlinked |
| `Acetyl tributyl citrate` + `77-90-7` | CAS → 6505, name → 65058 | ❌ unlinked, they disagree |
| `Alkene`, no CAS | nothing to cross-check | ❌ unlinked |

**Why so strict?** A compound is often measured as a salt, a hydrate or an
ester, whose CAS number legitimately belongs to a *different* substance than the
name suggests. Accepting the CAS alone would attach migration results to the
wrong compound. In a food-contact safety dataset that is worth being fussy
about.

**What it costs.** Row 2 above is a real compound with a valid CAS, rejected
only because the laboratory writes `tertiobutyl` where PubChem expects
`tert-butyl`. On a sample of forty compounds carrying a valid CAS, thirty-five
failed for that reason and only one was a genuine conflict. Expect roughly
20–25% of distinct compounds to be confirmed — though they cover a much larger
share of *rows*, because common compounds appear hundreds of times each.

The report tells you which is which, so the ones failing on spelling alone are a
working list rather than a mystery.

---

## Every scenario, side by side

| # | Registry has | Row says | What happens |
|---|---|---|---|
| 1 | same CAS | name + CAS | links to the registered compound |
| 2 | same CAS, different name | name + CAS | links — the CAS is decisive |
| 3 | same name, no CAS | name only | links on the name |
| 4 | same name, no CAS | name + unknown CAS | links — nothing to contradict |
| 5 | same name **with** a CAS | name + **different** CAS | **refused** — they disagree |
| 6 | CAS → compound A, name → compound B | name + CAS | links to **A**; the CAS wins |
| 7 | nothing | name + CAS, PubChem agrees | **registers** a new compound and links |
| 8 | nothing | name + CAS, PubChem disagrees | unlinked |
| 9 | nothing | name + CAS, PubChem does not know the name | unlinked |
| 10 | nothing | name, no CAS | unlinked |

Rows 8–10 are not failures. The row keeps the name the file gave it and appears
in the table exactly as recorded — the observation is real even when the
identity is not established.

---

## Why it will not create duplicates

Registering one substance twice would defeat the point, so three things prevent
it:

**The CAS map.** Before registering anything, the job checks a map of every CAS
number already registered. Ten spellings sharing one CAS produce **one** entry:
the first spelling registers it, and the other nine link to the same one without
asking PubChem again. The map is rebuilt from the database at the start of every
run, so this holds across runs and restarts.

**Name matching.** A compound you registered by name with no CAS is matched by
name, so the job links the row rather than creating a rival entry.

**The database.** `chemical_id` is a unique column. An attempt to register the
same identifier twice fails outright rather than silently duplicating.

Demonstrated: three uploads of five spellings each — fifteen rows — leave the
Chemicals table holding exactly **one** compound, with twelve rows pointing at
it.

> **The identifier never moves.** A compound is created once. Screening rows
> hold a *pointer* to it, the way messages point at a contact. New screening
> data, corrections, a sixth spelling — none of it changes the compound record.
> Twelve rows can point at `CHEM-000001`; there is still one `CHEM-000001`.

`./verify-deploy.sh` checks for duplicates by CAS, by PubChem identifier and by
name on every deployment. The PubChem identifier is checked separately because
two CAS numbers can legitimately point at one compound, so a repeated identifier
is a duplicate even when the CAS numbers differ.

---

## Running it

Stage 1 needs nothing — it happens at upload.

Stage 2 is a background job. It lives inside the container, which matters
because the RHEL8 host's own Python is too old to run it.

```bash
cd ~/work/Pandora_toolbox/nr-nips-crucible

# 1. Always back up first — this writes to every row it links
./container-py.sh backup

# 2. Preview. Writes nothing; prints what it would do.
podman exec crucible-py python /app/backend/scripts/link_pubchem.py --limit 60
```

**You should see** progress every five compounds, then a breakdown by reason.

**What it means:** `confirmed` are compounds the name and CAS agreed on;
`rejected` are genuine disagreements; the rest could not be checked.

```bash
# 3. The real run, detached, keeping a log and a report
podman exec -d crucible-py sh -c \
  'python /app/backend/scripts/link_pubchem.py --apply --report /app/backend/unlinked.csv \
   > /app/backend/link.log 2>&1'
```

Roughly an hour for a few thousand compounds. **This is a politeness limit, not
slow code**: PubChem asks callers not to exceed five requests a second, and each
compound needs three or four.

Check on it at any point:

```bash
podman top crucible-py | grep link_pubchem          # a line = running, empty = finished
podman exec crucible-py tail -5 /app/backend/link.log
sqlite3 data/crucible.db "SELECT (SELECT COUNT(*) FROM chemicals) AS chemicals, (SELECT COUNT(*) FROM screening WHERE chemical_id IS NOT NULL) AS linked_rows;"
```

> Do **not** use `ps` inside the container — the image is a slim one and has no
> `ps`, and piping the failure into `grep -c` prints `0`, which reads exactly
> like "not running". `podman top` runs on the host and is reliable.

**It is safe to interrupt and safe to re-run.** Work is committed as it goes,
and a re-run skips every compound already registered.

---

## Reading the report

```bash
podman cp crucible-py:/app/backend/unlinked.csv ./unlinked.csv
cut -d, -f3 unlinked.csv | sort | uniq -c | sort -rn
```

**You should see** something like:

```
   2210 "no CAS to corroborate the name"
    850 "name not in PubChem"
     40 "name=CID 6505 but CAS=CID 65058"
      9 "CAS not in PubChem"
```

**What each line means:**

- **no CAS to corroborate the name** — the largest group. The row named a
  compound but gave no registry number, so there is nothing to check the name
  against. Adding CAS numbers at source is what fixes this.
- **name not in PubChem** — the CAS is fine; the *name* is written in a house
  style PubChem does not recognise. Normalising those names, or adding them as
  synonyms, would link these on the next run with no change to the rule.
- **name=CID … but CAS=CID …** — a genuine disagreement. This is the check
  earning its keep; each of these deserves a human look.
- **CAS not in PubChem** — usually a malformed or obsolete number.

---

## When something goes wrong

**If instead:** the summary says *"PubChem throttled this run N times"* —
PubChem was refusing requests because you were asking too fast. Compounds it
refused are reported as *not in PubChem* but were **never actually asked**.
Re-run; it skips what is already registered and retries the rest.

**If instead:** *"N lookups gave up after retries"* — transient network faults.
Same remedy: re-run.

**If instead:** the job disappears with no report — it ended early. The log
records why, and everything already committed is kept. Re-running resumes.

**If instead:** `CERTIFICATE_VERIFY_FAILED` — a corporate proxy re-signs HTTPS
with an internal root that Python does not trust by default. Point at the host's
bundle:

```bash
podman exec crucible-py python /app/backend/scripts/link_pubchem.py \
  --ca-bundle /etc/pki/tls/certs/ca-bundle.crt --limit 20
```

**If instead:** every lookup times out — the machine has no outbound internet, or
needs a proxy. Test it in isolation:

```bash
podman exec crucible-py python -c "
import sys; sys.path.insert(0,'/app/backend')
from app.utils.pubchem import PubChemClient
c = PubChemClient(); r = c.lookup('Benzaldehyde','100-52-7')
print('OK cid=%d' % r.cid if r else 'FAILED: %s' % c.last_error)"
```

**You should see** `OK cid=240`.

> **A note on what leaves the building.** Identification sends compound names
> and CAS numbers to PubChem, an external service. Those are not secret — a CAS
> number is a public identifier — but it is outbound traffic carrying your
> compound list, and worth knowing about rather than discovering.

---

**Last Updated:** August 25, 2026
