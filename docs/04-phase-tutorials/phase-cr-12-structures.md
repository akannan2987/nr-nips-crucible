[← README](../../README.md) · [Handbook](../HANDBOOK.md) · [Glossary](../00-glossary.md) · [← Phase SH-3b](phase-sh-3b-local-accounts.md)

# Phase CR-12 — Structures: derive, draw, edit. Step A: one derived structure per entry, checked

**Version shipped:** 2.24.0 (step A) · **Date:** 2026-09-23 · **Status:** step A complete; step B (draw) and step C (edit) follow in their own releases and are added to this page as they ship
**Track:** CR, the Chemical Registry ([roadmap](../05-roadmap.md#cr--chemical-registry)); the owner's request of 2026-09-14, specified in [`09-structures.md`](../09-structures.md) with decisions S1–S5, built on the go of 2026-09-23 ("build on what you have planned").
**Prerequisites:** [Phase CR-9](phase-cr-9-real-registry-sources.md) (the three real sources, which put the MOL blocks, SMILES and InChIs into the registry), [Phase CR-10](phase-cr-10-attention-page.md) (the attention page, which gains a fifth kind here), [Phase CR-2](phase-cr-2-views-sort-filter.md) (the column picker, which gains a group); the specification read once; a setup guide completed for your platform; the test virtual environment from its V7 check for the Python route.
**Learning goal:** you understand what a chemical structure is and the three text forms it travels in, why a structure is the one fact about a compound that can be *checked* rather than merely copied, how one structure is derived from whatever the source gave and stored beside the laboratory's values without touching them, what the four checks compare and why a salt or an exact mass is not a disagreement, and how to derive, list and review the findings from the browser, the API, the terminal, the container, Python and the database.
**Deliverable:** for every registry entry that carries a MOL block, a SMILES or an InChI, one **derived structure** under a new key `structure`: the canonical SMILES, the InChI and InChIKey, the computed formula, average weight and exact mass, the counts of atoms, bonds, rings, charge and fragments, which source it came from, and the verdict of four checks against the source's own formula, weight and InChI. A disagreement is a **structure finding**, the fifth kind on the attention page, with the two values side by side and the same *mark reviewed* as the others. `POST /api/chemicals/structures/derive`, `derive_structures.py` and a **Derive structures** button call one module, report first and write on *apply*. On the real export: 6,553 entries with a source, 6,544 derived, 446 with a finding. Eight tests; the suite at 201.

![Three text forms of a structure go into RDKit in a fixed order; one derived structure with computed facts is stored beside the entry; four checks compare the source's own formula, weight and InChI with its structure; a disagreement becomes a finding on the attention page](../img/fig_structure_derive.svg)

---

## Contents

1. [Why this phase exists](#why-this-phase-exists)
2. [The words you need](#the-words-you-need)
3. [What we built](#what-we-built)
4. [Step 1 — Read what the entry carries, in a fixed order](#step-1--read-what-the-entry-carries-in-a-fixed-order)
5. [Step 2 — Compute the facts, and store them beside the entry](#step-2--compute-the-facts-and-store-them-beside-the-entry)
6. [Step 3 — Check the source against its own structure](#step-3--check-the-source-against-its-own-structure)
7. [Step 4 — One module, three doors](#step-4--one-module-three-doors)
8. [Step 5 — The fifth kind on the attention page, and the detail view](#step-5--the-fifth-kind-on-the-attention-page-and-the-detail-view)
9. [Step 6 — Tests, build, rehearsal](#step-6--tests-build-rehearsal)
10. [Step 7 — Derive on the server, beta first](#step-7--derive-on-the-server-beta-first)
11. [Checkpoint](#checkpoint)
12. [How to test it, by every route](#how-to-test-it-by-every-route)
13. [What this step deliberately did not do](#what-this-step-deliberately-did-not-do)
14. [Publish](#publish)

---

## Why this phase exists

The registry records what the sources *say* about a compound: a name, a
CAS number, a formula, a weight. None of those can be checked against the
others; a wrong CAS number looks exactly like a right one. A **structure**
is different. It is the drawing chemists think in, which atoms joined how,
and from the drawing alone a program can *compute* the formula, the weight
and a fingerprint (the InChIKey) that is the same for the compound whatever
it is called. So a structure lets the registry check a source against
itself: if the formula the source wrote beside its own structure is not the
formula of that structure, one of the two is wrong, and no naming
convention explains it away.

Half the registry already carried a structure nobody could see or check:
6,553 of the 12,539 entries hold a MOL block, a SMILES or an InChI from the
three real sources of [phase CR-9](phase-cr-9-real-registry-sources.md).
Until this step the detail view drew the 77 MOL blocks with a small viewer
and showed the rest as a line of text. Nothing was computed from a SMILES
or an InChI, nothing was compared, and a person could not draw one. The
owner asked on 2026-09-14 for the three things a chemist expects from a
registry: derive one checked structure per entry, draw it, edit it. This
step is the first, and the one the other two depend on.

*Everyday version:* the parcel's label says what is inside; the X-ray
shows what is inside. Where the two disagree, a person looks. The machine
does not rewrite the label.

---

## The words you need

| Term | Plain words | Everyday version |
|---|---|---|
| **Structure** | Which atoms a molecule has and how they are joined. The one fact about a compound that other facts (formula, weight, InChIKey) can be computed from | The X-ray of the parcel |
| **MOL block** | A structure as a text table of atoms with coordinates and bonds, the format drawing programs save (V2000 or V3000); the registry SDF carries one per molecule | The architect's drawing, with every wall's position |
| **SMILES** | A structure as one line of text, `Cn1cnc2c1c(=O)n(C)c(=O)n2C` for caffeine; what a chemist types. Many different lines can describe the same molecule | A route written as turns: several ways to write the same route |
| **Canonical SMILES** | The one SMILES RDKit writes for a molecule, always the same for the same structure, whichever way it was typed in | The route written in the one agreed way, so two people's notes match |
| **InChI / InChIKey** | Another standard text form (InChI), and a fixed-length fingerprint made from it (InChIKey, 27 characters): the same for the compound whatever it is called. The first 14 characters name the skeleton, the rest the stereo and charge layers | A passport number: the person, not the spelling of the name |
| **Derived structure** | The one structure this step computes for an entry from what the source gave, stored under `structure` beside the entry's own fields, never over them | The X-ray, filed with the parcel, the label untouched |
| **Fragment** | A part of a structure not bonded to the rest. A salt is written as several fragments, `[Na+].CC(=O)[O-]`; the laboratory often records only the parent's formula | The kit's two loose parts in one box |
| **Average weight, exact mass** | Two weights for one molecule: the average over the natural isotopes (what a balance sees, `194.194` for caffeine), and the exact mass of the most common isotopes (what a mass spectrometer sees, `194.0804`). The laboratory's weight is the second, 6,179 times in 6,382 | The parcel's weight on the post-office scale, and its weight on the laboratory balance |
| **Structure finding** | A disagreement between what the source recorded (formula, weight, InChI) and what its own structure is; or a source no structure could be read from. The fifth kind on the attention page | The inspector's note: "label says 3 kg, scale says 2" |
| **RDKit** | The open-source chemistry library the backend already uses to read SDF files; here it reads all three text forms, builds the molecule and computes the facts | The X-ray machine |
| **Report first, apply** | The derive runs as a report that writes nothing, then again with *apply* to store the result; the same rule as every job that touches data in this project | The estimate before the work |

---

## What we built

| Piece | What it is | Where |
|---|---|---|
| The module | Reads the entry's sources in a fixed order, computes the facts, runs the four checks, writes the `structure` on *apply*; called by the endpoint, the script and the button | `backend/app/structures.py` |
| The audit, extended | A fifth kind, *structure findings*, read from what the module stored; the count on the banner and the sidebar; the review key `structure` | `backend/app/audit.py` |
| The endpoint | `POST /api/chemicals/structures/derive` `{chemical_ids?, apply?}`: the report, or the write; 404 for an unknown identifier, nothing written | `backend/app/routers/chemicals.py`, `backend/app/schemas.py` |
| The columns | Four derived columns in the picker, group *structure*: derived formula, derived weight, InChIKey (derived), structure source; sortable and filterable like every column | `backend/app/routers/chemicals.py` |
| The script | `derive_structures.py [--apply] [--ids …] [--json]`: the same report, printed; `./container-py.sh script derive_structures.py` on the server | `backend/scripts/derive_structures.py` |
| The audit script | Prints the fifth kind and where the registry stands (with a source, derived, still to derive) | `backend/scripts/audit_chemicals.py` |
| The page | The fifth tile and section on *Needs attention*: the derive panel (where the registry stands, **Derive structures…**, the report, **Apply**), one card per finding with the source's values beside the structure's and the verdict of each check, *It is fine — mark reviewed* | `client/src/pages/RegistryAttention.jsx` |
| The detail view | A *Derived structure* strip under the picture: source, formula, weights, InChIKey and canonical SMILES beside the laboratory's values with each check's verdict; the findings; or *not derived yet* / *none* | `client/src/pages/ChemicalsView.jsx` |
| The banner | One more sentence on the registry page, a link to the section | `client/src/pages/ChemicalsView.jsx`, `client/src/services/api.js` |
| Tests | Eight: the facts, the source order and the fall-through, the bracket repair and the unreadable source, the fragment and the two masses, the InChI layers, the endpoint and the audit end to end, the columns, the script | `backend/tests/test_structures.py` |
| Figure | The three sources, RDKit, the stored structure, the four checks | `docs/img/fig_structure_derive.svg` |

---

## Step 1 — Read what the entry carries, in a fixed order

**What:** for each entry, try the MOL block, then the SMILES, then the
InChI, and take the first RDKit can read (decision S5). Record which one
it was, and which ones were tried and failed.

**How:** `read_structure(doc)` in `backend/app/structures.py`:

```python
for name in ("mol_block", "smiles", "inchi"):      # S5: the drawing, then what the chemist typed, then the standard form
    text = sources.get(name)
    if not text:
        continue
    mol = Chem.MolFromMolBlock(text) if name == "mol_block" else Chem.MolFromSmiles(text) if name == "smiles" else Chem.MolFromInchi(text)
    if mol is not None:
        return mol, name, repair, unreadable         # the first that reads, wins
    unreadable.append(name)                          # remembered on the entry: it was tried
```

**Why this order.** A MOL block is the most explicit form: a drawing with
every atom placed. The SMILES is what the chemist entered, `SMILES_ORIGINAL`
in the export. The InChI is a standard form usually generated by a program
from one of the other two. When an entry has several, the most explicit one
is the structure and the InChI becomes a *check* (Step 3), which is why the
InChI is last.

**One repair, recorded.** 147 SMILES in the export are wrapped in square
brackets the source added: `[CCO]` instead of `CCO`. RDKit reads that as one
malformed atom. When a SMILES fails and is bracketed like that, the inside is
tried; if it reads, the structure is kept and `repaired: "outer brackets
removed"` is stored on it. 135 of the 147 read that way; the rest are
counted as unreadable. The repair is a fact on the entry, not a finding: a
person can see it, and nothing was guessed.

**You should see** (the development machine, the test virtual environment):

```bash
cd backend && .venv/bin/python -c "
from rdkit import Chem
from app import structures as s
ethanol = Chem.MolToMolBlock(Chem.MolFromSmiles('CCO'))
print(s.read_structure({'mol_block': ethanol, 'smiles': 'CO'})[1:])       # ('mol_block', None, [])
print(s.read_structure({'mol_block': 'garbage', 'smiles': 'CCO'})[1:])   # ('smiles', None, ['mol_block'])
print(s.read_structure({'smiles': '[CCO]'})[1:])                          # ('smiles', 'outer brackets removed', [])
print(s.read_structure({'smiles': 'not a smiles', 'inchi': 'nope'})[1:])  # (None, None, ['smiles', 'inchi'])
"
```

**What it means:** the source that wins is named; the ones that failed are
named too; a repair is named; and an entry nothing can read says so rather
than pretending.

**If instead:** `ModuleNotFoundError: rdkit` — the virtual environment was
not built (setup guide, V7); the container has it regardless.

---

## Step 2 — Compute the facts, and store them beside the entry

**What:** from the molecule, compute everything a structure can tell, and
store it under one key, `structure`, on the entry. The entry's own
`molecular_formula`, `molecular_weight`, `smiles`, `inchi` are never
changed.

**How:** `describe(mol)` and `derive_one(doc)`:

| Under `structure` | What it is | Caffeine |
|---|---|---|
| `source` | which field it came from: `mol_block`, `smiles` or `inchi`; `null` when nothing could be read | `smiles` |
| `repaired` | present only when the SMILES was read after removing the source's brackets | — |
| `unreadable` | the sources tried before this one that RDKit could not read | — |
| `smiles` | the canonical SMILES RDKit writes | `Cn1cnc2c1c(=O)n(C)c(=O)n2C` |
| `inchi`, `inchikey` | computed, not copied | `RYYVLZVUVIJVGH-UHFFFAOYSA-N` |
| `formula` | computed from the atoms | `C8H10N4O2` |
| `weight`, `exact_mass` | the average weight and the exact (monoisotopic) mass | `194.194`, `194.0804` |
| `atoms`, `bonds`, `rings`, `charge`, `fragments` | counts; `atoms` are the heavy atoms | `14, 15, 2, 0, 1` |
| `largest_fragment` | for a salt or a mixture: the biggest fragment's formula, weights and atoms | — |
| `checks` | the verdict of each check: `agrees`, `differs`, `none` (nothing to compare), `same source`, `unreadable`, `not computable` (a polymer or placeholder atoms: RDKit makes no InChI) | `{"formula": "agrees", "weight": "agrees", "inchi": "none"}` |
| `findings` | the disagreements, each `{"kind", "reason"}` | `[]` |
| `derived_at` | when | `2026-09-23T…Z` |

**Why beside, never over.** The laboratory's formula is *their* record;
the derived formula is what the structure implies. If the module
overwrote the first with the second, the disagreement would vanish and
with it the only evidence that something is wrong. The one design rule of
the project holds too: `structure` is one more fact in the document, no
column, no migration, and `derive_registry` is its only writer. A derived
fact is not an edit of the record by a person, so the entry's `updated_at`
is left alone; a later run rewrites only the entries whose result changed.

**You should see:**

```bash
cd backend && .venv/bin/python -c "
from app import structures as s
caffeine = {'chemical_id': 'X', 'smiles': 'Cn1cnc2c1c(=O)n(C)c(=O)n2C', 'molecular_formula': 'C8H10N4O2', 'molecular_weight': 194.0804}
st = s.derive_one(caffeine)
print({k: st[k] for k in ('source', 'formula', 'weight', 'exact_mass', 'inchikey', 'atoms', 'bonds', 'rings', 'fragments', 'checks', 'findings')})
print(s.derive_one({'chemical_id': 'Y', 'name': 'no structure'}))     # None: nothing to derive from
"
```

`{'source': 'smiles', 'formula': 'C8H10N4O2', 'weight': 194.194, 'exact_mass': 194.0804, 'inchikey': 'RYYVLZVUVIJVGH-UHFFFAOYSA-N', 'atoms': 14, 'bonds': 15, 'rings': 2, 'fragments': 1, 'checks': {'formula': 'agrees', 'weight': 'agrees', 'inchi': 'none'}, 'findings': []}` and `None`.

**If instead:** an entry with no MOL block, SMILES or InChI gets no
`structure` at all, on purpose: there is nothing to derive from, and
nothing to say. Drawing one is step C.

---

## Step 3 — Check the source against its own structure

**What:** four comparisons, each a verdict and, when it disagrees, a
finding with a plain reason.

| Check | Compares | Passes when | On the real export |
|---|---|---|---|
| **formula** | the laboratory's `molecular_formula` with the structure's formula | it equals the whole structure's formula **or any fragment's**, spaces and a trailing charge ignored | 6,403 checked, **398** disagree |
| **weight** | the laboratory's `molecular_weight` with the structure's weights | it is within 1 g/mol or 0.5 % of the **average weight or the exact mass**, of the whole or of a fragment | 6,382 checked, **79** disagree |
| **InChI** | the InChI the source carries (when the structure came from a MOL block or a SMILES) with the derived one, as InChIKeys | the keys are equal; a different first block is a different skeleton, a different tail a stereo or charge difference; an InChI RDKit cannot read is reported | 6,282 checked, **27** disagree (24 skeleton, 3 stereo), 20 unreadable |
| **unreadable** | — | there is a source but nothing reads | **9** entries |

**Why the fragments.** The first version compared the laboratory's formula
with the whole structure's and flagged 938 entries. Reading them showed
the pattern: a salt is written as several fragments (`[Ag+].[Cl-]` for
silver chloride) and the laboratory records the parent (`Ag`). That is not a disagreement,
it is a convention. Comparing with each fragment too leaves 398, and
those are real: for the inorganic salts the export's formula column lists
only the metals (`Al2` for aluminium chloride hydroxide, `B2` for boron
oxide) while its own weight is the full salt's exact mass to the fourth
decimal, so the formula column, not the structure, is the odd one out.
That is exactly what the page should show a person.

**Why two weights.** 6,179 of the 6,382 laboratory weights are exact
masses (`285.9622`, four decimals, the mass spectrometer's number), 314
are averages (`287.17`, the balance's number). Both are right; the check
accepts either. A weight that is neither, on an entry whose formula
agrees, is the rarest and most interesting finding: 25 entries.

**Why the InChI is a check and not a source.** When the entry has a MOL
block or a SMILES, the InChI was generated from something; if it names a
different skeleton than the structure the entry carries, the two files the
source produced disagree with each other, and that is worth a look. The
InChIKey's first 14 characters name the skeleton, the rest the stereo and
charge layers, so the reason says which.

**You should see:**

```bash
cd backend && .venv/bin/python -c "
from rdkit import Chem
from app import structures as s
salt = {'smiles': 'CC(=O)[O-].[Na+]', 'molecular_formula': 'C2H3O2', 'molecular_weight': 82.03}
print(s.derive_one(salt)['checks'], s.derive_one(salt)['findings'])
wrong = {'smiles': 'CCO', 'molecular_formula': 'C5H10', 'molecular_weight': 250.0}
for f in s.derive_one(wrong)['findings']: print(f)
other = {'smiles': 'CCO', 'inchi': Chem.MolToInchi(Chem.MolFromSmiles('CO'))}
print(s.derive_one(other)['findings'][0]['reason'])
"
```

```
{'formula': 'agrees', 'weight': 'agrees', 'inchi': 'none'} []
{'kind': 'formula', 'reason': "the laboratory's formula C5H10 is not the formula of the structure (C2H6O)"}
{'kind': 'weight', 'reason': "the laboratory's weight 250.0 is neither the average weight (46.069) nor the exact mass (46.0419) of the structure or of a fragment"}
the InChI the source carries describes a different skeleton (its key starts OKKJLVBELUTLKV, the structure's LFQSCWFLJHTTHZ)
```

**What it means:** a salt recorded by its parent passes; a wrong formula
and a wrong weight are two findings on one entry, each saying what it
compared; an InChI for another molecule is named by the skeleton it
describes.

**If instead:** a finding you disagree with is not an error in the check,
it is the check doing its job on a source that is inconsistent with
itself; *It is fine — mark reviewed* records your decision. A finding
that turns out to be a bug in the check is a test case: add it to
`backend/tests/test_structures.py`.

---

## Step 4 — One module, three doors

**What:** the browser, the API and the terminal call one function,
`derive_registry(db, chemical_ids=None, apply=False)`, so they cannot
disagree; and every door reports first and writes only on *apply*.

| Door | How | Report | Apply |
|---|---|---|---|
| **API** | `POST /api/chemicals/structures/derive` with `{}` or `{"chemical_ids": [...]}` | the counts and the findings, nothing written | `{"apply": true}` |
| **Terminal** | `./container-py.sh script derive_structures.py` (the server) · `.venv/bin/python scripts/derive_structures.py` (the development machine) | the same, printed | `--apply` |
| **Browser** | *Needs attention → Doubtful structures → Derive structures…* | the report in an amber box | **Apply** |

**The report**, from the real export on the development machine:

```
6,553 of 12,539 entries carry a structure source.
Derived 6,544: 77 from a MOL block, 6,322 from a SMILES (135 read after removing the outer brackets the source added), 145 from an InChI; 9 could not be read.
Findings on 446 entries: formula 398, weight 79, InChI 47, unreadable 9.
```

then one block per entry with a finding (the terminal shows the first 30
and counts the rest; the page and the JSON list them all), and either
`Report only — nothing written (10.7 s)` or `Applied: 6,553 entries
written, 0 unchanged, in 25.6 s`. A second *apply* writes nothing:
`0 entries written, 6,553 unchanged`.

**Why an unknown identifier writes nothing.** `{"chemical_ids": ["CHEM-000232", "CHEM-999999"], "apply": true}`
answers `404 {"error": "Chemical not found: CHEM-999999"}` before touching
the first entry, the same rule as the review mark and the merge: a bad
list is refused whole.

**How long.** About ten seconds per ten thousand entries for the
computation; the write through the container's mounted folder on the
development machine took 26 s for 6,553 entries. The endpoint is
synchronous, so the button says *Deriving…* for that long. The counts
the registry page shows are cached for 30 s, so the banner catches up
within half a minute of a script's write, at once after the button's.

---

## Step 5 — The fifth kind on the attention page, and the detail view

**What:** the findings where every other flag lives, with the buttons to
act; and the derived facts on every entry's detail view, beside the
laboratory's own.

**The attention page** (*Chemical Registry → Needs attention*): a fifth
tile, *doubtful structures*, with *N derived of M with a source* under it;
a fifth section with the **derive panel** (where the registry stands, the
button, the report, **Apply**) and one card per finding:

| Fact | The source says | Its own structure is | Check |
|---|---|---|---|
| Structure from | `smiles` | the canonical SMILES | `8 fragments` |
| Formula | `Al2` | `H10Al2ClO5` | ✗ differs |
| Weight | `178.9848` | `179.492 average · 178.9848 exact` | ✓ agrees |
| InChIKey | the InChI the source carries | `KMZVLRWDRFTSPT-UHFFFAOYSA-M` | ✓ agrees |

then the reasons, **Open the entry** and **It is fine — mark reviewed**.
The banner on the registry page gains a sentence, *N entries whose derived
structure disagrees with their own formula, weight or InChI*, and the
sidebar's amber number counts them.

**The detail view** (any entry, *View*): under the picture and the quick
facts, a *Derived structure* strip: *from the smiles · 2026-09-23*, then
*Formula C8H10N4O2 · lab C8H10N4O2 ✓ agrees*, *Weight 194.194 avg ·
194.0804 exact · lab 194.19 ✓ agrees*, *InChIKey …*, *Canonical SMILES …*;
amber, with the reasons listed, when there is a finding; *not derived
yet* with a link to the page for an entry with a source and no structure;
*none* for an entry with nothing to derive from.

**The column picker** (*Complete* view): a group *structure* with four
columns, *derived formula*, *derived weight*, *InChIKey (derived)*,
*structure source*, sortable and filterable like the others.

**Why the page draws and never computes.** The browser shows what the
server derived; it holds no chemistry library. One engine, one answer,
the same from the page, the API and a script.

---

## Step 6 — Tests, build, rehearsal

**What:** eight tests, the client built, the image rebuilt on the
development machine and the whole thing run against the real export.

```bash
cd ~/Documents/Work/pandora_toolbox/nr-nips-crucible
cd backend && .venv/bin/ruff check . && .venv/bin/pytest -p no:warnings 2>&1 | grep -E '[0-9]+ (passed|failed)' && cd ..    # All checks passed! · 201 passed
cd client && npm run build 2>&1 | tail -1 && cd ..                                                                          # ✓ built
./container-py.sh rebuild                                                                                                   # the image with the module and the page
./container-py.sh script derive_structures.py | head -3                                                                    # the report above
./container-py.sh script derive_structures.py --apply | tail -2                                                             # Applied: 6,553 entries written …
./container-py.sh script audit_chemicals.py | head -1                                                                       # 795 things need attention (… 125 doubtful formulas, 446 doubtful structures)
```

**You should see** the numbers of Step 4, and on the attention page the
fifth tile at 446 with *6,544 derived of 6,553 with a source*.

**What the rehearsal taught** (and the tests now hold): comparing with
the fragments (938 to 398); the two masses; the bracket repair; that a
second run must write nothing; that the audit's 30-second cache means the
sidebar's number follows a script's write within half a minute.

---

## Step 7 — Derive on the server, beta first

**What:** after block 3 of the six has pulled and rebuilt this version on
beta, derive there; after block 6, on production. The rebuild's backup
covers the write; the report comes first regardless.

```bash
# VM - beta folder, after block 3 (rebuild); then the production folder after block 6
cd ~/work/Pandora_toolbox/nr-nips-crucible-beta
./container-py.sh script derive_structures.py | head -3            # the report: 6,553 / 6,544 / 446, as on the development machine
./container-py.sh backup
./container-py.sh script derive_structures.py --apply | tail -2    # Applied: 6,553 entries written, 0 unchanged, in N s.
./container-py.sh script audit_chemicals.py | head -1              # 795 things need attention (…, 446 doubtful structures)
curl --noproxy '*' -sSk -H "Authorization: Bearer $T" https://localhost:49161/api/chemicals/notices/summary; echo   # "structure":446
```

**You should see:** the same three report lines as on the development
machine (the data is the same export), *Applied: 6,553 entries written*,
and the attention page showing the fifth tile. The sidebar's number goes
from 349 to 795.

**What it means:** 446 entries the registry cannot vouch for are listed
for a person, none was changed, and every other entry with a structure
now carries a checked, canonical form that steps B and C draw and edit.

**If instead:** `✗ crucible-py-beta is not running` — `./container-py.sh start`.
The report shows fewer than 6,553 with a source — the export was not
re-imported on that instance; the numbers are per instance. The page
shows *0 derived of 6,553* after the script — reload; the counts are
cached for 30 s.

---

## Checkpoint

On the development machine, against the real export copy, with the
container running:

```bash
./container-py.sh script derive_structures.py --json | python3 -c "import json, sys; r = json.load(sys.stdin); print(r['with_source'], r['derived'], r['unreadable'], r['findings'])"
curl --noproxy '*' -sS -H "Authorization: Bearer $T" http://localhost:49160/api/chemicals/audit | python3 -c "import json, sys; a = json.load(sys.stdin); print(a['counts']['structure'], a['counts']['attention'], a['structures_summary'])"
```

**You should see** `6553 6544 9 {'entries': 446, 'formula': 398, 'weight': 79, 'inchi': 47, 'unreadable': 9}` and
`446 795 {'with_source': 6553, 'derived': 6544, 'to_derive': 0, 'findings': 446}`.
That is "done" as the specification defined step A: every entry with a
source has a `structure`, the attention page shows the findings with their
counts, the script and the endpoint report first and write on *apply*.

---

## How to test it, by every route

Synthetic first, then the real export. The synthetic set is the JSON
template plus three entries made for this step: load
`docs/excel-templates/chemicals/chemicals_template.json` (five compounds
with a SMILES), then save the block below as `structures_rehearsal.json`
and load it the same way (*Chemical Registry → Upload → JSON*, or
`./container-py.sh import chemicals structures_rehearsal.json`): a salt
recorded by its parent's formula, an entry whose formula and weight are
wrong for its structure, and an entry nothing can read. Eight entries with
a source, seven derived, two with a finding. The last column is the
development copy of the real export, which is what the server shows.
`$T` is your personal token; `$J` stands for `-H 'Content-Type: application/json'`.

```json
[
  {"name": "Sodium acetate", "cas_number": "127-09-3", "smiles": "CC(=O)[O-].[Na+]", "molecular_formula": "C2H3O2", "molecular_weight": 82.03},
  {"name": "Mislabelled ethanol", "smiles": "CCO", "molecular_formula": "C5H10", "molecular_weight": 250.0},
  {"name": "Unreadable structure", "smiles": "not a smiles", "inchi": "nope"}
]
```

| Route | How | You should see (synthetic) | Real export |
|---|---|---|---|
| **Browser, before deriving** | *Chemical Registry → Needs attention* | five tiles; *doubtful structures 0* with *0 derived of 8 with a source*; the derive panel: *8 entries carry a structure source · 0 derived · 8 still to derive · 0 with a finding* | *0 derived of 6,553 with a source* |
| **Browser, the report** | **Derive structures…** | an amber box: *Report — nothing written yet (0.1 s)*, *8 of 8 entries carry a source. Derived 7: 0 from a MOL block, 7 from a SMILES, 0 from an InChI; 1 could not be read.*, *Findings on 2 entries: formula 1, weight 1, InChI 0, unreadable 1.*; **Apply: store the result on 8 entries** and *Cancel* | *6,553 of 12,539 … Derived 6,544: 77 from a MOL block, 6,322 from a SMILES (135 read after removing the outer brackets the source added), 145 from an InChI; 9 could not be read. Findings on 446 entries: formula 398, weight 79, InChI 47, unreadable 9.*; the button says *6,553 entries*; about 10 s |
| **Browser, apply** | **Apply** | a green toast *8 structures written, 0 unchanged; 2 with a finding*; the tile *2* with *7 derived of 8*; two cards | *6,553 structures written, 0 unchanged; 446 with a finding*; the tile *446* with *6,544 derived of 6,553*; 446 cards, lowest identifier first; the first are the inorganic salts whose formula column lists only the metals |
| **Browser, a card** | the *Mislabelled ethanol* card | *Structure from* `smiles` · the canonical SMILES `CCO`; *Formula* `C5H10` / `C2H6O` / ✗ differs; *Weight* `250` / `46.069 average · 46.0419 exact` / ✗ differs; *InChIKey* `LFQSCWFLJHTTHZ-UHFFFAOYSA-N` / *no InChI on the entry*; two reasons; **Open the entry**, **It is fine — mark reviewed** | the *Aluminium chloride hydroxide* card as in Step 5: formula ✗, weight ✓, InChI ✓, one reason |
| **Browser, the unreadable one** | the *Unreadable structure* card | *Structure from* `unreadable: smiles, inchi`; the checks empty; one reason, *no structure could be read from the SMILES or the InChI the source carries* | 9 such cards |
| **Browser, mark reviewed** | **It is fine — mark reviewed** on a card | the card greys; the tile goes 2 → 1; the banner sentence updates; *Show reviewed* brings it back; **Reopen** lifts the mark | the same, per card |
| **Browser, the banner** | the Chemical Registry page | *Needs a person's eye: … **2 entries** whose derived structure disagrees with their own formula, weight or InChI.*, the count a link to the section | *446 entries …* |
| **Browser, the sidebar** | *Chemical Registry ▸ Needs attention* | the amber number counts the structure findings with the rest | **795** (was 349) |
| **Browser, the detail view** | *View* on Caffeine, then on *Mislabelled ethanol*, then on an entry with no SMILES | a grey strip *Derived structure from the smiles · 2026-09-23 · Formula C8H10N4O2 · lab C8H10N4O2 ✓ agrees · Weight 194.194 avg · 194.0804 exact · lab 194.19 ✓ agrees · InChIKey RYYVLZVUVIJVGH-UHFFFAOYSA-N · Canonical SMILES …*; an amber strip with the two reasons; *none — this entry carries no MOL block, SMILES or InChI* | the same; *Aluminium chloride hydroxide*: `8 fragments`, the largest fragment's formula in brackets |
| **Browser, before deriving, the detail view** | *View* on any entry with a SMILES, before **Apply** | *not derived yet — this entry carries a structure source; Derive structures on the attention page computes and checks it* | the same |
| **Browser, the columns** | *Complete* view → *Columns* | a group *structure*: *derived formula*, *derived weight*, *InChIKey (derived)*, *structure source*; sort by *derived weight*; filter *structure source* = `smiles` | the same; 6,544 filled |
| **API, the report** | `curl --noproxy '*' -sSk -H "Authorization: Bearer $T" $J -d '{}' -X POST https://localhost:49160/api/chemicals/structures/derive \| python3 -m json.tool \| head -24` | `"entries": 8, "with_source": 8, "derived": 7, "from": {"mol_block": 0, "smiles": 7, "inchi": 0}, "repaired": 0, "unreadable": 1, "findings": {"entries": 2, "formula": 1, "weight": 1, "inchi": 0, "unreadable": 1}, "applied": false, "written": 0` and two `items` | `12539, 6553, 6544, {77, 6322, 145}, 135, 9, {446, 398, 79, 47, 9}` |
| **API, apply, twice** | the same with `-d '{"apply": true}'`, twice | `"applied": true, "written": 8, "unchanged": 0`; then `"written": 0, "unchanged": 8` | `6553, 0`; then `0, 6553` |
| **API, a subset, an unknown id** | `-d '{"chemical_ids": ["CHEM-000007"]}'` · `-d '{"chemical_ids": ["CHEM-000007", "CHEM-999999"], "apply": true}'` | `"entries": 1` and one item with `"kinds": ["formula", "weight"]` · `404 {"error": "Chemical not found: CHEM-999999"}`, nothing written | the same with `CHEM-000232` |
| **API, the entry** | `curl … https://localhost:49160/api/chemicals/CHEM-000001 \| python3 -c "import json, sys; print(json.load(sys.stdin)['structure'])"` | the dictionary of Step 2, `checks` all `agrees` or `none`, `findings: []`; `molecular_formula` unchanged beside it | `CHEM-000232`: `source smiles`, `fragments 8`, `largest_fragment`, `checks {"formula": "differs", "weight": "agrees", "inchi": "agrees"}`, one finding |
| **API, the audit** | `curl … https://localhost:49160/api/chemicals/audit \| python3 -c "import json, sys; a = json.load(sys.stdin); print(a['counts'], a['structures_summary'], a['structures'][0]['kinds'])"` | `'structure': 2` in the counts, `attention` two more than before; `{'with_source': 8, 'derived': 7, 'to_derive': 0, 'findings': 2}`; `['formula', 'weight']` | `'structure': 446, 'attention': 795`; `{6553, 6544, 0, 446}` |
| **API, the notices** | `curl … https://localhost:49160/api/chemicals/notices/summary; echo` | `"structure": 2` beside the four older counts | `"structure": 446, "attention": 795` |
| **API, review** | `curl … $J -d '{"chemical_ids": ["CHEM-000007"], "key": "structure"}' -X POST https://localhost:49160/api/chemicals/audit/review` | `{"updated": 1, "key": "structure", "reviewed": true}`; the notices say `"structure": 1`; `"reviewed": false` lifts it | the same |
| **API, the columns, sort, filter** | `curl … https://localhost:49160/api/chemicals/columns \| python3 -c "import json, sys; print([c for c in json.load(sys.stdin)['columns'] if c['group'] == 'structure'])"` · `…/api/chemicals?sort=structure.weight&order=desc&limit=3` · `…/api/chemicals?filters=%7B%22structure.source%22%3A%22smiles%22%7D&limit=1` | four columns, `filled: 7` (the unreadable one has no formula); the heaviest first; `total: 7` | `filled: 6544`; `total: 6322` |
| **API, the explorer** | `https://<vm-hostname>:49160/docs`, section *chemicals* | `POST /api/chemicals/structures/derive` with its schema `{chemical_ids, apply}` | the same |
| **Terminal, the report** | `./container-py.sh script derive_structures.py` | the three lines with 8 / 7 / 2, the two entries, *Report only — nothing written* | the three lines of Step 4, the first 30 entries, *… and 416 more* |
| **Terminal, apply, twice** | `./container-py.sh script derive_structures.py --apply \| tail -2` | *Applied: 8 entries written, 0 unchanged, in 0.1 s.*; then *0 entries written, 8 unchanged* | *6,553 entries written* (about 10 to 30 s); then *0 written, 6,553 unchanged* |
| **Terminal, a subset, as JSON** | `./container-py.sh script derive_structures.py --ids CHEM-000007 --json \| head -12` · `--ids CHEM-404` | the endpoint's answer for one entry · *Unknown identifier: CHEM-404. Nothing written.*, exit 1 | the same |
| **Terminal, the audit** | `./container-py.sh script audit_chemicals.py \| grep -E 'need attention\|^Structures:'` | *… 2 doubtful structures); 0 reviewed.* · *Structures: 8 entries carry a structure source, 7 derived, 0 still to derive …, 2 with a finding.*, then the *Doubtful structures* section with the two | *795 things need attention (221 …, 125 doubtful formulas, 446 doubtful structures)* · *6553 … 6544 … 446* |
| **Terminal, the deploy check** | `CRUCIBLE_TOKEN="$T" ./verify-deploy.sh https://localhost:49160 \| tail -2` | `19 passed, 0 failed`: nothing here changes what the checks look at | the same |
| **Podman / Docker, the script by its long name** | `podman exec crucible-py python /app/backend/scripts/derive_structures.py --json \| python3 -c "import json, sys; print(json.load(sys.stdin)['findings'])"` | `{'entries': 2, 'formula': 1, 'weight': 1, 'inchi': 0, 'unreadable': 1}` | `{'entries': 446, …}` |
| **Podman / Docker, the chemistry library inside** | `podman exec crucible-py python -c "import rdkit; print(rdkit.__version__)"` | `2025.09.3`: the image's RDKit, the same the tests run on | the same |
| **Podman / Docker, the table inside** | `podman exec crucible-py python -c "import sqlite3, json; db = sqlite3.connect('/app/data/crucible.db'); print(db.execute(\"SELECT json_extract(doc,'$.structure.source') AS src, count(*) FROM chemicals GROUP BY src\").fetchall())"` | `[(None, 1), ('smiles', 7)]` (the entry with nothing to derive from and the unreadable one both read `None`; the JSON template has 5 with a SMILES + 2) | `[(None, 5995), ('inchi', 145), ('mol_block', 77), ('smiles', 6322)]` |
| **Podman / Docker, the write is visible at once** | after a script `--apply`, `curl … /api/chemicals/notices/summary` within 30 s, then again | the count may lag up to 30 s (the cache), then `"structure": 2` | the same |
| **Python directly, the module** | `cd backend && .venv/bin/python -c "from app import structures as s; print(s.derive_one({'smiles': 'CC(=O)[O-].[Na+]', 'molecular_formula': 'C2H3O2'})['checks'])"` | `{'formula': 'agrees', 'weight': 'none', 'inchi': 'none'}` | — |
| **Python directly, the script on the development copy** | `cd backend && .venv/bin/python scripts/derive_structures.py \| head -3` | — | the three report lines in 10.7 s, straight against `data/crucible.db` |
| **Python, a script that reads the result** | the script below, `python3 structures_report.py` on the development machine, or `podman exec -i crucible-py python - < structures_report.py` with the container's path | `8 entries with a structure: by source {'smiles': 7, None: 1}; findings by kind {'formula': 1, 'weight': 1, 'unreadable': 1}; repaired 0` | `6553 …: {'smiles': 6322, 'inchi': 145, 'mol_block': 77, None: 9}; {'formula': 398, 'weight': 79, 'inchi': 47, 'unreadable': 9}; repaired 135` |
| **Database, the Query page** | `SELECT chemical_id, json_extract(doc,'$.molecular_formula') lab, json_extract(doc,'$.structure.formula') derived, json_extract(doc,'$.structure.checks.formula') verdict FROM chemicals WHERE json_extract(doc,'$.structure.checks.formula') = 'differs'` | one row, `C5H10 · C2H6O · differs` | 398 rows |
| **Database, the marks** | `SELECT chemical_id, json_extract(doc,'$.reviewed.structure') reviewed FROM chemicals WHERE json_extract(doc,'$.reviewed.structure') IS NOT NULL` | the entry you marked, with the timestamp | the same |
| **Database, from the host, read-only** | development machine: `sqlite3 -readonly data/crucible.db "SELECT json_extract(doc,'$.structure.source') src, count(*) FROM chemicals GROUP BY src;"` | the counts above | the counts above |
| **Automated tests** | `cd backend && .venv/bin/pytest -p no:warnings 2>&1 \| grep -E '[0-9]+ (passed\|failed)'` | `201 passed` (the eight of this step among them) | — |

The script of the Python row:

```python
# structures_report.py: what the registry holds after a derive, from the database, no RDKit needed
import collections, json, sqlite3
db = sqlite3.connect("file:data/crucible.db?mode=ro", uri=True)          # in the container: /app/data/crucible.db
by_source, by_kind, repaired, total = collections.Counter(), collections.Counter(), 0, 0
for (raw,) in db.execute("SELECT doc FROM chemicals"):
    s = json.loads(raw).get("structure")
    if s is None:
        continue
    total += 1
    by_source[s.get("source")] += 1
    repaired += bool(s.get("repaired"))
    for kind in {f["kind"] for f in s.get("findings") or []}:
        by_kind[kind] += 1
print(f"{total} entries with a structure: by source {dict(by_source)}; findings by kind {dict(by_kind)}; repaired {repaired}")
```

---

## What this step deliberately did not do

- **Draw the structure.** Step B: `GET /api/chemicals/{id}/structure.svg`
  from the server, in the detail view, the chooser dialogs and a thumbnail
  column. The existing viewer still draws the 77 MOL blocks.
- **Let a person draw or correct one.** Step C: the structure editor
  (Ketcher, decision S1), a save checked by RDKit, the previous structure
  kept under `structure_history`.
- **Fetch a structure from PubChem for the 5,986 entries with none.**
  Decision S3: enrichment goes through the review table of CR-4, one
  accepted value at a time, under the two-identifier rule. Lesson 24.
- **Derive on import.** An upload records what the file says; deriving is
  a separate, reported step a person runs, so that a file with a wrong
  structure does not silently gain a wrong canonical form. Step C
  re-derives one entry on save, where a person is looking.
- **Rewrite the laboratory's formula or weight.** Never. The finding is
  the evidence; a correction is a person's edit.
- **Lift a review mark when the finding changes.** A mark stays until a
  person lifts it, as for every other kind; a re-derive that produces a
  different finding on a reviewed entry is visible under *Show reviewed*.
- **Speed.** Ten seconds per ten thousand entries, synchronous, with the
  button saying so. A background job with progress is a later, shared
  piece of work (SH-7 territory), not a chemistry problem.
- **Name-to-structure** ("type *caffeine*, get the drawing"): a separate
  tool (OPSIN) and a separate decision, as the specification says.

---

## Publish

The six blocks of [`03-git-workflow.md`](../03-git-workflow.md#the-six-blocks-at-a-glance).
This release changes code under `backend/` and `client/`, so blocks 3 and
6 rebuild; each is followed by Step 7 on that instance (report, backup,
apply).

```bash
# DEVELOPMENT MACHINE - block 1
cd ~/Documents/Work/pandora_toolbox/nr-nips-crucible
git add -A && ./check-public-safe.sh && python3 check-links.py
git commit -F ~/.crucible/commit-v2.24.0.txt
git push origin develop develop:beta
git tag -a v2.24.0 -m "v2.24.0: Structures derived and checked"
git push origin v2.24.0
```

**Last Updated:** September 23, 2026
