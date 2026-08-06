# Excel Templates - Crucible: Pandora Toolbox Enhancement (v2.0)

Ready-to-fill upload templates for bulk data import into Crucible.

> **All rows in these files are synthetic examples** (public-domain reference
> compounds, placeholder IDs, people, and projects). Replace them with your own
> data — never commit a filled-in template back to the repository.
>
> The column names below are the ones the upload endpoints actually read
> (`backend/app/routers/*.py`), so a template that parses here will import.

---

## Available Templates

| Module | File | Accepted upload formats |
|--------|------|-------------------------|
| **Chemicals** | [chemicals_template.csv](./chemicals/chemicals_template.csv) · [chemicals_template.xlsx](./chemicals/chemicals_template.xlsx) · [chemicals_template.sdf](./chemicals/chemicals_template.sdf) | `.csv`, `.xlsx`, and `.sdf` |
| **Samples** | [Upload_Sample_Template.xlsx](./samples/Upload_Sample_Template.xlsx) | `.xlsx` only (SLIMS layout) |
| **Screening** | [screening_template.xlsx](./screening/screening_template.xlsx) | `.xlsx` only |
| **Toxicology** | [toxicology_template.xlsx](./toxicology/toxicology_template.xlsx) | `.xlsx` only |

> ⚠️ **Only the Chemicals endpoint accepts CSV.** Samples, Screening, and
> Toxicology are read with openpyxl and require a real `.xlsx` workbook —
> renaming a `.csv` to `.xlsx` will not work.

The samples template is also downloadable from the running app:
`GET /api/samples/template/download`.

---

## How to Use

1. Download the template for your data type.
2. Open it in Excel or Google Sheets.
3. **Keep the header row(s) exactly as they are** — replace only the example
   data rows.
4. Save as `.xlsx` (or `.csv` for chemicals).
5. In the app, open the module → **Upload** → select your file → review → import.

**Import order matters:** Samples, Screening, and Toxicology all reference a
`chemical_id`. Import chemicals first — rows referencing an unknown chemical
are rejected with `"Chemical not found"`.

---

## Chemicals

**Files:** `chemicals/chemicals_template.csv`, `.xlsx`, `.sdf`

| Column | Maps to | Notes |
|--------|---------|-------|
| `DTX_ID` | `chemical_id` | Auto-generated when blank. Re-uploading the same ID **updates** the record |
| `NESTLE_ID` | `nestle_id` | Optional internal identifier |
| `CHEMICAL_NAME` | `name` | Defaults to `Unknown` when blank |
| `CAS_NO` | `cas_number` | Keep the cell formatted as **text** so `58-08-2` is not read as a date |
| `MOL_WEIGHT_ORIG` | `molecular_weight` | Numeric |
| `MOL_FORMULA` | `molecular_formula` | e.g. `C8H10N4O2` |
| `Supplier_ref` | `supplier` | Free text |

Alternative header spellings are accepted (`chemical_id`, `CAS`, `MW`,
`Formula`, `Supplier`, …) — see `upload_excel` in
[`backend/app/routers/chemicals.py`](../../backend/app/routers/chemicals.py).

**Example:**
```csv
DTX_ID,NESTLE_ID,CHEMICAL_NAME,CAS_NO,MOL_WEIGHT_ORIG,MOL_FORMULA,Supplier_ref
CHEM-0001,INT-0001,Caffeine,58-08-2,194.19,C8H10N4O2,Example Supplier Cat# 00001
```

### SDF upload

`chemicals_template.sdf` holds three public-domain molecules with the data
fields the SDF parser promotes: `DTXSID`, `PREFERRED_NAME`, `CAS_NO`,
`MOL_FORMULA`, `MOL_WEIGHT`, `MONOISOTOPIC_MASS`, `MS_READY_SMILES`,
`SYNONYMS`. Structure-derived values (formula, weight, stereochemistry,
polymer/mixture detection) are recomputed with RDKit on import; every other
data field is preserved as metadata. Both V2000 and V3000 are supported.

---

## Samples (SLIMS layout)

**File:** `samples/Upload_Sample_Template.xlsx`

This template mirrors a SLIMS "Content record" export and has a **three-row
header** — do not flatten it:

| Row | Contents |
|-----|----------|
| 1 | Banner text — ignored by the importer |
| 2 | **Field keys** (`cntn_barCode`, `cntn_id`, …) — the importer reads these |
| 3 | Human-readable labels (`Barcode`, `Id *`, …) — kept for reference |
| 4+ | Your data |

