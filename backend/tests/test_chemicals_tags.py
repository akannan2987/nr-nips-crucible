"""CR-11 — counts, batch filters and source tags.

* every import records the route it came through under `formats`; the tags
  are derived from that when an entry is read, never stored;
* the owner's rules: every Excel file earns *Excel upload*, the Dotmatics
  export included, with or without a Dotmatics ID (T1); CSV is not Excel
  (T4); several tags ticked means ALL of them unless `any` is asked (T2);
* `GET /api/chemicals/summary` counts compounds, batches and tags;
  `batches=` and `tags=`/`tags_match=` filter the list; rows carry `tags`;
  the columns endpoint offers `tags`;
* entries loaded before `formats` existed are labelled from the source they
  name, or from what they hold;
* the terminal script prints the same counts.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

from openpyxl import Workbook
from rdkit import Chem

from app.database import SessionLocal
from app.models import Chemical
from app.store import insert_doc

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import registry_summary  # noqa: E402

DM_HEADER = ["FORMATTED_BATCH_ID", "REG_ID", "BATCH_ID", "BATCH_NUMBER", "CAS_NO", "CHEMICAL_NAME", "DTXSID", "MOL_FORMULA", "GC_RI_METHOD"]


def _xlsx(header, rows, sheet="browser export") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(header)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _dm(reg, batch, name, cas, dtx, formula="C8H10N4O2"):
    return [f"REG-{reg}-{batch}", reg, 900000 + batch, batch, cas, name, dtx, formula, "1810"]


def _sdf(dtx: str, name: str, smiles: str) -> bytes:
    buf = io.StringIO()
    writer = Chem.SDWriter(buf)
    writer.SetForceV3000(True)
    mol = Chem.MolFromSmiles(smiles)
    mol.SetProp("_Name", "")
    for k, v in {"DTXSID": dtx, "PREFERRED_NAME": name, "CAS Number": "58-08-2", "Chemical name": name,
                 "Synonyms / Composition": "x", "MOLECULAR_FORMULA": "C8H10N4O2", "MONOISOTOPIC_MASS": "194.08",
                 "Exact Molecular Weight": "194.19", "INCHI_STRING": "InChI=1S/x", "SMILES": smiles,
                 "MS_READY_SMILES": smiles, "FOUND_BY": "test", "Present in INK": "Yes"}.items():
        mol.SetProp(k, v)
    writer.write(mol)
    writer.close()
    return buf.getvalue().encode()


def _upload(client, name: str, payload: bytes, path: str):
    return client.post(path, files={"file": (name, io.BytesIO(payload), "application/octet-stream")})


def _tags(client, needle: str) -> list[str]:
    return client.get(f"/api/chemicals?search={needle}").json()["data"][0]["tags"]


def _seed_everything(client):
    """One entry per route, plus the export's compound with two batches, completed by the SDF."""
    rows = [_dm(100001, 1, "Caffeine", "58-08-2", "DTXSID0020232"), _dm(100001, 2, "Caffeine", "58-08-2", "DTXSID0020232"),
            _dm(100002, 1, "Vanillin", "121-33-5", "DTXSID0021976", formula="C8H8O3")]
    assert _upload(client, "Export_Chemicals.xlsx", _xlsx(DM_HEADER, rows), "/api/chemicals/upload/excel").json()["compounds"] == 2
    assert _upload(client, "Upload_Chemicals.sdf", _sdf("DTXSID0020232", "Caffeine", "Cn1cnc2c1c(=O)n(C)c(=O)n2C"), "/api/chemicals/upload/sdf").json()["updated"] == 1
    custom = _xlsx(["CHEMICAL_NAME", "CAS_NO", "MOL_FORMULA"], [["Custom xlsx compound", "100-00-1", "C6H5NO2"]], "Sheet1")
    assert _upload(client, "my_list.xlsx", custom, "/api/chemicals/upload/excel").json()["inserted"] == 1
    assert _upload(client, "my_list.csv", b"CHEMICAL_NAME,CAS_NO\nCustom csv compound,100-00-2\n", "/api/chemicals/upload/excel").json()["inserted"] == 1
    assert _upload(client, "my_list.json", b'[{"name": "JSON compound", "cas_number": "100-00-3"}]', "/api/chemicals/upload/json").json()["inserted"] == 1
    assert client.post("/api/chemicals", json={"chemical_id": "CHEM-TEST-M", "name": "Typed in compound"}).status_code == 201


