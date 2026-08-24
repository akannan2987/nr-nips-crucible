[← README](../README.md) · [All docs in order](../README.md#the-documentation-in-order) · [Glossary](GLOSSARY.md)

# Database Schema - Crucible: Pandora Toolbox Enhancement (v2.0)

Complete database schema documentation for the Python backend (**SQLite by
default, optional PostgreSQL** — both via SQLAlchemy 2). The field-by-field
record shapes are documented in [Collections](#collections); each record is
stored verbatim in its table's `doc` JSON column (JSONB on PostgreSQL).

---

## Table of Contents

- [SQL Schema (Python backend)](#sql-schema-python-backend)
- [Overview](#overview)
- [Schema Structure](#schema-structure)
- [Collections](#collections)
- [Relationships](#relationships)
- [Indexes and Constraints](#indexes-and-constraints)
- [Sample Data](#sample-data)

---

## SQL Schema (Python backend)

**File**: `data/crucible.db` (SQLite) · **Defined in**: `backend/app/models.py` ·
**Created by**: **Alembic** (`alembic upgrade head`) in the container; local dev
and tests use `Base.metadata.create_all()` (`AUTO_INIT_DB=true`)

### The hybrid document pattern

The original records were schemaless — records gain/lose fields depending on how they
were created (manual POST, Excel upload, SDF upload), and `PUT` merges
arbitrary keys. To keep API responses byte-identical, each table stores the
**complete record verbatim in a `doc` JSON column**, plus extracted columns
used only for lookups and ordering:

```sql
CREATE TABLE chemicals (
    id          VARCHAR(64)  PRIMARY KEY,   -- UUID, same as doc.id
    chemical_id VARCHAR(255) UNIQUE,        -- business key (URL paths, uploads)
    created_at  VARCHAR(40),                -- ISO string, newest-first sorting
    seq         INTEGER,                    -- original array insertion order
    doc         JSON NOT NULL               -- the full record, verbatim
);

CREATE TABLE samples (
    id          VARCHAR(64)  PRIMARY KEY,
    sample_id   VARCHAR(255) UNIQUE,        -- SLIMS barcode
    created_at  VARCHAR(40),
    seq         INTEGER,
    doc         JSON NOT NULL
);

CREATE TABLE screening (                    -- toxicology is identical
    id          VARCHAR(64)  PRIMARY KEY,
    chemical_id VARCHAR(255),               -- non-unique FK-by-convention
    created_at  VARCHAR(40),
    seq         INTEGER,
    doc         JSON NOT NULL
);
```

Rules (enforced by `backend/app/store.py`):

- The extracted columns are **always rewritten from `doc` on every insert/
  update** — `doc` is the single source of truth, columns are derived.
- `seq` preserves the original array order (some endpoints, e.g.
  `/api/stats/chemicals-summary`, depend on insertion order).
- Reads return `doc` as-is, which is why every field documented in the
  [Collections](#collections) section is preserved unchanged in the SQL storage.
- Relationships remain by-convention (`chemical_ids` arrays, `chemical_id`
  strings inside `doc`) — no foreign-key constraints yet.

### PostgreSQL support

PostgreSQL is supported today (not just "ready"): `psycopg[binary]` ships in
`backend/requirements.txt` and the `doc` column maps to **JSONB** automatically
(a SQLAlchemy type variant). Point `DATABASE_URL` at Postgres —
`postgresql+psycopg://user:pass@host/crucible` — or use the managed container
via `./container-py.sh db-start` + `USE_POSTGRES=true ./container-py.sh start`.
**Alembic** owns the schema (migrations in `backend/alembic/versions/`); see
[DEPLOYMENT.md → Database](../DEPLOYMENT.md#database-sqlite-and-postgresql).
Promoting hot fields into real, indexed columns is the next incremental step
behind the same API.

---

## Overview

Data lives in a single SQLite file (`data/crucible.db`) accessed through the
SQLAlchemy 2 ORM. Each of the four tables keeps the full record verbatim in a
`doc` JSON column plus indexed lookup columns (see the hybrid document pattern
above).

### Characteristics

- **Type**: SQL (SQLite) with a JSON `doc` column per row
- **Persistence**: single file, bind-mounted at `/app/data` in the container
- **Concurrency**: SQLite file locking (atomic transactions via SQLAlchemy)
- **Scale**: comfortable to ~15K chemicals; PostgreSQL supported via `DATABASE_URL` for larger/concurrent workloads
- **Backup**: `./container-py.sh backup` (SQLite online-backup API)

---

## Schema Structure

The database contains four tables / collections:

```
chemicals · samples · screening · toxicology
```

Each row stores the full record in its `doc` JSON column; the field shapes
below describe that document.

---

## Collections

> ℹ️ The field-by-field record shapes documented in this section describe the
> `doc` JSON stored in each table — a "chemical" has exactly these fields in
> the `chemicals.doc` column.

### 1. Chemicals Collection

Stores chemical compound information.

**Collection Name**: `chemicals`

**Schema:**

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `id` | string (UUID) | Yes | Internal unique identifier | `"550e8400-e29b-41d4-a716-446655440000"` |
| `chemical_id` | string | Yes | Chemical identifier (user-facing) | `"CHEM-001"` or `"DTX12345"` |
| `nestle_id` | string | No | Nestle internal ID | `"NST-98765"` |
| `name` | string | Yes | Chemical name | `"Caffeine"` |
| `cas_number` | string | No | CAS Registry Number | `"58-08-2"` |
| `molecular_formula` | string | No | Molecular formula | `"C8H10N4O2"` |
| `molecular_weight` | number | No | Molecular weight (g/mol) | `194.19` |
| `smiles` | string | No | SMILES notation | `"CN1C=NC2=C1C(=O)N(C(=O)N2C)C"` |
| `inchi` | string | No | InChI string | `"InChI=1S/C8H10N4O2/..."` |
| `inchi_key` | string | No | InChI Key | `"RYYVLZVUVIJVGH-UHFFFAOYSA-N"` |
| `supplier` | string | No | Supplier name | `"Sigma-Aldrich"` |
| `purity` | string | No | Purity percentage | `"≥98%"` |
| `mol_block` | string | No | MOL file content (from SDF) | `"..."` |
| `inchi_string` | string | No | Full InChI string (Tier 1 SDF field) | `"InChI=1S/..."` |
| `dtxsid` | string | No | EPA DSSTox identifier (Tier 1 SDF field) | `"DTXSID7020637"` |
| `preferred_name` | string | No | EPA preferred name (Tier 1 SDF field) | `"Caffeine"` |
| `monoisotopic_mass` | number | No | Monoisotopic mass (Tier 1 SDF field) | `194.0804` |
| `ms_ready_smiles` | string | No | EPA MS-Ready normalized SMILES | `"CN1C=NC2=C1C(=O)N(C(=O)N2C)C"` |
| `synonyms` | string[] | No | Alternate names (auto-split on `;,\n`) | `["1,3,7-Trimethylxanthine", "Theine"]` |
| `structural` | object | No | Derived structural intelligence — see below | `{ "isPolymer": false, ... }` |
| `hazard_info` | string | No | Hazard information | `"Toxic if swallowed"` |
| `storage_conditions` | string | No | Storage requirements | `"Store at 2-8°C"` |
| `description` | string | No | Additional notes | `"Stimulant compound"` |
| `metadata` | object | No | Catch-all for every `> <FIELD_NAME>` SDF property not promoted above (incl. EPA / Nestlé regulatory fields like `EU FCM substance code`, `Present in PLASTIC`, `ADI/TDI (mg/kg bw /day)`, `US 21 CFR REGNum`, `Nestle policy (St-80.008 ...)`) | `{ "EU FCM substance code": "...", ... }` |
| `created_at` | string (ISO 8601) | Yes | Creation timestamp | `"2026-02-08T10:30:00.000Z"` |
| `updated_at` | string (ISO 8601) | Yes | Last update timestamp | `"2026-02-08T15:45:00.000Z"` |

**`structural` sub-schema** (auto-derived by SDF parser):

| Field | Type | Description |
|-------|------|-------------|
| `isPolymer` | boolean | True when SRU / MUL / COP / CRO S-Group present |
| `polymerLabels` | string[] | SRU labels (`n`, `m`, ranges like `10-14`) |
| `isMixture` | boolean | SMILES contains disconnected components |
| `componentCount` | number | Number of `.`-separated SMILES components |
| `hasStereochemistry` | boolean | Atom CFG, bond wedge, or stereo collection present |
| `stereoAtomCount` | number | Atoms with stereo configuration |
| `stereoBondCount` | number | Bonds with stereo wedge |
| `totalCharge` | number | Sum of all atom formal charges |
| `chargedAtomCount` | number | Atoms with non-zero formal charge |
| `radicalCount` | number | Atoms flagged as radicals |
| `sGroupCount` | number | Total S-Groups |
| `sGroupTypes` | string[] | Distinct S-Group type codes (e.g. `["SRU"]`) |

**Constraints:**
- `chemical_id` must be unique
- `name` is required
- No hard limit on record count (optimized for 15,000+ chemicals)

**Example Document:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "chemical_id": "CHEM-001",
  "nestle_id": "NST-12345",
  "name": "Caffeine",
  "cas_number": "58-08-2",
  "molecular_formula": "C8H10N4O2",
  "molecular_weight": 194.19,
  "smiles": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
  "inchi": "InChI=1S/C8H10N4O2/c1-10-4-9-6-5(10)7(13)12(3)8(14)11(6)2/h4H,1-3H3",
  "inchi_key": "RYYVLZVUVIJVGH-UHFFFAOYSA-N",
  "supplier": "Sigma-Aldrich",
  "purity": "≥98%",
  "hazard_info": null,
  "storage_conditions": null,
  "description": null,
  "metadata": {},
  "created_at": "2026-02-08T10:00:00.000Z",
  "updated_at": "2026-02-08T10:00:00.000Z"
}
```

---

### 2. Samples Collection

Stores sample information imported from the **SLIMS "Content record"** export. A sample
may be linked to **several** chemicals via the `chemical_ids` array (linked manually in the
app — the SLIMS export has no chemical-reference column).

**Collection Name**: `samples`

**Schema:**

| Field | Type | Required | Description | SLIMS source (machine key) | Example |
|-------|------|----------|-------------|----------------------------|---------|
| `id` | string (UUID) | Yes | Internal unique identifier | — | `"uuid"` |
| `sample_id` | string | Yes | Sample identifier (unique) | `cntn_barCode` (Barcode) | `"SMPL00001"` |
| `name` | string | Yes | Display name (mirrors `identification`) | `cntn_id` | `"Ulterion 529HS coated on Alu"` |
| `identification` | string | No | SLIMS Id | `cntn_id` (Id) | `"Ulterion 529HS coated on Alu"` |
| `content_type` | string | No | Category | `cntn_fk_category` (Category) | `"Packaging"` |
| `material_type` | string | No | Sample subtype | `cntn_cf_fk_sampleSubtype` | `"Polymer"` |
| `responsible_person` | string | No | Contact person | `cntn_cf_fk_responsible` | `"RDKosterSa"` |
| `group_name` | string | No | Owner group | `cntn_cf_fk_ownerGroup` | `"NIPS - Advanced Packaging Sciences…"` |
| `project_number` | string | No | NPDI Project (Study) | `cntn_cf_fk_project` | `"DUND-103291 Buddy"` |
| `description` | string | No | Description (newlines preserved) | `cntn_cf_description` | `"Supplier JainChem\n…"` |
| `reception_date` | string (ISO 8601) | No | Reception date (DD/MM/YYYY → ISO) | `cntn_cf_receptionDate` | `"2023-05-01"` |
| `expiry_date` | string (ISO 8601) | No | Expiry date (DD/MM/YYYY → ISO) | `cntn_cf_exp_date` | `null` |
| `status` | string | No | Lifecycle status (lower-cased) | `cntn_fk_status` | `"available"` |
| `chemical_ids` | string[] | No | Manually linked chemicals (0..n) | — (app) | `["CHEM-001","CHEM-002"]` |
| `labels` | object | No | SLIMS human labels (key → label) | row 3 | `{ "cntn_barCode": "Barcode" }` |
| `metadata` | object | No | **Catch-all** — every raw SLIMS column verbatim (29 keys) | all | `{ "cntn_fk_provider": "…", … }` |
| `created_at` | string (ISO 8601) | Yes | Creation timestamp | — | `"2026-02-08T10:00:00.000Z"` |
| `updated_at` | string (ISO 8601) | Yes | Update timestamp | — | `"2026-02-08T10:00:00.000Z"` |

**Constraints:**
- `sample_id` (Barcode) must be unique; rows without a Barcode are skipped during import.
- `chemical_ids` is optional and populated via the app (one sample → many chemicals).
- On re-upload, existing `chemical_ids` are **preserved** (manual links are not wiped).
- No hard limit on record count (optimized for 1,000+ samples).

**SLIMS template parsing notes:**
- The export has a **3-row header**: row 1 = config/banner (skipped), row 2 = machine keys
  (the parse keys), row 3 = human labels (kept in `labels`). Data starts at row 4.
- Dates are European `DD/MM/YYYY` (Europe/Zurich) and are normalised to ISO `YYYY-MM-DD`.
- Empty cells become `null`. Nothing is dropped — unmapped columns live in `metadata`.

**Example Document:**

```json
{
  "id": "abc123-def456-ghi789",
  "sample_id": "SMPL00001",
  "name": "Ulterion 529HS coated on Alu",
  "identification": "Ulterion 529HS coated on Alu",
  "content_type": "Packaging",
  "material_type": "Polymer",
  "responsible_person": "RDKosterSa",
  "group_name": "NIPS - Advanced Packaging Sciences and Sustainability",
  "project_number": "DUND-103291 Buddy (buddy)",
  "description": "Supplier JainChem\nUlterion 529 HS coated on Alufoil (6 gsm)",
  "reception_date": "2023-05-01",
  "expiry_date": null,
  "status": "available",
  "chemical_ids": [],
  "labels": { "cntn_barCode": "Barcode", "cntn_id": "Id *" },
  "metadata": {
    "cntn_fk_contentType": "Pack - Material",
    "cntn_fk_provider": "Irrelevant",
    "cntn_fk_location": "K29",
    "cntn_cf_doc": "FALSE"
  },
  "created_at": "2026-02-08T10:00:00.000Z",
  "updated_at": "2026-02-08T10:00:00.000Z"
}
```

---

### 3. Screening Collection

Stores screening assay results linked to chemicals.

**Collection Name**: `screening`

**Schema:**

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `id` | string (UUID) | Yes | Internal unique identifier | `"uuid"` |
| `chemical_id` | string | Yes | Reference to chemical | `"CHEM-001"` |
| `assay_name` | string | Yes | Name of assay | `"Cytotoxicity (MTT)"` |
| `assay_type` | string | No | Type/category | `"Cell Viability"` |
| `target` | string | No | Assay target | `"Mitochondrial activity"` |
| `result` | string | No | Qualitative result | `"Positive"`, `"Negative"` |
| `result_value` | number | No | Quantitative result value | `10.5` |
| `result_unit` | string | No | Unit of `result_value` | `"% viability"` |
| `concentration` | number | No | Test concentration | `50` |
| `concentration_unit` | string | No | Concentration unit | `"μM"`, `"nM"` |
| `timepoint` | string | No | Measurement timepoint | `"24h"` |
| `replicate` | number | No | Replicate number | `2` |
| `plate_id` | string | No | Plate identifier | `"P123"` |
| `well_position` | string | No | Well position on plate | `"B07"` |
| `experiment_date` | string (ISO 8601) | No | Date performed | `"2026-02-01"` |
| `operator` | string | No | Person who ran assay | `"John Doe"` |
| `notes` | string | No | Additional notes | `"Repeat needed"` |
| `metadata` | object | No | Additional data (Excel upload stores the raw row here) | `{ "Assay_Name": "..." }` |
| `created_at` | string (ISO 8601) | Yes | Creation timestamp | `"2026-02-08T10:00:00.000Z"` |
| `updated_at` | string (ISO 8601) | Yes | Update timestamp | `"2026-02-08T10:00:00.000Z"` |

These are the columns of the shipped `screening_template.xlsx` (uploads are
XLSX-only; `Title_Case` column headers are accepted as aliases).

**Constraints:**
- `chemical_id` must reference existing chemical
- No limit on screening records

**Example Document:**

```json
{
  "id": "screen-uuid-001",
  "chemical_id": "CHEM-001",
  "assay_name": "Cytotoxicity (MTT)",
  "assay_type": "Cell Viability",
  "target": "Mitochondrial activity",
  "result": "Positive",
  "result_value": 10.5,
  "result_unit": "% viability",
  "concentration": 50,
  "concentration_unit": "μM",
  "timepoint": "24h",
  "replicate": 1,
  "plate_id": "P123",
  "well_position": "B07",
  "experiment_date": "2026-02-01",
  "operator": "Jane Smith",
  "notes": "Reproducible results",
  "metadata": null,
  "created_at": "2026-02-08T10:00:00.000Z",
  "updated_at": "2026-02-08T10:00:00.000Z"
}
```

---

### 4. Toxicology Collection

Stores toxicology study data linked to chemicals.

**Collection Name**: `toxicology`

**Schema:**

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `id` | string (UUID) | Yes | Internal unique identifier | `"uuid"` |
| `chemical_id` | string | Yes | Reference to chemical | `"CHEM-001"` |
| `study_type` | string | Yes | Type of study | `"Acute Toxicity"` |
| `species` | string | No | Test species | `"Rat"`, `"Mouse"` |
| `strain` | string | No | Animal strain | `"Sprague-Dawley"` |
| `sex` | string | No | Animal sex | `"Male"`, `"Female"` |
| `route_of_administration` | string | No | Administration route | `"Oral"`, `"Dermal"`, `"Inhalation"` |
| `duration` | number | No | Study duration | `14` |
| `duration_unit` | string | No | Duration unit | `"days"` |
| `dose` | number | No | Administered dose | `100` |
| `dose_unit` | string | No | Dose unit | `"mg/kg"` |
| `endpoint` | string | No | Measured endpoint | `"Body weight change"` |
| `endpoint_value` | number | No | Endpoint value | `-2.5` |
| `endpoint_unit` | string | No | Endpoint unit | `"%"` |
| `noael` | number | No | NOAEL value | `10` |
| `loael` | number | No | LOAEL value | `50` |
| `ld50` | number | No | LD50 value | `192` |
| `study_reference` | string | No | Study report/reference | `"TOX-2025-192"` |
| `study_date` | string (ISO 8601) | No | Study completion date | `"2025-12-15"` |
| `source` | string | No | Data source | `"ToxLab International"` |
| `notes` | string | No | Additional notes | `"No adverse effects"` |
| `metadata` | object | No | Additional data (Excel upload stores the raw row here) | `{}` |
| `created_at` | string (ISO 8601) | Yes | Creation timestamp | `"2026-02-08T10:00:00.000Z"` |
| `updated_at` | string (ISO 8601) | Yes | Update timestamp | `"2026-02-08T10:00:00.000Z"` |

These are the columns of the shipped `toxicology_template.xlsx` (uploads are
XLSX-only; `Title_Case` column headers are accepted as aliases).

**Constraints:**
- `chemical_id` must reference existing chemical
- No limit on toxicology records

**Example Document:**

```json
{
  "id": "tox-uuid-001",
  "chemical_id": "CHEM-001",
  "study_type": "Acute Oral Toxicity",
  "species": "Rat",
  "strain": "Sprague-Dawley",
  "sex": "Male",
  "route_of_administration": "Oral",
  "duration": 14,
  "duration_unit": "days",
  "dose": 100,
  "dose_unit": "mg/kg",
  "endpoint": "Mortality",
  "endpoint_value": 0,
  "endpoint_unit": "%",
  "noael": null,
  "loael": null,
  "ld50": 192,
  "study_reference": "TOX-2025-192",
  "study_date": "2025-12-15",
  "source": "ToxLab International",
  "notes": "No mortality observed at 100 mg/kg",
  "metadata": null,
  "created_at": "2026-02-08T10:00:00.000Z",
  "updated_at": "2026-02-08T10:00:00.000Z"
}
```

---

## Relationships

### Entity Relationship Diagram

```
┌─────────────────┐
│   Chemicals     │
│  (no hard cap)  │
│  chemical_id*   │
└────┬───────┬────┘
     │       │
     │       │ N:M (chemical_ids[], app-managed)
     │       │
     │       ▼
     │  ┌────────────────┐
     │  │    Samples     │
     │  │   (no cap)     │
     │  │ chemical_ids[] │
     │  └────────────────┘
     │
     │ 1:N
     ├──────────────────┐
     │                  │
     ▼                  ▼
┌─────────────┐  ┌──────────────┐
│  Screening  │  │ Toxicology   │
│ (Unlimited) │  │ (Unlimited)  │
│ chemical_id │  │ chemical_id  │
└─────────────┘  └──────────────┘
```

### Relationship Rules

1. **Chemicals ↔ Samples**: Many-to-Many (app-managed)
   - A sample links to 0..n chemicals via its `chemical_ids` array
     (set in the app — via `PUT /api/samples/{id}/chemicals`; the SLIMS
     export has no chemical-reference column)
   - A chemical can be linked from multiple samples
   - Deleting a chemical does NOT cascade delete samples (currently)

2. **Chemicals → Screening**: One-to-Many
   - A chemical can have multiple screening records
   - A screening record belongs to one chemical

3. **Chemicals → Toxicology**: One-to-Many
   - A chemical can have multiple toxicology studies
   - A toxicology record belongs to one chemical

---

## Indexes and Constraints

### Primary Keys

- **chemicals**: `id` (UUID) — `chemical_id` is the unique business key
- **samples**: `id` (UUID) — `sample_id` is the unique business key
- **screening**: `id` (UUID)
- **toxicology**: `id` (UUID)

### Foreign Keys

- `samples.chemical_ids[]` (each element) → `chemicals.chemical_id`
- `screening.chemical_id` → `chemicals.chemical_id`
- `toxicology.chemical_id` → `chemicals.chemical_id`

**Note**: relationships are by-convention — no foreign-key constraints are enforced; application logic ensures referential integrity.

### Unique Constraints

- `chemicals.chemical_id` must be unique
- `samples.sample_id` must be unique

### Capacity Constraints

- Chemicals: No hard limit (optimized for 15,000+ records)
- Samples: No hard limit (optimized for 1,000+ records)
- Screening: No hard limit
- Toxicology: No hard limit

---

## Sample Data

### Complete Database Example

```json
{
  "chemicals": [
    {
      "id": "uuid-001",
      "chemical_id": "CHEM-001",
      "nestle_id": "NST-12345",
      "name": "Caffeine",
      "cas_number": "58-08-2",
      "molecular_formula": "C8H10N4O2",
      "molecular_weight": 194.19,
      "smiles": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
      "supplier": "Sigma-Aldrich",
      "created_at": "2026-02-08T10:00:00.000Z",
      "updated_at": "2026-02-08T10:00:00.000Z"
    }
  ],
  "samples": [
    {
      "id": "uuid-101",
      "sample_id": "SMPL00001",
      "name": "Ulterion 529HS coated on Alu",
      "identification": "Ulterion 529HS coated on Alu",
      "content_type": "Packaging",
      "material_type": "Polymer",
      "status": "available",
      "chemical_ids": ["CHEM-001"],
      "metadata": { "cntn_fk_location": "K29" },
      "created_at": "2026-02-08T11:00:00.000Z",
      "updated_at": "2026-02-08T11:00:00.000Z"
    }
  ],
  "screening": [
    {
      "id": "uuid-201",
      "chemical_id": "CHEM-001",
      "assay_name": "Cytotoxicity",
      "result": "Positive",
      "result_value": 10.5,
      "result_unit": "% viability",
      "concentration": 50,
      "concentration_unit": "μM",
      "created_at": "2026-02-08T12:00:00.000Z",
      "updated_at": "2026-02-08T12:00:00.000Z"
    }
  ],
  "toxicology": [
    {
      "id": "uuid-301",
      "chemical_id": "CHEM-001",
      "study_type": "Acute Toxicity",
      "species": "Rat",
      "route_of_administration": "Oral",
      "ld50": 192,
      "dose_unit": "mg/kg",
      "created_at": "2026-02-08T13:00:00.000Z",
      "updated_at": "2026-02-08T13:00:00.000Z"
    }
  ]
}
```

---

## Query Patterns

### Common Queries

All routers go through the document verbs in `backend/app/store.py`
(SQLAlchemy underneath); cross-record filtering happens in Python over the
`doc` dicts:

**Get all chemicals (insertion order):**
```python
all_docs(db, Chemical)
```

**Find chemical by business key:**
```python
row = find_row(db, Chemical, "chemical_id", "CHEM-001")  # row.doc is the record
```

**Search chemicals:**
```python
[c for c in all_docs(db, Chemical)
 if search in (c.get("name") or "").lower()]
```

**Get screening by chemical:**
```python
[s for s in all_docs(db, Screening) if s.get("chemical_id") == "CHEM-001"]
```

Equivalent ad-hoc SQL against the `doc` column (SQLite shown):

```sql
SELECT doc FROM chemicals WHERE chemical_id = 'CHEM-001';
SELECT doc FROM screening WHERE chemical_id = 'CHEM-001' ORDER BY seq;
```

---

## Migration Considerations

### Column normalisation (future)

The database is already SQL — SQLite by default, with **PostgreSQL supported
today** via `DATABASE_URL` (see [PostgreSQL support](#postgresql-support)).
The remaining step is **column normalisation**: promoting hot `doc` fields
(name, CAS number, dates) into real, indexed columns via Alembic migrations,
without touching the API layer. For example:

```sql
ALTER TABLE chemicals ADD COLUMN name VARCHAR(500);
ALTER TABLE chemicals ADD COLUMN cas_number VARCHAR(50);
-- backfill from doc, then:
CREATE INDEX idx_chemicals_name ON chemicals(name);
CREATE INDEX idx_chemicals_cas ON chemicals(cas_number);
```

Each promotion is an `alembic revision` plus a backfill; `doc` stays the
single source of truth, so API responses are unaffected.

---

**Last Updated:** August 7, 2026  
**Schema Version:** 2.0
