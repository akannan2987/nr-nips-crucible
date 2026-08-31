[← README](../README.md) · [All docs in order](../README.md#the-documentation-in-order) · [Glossary](GLOSSARY.md)

# Query Cookbook — asking the database questions directly

**Prerequisites:** none beyond a running instance. No SQL experience assumed.
**Learning goal:** after this you will be able to answer questions the interface
does not have a button for — "which simulant gives the highest migration?",
"which compounds are still unidentified?" — and know why the queries look the
way they do.

The **Query** page in the application runs these. Everything here also works
over the API.

> **New here?** [The Playbook](PLAYBOOK.md) Part 7 introduces the query
> console and why the data is shaped the way it is.

## Table of Contents

- [Why queries look unusual here](#why-queries-look-unusual-here)
- [What you can and cannot do](#what-you-can-and-cannot-do)
- [The tables](#the-tables)
- [Recipes](#recipes)
- [Running a query from the API](#running-a-query-from-the-api)
- [When a query goes wrong](#when-a-query-goes-wrong)

---

## Why queries look unusual here

Most databases put every field in its own column. This one does not. Each row
keeps the **whole record as a single JSON document** in a column called `doc`,
with only a few real columns beside it for fast lookups.

**JSON** ([glossary](GLOSSARY.md#the-data-words)) — a way of writing structured
data as text, `{"name": "Benzaldehyde", "cas": "100-52-7"}`. Think of it as one
labelled box holding the whole record, rather than a row of separate pigeonholes.

That design is what lets a spreadsheet with columns nobody anticipated be
imported without losing anything ([architecture → the one design
rule](architecture.md#the-one-design-rule-everything-else-follows-from)). The
cost lands here: to read a field you reach inside the document.

```sql
json_extract(doc, '$.compound_name')
```

Read it as: *from the `doc` column, take the field named `compound_name`*. The
`$.` means "starting at the top of the document".

Two consequences worth knowing before you write anything:

**Everything comes out as text.** `json_extract` returns `'0.0026'`, not
`0.0026`. Sorting or averaging without converting first gives nonsense — `100`
sorts before `20`, exactly as `"apple"` sorts before `"banana"`. Convert with
`CAST(... AS REAL)`:

```sql
CAST(json_extract(doc, '$.mg_per_kg_food') AS REAL)
```

**A few fields *are* real columns** — `id`, `chemical_id`, `created_at`, `seq`.
Use those directly, without `json_extract`; they are indexed and much faster.

---

## What you can and cannot do

**Read-only, and enforced by the database itself.** The connection is opened in
read-only mode, so `DROP`, `DELETE`, `UPDATE` and friends are refused by SQLite
before anything in this application gets a say. There is also a check that only
`SELECT` (or `WITH … SELECT`) is submitted, and that it is a single statement —
but the read-only connection is the guarantee, not those checks.

You cannot break your data from this page. You *can* write a slow query: results
are capped at 5,000 rows and there is a time limit, so the worst outcome is a
query that gives up.

> ⚠️ **The API has no authentication** ([README →
> Security](../README.md#-security)). Anyone who can reach port 49160 can run
> queries and read everything in the database. That is the same exposure every
> other endpoint already has, but a query console makes it obvious. Treat it as
> another reason authentication is the next roadmap item.

---

## The tables

| Table | One row is | Real columns | Everything else |
|---|---|---|---|
| `chemicals` | one compound | `id`, `chemical_id`, `created_at`, `seq` | inside `doc` |
| `samples` | one physical sample | `id`, `sample_id`, `created_at`, `seq` | inside `doc` |
| `screening` | one compound detected in one sample | `id`, `chemical_id`, `created_at`, `seq` | inside `doc` |
| `toxicology` | one study record | `id`, `chemical_id`, `created_at`, `seq` | inside `doc` |

To see which fields a document actually holds, use the **Show tables & fields**
button on the Query page, or:

```bash
curl --noproxy '*' -sS http://localhost:49160/api/query/schema | python3 -m json.tool
```

---

## Recipes

### Count rows by a field

The simplest useful shape: pull one field out, group by it.

```sql
SELECT json_extract(doc, '$.simulant') AS simulant,
       COUNT(*) AS rows
FROM screening
GROUP BY simulant
ORDER BY rows DESC;
```

**You should see** one row per simulant with its count. Note that `tenax 2g` and
`Tenax 2g` appear separately — the data is recorded both ways, and the query is
showing you that faithfully. `LOWER(json_extract(doc, '$.simulant'))` merges them
if that is what you want.

### Highest migration per compound

```sql
SELECT json_extract(doc, '$.compound_name') AS compound,
       json_extract(doc, '$.cas')           AS cas,
       MAX(CAST(json_extract(doc, '$.mg_per_kg_food') AS REAL)) AS max_mg_per_kg
FROM screening
WHERE json_extract(doc, '$.mg_per_kg_food') IS NOT NULL
GROUP BY compound, cas
ORDER BY max_mg_per_kg DESC
LIMIT 25;
```

**The `CAST` is doing real work.** Remove it and the ordering becomes
alphabetical, putting `9.9` above `10000`.

### Samples where nothing was detected

```sql
SELECT json_extract(doc, '$.lims_id') AS lims,
       json_extract(doc, '$.factory') AS factory,
       COUNT(*) AS rows
FROM screening
WHERE json_extract(doc, '$.below_detection_limit') = 1
GROUP BY lims, factory
ORDER BY rows DESC;
```

`below_detection_limit` is a column this application added: the source cell held
a sentence like "No compounds found above 0.01 mg/kg" where a number was
expected. A clean sample is a result, not missing data. Note `= 1` — SQLite
stores JSON `true` as `1`.

### Compounds still unidentified

```sql
SELECT json_extract(doc, '$.compound_name') AS compound,
       json_extract(doc, '$.cas')           AS cas,
       COUNT(*) AS rows
FROM screening
WHERE chemical_id IS NULL
GROUP BY compound, cas
ORDER BY rows DESC
LIMIT 50;
```

`chemical_id` is empty where PubChem could not confirm the compound's name and
CAS number as the same substance. These are shown in the table under the name
the source file gave them.

### Join screening to the chemical registry

```sql
SELECT json_extract(c.doc, '$.name')             AS chemical,
       json_extract(c.doc, '$.molecular_formula') AS formula,
       COUNT(s.id) AS screening_rows
FROM chemicals c
JOIN screening s ON s.chemical_id = c.chemical_id
GROUP BY chemical, formula
ORDER BY screening_rows DESC
LIMIT 25;
```

This join is cheap because `chemical_id` is a real indexed column on both
tables, not a field inside the document.

### Find exact duplicate rows

```sql
SELECT json_extract(doc, '$.lims_id')       AS lims,
       json_extract(doc, '$.compound_name') AS compound,
       COUNT(*) AS copies
FROM screening
WHERE json_extract(doc, '$.duplicate_kind') = 'identical'
GROUP BY json_extract(doc, '$.duplicate_group')
ORDER BY copies DESC;
```

Change `'identical'` to `'repeat_measurement'` for the other kind: same sample
and compound, *different* measured values. Those are real repeat measurements
and are never removed automatically.

### Migration by temperature and time

```sql
SELECT json_extract(doc, '$.migration_temperature_c') AS temp_c,
       json_extract(doc, '$.migration_time_h')        AS hours,
       ROUND(AVG(CAST(json_extract(doc, '$.mg_per_dm2_material') AS REAL)), 4) AS avg_mg_dm2,
       COUNT(*) AS rows
FROM screening
GROUP BY temp_c, hours
ORDER BY rows DESC;
```

### One sample, everything found in it

```sql
SELECT json_extract(doc, '$.compound_name') AS compound,
       json_extract(doc, '$.cas')           AS cas,
       json_extract(doc, '$.simulant')      AS simulant,
       CAST(json_extract(doc, '$.mg_per_kg_food') AS REAL) AS mg_per_kg_food
FROM screening
WHERE json_extract(doc, '$.lims_id') = '844423370'
ORDER BY mg_per_kg_food DESC;
```

### What came from which source file

```sql
SELECT json_extract(doc, '$.source_tag') AS source,
       COUNT(*) AS rows,
       MIN(json_extract(doc, '$.analysis_date')) AS earliest,
       MAX(json_extract(doc, '$.analysis_date')) AS latest
FROM screening
GROUP BY source;
```

---

## Running a query from the API

```bash
curl --noproxy '*' -sS -X POST http://localhost:49160/api/query \
  -H 'Content-Type: application/json' \
  -d '{"sql":"SELECT json_extract(doc,'"'"'$.simulant'"'"') AS simulant, COUNT(*) AS rows FROM screening GROUP BY simulant ORDER BY rows DESC LIMIT 5"}'
```

**You should see:**

```json
{"columns": ["simulant", "rows"],
 "rows": [["tenax 2g", 13134], ["Tenax 2g", 10543]],
 "row_count": 5, "truncated": false, "limit": 5000, "elapsed_ms": 61.4}
```

`limit` accepts a smaller cap: `{"sql": "…", "limit": 100}`. `truncated: true`
means there were more rows than the cap allowed.

The single quotes inside a shell command are awkward — `'"'"'` closes the quote,
adds a literal `'`, and reopens it. Writing the JSON to a file avoids the whole
problem:

```bash
echo '{"sql":"SELECT COUNT(*) AS n FROM screening"}' > q.json
curl --noproxy '*' -sS -X POST http://localhost:49160/api/query \
  -H 'Content-Type: application/json' --data @q.json
```

---

## When a query goes wrong

**If instead:** `Only SELECT (or WITH … SELECT) queries are allowed.` — you sent
a statement that would change data. That is refused by design.

**If instead:** `Only one statement can be run at a time; remove the ';'` — there
is a semicolon in the middle of the query. A trailing one is fine.

**If instead:** `SQL error: no such column: simulant` — you used a document field
as though it were a real column. Wrap it:
`json_extract(doc, '$.simulant')`.

**If instead:** results sort strangely, `9.9` above `10000` — the values are
text. Add `CAST(... AS REAL)`.

**If instead:** `truncated: true` and you wanted everything — add your own
`LIMIT`, narrow the `WHERE`, or aggregate with `GROUP BY` rather than returning
raw rows. For a full extract of screening data, the
[export endpoint](API-COOKBOOK.md#downloading-a-selection) has no such cap.

**If instead:** a query is slow — you are probably filtering on a document field
across every row. Filtering on a real column (`chemical_id`, `created_at`) is far
faster, and promoting the frequently used fields into real columns is the next
planned piece of work.

---

**Last Updated:** August 31, 2026
