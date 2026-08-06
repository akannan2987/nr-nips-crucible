"""Regenerate the synthetic upload templates in this directory.

Run with the backend virtualenv (it has openpyxl + rdkit):

    backend/.venv/bin/python docs/excel-templates/generate_templates.py

Every value here is invented example data (public-domain compounds from
PubChem, placeholder IDs/people/projects). Column names are taken from the
actual parsers in backend/app/routers/ and backend/app/utils/ so the
templates really work against the upload endpoints.
"""

import csv
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors

# This script lives at <repo>/docs/excel-templates/generate_templates.py
TPL = Path(__file__).resolve().parent
ROOT = TPL.parent.parent


def strip_meta(wb: Workbook) -> Workbook:
    """Blank out Office document properties (creator, lastModifiedBy, ...)."""
    p = wb.properties
    p.creator = "Crucible"
    p.lastModifiedBy = "Crucible"
    p.title = "Crucible upload template"
    p.subject = None
    p.description = "Synthetic example data — replace with your own."
    p.keywords = None
    p.category = None
    p.company = None
    p.manager = None
    # Fixed timestamp: no authoring machine's clock, and regenerating the
    # templates produces identical files.
    p.created = datetime(2026, 1, 1)
    p.modified = datetime(2026, 1, 1)
    return wb


def write_sheet(path: Path, rows: list[list], sheet_title: str = "data") -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title
    for r in rows:
        ws.append(r)
    strip_meta(wb)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    print(f"  wrote {path.relative_to(ROOT)}  ({len(rows)} rows)")


