[← README](../README.md) · [All docs in order](../README.md#the-documentation-in-order) · [Glossary](GLOSSARY.md)

# The API cookbook — ready-to-run recipes

Every recipe on this page is a command you can paste straight into a terminal, followed by the answer the server actually gave back when we ran it. Nothing here is a sketch or a guess. If you have never touched an API before, read the next four paragraphs and you will have everything you need.

An **API** — a website built for programs instead of for people. When you open Crucible in a browser you get buttons, colours and tables. When a program asks the same server for the same information, it does not want any of that; it wants the raw facts. So the server offers a second set of addresses that return plain data. Those addresses all start with `/api`, and this cookbook is a tour of them.

**`curl`** — a small program that fetches a web address from the terminal instead of from a browser. It is already installed on macOS and on the RHEL8 VM. `curl http://example.com/thing` is the command-line equivalent of typing that address into Chrome and reading the page source.

**JSON** — a labelled text format that both people and programs can read. It is just names and values wrapped in braces: `{"total": 5}` means "the thing called total is 5". Square brackets `[ ... ]` mean a list of several items. Every answer in this cookbook is JSON.

By default the server sends JSON as one long unbroken line, which is hard on the eyes. Pipe it through Python's built-in formatter to spread it over indented lines:

```bash
curl --noproxy '*' -s http://localhost:49160/api/stats | python3 -m json.tool
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
curl --noproxy '*' -s http://localhost:49160/api/stats | python3 -m json.tool
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
curl --noproxy '*' -s http://localhost:49160/api/chemicals/list/dropdown
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
curl --noproxy '*' -s -X POST http://localhost:49160/api/chemicals/upload/excel \
  -F "file=@docs/excel-templates/chemicals/chemicals_template.csv"
```

```json
{"message":"Successfully processed 5 chemicals (5 new, 0 updated)","inserted":5,"updated":0,"total":5}
```

**What if I upload the same chemicals file twice by mistake? (nothing bad happens)**

Run the exact command again and the counts flip:

```json
{"message":"Successfully processed 5 chemicals (0 new, 5 updated)","inserted":0,"updated":5,"total":5}
```

What it means: this is an **upsert** — update-or-insert, the database deciding for you. A chemical ID already present is refreshed with the new values rather than duplicated. So re-running an upload after fixing a typo in the spreadsheet is the normal, intended way to correct data. You will not end up with two Caffeines.

**How do I load the samples?**

```bash
curl --noproxy '*' -s -X POST http://localhost:49160/api/samples/upload/excel \
  -F "file=@docs/excel-templates/samples/Upload_Sample_Template.xlsx"
```

```json
{"message":"Successfully processed 2 samples (2 new, 0 updated)","inserted":2,"updated":0,"total":2,"summary":{...}}
```

*(Abbreviated — `summary` holds a per-column breakdown that is long and not needed here.)*

**How do I load the screening results? (chemicals must already be loaded)**

```bash
curl --noproxy '*' -s -X POST http://localhost:49160/api/screening/upload/excel \
  -F "file=@docs/excel-templates/screening/screening_template.xlsx"
```

```json
{"message":"Successfully uploaded 3 screening records","inserted":3}
```

**How do I load the toxicology studies? (same rule — chemicals first)**

```bash
curl --noproxy '*' -s -X POST http://localhost:49160/api/toxicology/upload/excel \
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
curl --noproxy '*' -s http://localhost:49160/api/chemicals/CHEM-0001
```

```json
{"id":"7b7a84b8-79b3-4f44-ad20-16ad661ae4cc","chemical_id":"CHEM-0001","nestle_id":"INT-0001","name":"Caffeine","cas_number":"58-08-2","molecular_formula":"C8H10N4O2","molecular_weight":194.19,"smiles":null,"inchi":null,"inchi_key":null,"supplier":"Example Supplier Cat# 00001","description":null,"metadata":{...}}
```

*(Abbreviated — `metadata` carries any extra spreadsheet columns that did not map to a standard field.)*

Two things to notice. `null` means "we have no value for this" — it is not zero and not an empty string, it is an honest blank. And there are two identifiers: `id` is the database's own internal handle (a long random **UUID**, a universally unique identifier — a string long enough that no two systems will ever generate the same one by accident), while `chemical_id` is the human-facing label your spreadsheets use. Address chemicals by `chemical_id`.

**What screening has been done on this chemical?**

```bash
curl --noproxy '*' -s http://localhost:49160/api/screening/chemical/CHEM-0001 | python3 -m json.tool
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
curl --noproxy '*' -s "http://localhost:49160/api/chemicals?limit=2&page=1"
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
curl --noproxy '*' -s "http://localhost:49160/api/chemicals?search=caffeine"
```

The reply has the same two-part shape as above, with one item in `data`: the Caffeine record. The search is case-insensitive, which is why lower-case `caffeine` finds the chemical stored as `Caffeine`. Combine it with paging by joining the settings with `&`, still inside quotes: `"...?search=caffeine&limit=10&page=1"`.

---

## Linking samples to chemicals

Sample spreadsheets deliberately have no chemical column, so after importing samples you connect them to the chemicals they contain. One sample can hold many chemicals.

**How do I attach chemicals to a sample?**

```bash
curl --noproxy '*' -s -X PUT http://localhost:49160/api/samples/SMPL00001/chemicals \
  -H "Content-Type: application/json" \
  -d '{"chemical_ids": ["CHEM-0001", "CHEM-0002"]}'
```

Two new pieces here. `-d` supplies a **request body** — the data you are sending up to the server, rather than a setting tacked onto the address; it is used whenever you are creating or changing something. `-H "Content-Type: application/json"` is the accompanying label that tells the server "what follows is JSON", so it knows how to read it.

**(Read this before you run it.)** This request *replaces* the sample's chemical list rather than adding to it. Send one ID and any previously linked chemicals are dropped. Always send the complete list you want the sample to end up with. Unknown IDs are reported back to you in a field called `unknownChemicalIds` rather than causing the whole request to fail — worth checking the reply for, since a typo will otherwise pass quietly. The full response layout is in [API.md](../API.md).

---

## Cleaning up

These commands remove data. Read the caveat on each one before running it.

**How do I delete one chemical?**

```bash
curl --noproxy '*' -s -X DELETE http://localhost:49160/api/chemicals/CHEM-0001
```

`-X DELETE` sets the **method** — the verb of the request, saying what you intend rather than just where you are pointing. `GET` fetches, `POST` creates, `PUT` replaces, `DELETE` removes. Plain `curl` with no `-X` is a `GET`, which is why every look-up recipe above is safe to run at will.

**How do I delete a batch of chemicals at once?**

```bash
curl --noproxy '*' -s -X POST http://localhost:49160/api/chemicals/bulk/delete \
  -H "Content-Type: application/json" \
  -d '{"chemical_ids": ["CHEM-0001", "CHEM-0002"]}'
```

Samples have the matching `POST /api/samples/bulk/delete`, taking `sample_ids`.

**How do I empty a table completely? (no confirmation, no undo)**

```bash
curl --noproxy '*' -s -X DELETE http://localhost:49160/api/chemicals/all/clear
curl --noproxy '*' -s -X DELETE http://localhost:49160/api/samples/all/clear
```

There is no "are you sure?" step — the request *is* the confirmation. Only chemicals and samples offer this. Screening and toxicology have no clear-all: those records must be deleted one at a time by their own record ID (`DELETE /api/screening/<record-id>`), which is a deliberate guardrail around experimental results. Take a backup first; the backup and restore commands are in the [README](../README.md).

---

## Why some requests are refused (and that's correct)

A refusal is usually the system doing its job. Three you are likely to meet:

**Asking for something that isn't there**

```bash
curl --noproxy '*' -s http://localhost:49160/api/chemicals/NOPE-999
```

```json
{"error":"Chemical not found"}
```

The status code is **404** — the standard web code for "no such thing at this address", the same code your browser reports for a dead link. The server is not broken and your command is not malformed; that ID simply is not in the database. Check the spelling against `/api/chemicals/list/dropdown`, remembering that IDs are zero-padded (`CHEM-0001`, not `CHEM-1`).

**Sending a CSV to an endpoint that only takes Excel**

```bash
curl --noproxy '*' -s -X POST http://localhost:49160/api/screening/upload/excel \
  -F "file=@something.csv"
```

```json
{"error":"File is not a zip file"}
```

This is the most confusing message in the whole system, and it is worth knowing why it says that. An `.xlsx` file is secretly a **zip archive** — a compressed folder containing several XML files that together describe the workbook. Rename one to `.zip` and you can open it up and look inside. openpyxl, the library reading these uploads, therefore begins by unzipping the file. Hand it a CSV, which is plain text with no archive around it, and it stops at the very first step and reports the only thing it knows: this is not a zip. Translated: *this is not a real Excel workbook*. Open the CSV in Excel and use Save As → `.xlsx`. Only the chemicals endpoint takes CSV directly.

**Screening or toxicology rows pointing at a chemical that doesn't exist**

Rows whose `chemical_id` is not already in the chemicals table are rejected rather than imported. This is the import-order rule from the top of the page enforcing itself. Without it you would accumulate results attached to nothing — data that looks complete in a count and is worthless in an analysis. Import the chemicals, then run the same upload again; because uploads are upserts, nothing you loaded successfully the first time gets duplicated.

---

Every endpoint, with every field and every option, is catalogued live at <http://localhost:49160/docs> (Swagger UI, with a "Try it out" button on each one) and written up in full in [API.md](../API.md).

---
**Next:** [API testing guide](API-TESTING-GUIDE.md) — worked examples with Python as well as curl.