| Key | Maps to | Notes |
|-----|---------|-------|
| `cntn_barCode` | `sample_id` | **Required** — rows without it are rejected |
| `cntn_id` | `identification` / `name` | Display name |
| `cntn_fk_category` | `content_type` | |
| `cntn_cf_fk_sampleSubtype` | `material_type` | |
| `cntn_cf_fk_responsible` | `responsible_person` | |
| `cntn_cf_fk_ownerGroup` | `group_name` | |
| `cntn_cf_fk_project` | `project_number` | |
| `cntn_cf_description` | `description` | |
| `cntn_fk_status` | `status` | Lower-cased, spaces → `_`; defaults to `available` |
| `cntn_cf_receptionDate` | `reception_date` | `DD/MM/YYYY` → normalized to ISO |
| `cntn_cf_exp_date` | `expiry_date` | `DD/MM/YYYY` → normalized to ISO |

Every column is additionally preserved verbatim under `metadata`, so nothing is
lost. Chemical links are **not** set from the spreadsheet — make them in the app
(they survive re-uploads of the same sample).

---

## Screening

**File:** `screening/screening_template.xlsx` (`.xlsx` only)

Required: `chemical_id` (must already exist) and `assay_name` (defaults to
`Unknown Assay`).

Recognized columns: `chemical_id`, `assay_name`, `assay_type`, `target`,
`result`, `result_value`, `result_unit`, `concentration`, `concentration_unit`,
`timepoint`, `replicate`, `plate_id`, `well_position`, `experiment_date`,
`operator`, `notes`.

Each is also accepted in `Title_Case` (`Chemical_ID`, `Assay_Name`, …).
Unrecognized columns are still preserved under `metadata`.

> Numeric results go in `result_value` + `result_unit` (e.g. an IC50 of
> `12.7 uM`); `result` is the qualitative call (`Positive` / `Negative`).

---

## Toxicology

**File:** `toxicology/toxicology_template.xlsx` (`.xlsx` only)

Required: `chemical_id` (must already exist) and `study_type` (defaults to
`Unknown Study`).

Recognized columns: `chemical_id`, `study_type`, `species`, `strain`, `sex`,
`route_of_administration`, `duration`, `duration_unit`, `dose`, `dose_unit`,
`endpoint`, `endpoint_value`, `endpoint_unit`, `noael`, `loael`, `ld50`,
`study_reference`, `study_date`, `source`, `notes`.

Each is also accepted in `Title_Case` (`Chemical_ID`, `Study_Type`, `NOAEL`,
`LOAEL`, `LD50`, …). Unrecognized columns are preserved under `metadata`.

---

## Data Conventions

- **Dates** — `YYYY-MM-DD` everywhere, except the SLIMS samples template which
  uses `DD/MM/YYYY` and is normalized to ISO on import.
- **Numbers** — digits only, no thousands separators (`194.19`, not `1,194.19`).
- **CAS numbers** — format the column as text; Excel otherwise turns `58-08-2`
  into a date.
- **Empty values** — leave the cell blank. Do not write `N/A`, `null`, or `-`.
- **Booleans** — `TRUE` / `FALSE`.

---

## Common Issues

| Message | Cause | Fix |
|---------|-------|-----|
| `Chemical not found` | The row's `chemical_id` isn't in the database | Import chemicals first; check for typos |
| Columns arrive empty | Header row edited, or a `.csv` sent to an `.xlsx`-only endpoint | Restore the header row exactly; save as real `.xlsx` |
| CAS shows as a date | Excel auto-converted the cell | Format the column as text and re-enter the value |
| Samples import finds 0 rows | The three-row header was flattened | Start from a fresh copy of the template |

---

## Tips for Large Imports

- Test with 5–10 rows before a full import.
- Back up first: `./container-py.sh backup`.
- For very large files, split into batches of ~500 rows.
- Chemicals uploads are **upserts** — re-importing the same `DTX_ID` updates the
  existing record rather than creating a duplicate.

---

## Regenerating these templates

The templates are produced by
[`generate_templates.py`](./generate_templates.py) so they stay in sync with the
parsers, carry no document metadata, and contain no real data. To change a
template, edit the script and re-run it (it needs the backend virtualenv, which
has openpyxl and RDKit):

```bash
backend/.venv/bin/python docs/excel-templates/generate_templates.py
```

Then re-verify the suite still passes:

```bash
cd backend && .venv/bin/pytest
```

---

## Support

1. [API.md](../../API.md) — upload endpoint reference
2. [docs/API-TESTING-GUIDE.md](../API-TESTING-GUIDE.md) — worked `curl` examples
3. [CONTRIBUTING.md](../../CONTRIBUTING.md) — reporting bugs

---

**Last Updated:** August 6, 2026
**Template Version:** 2.1 (synthetic example data)
