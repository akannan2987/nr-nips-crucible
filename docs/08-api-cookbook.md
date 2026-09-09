[← README](../README.md) · [Handbook](HANDBOOK.md) · [Glossary](00-glossary.md)

# The API cookbook — ready-to-run recipes

Every recipe on this page is a command you can paste straight into a terminal, followed by the answer the server actually gave back when we ran it. Nothing here is a sketch or a guess. If you have never touched an API before, read the next four paragraphs and you will have everything you need.

An **API** — a website built for programs instead of for people. When you open Crucible in a browser you get buttons, colours and tables. When a program asks the same server for the same information, it does not want any of that; it wants the raw facts. So the server offers a second set of addresses that return plain data. Those addresses all start with `/api`, and this cookbook is a tour of them.

**`curl`** — a small program that fetches a web address from the terminal instead of from a browser. It is already installed on macOS and on the RHEL8 VM. `curl http://example.com/thing` is the command-line equivalent of typing that address into Chrome and reading the page source.

**JSON** — a labelled text format that both people and programs can read. It is just names and values wrapped in braces: `{"total": 5}` means "the thing called total is 5". Square brackets `[ ... ]` mean a list of several items. Every answer in this cookbook is JSON.

By default the server sends JSON as one long unbroken line, which is hard on the eyes. Pipe it through Python's built-in formatter to spread it over indented lines:

```bash
curl --noproxy '*' -sS http://localhost:49160/api/stats | python3 -m json.tool
```

Two flags appear in every command here:

- `-s` — **silent**. Suppresses curl's download-progress meter, which would otherwise scribble over your JSON.
- `--noproxy '*'` — on the corporate network your machine is told to send all web traffic through a proxy server. That proxy has no idea what `localhost` means and will hijack the request. This flag says "talk directly, never via the proxy". Leave it out and you will get confusing timeouts or proxy error pages instead of data.

**Your base address** is `http://localhost:49160/api` on a macOS development machine, and `https://<vm-hostname>:49160/api` in production on the RHEL8 VM. Every recipe below uses the macOS form; swap the front half if you are on the VM.

---

## The one thing to know first

Crucible's four kinds of data are not independent. **Chemicals come first.** Screening results and toxicology studies each carry a `chemical_id` column pointing at a chemical that must already be in the database. If it is not there, the server refuses that row rather than creating a half-real record pointing at nothing.

So the import order is:

1. **Chemicals** — always first.
2. **Screening** and **toxicology** — in any order, once the chemicals they reference exist.
3. **Samples** — any time. Sample files have no chemical column at all, so nothing can be dangling. Samples get connected to chemicals afterwards, either by clicking in the app or with the linking recipe further down this page.

If you load screening before chemicals you will not break anything — you will simply be told the chemical was not found, and you can load the chemicals and run the same upload again. Uploads are safe to repeat (see the next section).

---

## Getting your bearings

**How much data is in there right now?**

```bash
curl --noproxy '*' -sS http://localhost:49160/api/stats | python3 -m json.tool
```

```json
{
    "chemicals": {"total": 5, "max": 15000},
    "samples": {"total": 2, "max": 1000},
    "screening": {"total": 3},
    "toxicology": {"total": 3},
    "counts": {"chemicals": 5, "samples": 2, "screening": 3, "toxicology": 3},
    "capacities": {
        "chemicals": {"current": 5, "max": 15000, "percentage": "0.0"},
        "samples": {"current": 2, "max": 1000, "percentage": "0.2"}
    }
}
```

What it means: five chemicals and two samples are loaded, out of ceilings of 15,000 and 1,000 respectively. This is the single most useful command in the book — run it before and after any upload and the difference tells you exactly what landed.

**What chemicals exist, in one glance? (short answer, cheap to run)**

```bash
curl --noproxy '*' -sS http://localhost:49160/api/chemicals/list/dropdown
```

```json
[{"chemical_id":"CHEM-0005","name":"Acetylsalicylic acid"},{"chemical_id":"CHEM-0001","name":"Caffeine"},...]
```

*(Abbreviated — the real reply lists every chemical.)* This endpoint exists to fill the dropdown menus in the app, so it returns only an ID and a name per chemical. That makes it fast and readable even with thousands of records, and it is the quickest way to find the exact `chemical_id` spelling you need for the recipes below.

