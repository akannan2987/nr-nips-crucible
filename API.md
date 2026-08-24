[← README](README.md) · [All docs in order](README.md#the-documentation-in-order) · [Glossary](docs/GLOSSARY.md)

# API Documentation - Crucible: Pandora Toolbox Enhancement (v2.0)

Complete REST API reference for the Chemical and Sample Management System.

**Production URL (HTTPS):** `https://<vm-hostname>:49160/api`  
**Development URL:** `http://localhost:49160/api`

> 🔒 **Note:** Production endpoints use HTTPS. Add `-k` flag to `curl` commands if using self-signed certificates. All examples below show production HTTPS URLs.

---

## Table of Contents

- [HTTP Methods Explained](#http-methods-explained)
- [Quick Start Guide](#quick-start-guide)
- [Overview](#overview)
- [Response Format](#response-format)
- [Statistics & Dashboard](#statistics--dashboard)
- [Chemicals](#chemicals)
- [Samples](#samples)
- [Screening](#screening)
- [Toxicology](#toxicology)
- [Error Codes](#error-codes)
- [Integration Examples](#integration-examples)

---

## HTTP Methods Explained

REST APIs use HTTP methods (also called "verbs") to perform different operations:

### GET - Retrieve Data
- **Purpose**: Read/retrieve data without modifying it
- **Use When**: Fetching lists, getting details of a single item
- **Has Body**: No
- **Examples**: 
  - Get all chemicals: `GET /chemicals`
  - Get one chemical: `GET /chemicals/CHEM-001`

### POST - Create New Data
- **Purpose**: Create new resources or trigger actions
- **Use When**: Adding new chemicals, uploading files, bulk operations
- **Has Body**: Yes (JSON or form data)
- **Examples**:
  - Add chemical: `POST /chemicals` with JSON body
  - Upload file: `POST /chemicals/upload/excel` with file

### PUT - Update Existing Data
- **Purpose**: Update/replace existing resources
- **Use When**: Editing chemical information
- **Has Body**: Yes (JSON with fields to update)
- **Examples**:
  - Update chemical: `PUT /chemicals/CHEM-001` with JSON body

### DELETE - Remove Data
- **Purpose**: Delete resources
- **Use When**: Removing chemicals or records
- **Has Body**: No (usually)
- **Examples**:
  - Delete chemical: `DELETE /chemicals/CHEM-001`
  - Delete all: `DELETE /chemicals/all/clear`

---

## Quick Start Guide

### Testing the API

**Option 1: Using cURL (Command Line)**
```bash
# GET request - List chemicals
curl "https://<vm-hostname>:49160/api/chemicals"

# POST request - Add chemical
curl -X POST "https://<vm-hostname>:49160/api/chemicals" \
  -H "Content-Type: application/json" \
  -d '{"chemical_id":"TEST-001","name":"Test Chemical"}'

# PUT request - Update chemical
curl -X PUT "https://<vm-hostname>:49160/api/chemicals/TEST-001" \
  -H "Content-Type: application/json" \
  -d '{"supplier":"New Supplier"}'

# DELETE request - Remove chemical
curl -X DELETE "https://<vm-hostname>:49160/api/chemicals/TEST-001"
```

**Option 2: Using Browser**
- GET requests can be tested directly in browser:
  - Navigate to: `https://<vm-hostname>:49160/api/stats`
  - Navigate to: `https://<vm-hostname>:49160/api/chemicals`

**Option 3: Using Postman**
1. Download Postman (free tool for API testing)
2. Create new request
3. Select method (GET, POST, PUT, DELETE)
4. Enter URL: `https://<vm-hostname>:49160/api/chemicals`
5. For POST/PUT: Add JSON body in "Body" tab
6. Click "Send"

**Option 4: Using JavaScript in Browser Console**
```javascript
// GET request
fetch('https://<vm-hostname>:49160/api/chemicals')
  .then(res => res.json())
  .then(data => console.log(data));

// POST request
fetch('https://<vm-hostname>:49160/api/chemicals', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({chemical_id: 'TEST-001', name: 'Test'})
})
  .then(res => res.json())
  .then(data => console.log(data));
```

---

## Overview

All API endpoints return JSON responses. The API supports:
- Pagination for list endpoints
- Search/filtering capabilities
- Bulk operations (delete, update)
- File uploads (Excel, SDF)

### Authentication

Currently, no authentication is required. Future versions will implement SSO.

### Rate Limiting

No rate limiting is currently enforced.

### Upload & Body Size Limits

| Limit | Value | Purpose |
|-------|-------|---------|
| JSON body | No app-level limit† | JSON payloads (POST/PUT requests) are not size-capped by the backend |
| File upload | No app-level limit† | Excel/SDF uploads are not size-capped by the backend |
| Max chemicals | No hard limit* | Not capped by the API; optimized for 15,000+ records |
| Max samples | No hard limit* | Not capped by the API; optimized for 1,000+ records |
| Max screening | No hard limit* | Linked to chemicals; not capped |
| Max toxicology | No hard limit* | Linked to chemicals; not capped |

> † The FastAPI backend enforces no application-level request-size limit. The practical bound is available memory — uploaded files are read fully into memory while parsing.
>
> \* No collection is capped by the API — all are bounded only by SQLite read/write performance and available memory/disk. The 15,000 / 1,000 figures are recommended-scale references used for the dashboard gauge, **not** enforced limits.

### Non-API Routes

| Path | Description |
|------|-------------|
| `/` | React SPA (main application) |
| `/architecture` | Interactive architecture documentation page |

---

## Response Format

### Success Response

```json
{
  "data": {...},
  "message": "Operation successful"
}
```

### Paginated Response

```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 100,
    "totalPages": 5
  }
}
```

### Error Response

```json
{
  "error": "Error message description"
}
```

---

## Statistics & Dashboard

### Get Dashboard Statistics

Get real-time statistics for all modules.

**Endpoint:** `GET /stats`

**Response:**

```json
{
  "chemicals": {
    "total": 25,
    "max": 15000
  },
  "samples": {
    "total": 10,
    "max": 1000
  },
  "screening": {
    "total": 50
  },
  "toxicology": {
    "total": 30
  },
  "counts": {
    "chemicals": 25,
    "samples": 10,
    "screening": 50,
    "toxicology": 30
  },
  "capacities": {
    "chemicals": {
      "current": 25,
      "max": 15000,
      "percentage": "0.2"
    },
    "samples": {
      "current": 10,
      "max": 1000,
      "percentage": "1.0"
    }
  },
  "lastUpdated": "2026-02-08T10:30:00.000Z"
}
```

**cURL Example:**

```bash
curl http://localhost:49160/api/stats
```

---

### Other Statistics Endpoints

| Method & Endpoint | Description |
|-------------------|-------------|
| `GET /stats/recent?limit=10` | Merged newest-first activity feed across all modules — `[{type, id, name, created_at}]` (screening/toxicology entries also carry `chemical_id`) |
| `GET /stats/chemicals-summary?limit=20` | Chemicals with per-record `screening_count` / `toxicology_count` |
| `GET /stats/sample-types` | Sample distribution — `[{type, count}]` |
| `GET /stats/assay-types` | Screening assay distribution — `[{assay, count}]` |
| `GET /stats/study-types` | Toxicology study distribution — `[{study, count}]` |

---

## Chemicals

### List Chemicals

Get paginated list of all chemicals with optional search.

**Endpoint:** `GET /chemicals`

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `limit` | integer | 50 | Items per page (max: 100) |
| `search` | string | - | Search in name, ID, or CAS number |

**Response:**

```json
{
  "data": [
    {
      "id": "uuid",
      "chemical_id": "CHEM-001",
      "nestle_id": "NST-12345",
      "name": "Caffeine",
      "cas_number": "58-08-2",
      "molecular_formula": "C8H10N4O2",
      "molecular_weight": 194.19,
      "smiles": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
      "inchi": "InChI=1S/C8H10N4O2/c1-10-4-9-6-5(10)7(13)12(3)8(14)11(6)2/h4H,1-3H3",
      "supplier": "Sigma-Aldrich",
      "created_at": "2026-02-08T10:00:00.000Z",
      "updated_at": "2026-02-08T10:00:00.000Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 25,
    "totalPages": 1
  }
}
```

**cURL Example:**

```bash
# Get all chemicals
curl "http://localhost:49160/api/chemicals?page=1&limit=20"

# Search chemicals
curl "http://localhost:49160/api/chemicals?search=caffeine"
```

---

### Get Single Chemical

Get details of a specific chemical by ID.

**Endpoint:** `GET /chemicals/:id`

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Chemical ID (e.g., CHEM-001) |

**Response:**

```json
{
  "id": "uuid",
  "chemical_id": "CHEM-001",
  "nestle_id": "NST-12345",
  "name": "Caffeine",
  "cas_number": "58-08-2",
  "molecular_formula": "C8H10N4O2",
  "molecular_weight": 194.19,
  "smiles": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
  "inchi": "InChI=1S/C8H10N4O2/c1-10-4-9-6-5(10)7(13)12(3)8(14)11(6)2/h4H,1-3H3",
  "supplier": "Sigma-Aldrich",
  "created_at": "2026-02-08T10:00:00.000Z",
  "updated_at": "2026-02-08T10:00:00.000Z"
}
```

**cURL Example:**

```bash
curl http://localhost:49160/api/chemicals/CHEM-001
```

---

### Get Chemicals Dropdown List

Get simplified list of chemicals for dropdown menus.

**Endpoint:** `GET /chemicals/list/dropdown`

**Response:**

```json
[
  {
    "chemical_id": "CHEM-001",
    "name": "Caffeine"
  },
  {
    "chemical_id": "CHEM-002",
    "name": "Aspirin"
  }
]
```

**cURL Example:**

```bash
curl http://localhost:49160/api/chemicals/list/dropdown
```

---

### Add Single Chemical

Add a new chemical to the database.

**Endpoint:** `POST /chemicals`

**Request Body:**

```json
{
  "chemical_id": "CHEM-001",
  "nestle_id": "NST-12345",
  "name": "Caffeine",
  "cas_number": "58-08-2",
  "molecular_formula": "C8H10N4O2",
  "molecular_weight": 194.19,
  "smiles": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
  "inchi": "InChI=1S/C8H10N4O2/c1-10-4-9-6-5(10)7(13)12(3)8(14)11(6)2/h4H,1-3H3",
  "supplier": "Sigma-Aldrich"
}
```

**Required Fields:**
- `chemical_id` (string)
- `name` (string)

**Response:**

```json
{
  "message": "Chemical added successfully",
  "chemical_id": "CHEM-001"
}
```

**cURL Example:**

```bash
curl -X POST http://localhost:49160/api/chemicals \
  -H "Content-Type: application/json" \
  -d '{
    "chemical_id": "CHEM-001",
    "name": "Caffeine",
    "cas_number": "58-08-2",
    "molecular_formula": "C8H10N4O2",
    "molecular_weight": 194.19
  }'
```

---

### Update Chemical

Update an existing chemical.

**Endpoint:** `PUT /chemicals/:id`

**Request Body:**

```json
{
  "supplier": "New Supplier",
  "cas_number": "58-08-2",
  "molecular_weight": 194.19
}
```

**Response:**

```json
{
  "message": "Chemical updated successfully"
}
```

**cURL Example:**

```bash
curl -X PUT http://localhost:49160/api/chemicals/CHEM-001 \
  -H "Content-Type: application/json" \
  -d '{"supplier": "New Supplier"}'
```

---

### Delete Chemical

Delete a chemical by ID.

**Endpoint:** `DELETE /chemicals/:id`

**Response:**

```json
{
  "message": "Chemical deleted successfully"
}
```

**cURL Example:**

```bash
curl -X DELETE http://localhost:49160/api/chemicals/CHEM-001
```

---

### Upload Chemicals (Excel)

Bulk upload chemicals via Excel file.

**Endpoint:** `POST /chemicals/upload/excel`

**Content-Type:** `multipart/form-data`

**Form Data:**

| Field | Type | Description |
|-------|------|-------------|
| `file` | file | Excel or CSV file (.xlsx, .csv, .tsv) |

> **Note:** Legacy `.xls` files are **not** supported — re-save them as `.xlsx` first.
> Ready-to-fill templates ship in
> [`docs/excel-templates/chemicals/`](docs/excel-templates/chemicals/)
> (`chemicals_template.xlsx` and `chemicals_template.csv`).

**Excel Format:**

| DTX_ID | NESTLE_ID | CHEMICAL_NAME | CAS_NO | MOL_WEIGHT_ORIG | MOL_FORMULA | Supplier_ref |
|--------|-----------|---------------|--------|-----------------|-------------|--------------|
| CHEM-001 | NST-001 | Caffeine | 58-08-2 | 194.19 | C8H10N4O2 | Sigma |

**Response:**

```json
{
  "message": "Successfully processed 25 chemicals (20 new, 5 updated)",
  "inserted": 20,
  "updated": 5,
  "total": 25
}
```

> The `errors` key (a list of `{row, error}` objects) appears only when some rows failed to import.

**cURL Example:**

```bash
curl -X POST http://localhost:49160/api/chemicals/upload/excel \
  -F "file=@chemicals_template.xlsx"
```

---

### Upload Chemicals (SDF)

Bulk upload chemicals via SDF (Structure Data File). Supports both **V2000** and **V3000** molfile formats, including V3000 line continuations (`-` suffix) and S-Group records (`SRU`, `MUL`, `COP`, `MIX`, `SUP`).

The parser extracts structural data (atoms, bonds, coordinates, charges, stereo flags, S-Groups), computes molecular formula (Hill order) and molecular weight from the atom block, and maps over 50 common SDF property field-name variations to the Pandora schema. **Every** `> <FIELD_NAME>` data item is preserved in `metadata` — no field is ever dropped.

Validated against EPA DSSTox / Nestlé regulatory format (77-record fixture: 34 polymers, 36 mixtures, 18 charged-atom records, 6 stereo records). The full extraction matrix is documented in [`docs/architecture.md`](docs/architecture.md#sdf-handling-rdkit) and implemented by the RDKit-based module (`backend/app/utils/sdf.py`).

**Endpoint:** `POST /chemicals/upload/sdf`

**Content-Type:** `multipart/form-data`

**Form Data:**

| Field | Type | Description |
|-------|------|-------------|
| `file` | file | SDF file (.sdf) containing one or more molecule records separated by `$$$$` |

**Response:**

```json
{
  "message": "Successfully processed 3 chemicals from SDF (3 new, 0 updated)",
  "inserted": 3,
  "updated": 0,
  "total": 3,
  "totalRecords": 3,
  "summary": {
    "recordsInFile": 3,
    "successfullyProcessed": 3,
    "parseErrors": 0,
    "insertErrors": 0
  }
}
```

**Error Response (invalid SDF):**

```json
{
  "error": "No valid molecules found in the SDF file. Ensure the file follows the V2000/V3000 SDF format with $$$$ record delimiters."
}
```

**Tier 1 — Explicit named fields (promoted to top-level):**

| Pandora Field | Example SDF Property Names (case-insensitive) |
|---------------|-----------------------------------------------|
| `chemical_id` | `COMPOUND_ID`, `DTX_ID`, `DTXSID`, `PUBCHEM_COMPOUND_CID`, `CHEMBL_ID`, `REGISTRY_NUMBER` |
| `name` | `COMPOUND_NAME`, `CHEMICAL_NAME`, `Name`, `IUPAC_NAME`, `PREFERRED_NAME`, `TRADE_NAME` |
| `cas_number` | `CAS_NUMBER`, `CAS_NO`, `CAS`, `CASRN`, `CAS Registry Number` |
| `molecular_formula` | `MOLECULAR_FORMULA`, `MOL_FORMULA`, `Formula` *(or auto-computed from atom block)* |
| `molecular_weight` | `MOLECULAR_WEIGHT`, `MOL_WEIGHT`, `MW`, `EXACT_MASS` *(or auto-computed)* |
| `smiles` | `SMILES`, `CANONICAL_SMILES`, `ISOMERIC_SMILES`, `OPENEYE_ISO_SMILES` |
| `inchi` / `inchi_string` | `InChI`, `STANDARD_INCHI`, `INCHI_STRING`, `PUBCHEM_IUPAC_INCHI` |
| `inchi_key` | `InChIKey`, `STANDARD_INCHIKEY`, `PUBCHEM_IUPAC_INCHIKEY` |
| `dtxsid` | `DTXSID`, `DTX_ID`, `DTXID` |
| `preferred_name` | `PREFERRED_NAME`, `Preferred Name` |
| `monoisotopic_mass` | `MONOISOTOPIC_MASS`, `EXACT_MASS` |
| `ms_ready_smiles` | `MS_READY_SMILES`, `MS-Ready SMILES` |
| `synonyms` | `SYNONYMS / COMPOSITION`, `SYNONYMS`, `COMMON_NAMES` *(auto-split on `;`, `,`, newline)* |
| `supplier` | `Supplier`, `Vendor`, `SOURCE`, `Manufacturer` |
| `purity` | `PURITY`, `PERCENT_PURITY`, `ASSAY_PURITY` |
| `nestle_id` | `NESTLE_ID`, `Nestle ID` |

**Tier 2 — Catch-all metadata:**

Every other `> <FIELD_NAME>` block is preserved verbatim in `metadata`, including the 40+ EPA / Nestlé regulatory fields:
`Present in PLASTIC`, `Present in COATING`, `Present in INK`, `Present as NIAS`, `EU FCM substance code`, `EU PM substance code`, `Listed / Updated in EU plastic regulation`, `Restrictions and Specifications (SML in mg/kg)`, `ADI/TDI (mg/kg bw /day)`, `US FCS code`, `US FCN + TOR codes`, `US 21 CFR REGNum (list of articles)`, `Nestle policy (St-80.008 …)`, `Nestle safety-based level SBL (mg/kg food)`, `log P(o/w) (25°C)`, `RI from compilation (DB-5)`, `Color Index Code`, etc.

**Tier 3 — Structural intelligence (`structural` object on each record):**

| Property | Type | Meaning |
|----------|------|---------|
| `isPolymer` | bool | At least one `SRU` / `MUL` / `COP` / `CRO` S-Group |
| `polymerLabels` | string[] | SRU labels (`n`, `m`, `x`, ranges like `10-14`) |
| `isMixture` | bool | SMILES contains multiple disconnected components |
| `componentCount` | int | Number of `.`-separated components in SMILES |
| `hasStereochemistry` | bool | Atom CFG, bond wedge, or `STEABS/STEREL/STERAC` collection present |
| `stereoAtomCount` / `stereoBondCount` | int | Count of stereo atoms / bonds |
| `totalCharge` / `chargedAtomCount` | int | Sum and count of non-zero atom charges |
| `radicalCount` | int | Atoms flagged as radicals |
| `sGroupCount` / `sGroupTypes` | int / string[] | S-Group totals |

> **Note:** When a `chemical_id` is found in the SDF properties and matches an existing record, the chemical is **updated** rather than duplicated. All raw SDF properties are preserved in the `metadata` field — nothing is dropped.

**cURL Example:**

```bash
curl -X POST http://localhost:49160/api/chemicals/upload/sdf \
  -F "file=@chemicals_template.sdf"
```

---

### Bulk Delete Chemicals

Delete multiple chemicals at once.

**Endpoint:** `POST /chemicals/bulk/delete`

**Request Body:**

```json
{
  "chemical_ids": ["CHEM-001", "CHEM-002", "CHEM-003"]
}
```

**Response:**

```json
{
  "message": "Successfully deleted 3 chemicals",
  "deleted": 3,
  "requested": 3
}
```

**cURL Example:**

```bash
curl -X POST http://localhost:49160/api/chemicals/bulk/delete \
  -H "Content-Type: application/json" \
  -d '{"chemical_ids": ["CHEM-001", "CHEM-002"]}'
```

---

### Bulk Update Chemicals

Update multiple chemicals with the same data.

**Endpoint:** `POST /chemicals/bulk/update`

**Request Body:**

```json
{
  "chemical_ids": ["CHEM-001", "CHEM-002"],
  "updates": {
    "supplier": "Sigma-Aldrich",
    "cas_number": "12345-67-8"
  }
}
```

**Response:**

```json
{
  "message": "Successfully updated 2 chemicals",
  "updated": 2,
  "requested": 2
}
```

**cURL Example:**

```bash
curl -X POST http://localhost:49160/api/chemicals/bulk/update \
  -H "Content-Type: application/json" \
  -d '{
    "chemical_ids": ["CHEM-001", "CHEM-002"],
    "updates": {"supplier": "Sigma-Aldrich"}
  }'
```

---

### Clear All Chemicals

**⚠️ DANGER:** Delete all chemicals from the database.

**Endpoint:** `DELETE /chemicals/all/clear`

**Response:**

```json
{
  "message": "Successfully deleted all 25 chemicals",
  "deleted": 25
}
```

**cURL Example:**

```bash
curl -X DELETE http://localhost:49160/api/chemicals/all/clear
```

---

## Samples

Samples are imported from the **SLIMS "Content record"** Excel export. A sample can be
linked to **several** chemicals via `chemical_ids` (linked manually in the app).

### List Samples

Get paginated list of all samples.

**Endpoint:** `GET /samples`

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `limit` | integer | 50 | Items per page |
| `search` | string | - | Search in barcode, identification, project, content/material type |

**Response:**

```json
{
  "data": [
    {
      "id": "uuid",
      "sample_id": "SMPL00001",
      "name": "Ulterion 529HS coated on Alu",
      "identification": "Ulterion 529HS coated on Alu",
      "content_type": "Packaging",
      "material_type": "Polymer",
      "responsible_person": "RDKosterSa",
      "group_name": "NIPS - Advanced Packaging Sciences and Sustainability",
      "project_number": "DUND-103291 Buddy (buddy)",
      "reception_date": "2023-05-01",
      "expiry_date": null,
      "status": "available",
      "chemical_ids": [],
      "metadata": { "cntn_fk_provider": "Irrelevant", "cntn_fk_location": "K29" },
      "created_at": "2026-02-08T10:00:00.000Z"
    }
  ],
  "pagination": { "page": 1, "limit": 50, "total": 10, "totalPages": 1 }
}
```

---

### Add Sample

**Endpoint:** `POST /samples`

**Request Body:**

```json
{
  "sample_id": "SMPL00001",
  "identification": "Ulterion 529HS coated on Alu",
  "content_type": "Packaging",
  "material_type": "Polymer",
  "project_number": "DUND-103291 Buddy",
  "status": "available"
}
```

---

### Download Sample Template

Download the SLIMS sample upload template (`.xlsx`).

**Endpoint:** `GET /samples/template/download`

**Response:** binary `.xlsx` attachment (`Upload_Sample_Template.xlsx`).

---

### Upload Samples (SLIMS Excel)

Bulk-import samples from a SLIMS "Content record" export. The parser auto-detects the
**3-row header** (config row, machine-key row `cntn_barCode`/`cntn_id`/…, human-label row),
maps key columns to Pandora fields, normalises European dates (`DD/MM/YYYY` → ISO), and
preserves **every** raw SLIMS column in `metadata`. Rows without a Barcode are skipped.
Re-uploading a sample **preserves** its existing `chemical_ids`.

**Endpoint:** `POST /samples/upload/excel`

**Content-Type:** `multipart/form-data` (field: `file`)

**Field mapping (renames):**

| SLIMS column (label) | Machine key | → Pandora field |
|----------------------|-------------|-----------------|
| Barcode | `cntn_barCode` | `sample_id` |
| Id | `cntn_id` | `identification` |
| Category | `cntn_fk_category` | `content_type` |
| Sample Subtype | `cntn_cf_fk_sampleSubtype` | `material_type` |
| Responsible | `cntn_cf_fk_responsible` | `responsible_person` |
| Owner Group | `cntn_cf_fk_ownerGroup` | `group_name` |
| NPDI number Project | `cntn_cf_fk_project` | `project_number` |
| Description | `cntn_cf_description` | `description` |
| Reception Date | `cntn_cf_receptionDate` | `reception_date` |
| Status | `cntn_fk_status` | `status` |
| Expiry date | `cntn_cf_exp_date` | `expiry_date` |
| *(all other columns)* | — | preserved in `metadata` |

**Response:**

```json
{
  "message": "Successfully processed 1 samples (1 new, 0 updated)",
  "inserted": 1,
  "updated": 0,
  "total": 1,
  "summary": {
    "rowsInFile": 1,
    "successfullyProcessed": 1,
    "skipped": 0,
    "parseWarnings": [],
    "sheet": "data"
  }
}
```

**cURL Example:**

```bash
curl -X POST http://localhost:49160/api/samples/upload/excel \
  -F "file=@Upload_Sample_Template.xlsx"
```

---

### Link Chemicals to a Sample

Set the full list of chemicals linked to a sample (one sample → many chemicals).
Unknown chemical IDs are reported in `unknownChemicalIds` but not rejected.

**Endpoint:** `PUT /samples/:id/chemicals`  *(`:id` is the `sample_id` / barcode)*

**Request Body:**

```json
{ "chemical_ids": ["CHEM-001", "CHEM-002"] }
```

**Response:**

```json
{
  "message": "Linked 2 chemical(s) to sample SMPL00001",
  "sample_id": "SMPL00001",
  "chemical_ids": ["CHEM-001", "CHEM-002"],
  "unknownChemicalIds": ["CHEM-002"]
}
```

---

### Get / Update / Delete a Sample

Samples are addressed by their `sample_id` (the SLIMS barcode).

| Method & Endpoint | Description |
|-------------------|-------------|
| `GET /samples/:id` | One sample record |
| `PUT /samples/:id` | Merge arbitrary JSON fields into the sample |
| `DELETE /samples/:id` | Delete the sample |

```bash
curl http://localhost:49160/api/samples/SMPL00001
curl -X PUT http://localhost:49160/api/samples/SMPL00001 \
  -H "Content-Type: application/json" -d '{"status": "depleted"}'
curl -X DELETE http://localhost:49160/api/samples/SMPL00001
```

---

### Bulk Delete Samples

**Endpoint:** `POST /samples/bulk/delete`

**Request Body:**

```json
{ "sample_ids": ["SMPL00001", "SMPL00002"] }
```

**Response:**

```json
{
  "message": "Successfully deleted 2 samples",
  "deleted": 2,
  "requested": 2
}
```

---

### Clear All Samples

**⚠️ DANGER:** Delete all samples from the database.

**Endpoint:** `DELETE /samples/all/clear`

**Response:**

```json
{
  "message": "Successfully deleted all 10 samples",
  "deleted": 10
}
```

---

## Screening

Screening records are always linked to an existing chemical (`chemical_id`).
Record fields: `chemical_id`, `assay_name`, `assay_type`, `target`, `result`,
`result_value`, `result_unit`, `concentration`, `concentration_unit`,
`timepoint`, `replicate`, `plate_id`, `well_position`, `experiment_date`,
`operator`, `notes`, plus a free-form `metadata` object — the same columns as
the shipped
[`screening_template.xlsx`](docs/excel-templates/screening/screening_template.xlsx).

### List Screening Records

Get paginated list of screening data. Each record in the list is enriched with
`chemical_name` (looked up from the chemicals collection).

**Endpoint:** `GET /screening`

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `page` | integer | Page number |
| `limit` | integer | Items per page |
| `search` | string | Search in assay name, chemical ID, or result |
| `chemical_id` | string | Filter by chemical ID |

---

### Get Screening by Chemical

Raw records for one chemical (no `chemical_name` enrichment).

**Endpoint:** `GET /screening/chemical/:chemical_id`

**Response:**

```json
[
  {
    "id": "uuid",
    "chemical_id": "CHEM-001",
    "assay_name": "Cytotoxicity",
    "assay_type": "Cell viability",
    "target": "HepG2",
    "result": "Positive",
    "result_value": 10.5,
    "result_unit": "μM",
    "concentration": 50,
    "concentration_unit": "μM",
    "timepoint": "24h",
    "replicate": 1,
    "plate_id": "PLATE-01",
    "well_position": "B4",
    "experiment_date": "2026-02-01",
    "operator": "J. Doe",
    "notes": null,
    "metadata": null,
    "created_at": "2026-02-08T10:00:00.000Z",
    "updated_at": "2026-02-08T10:00:00.000Z"
  }
]
```

---

### Add Screening Record

The `chemical_id` must reference an existing chemical (otherwise `400`).
Keys outside the field list above are silently dropped.

**Endpoint:** `POST /screening`

**Request Body:**

```json
{
  "chemical_id": "CHEM-001",
  "assay_name": "Cytotoxicity",
  "assay_type": "Cell viability",
  "target": "HepG2",
  "result": "Positive",
  "result_value": 10.5,
  "result_unit": "μM",
  "concentration": 50,
  "concentration_unit": "μM",
  "timepoint": "24h",
  "replicate": 1,
  "plate_id": "PLATE-01",
  "well_position": "B4",
  "experiment_date": "2026-02-01",
  "operator": "J. Doe",
  "notes": "Optional free text"
}
```

**Response (201):**

```json
{
  "message": "Screening data added successfully",
  "id": "uuid"
}
```

---

### Upload Screening Records (Excel)

Bulk upload screening records via Excel. Use the shipped
[`screening_template.xlsx`](docs/excel-templates/screening/screening_template.xlsx)
(`.xlsx` only). Column headers are the field names above, accepted in
`snake_case` or `Title_Case` (`chemical_id` / `Chemical_ID`, `assay_name` /
`Assay_Name`, …). Rows whose `chemical_id` does not match an existing chemical
are skipped and reported in `errors`; every raw row is preserved in the
record's `metadata`.

**Endpoint:** `POST /screening/upload/excel`

**Content-Type:** `multipart/form-data` (field: `file`)

**Response:**

```json
{
  "message": "Successfully uploaded 2 screening records",
  "inserted": 2
}
```

> The `errors` key (a list of `{row, error}` objects) appears only when rows failed.

**cURL Example:**

```bash
curl -X POST http://localhost:49160/api/screening/upload/excel \
  -F "file=@screening_template.xlsx"
```

---

### Get / Update / Delete a Screening Record

Records are addressed by their `id` (UUID, returned on create).

| Method & Endpoint | Description |
|-------------------|-------------|
| `GET /screening/:id` | One record, enriched with `chemical_name` |
| `PUT /screening/:id` | Merge arbitrary JSON fields into the record |
| `DELETE /screening/:id` | Delete the record |

---

## Toxicology

Toxicology records are always linked to an existing chemical (`chemical_id`).
Record fields: `chemical_id`, `study_type`, `species`, `strain`, `sex`,
`route_of_administration`, `duration`, `duration_unit`, `dose`, `dose_unit`,
`endpoint`, `endpoint_value`, `endpoint_unit`, `noael`, `loael`, `ld50`,
`study_reference`, `study_date`, `source`, `notes`, plus a free-form
`metadata` object — the same columns as the shipped
[`toxicology_template.xlsx`](docs/excel-templates/toxicology/toxicology_template.xlsx).

### List Toxicology Records

Get paginated list of toxicology data. Each record in the list is enriched
with `chemical_name`.

**Endpoint:** `GET /toxicology`

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `page` | integer | Page number |
| `limit` | integer | Items per page |
| `search` | string | Search in study type, chemical ID, endpoint, or species |
| `chemical_id` | string | Filter by chemical ID |

---

### Get Toxicology by Chemical

Raw records for one chemical (no `chemical_name` enrichment).

**Endpoint:** `GET /toxicology/chemical/:chemical_id`

**Response:**

```json
[
  {
    "id": "uuid",
    "chemical_id": "CHEM-001",
    "study_type": "Acute Toxicity",
    "species": "Rat",
    "strain": "Wistar",
    "sex": "M",
    "route_of_administration": "Oral",
    "duration": 14,
    "duration_unit": "days",
    "dose": 200,
    "dose_unit": "mg/kg",
    "endpoint": "Mortality",
    "endpoint_value": 192,
    "endpoint_unit": "mg/kg",
    "noael": 50,
    "loael": 100,
    "ld50": 192,
    "study_reference": "OECD TG 423",
    "study_date": "2025-11-15",
    "source": "Internal study",
    "notes": null,
    "metadata": null,
    "created_at": "2026-02-08T10:00:00.000Z",
    "updated_at": "2026-02-08T10:00:00.000Z"
  }
]
```

---

### Add Toxicology Record

The `chemical_id` must reference an existing chemical (otherwise `400`).
Keys outside the field list above (e.g. `route`, `unit`) are silently dropped.

**Endpoint:** `POST /toxicology`

**Request Body:**

```json
{
  "chemical_id": "CHEM-001",
  "study_type": "Acute Toxicity",
  "species": "Rat",
  "strain": "Wistar",
  "sex": "M",
  "route_of_administration": "Oral",
  "dose": 200,
  "dose_unit": "mg/kg",
  "endpoint": "Mortality",
  "endpoint_value": 192,
  "endpoint_unit": "mg/kg",
  "ld50": 192,
  "study_reference": "OECD TG 423",
  "study_date": "2025-11-15",
  "source": "Internal study"
}
```

**Response (201):**

```json
{
  "message": "Toxicology data added successfully",
  "id": "uuid"
}
```

---

### Upload Toxicology Records (Excel)

Bulk upload toxicology records via Excel. Use the shipped
[`toxicology_template.xlsx`](docs/excel-templates/toxicology/toxicology_template.xlsx)
(`.xlsx` only). Column headers are the field names above, accepted in
`snake_case` or `Title_Case` (`Chemical_ID`, `Study_Type`, `NOAEL`, `LD50`, …).
Rows whose `chemical_id` does not match an existing chemical are skipped and
reported in `errors`; every raw row is preserved in the record's `metadata`.

**Endpoint:** `POST /toxicology/upload/excel`

**Content-Type:** `multipart/form-data` (field: `file`)

**Response:**

```json
{
  "message": "Successfully uploaded 2 toxicology records",
  "inserted": 2
}
```

> The `errors` key (a list of `{row, error}` objects) appears only when rows failed.

**cURL Example:**

```bash
curl -X POST http://localhost:49160/api/toxicology/upload/excel \
  -F "file=@toxicology_template.xlsx"
```

---

### Get / Update / Delete a Toxicology Record

Records are addressed by their `id` (UUID, returned on create).

| Method & Endpoint | Description |
|-------------------|-------------|
| `GET /toxicology/:id` | One record, enriched with `chemical_name` |
| `PUT /toxicology/:id` | Merge arbitrary JSON fields into the record |
| `DELETE /toxicology/:id` | Delete the record |

---

## Error Codes

| HTTP Code | Description |
|-----------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request (validation error) |
| 404 | Not Found |
| 500 | Internal Server Error |

**Example Error Response:**

```json
{
  "error": "Chemical ID already exists"
}
```

---

## Integration Examples

### JavaScript (Axios)

```javascript
import axios from 'axios';

const API_BASE = 'http://localhost:49160/api';

// Get all chemicals
const getChemicals = async () => {
  const response = await axios.get(`${API_BASE}/chemicals`);
  console.log(response.data);
};

// Add a chemical
const addChemical = async () => {
  const chemical = {
    chemical_id: 'CHEM-001',
    name: 'Caffeine',
    cas_number: '58-08-2'
  };
  
  const response = await axios.post(`${API_BASE}/chemicals`, chemical);
  console.log(response.data);
};

// Upload Excel file
const uploadExcel = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await axios.post(
    `${API_BASE}/chemicals/upload/excel`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  console.log(response.data);
};

// Bulk delete
const bulkDelete = async (ids) => {
  const response = await axios.post(`${API_BASE}/chemicals/bulk/delete`, {
    chemical_ids: ids
  });
  console.log(response.data);
};
```

---

### Python (Requests) — step-by-step guide

A complete walkthrough for scripting the chemicals API from Python. Every
step shows the code, the real response, and what to check.

#### Step 0 — One-time setup

```bash
pip install requests
```

```python
import requests

# All endpoints live under this base URL.
API_BASE = 'http://localhost:49160/api'
# On the VM use: 'http://<vm-hostname>:49160/api'
```

#### Step 1 — CREATE a chemical (POST)

You send a JSON body with at least `chemical_id` and `name`. Use the `json=`
argument — requests converts your dict to JSON and sets the header for you.

```python
new_chemical = {
    'chemical_id': 'CHEM-001',
    'name': 'Caffeine',
    'cas_number': '58-08-2',
    'molecular_formula': 'C8H10N4O2',
    'molecular_weight': 194.19,
}
response = requests.post(f'{API_BASE}/chemicals', json=new_chemical)

print(response.status_code)   # 201  (201 = "Created")
print(response.json())        # {'message': 'Chemical added successfully', 'chemical_id': 'CHEM-001'}
```

If a chemical with that `chemical_id` already exists you get:

```python
print(response.status_code)   # 400
print(response.json())        # {'error': 'Chemical ID already exists'}
```

#### Step 2 — READ chemicals (GET)

**One record** — put the chemical_id in the URL path:

```python
response = requests.get(f'{API_BASE}/chemicals/CHEM-001')
chemical = response.json()

print(response.status_code)          # 200
print(chemical['name'])              # Caffeine
print(chemical['molecular_weight'])  # 194.19
```

An unknown id returns `404` with `{'error': 'Chemical not found'}`.

**A list (paginated, searchable)** — filters go in `params=` (they become
`?page=1&limit=10&search=caffeine` in the URL):

```python
response = requests.get(f'{API_BASE}/chemicals',
                        params={'page': 1, 'limit': 10, 'search': 'caffeine'})
body = response.json()

print(body['pagination'])   # {'page': 1, 'limit': 10, 'total': 1, 'totalPages': 1}
for chem in body['data']:   # the actual records are in body['data']
    print(chem['chemical_id'], chem['name'])
```

#### Step 3 — UPDATE a chemical (PUT)

Send **only the fields you want to change** — PUT merges them into the
record, everything else is preserved:

```python
response = requests.put(f'{API_BASE}/chemicals/CHEM-001',
                        json={'supplier': 'Sigma-Aldrich'})

print(response.status_code)   # 200
print(response.json())        # {'message': 'Chemical updated successfully'}

# Verify: supplier changed, name untouched
chemical = requests.get(f'{API_BASE}/chemicals/CHEM-001').json()
print(chemical['supplier'])   # Sigma-Aldrich
print(chemical['name'])       # Caffeine   (still there)
```

#### Step 4 — DELETE a chemical

```python
response = requests.delete(f'{API_BASE}/chemicals/CHEM-001')
print(response.status_code)   # 200
print(response.json())        # {'message': 'Chemical deleted successfully'}

# It is really gone:
response = requests.get(f'{API_BASE}/chemicals/CHEM-001')
print(response.status_code)   # 404
print(response.json())        # {'error': 'Chemical not found'}
```

#### Step 5 — Handle errors properly (recommended for real scripts)

Every failure returns `{'error': 'message'}` with a 4xx/5xx status, so one
helper covers all verbs:

```python
def api_call(method: str, path: str, **kwargs):
    """Call the API; return parsed JSON or raise with the server's message."""
    response = requests.request(method, f'{API_BASE}{path}', timeout=30, **kwargs)
    payload = response.json()
    if not response.ok:                # True for status codes >= 400
        raise RuntimeError(f'{method} {path} -> {response.status_code}: {payload.get("error")}')
    return payload

# Usage:
api_call('POST',   '/chemicals', json={'chemical_id': 'CHEM-002', 'name': 'Aspirin'})
api_call('GET',    '/chemicals/CHEM-002')
api_call('PUT',    '/chemicals/CHEM-002', json={'supplier': 'Bayer'})
api_call('DELETE', '/chemicals/CHEM-002')
```

#### Step 6 — Bulk operations and file uploads

```python
# Bulk delete / bulk update take a JSON body with a list of ids
requests.post(f'{API_BASE}/chemicals/bulk/delete',
              json={'chemical_ids': ['CHEM-001', 'CHEM-002']})

requests.post(f'{API_BASE}/chemicals/bulk/update',
              json={'chemical_ids': ['CHEM-003'], 'updates': {'supplier': 'Merck'}})

# File uploads use files= (multipart), NOT json=
with open('chemicals_template.xlsx', 'rb') as f:
    response = requests.post(f'{API_BASE}/chemicals/upload/excel', files={'file': f})
    print(response.json())   # {'message': 'Successfully processed ...', 'inserted': ..., 'updated': ...}
```

> 💡 The same patterns work for `/samples`, `/screening`, and `/toxicology` —
> only the paths and field names differ (see their sections above). You can
> also explore and test every endpoint interactively in a browser at
> `http://localhost:49160/docs` (FastAPI's auto-generated API console).

---

### cURL Scripts

```bash
#!/bin/bash

API_BASE="http://localhost:49160/api"

# Get statistics
curl "$API_BASE/stats"

# Get chemicals with pagination
curl "$API_BASE/chemicals?page=1&limit=10"

# Search chemicals
curl "$API_BASE/chemicals?search=caffeine"

# Add chemical
curl -X POST "$API_BASE/chemicals" \
  -H "Content-Type: application/json" \
  -d '{
    "chemical_id": "CHEM-001",
    "name": "Caffeine",
    "cas_number": "58-08-2"
  }'

# Upload Excel
curl -X POST "$API_BASE/chemicals/upload/excel" \
  -F "file=@chemicals_template.xlsx"

# Bulk operations
curl -X POST "$API_BASE/chemicals/bulk/delete" \
  -H "Content-Type: application/json" \
  -d '{"chemical_ids": ["CHEM-001", "CHEM-002"]}'
```

---

## Interactive API Explorer (OpenAPI)

The backend serves an auto-generated OpenAPI console — no Postman collection is needed:

- **Swagger UI:** `http://localhost:49160/docs` — browse and try every endpoint interactively
- **Raw schema:** `http://localhost:49160/openapi.json` — importable into Postman, Insomnia, etc.

---

## Support

For API support or feature requests:
- Email: `<maintainer-email>`
- GitHub Issues: [Create an issue](https://github.com/nestle-it/nr-nips-crucible/issues) *(requires access to the private `nestle-it` org)*

---

**Last Updated:** August 7, 2026  
**API Version:** 2.0
