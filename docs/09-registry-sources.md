[← README](../README.md) · [Handbook](HANDBOOK.md) · [Glossary](00-glossary.md)

# Registry sources — the laboratory's real files, described as data

**Prerequisites:** none. If you have not met the idea of a *template
specification* before, [`09-chemical-identification.md`](09-chemical-identification.md)
and [phase 04](04-phase-tutorials/phase-04-template-ingestion.md) introduced
it for screening files; this page applies it to the registry.
**Learning goal:** after this you will know the three real sources the
Chemical Registry is filled from, exactly which of their columns become the
registry's own fields and what happens to every other column, how several
rows about one compound become one entry, why two entries may legitimately
share a CAS number, and what "the identifier is coming from screening"
means for an entry.
**Status:** ✅ built and shipped as v2.14.0 on 2026-09-09, phase
[CR-9](04-phase-tutorials/phase-cr-9-real-registry-sources.md). This page is
the specification it was built from, kept current with the code in
`backend/app/utils/registry_templates.py`.

![The Dotmatics export, the registry SDF and the limited list, each described as a template spec, feeding one registry](img/fig_registry_sources.svg)

---

## Contents

- [The idea, in plain words](#the-idea-in-plain-words)
- [The three sources at a glance](#the-three-sources-at-a-glance)
- [Source 1 — the Dotmatics export](#source-1--the-dotmatics-export)
- [Source 2 — the registry structure file (SDF)](#source-2--the-registry-structure-file-sdf)
- [Source 3 — the limited list](#source-3--the-limited-list)
- [What every source shares](#what-every-source-shares)
- [The decisions this was built on](#the-decisions-this-was-built-on)
- [Loading a source, by every route](#loading-a-source-by-every-route)
- [What the notices mean, and what to do](#what-the-notices-mean-and-what-to-do)
- [When something goes wrong](#when-something-goes-wrong)

---

## The idea, in plain words

A **template specification** is a description of a file format written as
*data*: which column names mark the file as this kind of file (the
**fingerprint**), which column says what compound a row is about, which
columns become the registry's own fields, and the rule that everything else
is kept. The application reads the description and does the rest. Adding a
fourth source should mean writing a fourth description, not a fourth parser
— if it needs new code, the design has failed.

*Everyday version:* three suppliers deliver in three kinds of crate. The
stockroom does not hire a specialist per supplier; it has one form per crate
type saying where each thing goes, and nothing on the delivery note is
thrown away.

Two rules from the [registry-first rule](09-chemical-identification.md#the-next-rule-registry-first--specification)
hold here as everywhere: **a compound may be registered without a CAS
number**, and **the system never invents identity** — every entry comes from
a file a person chose to load.

---

## The three sources at a glance

| Source | What it is | Recognised by | One entry per | Matched to an existing entry by | Distinct fields |
|---|---|---|---|---|---|
| **Dotmatics export** | The master export of the laboratory's other registry: one spreadsheet, 115 columns | `REG_ID`, `BATCH_ID`, `FORMATTED_BATCH_ID`, `CHEMICAL_NAME`, `CAS_NO`, `DTXSID` all present | `REG_ID` — several rows are *batches* of one compound | `dotmatics_reg_id`, then `dtx_id` | `batches`, `batch_conflicts` |
| **Registry SDF** | Structures (V3000) with about fifty properties per molecule | `DTXSID`, `PREFERRED_NAME`, `CAS Number`, `Chemical name` all present | molecule | `dtx_id`, then `cas_number` | `mol_block`, `structural`, `merged_from` |
| **Limited list** | Six columns; the identifier column says *Coming from screening* | exactly `Supplier_ref`, `CAS_NO`, `CHEMICAL_NAME`, `MOL_WEIGHT_ORIG`, `MOL_FORMULA`, `NESTLE_ID` and nothing else | row | `cas_number`, then `name` | `nestle_id_pending` |

Any other spreadsheet, CSV, SDF or JSON file goes through the generic route
of [phase CR-3](04-phase-tutorials/phase-cr-3-every-way-in.md), unchanged.

---

## Source 1 — the Dotmatics export

**What it is.** The laboratory's other electronic notebook exports its whole
registry as one sheet, `browser export`. Each row is a **batch** — one
physical lot of a compound — so a compound with three batches is three
rows. The 2026-09 export has 12,561 rows describing 12,539 compounds; six
compounds have several batches, one has fifteen. One header,
`FORMATTED_BATCH_ID`, appears twice; the second copy wins, and both carry
the same value.

**Which compound a row is about:** `REG_ID`. Rows sharing it are one entry.

**How an entry is matched to one already in the registry:** by
`dotmatics_reg_id` first (the same export loaded again updates rather than
duplicates), then by `dtx_id` (so an entry the SDF created first is
completed, not duplicated).

**The registry's own fields, and the columns they come from:**

| Registry field | Column | Notes |
|---|---|---|
| `dotmatics_reg_id` | `REG_ID` | kept as text; the key for re-imports |
| `name` | `CHEMICAL_NAME` | |
| `cas_number` | `CAS_NO` | may be empty: 2,557 rows have none, and that is valid |
| `other_names` | `OTHER_NAMES` | split on `;` into a list |
| `synonyms` | `SYNONYMS` | split on `;` — **not** on commas, which sit inside names |
| `dtx_id` | `DTXSID` | the merge key with the SDF |
| `pubchem_cid` | `PUBCHEM_ID` | a number when it is one |
| `smiles` · `smiles_neutral` | `SMILES_ORIGINAL` (else `SMILES_NEUT`, else `MOLECULE_CANON_SMILES`) · `SMILES_NEUT` | |
| `inchi` | `INCHI` | |
| `molecular_formula` | `MOL_FORMULA`, else `MOL_FORMULA_ORIG` | |
| `molecular_weight` | `MOL_WEIGHT_ORIG`, else `MW_NEUT`, else `MOL_WEIGHT_NEUT` | |
| `xlogp` · `vapor_pressure` | `XLOGP_ORIG` (else `XLOGP_NEUT`) · `VAPOR_PRESSURE` | |
| `nestle_id` · `family` · `type_origin` | `NESTLE_ID` · `FAMILY` · `TYPE_ORIGIN` | |
| `source` · `source_template` | — | `dotmatics` · `dotmatics_export` |

**Batches.** These columns legitimately differ from batch to batch and are
recorded per batch under `batches`, one object per row: `BATCH_ID`,
`BATCH_NUMBER`, `FORMATTED_BATCH_ID`, `GC_RI_METHOD`, `GC_RI_METHOD_2`,
`RI_PACKAGING_L`, `RI_COMPILATION`, `RI_HS_NIST`, `HS_RI_METHOD_1`,
`HS_RI_METHOD_2`, `LC_RT_METHOD_1`, `LC_RT_METHOD_2`, `NESTLE_DEPT`.

**Batch conflicts.** Any *other* column that differs between a compound's
batch rows — in the real export, two compounds disagree on their own CAS
number across batches, three on their name — is recorded under
`batch_conflicts` as the list of column names; the first batch's values are
promoted, **and every batch keeps its own value of each disputed column
under `batches`**, so nothing a later batch said is lost. The entry is a
notice for the audit. The system does not choose between them; a person
does.

**Everything else** — the analytical methods, adduct masses, presence
flags, roles, regulatory codes, EFSA opinions, restrictions, policy,
comments — is kept under `metadata`, column name as key, empty cells
omitted. Nothing in the file is lost; the Complete view (CR-2) will show it.

**Shared CAS numbers.** Twelve CAS numbers in the export belong to more
than one registration. Decision 2: both entries are kept, and each carries
`cas_shared_with`, the list of the others' identifiers. The deploy check's
duplicate test skips flagged entries; the audit lists them.

---

## Source 2 — the registry structure file (SDF)

**What it is.** 77 molecules in **V3000** form — the newer, wider layout of
the structure format — each with about fifty properties: the identifiers
(`DTXSID`, `PREFERRED_NAME`, `CAS Number`, `Chemical name`), the structure
strings (`SMILES`, `MS_READY_SMILES`, `INCHI_STRING`, `MOLECULAR_FORMULA`,
`MONOISOTOPIC_MASS`), and the same presence and regulatory columns as the
export, under their long names (*Present in INK*, *EFSA Opinions*, …).

**What changed to read it.** The structure parser stripped leading blank
lines from each record, but in this file the blank first line *is* the
molecule's empty name line; removing it shifted every header by one and
RDKit read the atom counts from the comment line. Fixed at the record
split; every one of the 77 structures is now read, drawn and analysed.
The formula RDKit computes from the drawing rarely equals the file's
stated formula (hydrogens are implicit in these drawings), so the file's
value is the promoted `molecular_formula` and the computed one sits under
`structural` for the audit to compare.

**Matched by** `dtx_id`, then `cas_number`. When the export has been
loaded first, the SDF **merges** into that entry: the export's identifiers
stay, the structure and the SDF's properties are added, `merged_from`
records it, and the two sources' metadata sit side by side. Loaded the
other way round, the export completes the SDF's entry the same way.

**The registry's own fields:** `name` (`Chemical name`, else
`PREFERRED_NAME`), `preferred_name`, `cas_number`, `dtx_id`, `synonyms`
(`Synonyms / Composition`, split on `;`), `smiles`, `ms_ready_smiles`,
`inchi` (`INCHI_STRING`), `molecular_formula`, `molecular_weight` (`Exact
Molecular Weight`), `monoisotopic_mass`, `xlogp`, `found_by`, plus
`mol_block` and `structural` from the drawing. Every property is kept under
`metadata`.

**Its identifier is never the DTXSID.** Before this phase the generic SDF
route used a DTXSID as the entry's own identifier when it found one. A
registry-SDF entry gets the next sequential identifier like every other;
the DTXSID is a field.

---

## Source 3 — the limited list

**What it is.** A short spreadsheet, six columns, from a source that knows
the compound but not yet its identifier: `NESTLE_ID` says *Coming from
screening* on every row.

**Recognised exactly.** These six column names and no others. The generic
chemicals template carries the same six plus `DTX_ID`, and must keep going
through the generic route; the exact match is what tells them apart.

**What "Coming from screening" means.** The entry is registered now with
what the list gives — name, CAS if present, formula, weight, supplier
reference — and `nestle_id_pending: screening` marks that the identifier
is still to come. It comes from the **NR screening data**, which has not
been loaded yet; when it is, the matching of [SD-1](05-roadmap.md#sd--screening-data)
fills it in, and the notice goes away. Until then the Chemical Registry
page shows *N compounds still await an identifier from the screening
data*.

**Matched by** `cas_number`, then `name`, so a compound the export already
registered is completed rather than duplicated. A row without a CAS is
matched by name alone, and registered on its own if no name matches — a
person chose to load the list, so that is not inference.

---

## What every source shares

- **One door.** All three go through `backend/app/imports.py`, so the
  browser, the API and the terminal give the same result; the report says
  `template`, `rows`, `compounds`, `inserted`, `updated`,
  `batch_conflicts`, `pending_identifiers`, `cas_shared`.
- **Sequential identifiers.** Every new entry gets the next `CHEM-nnnnnn`;
  the sources' own identifiers are fields on it.
- **Nothing is lost.** Every column of every file is under `metadata`.
- **Loading twice updates.** The match order makes a re-import an update.
- **A person decides the doubtful cases**, and the system points at them:
  the notices on the registry page, and `./container-py.sh script
  audit_chemicals.py`, which lists every flagged entry.

---

## The decisions this was built on

Agreed with the owner on 2026-09-09.

| # | Decision | Answer |
|---|---|---|
| 1 | Identity for the Dotmatics rows | One entry per `REG_ID`; batches as a list on it |
| 2 | The twelve CAS numbers shared by more than one registration | Keep both entries; flag both (`cas_shared_with`); the audit lists them |
| 3 | The same compound in the export and the SDF | Merge on `DTXSID`: the export supplies the identifiers, the SDF the structure |
| 4 | Who loads the real files | The owner, through any route, once the phase ships; the phase ships the capability and its tests on synthetic files |
| 5 | Order | CR-9 before the SD-1 build, so the rule is tested against a registry of 12,539 real entries |

---

## Loading a source, by every route

The file is recognised by its columns, not its name, so any of the routes
of [`10-registry-tasks.md` → task 3](10-registry-tasks.md#3-load-many-compounds-from-a-file)
works. On the server, from the repository folder:

```bash
./container-py.sh import chemicals ~/Export_Chemicals_dotmatics.xlsx     # the export:   Successfully processed 12539 chemicals from the Dotmatics registry export (12539 new, 0 updated)
./container-py.sh import chemicals ~/Upload_Chemicals_SDF.sdf            # the SDF:      … from the Registry structure file (SDF, V3000) (N new, M updated) — M merged on DTXSID
./container-py.sh import chemicals ~/Upload_Chemicals_limited.xlsx       # the list:     … from the Limited chemicals list … ; pending identifiers: 25
./container-py.sh script audit_chemicals.py                              # the flags, listed
```

In the browser: **Chemical Registry → Upload Chemicals → Excel Upload** (or
**SDF Upload**) → the file → **Upload**; the result box shows the same
report. Through the API: `curl --noproxy '*' -sSk -X POST
https://localhost:49160/api/chemicals/upload/excel -F "file=@…"` (or
`…/upload/sdf`). The full test table with expected numbers is in the
[phase tutorial](04-phase-tutorials/phase-cr-9-real-registry-sources.md#how-to-test-it-by-every-route).

---

## What the notices mean, and what to do

| Notice on the registry page | Meaning | What a person does |
|---|---|---|
| *N compounds still await an identifier from the screening data* | entries from the limited list, `nestle_id_pending: screening` | nothing yet — SD-1 fills them in when the NR screening data is loaded; or edit the entry and set `nestle_id` by hand |
| *N entries share a CAS number with another entry* | `cas_shared_with` set by the export import | decide, per pair, whether they are one substance (merge with `merge_duplicate_chemicals.py`) or two (leave them; the flag stays as a record) |
| *N compounds whose batches disagree on a field* | `batch_conflicts` set by the export import | open the entry, look at `batches` and `metadata`, correct the field by hand if the first batch was wrong |

`GET /api/chemicals/notices/summary` answers the three counts for scripts.

---

## When something goes wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| The report has no `template` line | the file's columns did not match a fingerprint; it went through the generic route | check the header row against the fingerprint above; a renamed column breaks recognition |
| *Successfully processed 0 chemicals* on the export | the first sheet is not `browser export` or has no header row | the reader takes the first sheet; move or re-export |
| Every SDF molecule has a *structure warning* | an older image without the split fix | rebuild the image (the parser lives inside it) |
| Two entries for one compound after loading export then SDF | the DTXSID differs between the two files | they are two registrations to the sources too; merge by hand if you know better |

**Last Updated:** September 9, 2026