**Is there a version of this page I can click instead of type?**

Yes. Open <http://localhost:49160/docs> in a browser. FastAPI, the framework behind Crucible, generates an interactive listing of every endpoint — **Swagger UI**, a live catalogue where each entry has a "Try it out" button that runs the request against your own server and shows you the reply. It is the authoritative list; this cookbook is the friendly subset.

---

## Loading data in

All four uploads work the same way: `-F "file=@<path>"` attaches a file to the request, exactly as if you had picked it in a browser's file-chooser. Run these from the project root so the template paths resolve.

**How do I load the chemicals?**

```bash
curl --noproxy '*' -sS -X POST http://localhost:49160/api/chemicals/upload/excel \
  -F "file=@docs/excel-templates/chemicals/chemicals_template.csv"
```

```json
{"message":"Successfully processed 5 chemicals (5 new, 0 updated)","inserted":5,"updated":0,"total":5}
```

**How do I load chemicals from a JSON file, or from a list my script built?**

```bash
curl --noproxy '*' -sS -X POST http://localhost:49160/api/chemicals/upload/json \
  -F "file=@docs/excel-templates/chemicals/chemicals_template.json"
curl --noproxy '*' -sS -X POST http://localhost:49160/api/chemicals/import \
  -H "Content-Type: application/json" \
  -d '{"chemicals": [{"chemical_id": "CHEM-0009", "name": "Test compound", "cas_number": null}]}'
```

```json
{"message":"Successfully processed 5 chemicals (5 new, 0 updated)","inserted":5,"updated":0,"total":5}
```

