"""CR-9 — the three real registry sources, recognised as template specs.

Every file here is synthetic, built in the test from the laboratory's column
and property NAMES with invented values. What is proved:

* a Dotmatics export is recognised by its headers; rows sharing REG_ID are
  one compound with a `batches` list; a column that differs between batches
  outside the batch-level set is flagged; the identifiers are promoted and
  every column kept under metadata; a second import updates, never duplicates;
* the registry SDF (V3000) is recognised by its properties, its structure is
  read by RDKit, and it MERGES with the Dotmatics entry on DTXSID;
* the limited list registers entries whose identifier is still to come from
  the screening data, and the notices endpoint counts them;
* two registrations sharing one CAS are both kept and both flagged, and the
  generic spreadsheet path is untouched.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

from openpyxl import Workbook
from rdkit import Chem

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import import_file  # noqa: E402

from app.database import SessionLocal  # noqa: E402

DM_HEADER = ["FORMATTED_BATCH_ID", "REG_ID", "BATCH_ID", "BATCH_NUMBER", "CAS_NO", "SMILES_ORIGINAL", "CHEMICAL_NAME",
             "OTHER_NAMES", "MOL_FORMULA", "NESTLE_ID", "DTXSID", "SYNONYMS", "MOL_WEIGHT_ORIG", "PUBCHEM_ID", "INCHI",
             "GC_RI_METHOD", "PRESENT_INK", "EFSA_OPINIONS"]


def _xlsx(header: list[str], rows: list[list], sheet: str = "browser export") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(header)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _dm(reg, batch, name, cas, dtx, pubchem="2519", gc_ri="1810", formula="C8H10N4O2"):
    return [f"REG-{reg}-{batch}", reg, 900000 + batch, batch, cas, "Cn1cnc2c1c(=O)n(C)c(=O)n2C", name,
            "Other A; Other B", formula, "", dtx, "Syn one; Syn two, with comma", 194.19, pubchem,
            "InChI=1S/example", gc_ri, "Yes", "Opinion 1"]


def _upload(client, name: str, payload: bytes, path: str = "/api/chemicals/upload/excel"):
    return client.post(path, files={"file": (name, io.BytesIO(payload), "application/octet-stream")})


def _v3000_sdf(records: list[dict[str, str]]) -> bytes:
    buf = io.StringIO()
    writer = Chem.SDWriter(buf)
    writer.SetForceV3000(True)
    for props in records:
        mol = Chem.MolFromSmiles(props.pop("_smiles"))
        mol.SetProp("_Name", "")
        for k, v in props.items():
            mol.SetProp(k, v)
        writer.write(mol)
    writer.close()
    return buf.getvalue().encode()


SDF_PROPS = {"DTXSID": "DTXSID0020232", "PREFERRED_NAME": "Caffeine", "CAS Number": "58-08-2", "Chemical name": "Caffeine",
             "Synonyms / Composition": "Guaranine; Theine", "MOLECULAR_FORMULA": "C8H10N4O2", "MONOISOTOPIC_MASS": "194.080376",
             "Exact Molecular Weight": "194.19", "INCHI_STRING": "InChI=1S/C8H10N4O2/example", "SMILES": "Cn1cnc2c1c(=O)n(C)c(=O)n2C",
             "MS_READY_SMILES": "Cn1cnc2c1c(=O)n(C)c(=O)n2C", "FOUND_BY": "test", "Present in INK": "Yes"}


def test_dotmatics_export_groups_batches_and_promotes(client):
    rows = [
        _dm(100001, 1, "Caffeine", "58-08-2", "DTXSID0020232", gc_ri="1810"),
        _dm(100001, 2, "Caffeine", "58-08-2", "DTXSID0020232", gc_ri="1815"),           # same compound, second batch
        _dm(100002, 1, "Vanillin", "121-33-5", "DTXSID0021976", pubchem="1183", formula="C8H8O3"),
        _dm(100003, 1, "Vanillin batch conflict", "121-33-5", "DTXSID0000001", formula="C8H8O3"),
        _dm(100003, 2, "Vanillin batch conflict", "121-33-5", "DTXSID0000001", formula="C8H8O4"),  # formula differs → conflict
    ]
    res = _upload(client, "Export_Chemicals.xlsx", _xlsx(DM_HEADER, rows))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["template"] == "dotmatics_export"
    assert (body["rows"], body["compounds"], body["inserted"], body["updated"]) == (5, 3, 3, 0)
    assert body["batch_conflicts"] == 1
    assert body["cas_shared"] == 2  # 121-33-5 held by two registrations, both flagged, both kept
    assert client.get("/api/stats").json()["chemicals"]["total"] == 3

    listing = client.get("/api/chemicals?search=Caffeine").json()["data"]
    caff = listing[0]
    assert caff["chemical_id"].startswith("CHEM-")            # sequential identifier, not the REG_ID
    assert caff["dotmatics_reg_id"] == "100001" and caff["dtx_id"] == "DTXSID0020232"
    assert caff["pubchem_cid"] == 2519 and caff["cas_number"] == "58-08-2"
    assert caff["synonyms"] == ["Syn one", "Syn two, with comma"]   # semicolon splits, the comma does not
    assert caff["other_names"] == ["Other A", "Other B"]
    assert [b["BATCH_NUMBER"] for b in caff["batches"]] == ["1", "2"]   # spreadsheet cells arrive as text
    assert [b["GC_RI_METHOD"] for b in caff["batches"]] == ["1810", "1815"]
    assert "batch_conflicts" not in caff
    assert caff["metadata"]["EFSA_OPINIONS"] == "Opinion 1"   # every column kept
    assert caff["source_template"] == "dotmatics_export"

    conflict = client.get("/api/chemicals?search=conflict").json()["data"][0]
    assert conflict["batch_conflicts"] == ["MOL_FORMULA"]
    assert [b["MOL_FORMULA"] for b in conflict["batches"]] == ["C8H8O3", "C8H8O4"]  # both values kept, per batch
    assert conflict["molecular_formula"] == "C8H8O3"                                   # the first batch's is promoted
    vanillin = client.get("/api/chemicals?search=Vanillin").json()["data"]
    assert all(sorted(v["cas_shared_with"]) for v in vanillin)

    # the same file again: three updates, no duplicates
    res = _upload(client, "Export_Chemicals.xlsx", _xlsx(DM_HEADER, rows))
    assert (res.json()["inserted"], res.json()["updated"]) == (0, 3)
    assert client.get("/api/stats").json()["chemicals"]["total"] == 3


def test_registry_sdf_is_read_by_rdkit_and_merges_on_dtxsid(client):
    _upload(client, "Export_Chemicals.xlsx", _xlsx(DM_HEADER, [_dm(100001, 1, "Caffeine", "58-08-2", "DTXSID0020232")]))
    before = client.get("/api/chemicals?search=Caffeine").json()["data"][0]

    res = _upload(client, "Upload_Chemicals.sdf", _v3000_sdf([{**SDF_PROPS, "_smiles": "Cn1cnc2c1c(=O)n(C)c(=O)n2C"}]), "/api/chemicals/upload/sdf")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["template"] == "registry_sdf" and body["totalRecords"] == 1
    assert (body["inserted"], body["updated"]) == (0, 1)       # merged, not duplicated
    assert client.get("/api/stats").json()["chemicals"]["total"] == 1

    after = client.get(f"/api/chemicals/{before['chemical_id']}").json()
    assert after["dotmatics_reg_id"] == "100001"               # the export's identifiers survive
    assert after["mol_block"] and "V3000" in after["mol_block"]
    assert after["structural"]["atom_count"] > 0                # RDKit read the V3000 block
    assert after["merged_from"] == ["registry_sdf"]
    assert after["source_template"] == "dotmatics_export"   # the first source stays the source
    assert after["metadata"]["EFSA_OPINIONS"] == "Opinion 1"    # both sources' columns side by side
    assert after["metadata"]["Present in INK"] == "Yes"
    assert after["synonyms"] == ["Guaranine", "Theine"]         # the SDF's value, the later source


def test_limited_list_registers_with_a_pending_identifier(client):
    header = ["Supplier_ref", "CAS_NO", "CHEMICAL_NAME", "MOL_WEIGHT_ORIG", "MOL_FORMULA", "NESTLE_ID"]
    rows = [[10001, "58-08-2", "Caffeine", "194.19", "C8H10N4O2", "Coming from screening"],
            [10002, None, "House material X", "0", None, "Coming from screening"],
            [10003, "121-33-5", "Vanillin", "152.15", "C8H8O3", "NID-0007"]]
    res = _upload(client, "Upload_Chemicals_limited.xlsx", _xlsx(header, rows, "default_1"))
    body = res.json()
    assert body["template"] == "limited_list" and body["inserted"] == 3
    assert body["pending_identifiers"] == 2
    assert client.get("/api/chemicals/notices/summary").json() == {"nestle_id_pending": 2, "cas_shared": 0, "batch_conflicts": 0}
    caff = client.get("/api/chemicals?search=Caffeine").json()["data"][0]
    assert caff["nestle_id_pending"] == "screening" and "nestle_id" not in caff
    assert caff["supplier"] == "10001"
    van = client.get("/api/chemicals?search=Vanillin").json()["data"][0]
    assert van["nestle_id"] == "NID-0007" and "nestle_id_pending" not in van
    house = client.get("/api/chemicals?search=House").json()["data"][0]
    assert "cas_number" not in house                            # no CAS is a valid entry


def test_generic_spreadsheet_is_untouched_by_the_specs(client):
    header = ["CHEMICAL_NAME", "CAS_NO", "MOL_FORMULA"]
    res = _upload(client, "plain.xlsx", _xlsx(header, [["Water", "7732-18-5", "H2O"]], "Sheet1"))
    assert res.json() == {"message": "Successfully processed 1 chemicals (1 new, 0 updated)", "inserted": 1, "updated": 0, "total": 1}
    assert "template" not in res.json()


def test_terminal_import_uses_the_same_specs(client, tmp_path):
    path = tmp_path / "Export_Chemicals_dotmatics.xlsx"
    path.write_bytes(_xlsx(DM_HEADER, [_dm(100001, 1, "Caffeine", "58-08-2", "DTXSID0020232")]))
    with SessionLocal() as db:
        assert import_file.run(["chemicals", str(path), "--json"], db=db) == 0
    assert client.get("/api/chemicals?search=Caffeine").json()["data"][0]["source_template"] == "dotmatics_export"


def test_pending_identifier_is_dropped_when_another_source_knows_it(client):
    """The limited list says 'coming from screening'; the export already has the identifier → no pending flag."""
    rows = [_dm(100002, 1, "Vanillin", "121-33-5", "DTXSID0021976", pubchem="1183", formula="C8H8O3")]
    rows[0][9] = "NID-0002"  # NESTLE_ID column of the Dotmatics row
    _upload(client, "Export_Chemicals.xlsx", _xlsx(DM_HEADER, rows))
    header = ["Supplier_ref", "CAS_NO", "CHEMICAL_NAME", "MOL_WEIGHT_ORIG", "MOL_FORMULA", "NESTLE_ID"]
    res = _upload(client, "Upload_Chemicals_limited.xlsx", _xlsx(header, [[10002, "121-33-5", "Vanillin", "152.15", "C8H8O3", "Coming from screening"]], "default_1"))
    assert (res.json()["inserted"], res.json()["updated"], res.json()["pending_identifiers"]) == (0, 1, 0)
    van = client.get("/api/chemicals?search=Vanillin").json()["data"][0]
    assert van["nestle_id"] == "NID-0002" and "nestle_id_pending" not in van
    assert van["supplier"] == "10002"  # the list still contributed what it knew
    assert client.get("/api/chemicals/notices/summary").json()["nestle_id_pending"] == 0