def test_every_route_earns_its_tag_and_every_excel_file_counts(client):
    _seed_everything(client)
    assert _tags(client, "Caffeine") == ["Dotmatics ID", "Excel upload", "SDF upload"]   # export, then the structure file
    assert _tags(client, "Vanillin") == ["Dotmatics ID", "Excel upload"]                  # T1: the export IS an Excel upload
    assert _tags(client, "Custom xlsx") == ["Excel upload"]                               # …and so is a custom file without an ID
    assert _tags(client, "Custom csv") == ["CSV upload"]                                  # T4: CSV is not Excel
    assert _tags(client, "JSON compound") == ["JSON upload"]
    assert _tags(client, "Typed in") == ["Manual"]                                     # inferred: no file has touched it
    typed = client.get("/api/chemicals/CHEM-TEST-M").json()
    assert "formats" not in typed                                                           # the v1 key set is untouched
    # the route is recorded on the entry, the tag is not
    caff = client.get("/api/chemicals?search=Caffeine").json()["data"][0]
    stored = client.get(f"/api/chemicals/{caff['chemical_id']}").json()
    assert stored["formats"] == ["excel", "sdf"] and "tags" not in stored


def test_summary_counts_compounds_batches_and_tags(client):
    _seed_everything(client)
    s = client.get("/api/chemicals/summary").json()
    assert (s["total"], s["one_batch"], s["several_batches"], s["batch_rows"]) == (6, 5, 1, 7)
    assert s["tags"] == {"Dotmatics ID": 2, "Excel upload": 3, "SDF upload": 1, "CSV upload": 1, "JSON upload": 1, "Manual": 1}


def test_list_filters_by_batches_and_by_tags_all_or_any(client):
    _seed_everything(client)
    names = lambda q: sorted(r["name"] for r in client.get(f"/api/chemicals?limit=50&{q}").json()["data"])  # noqa: E731
    assert names("batches=several") == ["Caffeine"]
    assert len(names("batches=one")) == 5
    assert names("view=batches&batches=several") == ["Caffeine", "Caffeine"]               # the batch rows of those compounds
    assert names("tags=Excel upload,SDF upload") == ["Caffeine"]                              # T2: all of them
    assert names("tags=Excel upload,SDF upload&tags_match=all") == ["Caffeine"]
    assert names("tags=Excel upload,SDF upload&tags_match=any") == ["Caffeine", "Custom xlsx compound", "Vanillin"]
    assert names("tags=SDF upload,Manual") == []                                              # nothing came both ways
    assert names("tags=SDF upload,Manual&tags_match=any") == ["Caffeine", "Typed in compound"]
    assert names("tags=Excel upload,Dotmatics ID") == ["Caffeine", "Vanillin"]                # the owner's example
    assert client.get("/api/chemicals?tags_match=sometimes").status_code == 400
    assert client.get("/api/chemicals?batches=few").status_code == 400
    assert len(client.get("/api/chemicals?limit=50").json()["data"]) == 6                    # without the parameters: everything
    cols = [c["key"] for c in client.get("/api/chemicals/columns").json()["columns"]]
    assert cols[1] == "tags"                                                                   # offered as a column, after the identifier


def test_entries_loaded_before_formats_existed_are_still_labelled(client):
    with SessionLocal() as db:
        insert_doc(db, Chemical, {"id": "l-1", "chemical_id": "CHEM-000001", "name": "Old export entry", "dotmatics_reg_id": "1",
                                  "source_template": "dotmatics_export", "merged_from": ["registry_sdf", "limited_list"]})
        insert_doc(db, Chemical, {"id": "l-2", "chemical_id": "CHEM-000002", "name": "Old generic sdf entry", "mol_block": "V3000…"})
        insert_doc(db, Chemical, {"id": "l-3", "chemical_id": "CHEM-000003", "name": "Old generic sheet entry", "metadata": {"X": 1}})
        insert_doc(db, Chemical, {"id": "l-4", "chemical_id": "CHEM-000004", "name": "Old bare entry"})
    assert _tags(client, "Old export") == ["Dotmatics ID", "Excel upload", "SDF upload"]
    assert _tags(client, "Old generic sdf") == ["SDF upload"]
    assert _tags(client, "Old generic sheet") == ["Excel upload"]
    assert _tags(client, "Old bare") == ["Manual"]


def test_the_terminal_script_prints_the_same_counts(client, capsys):
    _seed_everything(client)
    assert registry_summary.main([]) == 0
    out = capsys.readouterr().out
    assert "6 compounds: 5 with one batch, 1 with several; 7 batch rows." in out
    assert "      3  Excel upload" in out
    assert registry_summary.main(["--tag", "Excel upload", "--tag", "SDF upload"]) == 0
    out = capsys.readouterr().out
    assert "1 entry with Excel upload and SDF upload:" in out and "Caffeine" in out
    assert registry_summary.main(["--batches", "several", "--json"]) == 0
    assert '"several_batches": 1' in capsys.readouterr().out