JSON is the format that round-trips: `./container-py.sh export chemicals
registry.json` writes every entry with these same field names, and the file
loads straight back. A record without a CAS number is a valid entry. Every
route — browser, these two endpoints, the terminal — reads the file with the
same code ([`10-registry-tasks.md`](10-registry-tasks.md#3-load-many-compounds-from-a-file)).

**What if I upload the same chemicals file twice by mistake? (nothing bad happens)**

Run the exact command again and the counts flip:

```json
{"message":"Successfully processed 5 chemicals (0 new, 5 updated)","inserted":0,"updated":5,"total":5}
```

What it means: this is an **upsert** — update-or-insert, the database deciding for you. A chemical ID already present is refreshed with the new values rather than duplicated. So re-running an upload after fixing a typo in the spreadsheet is the normal, intended way to correct data. You will not end up with two Caffeines.

**How do I load the samples?**

```bash
curl --noproxy '*' -sS -X POST http://localhost:49160/api/samples/upload/excel \
  -F "file=@docs/excel-templates/samples/Upload_Sample_Template.xlsx"
```

```json
{"message":"Successfully processed 2 samples (2 new, 0 updated)","inserted":2,"updated":0,"total":2,"summary":{...}}
```

*(Abbreviated — `summary` holds a per-column breakdown that is long and not needed here.)*

**How do I load the screening results? (chemicals must already be loaded)**

```bash
curl --noproxy '*' -sS -X POST http://localhost:49160/api/screening/upload/excel \
  -F "file=@docs/excel-templates/screening/screening_template.xlsx"
```

```json
{"message":"Successfully uploaded 3 screening records","inserted":3}
```

**How do I load the toxicology studies? (same rule — chemicals first)**

```bash
curl --noproxy '*' -sS -X POST http://localhost:49160/api/toxicology/upload/excel \
  -F "file=@docs/excel-templates/toxicology/toxicology_template.xlsx"
```

```json
{"message":"Successfully uploaded 3 toxicology records","inserted":3}
```

**Which file formats does each upload accept? (this trips everyone up once)**

Only the **chemicals** endpoint reads CSV as well as XLSX — and it also has a separate `/api/chemicals/upload/sdf` endpoint for SDF chemical-structure files. Samples, screening and toxicology are read with a library called openpyxl, which understands genuine Excel workbooks and nothing else. Hand one of them a `.csv` and you get a strange-looking complaint; see the refusals section at the end for why.

**(A note on timing.)** These four template files are tiny and return instantly. A real workbook of several thousand rows takes proportionally longer, and curl will simply sit there with no output until the server has finished the whole file and is ready to report. That silence is normal — resist the urge to press Ctrl-C, because interrupting mid-upload leaves you guessing how much got in. Run `/api/stats` afterwards to find out exactly what landed.

---

## Looking things up

**What do we know about one particular chemical?**

```bash
curl --noproxy '*' -sS http://localhost:49160/api/chemicals/CHEM-0001
```

```json
{"id":"7b7a84b8-79b3-4f44-ad20-16ad661ae4cc","chemical_id":"CHEM-0001","nestle_id":"INT-0001","name":"Caffeine","cas_number":"58-08-2","molecular_formula":"C8H10N4O2","molecular_weight":194.19,"smiles":null,"inchi":null,"inchi_key":null,"supplier":"Example Supplier Cat# 00001","description":null,"metadata":{...}}
```

*(Abbreviated — `metadata` carries any extra spreadsheet columns that did not map to a standard field.)*

Two things to notice. `null` means "we have no value for this" — it is not zero and not an empty string, it is an honest blank. And there are two identifiers: `id` is the database's own internal handle (a long random **UUID**, a universally unique identifier — a string long enough that no two systems will ever generate the same one by accident), while `chemical_id` is the human-facing label your spreadsheets use. Address chemicals by `chemical_id`.

**What screening has been done on this chemical?**

```bash
curl --noproxy '*' -sS http://localhost:49160/api/screening/chemical/CHEM-0001 | python3 -m json.tool
```

```json
[
    {
        "assay_name": "Cell viability (MTT)",
        "result": "Negative",
        "result_value": "98.4",
        "result_unit": "%",
        ...
    }
]
```

*(Abbreviated — one record came back; the remaining fields are omitted here.)*

What it means: the square brackets matter. This endpoint returns a **list**, because a chemical can have been screened many times, and it returns an empty list `[]` rather than an error when it has never been screened at all. Fetching a single chemical returns an object in braces; asking "everything about X" returns a list. Watch the first character of the reply and you always know which you have.

---

## Searching and paging

**How do I get chemicals a page at a time, instead of all at once?**

```bash
curl --noproxy '*' -sS "http://localhost:49160/api/chemicals?limit=2&page=1"
```

```json
{
  "data": [ ... ],
  "pagination": {"page":1,"limit":2,"total":5,"totalPages":3}
}
```

*(Abbreviated — `data` holds the two chemical objects for this page, each in the full form shown earlier.)*

What it means: the reply has two parts. `data` is the records themselves; `pagination` is the server telling you where you are — page 1 of 3, showing 2 at a time, 5 matching records in total. Ask for `page=2` to get the next two. Note the quotation marks around the address: the `&` joining the two settings would otherwise be read by your shell as "run this in the background", and the command would break in a baffling way. **Quote any address containing `&`.**

**(Why bother paging?)** With five chemicals you never need to. With fifteen thousand, asking for all of them in one request means the server builds an enormous reply and your terminal drowns in it. Paging keeps every request small and fast.

**How do I find a chemical when I only remember part of the name?**

```bash
curl --noproxy '*' -sS "http://localhost:49160/api/chemicals?search=caffeine"
```

The reply has the same two-part shape as above, with one item in `data`: the Caffeine record. The search is case-insensitive, which is why lower-case `caffeine` finds the chemical stored as `Caffeine`. Combine it with paging by joining the settings with `&`, still inside quotes: `"...?search=caffeine&limit=10&page=1"`.

---

## Linking samples to chemicals

Sample spreadsheets deliberately have no chemical column, so after importing samples you connect them to the chemicals they contain. One sample can hold many chemicals.

**How do I attach chemicals to a sample?**

```bash
curl --noproxy '*' -sS -X PUT http://localhost:49160/api/samples/SMPL00001/chemicals \
  -H "Content-Type: application/json" \
  -d '{"chemical_ids": ["CHEM-0001", "CHEM-0002"]}'
```

Two new pieces here. `-d` supplies a **request body** — the data you are sending up to the server, rather than a setting tacked onto the address; it is used whenever you are creating or changing something. `-H "Content-Type: application/json"` is the accompanying label that tells the server "what follows is JSON", so it knows how to read it.

**(Read this before you run it.)** This request *replaces* the sample's chemical list rather than adding to it. Send one ID and any previously linked chemicals are dropped. Always send the complete list you want the sample to end up with. Unknown IDs are reported back to you in a field called `unknownChemicalIds` rather than causing the whole request to fail — worth checking the reply for, since a typo will otherwise pass quietly. The full response layout is in [docs/08-api-reference.md](08-api-reference.md).

---

## Screening data: reading it back

Screening records keep whatever columns their source file had, so there is no
fixed field list to memorise. Ask the application what it holds:

```bash
# 1. Which columns exist, how well populated each is, and which are ours
curl --noproxy '*' -sS http://localhost:49160/api/screening/columns | python3 -m json.tool
```

**You should see** a `columns` array. Each entry carries `label` (the heading
shown in the table, in snake_case), `source_column` (the heading the uploaded
file used, or `null`), `derived` (true when this application added the column
rather than reading it), `type`, and `filled`.

**What it means:** `derived: true` marks a column Crucible calculated —
`below_detection_limit`, for instance. `docs/00-glossary.md` explains each one.

```bash
# 2. A page of records
curl --noproxy '*' -sS "http://localhost:49160/api/screening?page=1&limit=25"

# 3. Filter one column — ?f.<column>=<substring>, case-insensitive
curl --noproxy '*' -sS "http://localhost:49160/api/screening?f.simulant=ethanol&limit=5"

# 4. Combine filters; they are ANDed
curl --noproxy '*' -sS "http://localhost:49160/api/screening?f.simulant=ethanol&f.category=Rigid&limit=5"

# 5. Free text across every field of every record
curl --noproxy '*' -sS "http://localhost:49160/api/screening?search=benzaldehyde&limit=5"

# 6. Everything from one data source
curl --noproxy '*' -sS "http://localhost:49160/api/screening?tag=Cergy_data&limit=5"

# 7. Sort. sort_numeric=true stops 100 sorting before 20
curl --noproxy '*' -sS "http://localhost:49160/api/screening?sort=mg_per_kg_food&dir=desc&sort_numeric=true&limit=5"

# 8. Everything measured for one compound
curl --noproxy '*' -sS "http://localhost:49160/api/screening?chemical_id=CHEM-000042&limit=10"
```

**Note the field names.** Filtering and sorting use the *stored* field name
(`mg_per_kg_food`), not the heading shown in the table (`mg_kg_food`). The
`columns` endpoint gives you both: `key` is what you pass, `label` is what is
displayed.

### Duplicates

```bash
# How many rows are in each state
curl --noproxy '*' -sS http://localhost:49160/api/screening/duplicates/summary
```

**You should see:**

```json
{"total": 49065, "identical": 1482, "repeat_measurement": 1002,
 "unique": 47583, "copies_removed_by_unique": 1482}
```

**What it means:** `identical` rows match another row in every column — the same
row present twice. `repeat_measurement` rows share a sample, compound and
conditions but hold *different* values: the substance was measured more than
once, and both results are real. Select between them with `?duplicates=`:

```bash
curl --noproxy '*' -sS "http://localhost:49160/api/screening?duplicates=unique&limit=5"     # hide exact copies
curl --noproxy '*' -sS "http://localhost:49160/api/screening?duplicates=identical&limit=5"  # only exact copies
curl --noproxy '*' -sS "http://localhost:49160/api/screening?duplicates=repeat&limit=5"     # only repeats
curl --noproxy '*' -sS "http://localhost:49160/api/screening?duplicates=flagged&limit=5"    # either
```

`unique` never removes a repeat measurement — doing so would discard a result.

### Downloading a selection

Export takes the same filters as the list, and returns **every** matching row
rather than one page:

```bash
# CSV of one compound's results
curl --noproxy '*' -sS -o benzaldehyde.csv \
  "http://localhost:49160/api/screening/export?format=csv&f.compound_name=Benzaldehyde"

# Excel, only the columns you name
curl --noproxy '*' -sS -o migration.xlsx \
  "http://localhost:49160/api/screening/export?format=xlsx&columns=lims_id,compound_name,cas,mg_per_kg_food"

# The original spreadsheet values, exactly as the file had them
curl --noproxy '*' -sS -o original.csv \
  "http://localhost:49160/api/screening/export?format=csv&raw=true&f.lims_id=844423370"
```

Formats: `csv`, `tsv`, `xlsx`, `json`. `raw=true` gives the untouched source
row — what you want when reconciling against the original file.

---

## Linking rows to a chemical by hand

The identification job links rows in bulk by rule; these two requests are
for the cases a person decides. They only move the pointer from a row to a
registry entry; the row and its values are untouched.

**How do I point a few rows at the right compound?** (the chemical must be
registered — check with `/api/chemicals/list/dropdown`)

```bash
curl --noproxy '*' -sS -X POST http://localhost:49160/api/screening/link \
  -H "Content-Type: application/json" \
  -d '{"record_ids": ["<row id>", "<row id>"], "chemical_id": "CHEM-000042"}'
```

```json
{"message":"Linked 2 screening record(s) to CHEM-000042","linked":2,"not_found":[]}
```

Row ids come from the list endpoint (`id` on every row) or the record's
detail view in the browser.

**How do I act on every row of one compound name, not one page of it?** Send
the table's filters instead of ids; the server resolves them the way the
table does, across every page:

```bash
curl --noproxy '*' -sS -X POST http://localhost:49160/api/screening/unlink \
  -H "Content-Type: application/json" \
  -d '{"match": {"search": "Phenol, 2,4-di-tertiobutyl"}}'
```

```json
{"message":"Unlinked 441 screening record(s) from 1 chemical(s)","unlinked":441,"chemicals":1,"by_chemical":[{"chemical_id":"CHEM-000374","name":"Phenol, 2,4-di-tertiobutyl","rows":441}],"not_found":[]}
```

`match` takes the same keys the table uses: `search`, `chemical_id`, `tag`,
`filters` (a column name to the text it must contain), `duplicates`. The same
shape works for `/link`, with a `chemical_id`.

**How do I detach a row that was linked wrongly?**

```bash
curl --noproxy '*' -sS -X POST http://localhost:49160/api/screening/unlink \
  -H "Content-Type: application/json" \
  -d '{"record_ids": ["<row id>"]}'
```

**How do I detach every row from every chemical? (a registry reset — back up first)**

```bash
./container-py.sh backup
curl --noproxy '*' -sS -X POST http://localhost:49160/api/screening/unlink \
  -H "Content-Type: application/json" -d '{"all": true}'
```

```json
{"message":"Unlinked 43399 screening record(s) from 664 chemical(s)","unlinked":43399,"chemicals":664,"by_chemical":[{"chemical_id":"CHEM-000374","name":"Phenol, 2,4-di-tertiobutyl","rows":441},"…"],"not_found":[]}
```

The same actions are buttons on the Screening Data page: a link or unlink icon on
each row, *Link to a chemical…* and *Unlink* for ticked rows or for every row
matching your filters, a confirmation showing the compound's name and CAS
number before a link is written, and *Unlink all rows…*, which asks you to
type the words. The registry is never
changed by any of them; removing compounds is [a separate, gated script](09-chemical-identification.md#resetting-the-registry).

---

## Cleaning up

These commands remove data. Read the caveat on each one before running it.
**Since v2.11.0 a delete is refused while rows still point at the chemical**
— you get `409` and `{"error": "N screening rows linked to …; unlink them
first …"}` and nothing changes. Either unlink first (every route in
[`10-registry-tasks.md`](10-registry-tasks.md)) or add `force=true`, which
unlinks the rows and then deletes, and tells you both counts:

```bash
curl --noproxy '*' -sS -X DELETE "http://localhost:49160/api/chemicals/CHEM-0001?force=true"
```

```json
{"message":"Chemical deleted successfully","unlinked":{"screening":3,"total":3}}
```

**How do I delete one chemical?**

```bash
curl --noproxy '*' -sS -X DELETE http://localhost:49160/api/chemicals/CHEM-0001
```

`-X DELETE` sets the **method** — the verb of the request, saying what you intend rather than just where you are pointing. `GET` fetches, `POST` creates, `PUT` replaces, `DELETE` removes. Plain `curl` with no `-X` is a `GET`, which is why every look-up recipe above is safe to run at will.

**How do I delete a batch of chemicals at once?**

```bash
curl --noproxy '*' -sS -X POST http://localhost:49160/api/chemicals/bulk/delete \
  -H "Content-Type: application/json" \
  -d '{"chemical_ids": ["CHEM-0001", "CHEM-0002"]}'
```

Samples have the matching `POST /api/samples/bulk/delete`, taking `sample_ids`.

**How do I empty a table completely? (no confirmation, no undo)**

```bash
curl --noproxy '*' -sS -X DELETE http://localhost:49160/api/chemicals/all/clear
curl --noproxy '*' -sS -X DELETE http://localhost:49160/api/samples/all/clear
```

There is no "are you sure?" step — the request *is* the confirmation. Only chemicals and samples offer this. Screening and toxicology have no clear-all: those records must be deleted one at a time by their own record ID (`DELETE /api/screening/<record-id>`), which is a deliberate guardrail around experimental results. Take a backup first; the backup and restore commands are in the [README](../README.md).

---

## Why some requests are refused (and that's correct)

A refusal is usually the system doing its job. Three you are likely to meet:

**Asking for something that isn't there**

```bash
curl --noproxy '*' -sS http://localhost:49160/api/chemicals/NOPE-999
```

```json
{"error":"Chemical not found"}
```

The status code is **404** — the standard web code for "no such thing at this address", the same code your browser reports for a dead link. The server is not broken and your command is not malformed; that ID simply is not in the database. Check the spelling against `/api/chemicals/list/dropdown`, remembering that IDs are zero-padded (`CHEM-0001`, not `CHEM-1`).

**Sending a CSV to an endpoint that only takes Excel**

```bash
curl --noproxy '*' -sS -X POST http://localhost:49160/api/screening/upload/excel \
  -F "file=@something.csv"
```

```json
{"error":"File is not a zip file"}
```

This is the most confusing message in the whole system, and it is worth knowing why it says that. An `.xlsx` file is secretly a **zip archive** — a compressed folder containing several XML files that together describe the workbook. Rename one to `.zip` and you can open it up and look inside. openpyxl, the library reading these uploads, therefore begins by unzipping the file. Hand it a CSV, which is plain text with no archive around it, and it stops at the very first step and reports the only thing it knows: this is not a zip. Translated: *this is not a real Excel workbook*. Open the CSV in Excel and use Save As → `.xlsx`. Only the chemicals endpoint takes CSV directly.

**Screening or toxicology rows pointing at a chemical that doesn't exist**

Rows whose `chemical_id` is not already in the chemicals table are rejected rather than imported. This is the import-order rule from the top of the page enforcing itself. Without it you would accumulate results attached to nothing — data that looks complete in a count and is worthless in an analysis. Import the chemicals, then run the same upload again; because uploads are upserts, nothing you loaded successfully the first time gets duplicated.

---

---

## Fetching a compound from PubChem and registering it

**The normal way is not this section.** Since [phase 04](04-phase-tutorials/phase-04-template-ingestion.md) the system consults PubChem itself, in stage 2 of [chemical identification](09-chemical-identification.md), and registers a compound only when its name and its CAS number resolve to the same substance. That is the safe path for laboratory data. This section is for the other case: you want to add **one compound you already know**, by name or CAS, and see what PubChem says about it first.

**What does PubChem say about a compound? (no Crucible involved yet)**

PubChem is the free public compound database. Its address scheme puts the question in the URL: the compound, then the properties you want, then the format.

```bash
# By name
curl --noproxy '*' -sS "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/caffeine/property/MolecularFormula,MolecularWeight,IUPACName/JSON"
# By CAS number — the same address; PubChem accepts a CAS where it accepts a name
curl --noproxy '*' -sS "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/58-08-2/property/MolecularFormula,MolecularWeight,IUPACName/JSON"
```

```json
{"PropertyTable":{"Properties":[{"CID":2519,"MolecularFormula":"C8H10N4O2","MolecularWeight":194.19,"IUPACName":"1,3,7-trimethylpurine-2,6-dione"}]}}
```

`CID` is PubChem's own identifier for the compound. The same URL pasted into a browser shows the same answer. Other useful shapes: synonyms at `…/compound/cid/2519/synonyms/JSON`; a structure search at `…/compound/smiles/CCO/property/MolecularFormula,MolecularWeight,IUPACName/JSON` (`CCO` is ethanol written as **SMILES**, a line notation for a structure).

> **A caution the identification job learned the hard way.** Asking PubChem for a CAS number through the cross-reference address (`xref/rn`) returns *every compound that mentions that number*, unranked. Taking the first is how 19 compounds were once registered with another substance's chemistry ([lessons entry 25](11-lessons-learned.md)). The `name/<cas>` form above resolves to one compound, and the identification job additionally checks that the candidate lists the number among its own synonyms. Do the same if you script this.

**How do I add that compound to Crucible in one command?**

The helper script does the lookup and the registration; it targets `http://localhost:49160` unless `PANDORA_URL` says otherwise:

```bash
./docs/pubchem-to-pandora.sh caffeine          # by name
./docs/pubchem-to-pandora.sh "50-78-2"         # by CAS (aspirin)
PANDORA_URL=https://<vm-hostname>:49160 ./docs/pubchem-to-pandora.sh vanillin
```

It prints the fetched formula, weight, InChIKey and CID, the record it will send, and the server's reply. A second run for a compound already present is refused by the server as a duplicate, which is the right answer.

**The same thing by hand, so you can see the two steps**

```bash
# Step 1: ask PubChem
curl --noproxy '*' -sS "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/caffeine/property/IUPACName,MolecularFormula,MolecularWeight,CanonicalSMILES,InChIKey/JSON"

# Step 2: register it (fill the values from step 1; give it an explicit chemical_id so re-runs are detectable as duplicates)
curl --noproxy '*' -sS -X POST http://localhost:49160/api/chemicals \
  -H "Content-Type: application/json" \
  -d '{"chemical_id":"PUBCHEM-2519","name":"caffeine","cas_number":"58-08-2","molecular_formula":"C8H10N4O2","molecular_weight":194.19,"inchi_key":"RYYVLZVUVIJVGH-UHFFFAOYSA-N","description":"1,3,7-trimethylpurine-2,6-dione","metadata":{"pubchem_cid":2519,"source":"PubChem"}}'

# Step 3: confirm
curl --noproxy '*' -sS "http://localhost:49160/api/chemicals?search=caffeine"
```

**And from Python, as a starting point for your own scripts**

```python
"""Fetch a compound from PubChem and register it in Crucible."""
import requests

CRUCIBLE = "http://localhost:49160/api"     # or the VM's https:// address
query = "vanillin"                           # a name or a CAS number

props = requests.get(
    "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
    f"{query}/property/IUPACName,MolecularFormula,MolecularWeight,CanonicalSMILES,InChIKey/JSON",
    timeout=30,
).json()["PropertyTable"]["Properties"][0]

chemical = {
    "chemical_id": f"PUBCHEM-{props['CID']}",
    "name": query,
    "molecular_formula": props.get("MolecularFormula"),
    "molecular_weight": float(props.get("MolecularWeight", 0)) or None,
    "smiles": props.get("CanonicalSMILES"),
    "inchi_key": props.get("InChIKey"),
    "description": props.get("IUPACName"),
    "metadata": {"pubchem_cid": props["CID"], "source": "PubChem"},
}

r = requests.post(f"{CRUCIBLE}/chemicals", json=chemical)
if r.status_code == 201:
    print("Added:", r.json()["chemical_id"])
elif r.status_code == 400:
    print("Skipped:", r.json()["error"])      # already exists
else:
    r.raise_for_status()
```

The fields a chemical record accepts are in [`08-api-reference.md` → Chemicals](08-api-reference.md#chemicals). A ready-made demonstration of five PubChem lookups, standard library only, is `docs/api-demo.py` (`python3 docs/api-demo.py`).

**When PubChem itself misbehaves**

| Symptom | Cause | Fix |
|---|---|---|
| `curl` works, Python `requests` fails with an SSL error | corporate TLS interception | `export REQUESTS_CA_BUNDLE=/path/to/corporate-ca.pem` |
| no response, then a timeout | a proxy in the way | `export https_proxy=http://<proxy>:<port>` for the PubChem call only — never for localhost, which needs `--noproxy '*'` |
| `404` from PubChem | the name or number is unknown to it | check the spelling; try the CAS instead of the name |
| `503` under repeated calls | PubChem throttles callers above about five requests a second | slow down; the identification job backs off automatically |

---

Every endpoint, with every field and every option, is catalogued live at <http://localhost:49160/docs> (Swagger UI, with a "Try it out" button on each one) and written up in full in [docs/08-api-reference.md](08-api-reference.md).

**Next:** [`09-chemical-identification.md`](09-chemical-identification.md) — how the system identifies compounds in bulk, and the rule this section's caution comes from.