def write_csv(path: Path, rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    print(f"  wrote {path.relative_to(ROOT)}  ({len(rows)} rows)")


# ── Chemicals ───────────────────────────────────────────────────────────
# Columns from chemicals.upload_excel(): DTX_ID, NESTLE_ID, CAS_NO,
# CHEMICAL_NAME, MOL_WEIGHT_ORIG, MOL_FORMULA, Supplier_ref.
CHEM_HEADER = ["DTX_ID", "NESTLE_ID", "CHEMICAL_NAME", "CAS_NO",
               "MOL_WEIGHT_ORIG", "MOL_FORMULA", "Supplier_ref"]

# name, CAS, MW, formula, SMILES — all public-domain reference compounds.
CHEMICALS = [
    ("CHEM-0001", "INT-0001", "Caffeine", "58-08-2", "194.19", "C8H10N4O2",
     "Example Supplier Cat# 00001", "Cn1cnc2c1c(=O)n(C)c(=O)n2C"),
    ("CHEM-0002", "INT-0002", "Vanillin", "121-33-5", "152.15", "C8H8O3",
     "Example Supplier Cat# 00002", "COc1cc(C=O)ccc1O"),
    ("CHEM-0003", "INT-0003", "Citric acid", "77-92-9", "192.12", "C6H8O7",
     "Example Supplier Cat# 00003", "OC(=O)CC(O)(CC(=O)O)C(=O)O"),
    ("CHEM-0004", "INT-0004", "L-Ascorbic acid", "50-81-7", "176.12", "C6H8O6",
     "Example Supplier Cat# 00004", "OC[C@H](O)[C@H]1OC(=O)C(O)=C1O"),
    ("CHEM-0005", "INT-0005", "Acetylsalicylic acid", "50-78-2", "180.16", "C9H8O4",
     "Example Supplier Cat# 00005", "CC(=O)Oc1ccccc1C(=O)O"),
]

chem_rows = [CHEM_HEADER] + [list(c[:7]) for c in CHEMICALS]
write_csv(TPL / "chemicals" / "chemicals_template.csv", chem_rows)
write_sheet(TPL / "chemicals" / "chemicals_template.xlsx", chem_rows, "chemicals")


# ── Chemicals SDF ───────────────────────────────────────────────────────
# Built with RDKit from the SMILES above; field names match the ones
# backend/app/utils/sdf.py promotes (DTXSID, PREFERRED_NAME, CAS_NO, ...).
sdf_path = TPL / "chemicals" / "chemicals_template.sdf"
sdf_path.parent.mkdir(parents=True, exist_ok=True)
writer = Chem.SDWriter(str(sdf_path))
for chem_id, nestle_id, name, cas, mw, formula, supplier, smiles in CHEMICALS[:3]:
    mol = Chem.MolFromSmiles(smiles)
    assert mol is not None, f"bad SMILES for {name}"
    mol = Chem.AddHs(mol)
    AllChem.Compute2DCoords(mol)
    mol = Chem.RemoveHs(mol)
    mol.SetProp("_Name", name)
    mol.SetProp("DTXSID", chem_id)
    mol.SetProp("PREFERRED_NAME", name)
    mol.SetProp("CAS_NO", cas)
    mol.SetProp("MOL_FORMULA", rdMolDescriptors.CalcMolFormula(mol))
    mol.SetProp("MOL_WEIGHT", f"{Descriptors.MolWt(mol):.2f}")
    mol.SetProp("MONOISOTOPIC_MASS", f"{Descriptors.ExactMolWt(mol):.4f}")
    mol.SetProp("MS_READY_SMILES", Chem.MolToSmiles(mol))
    mol.SetProp("SYNONYMS", f"{name}; Example synonym")
    writer.write(mol)
writer.close()
print(f"  wrote {sdf_path.relative_to(ROOT)}  (3 molecules)")


# ── Samples (SLIMS "Content record" layout) ─────────────────────────────
# The parser needs: row with the machine keys (cntn_*), then a label row
# containing '*' or '(...)', then data. Row 1 is skipped entirely.
SLIMS_KEYS = [
    "cntn_fk_contentType", "<SLIMSGUID>", "cntn_fk_category",
    "cntn_cf_fk_sampleSubtype", "cntn_cf_fk_responsible", "cntn_cf_fk_ownerGroup",
    "cntn_id", "cntn_cf_description", "cntn_cf_fk_project", "cntn_fk_status",
    "cntn_barCode", "cntn_cf_receptionDate", "cntn_cf_externalReferencePerson",
    "cntn_cf_externalReferenceGroup", "cntn_fk_provider", "cntn_cf_gradeTradeName",
    "cntn_cf_doc", "cntn_cf_loc", "cntn_cf_specificationNumber",
    "cntn_cf_ext_barcode", "cntn_cf_nestmsBatch", "cntn_cf_fk_masterSample",
    "cntn_cf_fk_masterSampleBarcode", "cntn_fk_location", "cntn_position_row",
    "cntn_position_column", "derivedCount", "cntn_cf_historicalSmSampleid",
    "cntn_cf_exp_date",
]
SLIMS_LABELS = [
    "Content Type * (cntp_name)", "<SLIMSGUID>", "Category (cntp_name)",
    "Sample Subtype (rdrc_name)", "Responsible (contact person) * (user_userName)",
    "Owner Group * (grps_groupName)", "Id *", "Description",
    "Project (Study) * (cntn_cf_studyProjectComposite)", "Status * (stts_name)",
    "Barcode", "Reception Date", "External reference (person)",
    "External reference (group)", "Provider (prvd_name)", "Grade/Trade name",
    "DOC", "LOC", "Specification Number", "External Barcode", "Batch",
    "Master sample Id (cntn_id)", "Master sample Barcode (cntn_barCode)",
    "Location (cntn_id)", "Located at row", "Located at column", "Derived Count",
    "Historical SampleID", "Expiry date",
]
assert len(SLIMS_KEYS) == len(SLIMS_LABELS) == 29


def slims_row(**vals) -> list:
    row = [""] * len(SLIMS_KEYS)
    for key, val in vals.items():
        row[SLIMS_KEYS.index(key)] = val
    return row


banner = ("Example template for updating Content records — row 2 holds the "
          "field keys, row 3 the human labels, data starts on row 4.")
sample_rows = [
    ["", "", "", "", banner],
    SLIMS_KEYS,
    SLIMS_LABELS,
    slims_row(
        cntn_fk_contentType="Pack - Material",
        **{"<SLIMSGUID>": "00000000-0000-0000-0000-000000000001"},
        cntn_fk_category="Packaging",
        cntn_cf_fk_sampleSubtype="Polymer",
        cntn_cf_fk_responsible="ExampleUser",
        cntn_cf_fk_ownerGroup="Example Research Group",
        cntn_id="Example laminate film 12 um",
        cntn_cf_description="Example description - replace with your own data",
        cntn_cf_fk_project="PRJ-000001 Example study (example)",
        cntn_fk_status="Available",
        cntn_barCode="SMPL00001",
        cntn_cf_receptionDate="01/05/2024",
        cntn_cf_gradeTradeName="Example grade",
        cntn_cf_doc="False",
        cntn_cf_loc="False",
        cntn_fk_location="A01",
        derivedCount="0",
        cntn_cf_exp_date="31/12/2026",
    ),
    slims_row(
        cntn_fk_contentType="Raw material",
        **{"<SLIMSGUID>": "00000000-0000-0000-0000-000000000002"},
        cntn_fk_category="Ingredient",
        cntn_cf_fk_sampleSubtype="Powder",
        cntn_cf_fk_responsible="ExampleUser",
        cntn_cf_fk_ownerGroup="Example Research Group",
        cntn_id="Example ingredient powder",
        cntn_cf_description="Second example row",
        cntn_cf_fk_project="PRJ-000002 Example study (example)",
        cntn_fk_status="Available",
        cntn_barCode="SMPL00002",
        cntn_cf_receptionDate="15/06/2024",
        cntn_cf_doc="False",
        cntn_cf_loc="False",
        cntn_fk_location="A02",
        derivedCount="0",
        cntn_cf_exp_date="30/06/2027",
    ),
]
write_sheet(TPL / "samples" / "Upload_Sample_Template.xlsx", sample_rows, "data")


# ── Screening (Excel only — the endpoint uses openpyxl, not CSV) ────────
SCREEN_HEADER = ["chemical_id", "assay_name", "assay_type", "target", "result",
                 "result_value", "result_unit", "concentration", "concentration_unit",
                 "timepoint", "replicate", "plate_id", "well_position",
                 "experiment_date", "operator", "notes"]
screen_rows = [
    SCREEN_HEADER,
    ["CHEM-0001", "Cell viability (MTT)", "Cytotoxicity", "HepG2", "Negative",
     "98.4", "%", "10", "uM", "24h", "1", "PLATE-001", "A01",
     "2026-01-15", "ExampleUser", "Example row - replace with your own data"],
    ["CHEM-0002", "Cell viability (MTT)", "Cytotoxicity", "HepG2", "Negative",
     "95.1", "%", "10", "uM", "24h", "1", "PLATE-001", "A02",
     "2026-01-15", "ExampleUser", ""],
    ["CHEM-0003", "Receptor binding", "Binding", "Example receptor", "Positive",
     "12.7", "uM", "50", "uM", "1h", "2", "PLATE-002", "B01",
     "2026-01-16", "ExampleUser", "IC50 reported in result_value"],
]
write_sheet(TPL / "screening" / "screening_template.xlsx", screen_rows, "screening")


# ── Toxicology (Excel only) ─────────────────────────────────────────────
TOX_HEADER = ["chemical_id", "study_type", "species", "strain", "sex",
              "route_of_administration", "duration", "duration_unit", "dose",
              "dose_unit", "endpoint", "endpoint_value", "endpoint_unit",
              "noael", "loael", "ld50", "study_reference", "study_date",
              "source", "notes"]
tox_rows = [
    TOX_HEADER,
    ["CHEM-0001", "Acute oral toxicity", "Rat", "Example strain", "M/F", "Oral",
     "14", "days", "200", "mg/kg bw/day", "Mortality", "0", "%",
     "100", "200", "192", "EXAMPLE-REF-001", "2026-01-10",
     "Public literature", "Example row - replace with your own data"],
    ["CHEM-0002", "Repeated dose 90-day", "Rat", "Example strain", "M/F", "Oral",
     "90", "days", "50", "mg/kg bw/day", "Body weight change", "-3.2", "%",
     "50", "150", "", "EXAMPLE-REF-002", "2026-01-12", "Public literature", ""],
    ["CHEM-0003", "Genotoxicity (Ames)", "Bacteria", "TA98", "n/a", "In vitro",
     "48", "hours", "5000", "ug/plate", "Revertant colonies", "Negative", "",
     "", "", "", "EXAMPLE-REF-003", "2026-01-14", "Public literature", ""],
]
write_sheet(TPL / "toxicology" / "toxicology_template.xlsx", tox_rows, "toxicology")

print("\nAll templates generated.")
