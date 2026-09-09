"""CR-3 — every way into the registry goes through one door (app/imports.py).

JSON joins CSV, TSV, XLSX and SDF; the upload page, the API and the terminal
script share the parsers, so a file behaves identically by every route; an
export can be reviewed and loaded back without loss; a record without a CAS
number is a valid entry.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from app.database import SessionLocal

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import export_chemicals  # noqa: E402
import import_file  # noqa: E402

RECORDS = [
    {"chemical_id": "CHEM-J-001", "name": "Caffeine", "cas_number": "58-08-2", "molecular_formula": "C8H10N4O2", "pubchem_cid": 2519},
    {"chemical_id": "CHEM-J-002", "name": "House material X", "cas_number": None, "supplier": "internal"},
    {"name": "No identifier given", "cas_number": "50-78-2"},
]


def _upload(client, name: str, payload: bytes, path: str = "/api/chemicals/upload/json"):
    return client.post(path, files={"file": (name, io.BytesIO(payload), "application/octet-stream")})


def test_json_file_upload_upserts_and_keeps_unknown_keys(client):
    res = _upload(client, "reg.json", json.dumps(RECORDS).encode())
    assert res.status_code == 200
    assert res.json() == {"message": "Successfully processed 3 chemicals (3 new, 0 updated)", "inserted": 3, "updated": 0, "total": 3}
    caffeine = client.get("/api/chemicals/CHEM-J-001").json()
    assert caffeine["pubchem_cid"] == 2519  # unknown keys kept: the document is the record
    assert caffeine["created_at"] and caffeine["id"]
    no_cas = client.get("/api/chemicals/CHEM-J-002").json()
    assert no_cas["cas_number"] is None  # a compound without a CAS is valid
    listing = client.get("/api/chemicals?limit=10").json()["data"]
    generated = [c for c in listing if c["name"] == "No identifier given"]
    assert generated and generated[0]["chemical_id"].startswith("CHEM-")

    # a second upload of the same file updates, never duplicates
    res = _upload(client, "reg.json", json.dumps(RECORDS[:2]).encode())
    assert res.json()["updated"] == 2 and res.json()["inserted"] == 0
    assert client.get("/api/stats").json()["chemicals"]["total"] == 3


def test_json_object_wrapper_and_body_endpoint(client):
    res = _upload(client, "reg.json", json.dumps({"chemicals": RECORDS[:1]}).encode())
    assert res.json()["inserted"] == 1
    res = client.post("/api/chemicals/import", json={"chemicals": [{"chemical_id": "CHEM-J-009", "name": "Body"}]})
    assert res.status_code == 200 and res.json()["inserted"] == 1
    res = client.post("/api/chemicals/import", json=[{"chemical_id": "CHEM-J-010", "name": "Bare list"}])
    assert res.json()["inserted"] == 1


def test_json_refusals_say_why(client):
    assert _upload(client, "reg.json", b"{not json").json()["error"].startswith("Not valid JSON")
    assert _upload(client, "reg.json", b"[]").json() == {"error": "JSON file has no chemicals"}
    assert _upload(client, "reg.json", b'{"nope": 1}').json()["error"].startswith("JSON must be a list")
    assert _upload(client, "reg.json", b'[1, 2]').json() == {"error": "Record #1 is not an object"}
    assert client.post("/api/chemicals/upload/json").json() == {"error": "No file uploaded"}


def test_spreadsheet_routes_still_answer_as_before(client):
    csv = b"CHEMICAL_NAME,CAS_NO,MOL_FORMULA\nCaffeine,58-08-2,C8H10N4O2\nWater,7732-18-5,H2O\n"
    res = _upload(client, "chem.csv", csv, "/api/chemicals/upload/excel")
    assert res.json() == {"message": "Successfully processed 2 chemicals (2 new, 0 updated)", "inserted": 2, "updated": 0, "total": 2}
    assert _upload(client, "chem.csv", b"CHEMICAL_NAME\n", "/api/chemicals/upload/excel").json() == {"error": "CSV file is empty or has no data rows"}


def test_terminal_import_script_uses_the_same_door(client, tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(RECORDS))
    with SessionLocal() as db:
        assert import_file.run(["chemicals", str(path)], db=db) == 0
    assert client.get("/api/stats").json()["chemicals"]["total"] == 3

    csv = tmp_path / "more.csv"
    csv.write_text("CHEMICAL_NAME,CAS_NO\nWater,7732-18-5\n")
    with SessionLocal() as db:
        assert import_file.run(["chemicals", str(csv)], db=db) == 0
    assert client.get("/api/stats").json()["chemicals"]["total"] == 4

    with SessionLocal() as db:
        assert import_file.run(["chemicals", str(tmp_path / "missing.json")], db=db) == 2
        bad = tmp_path / "bad.txt"
        bad.write_text("x")
        assert import_file.run(["chemicals", str(bad)], db=db) == 1


def test_export_then_import_round_trips(client, tmp_path):
    _upload(client, "reg.json", json.dumps(RECORDS).encode())
    out = tmp_path / "export.json"
    with SessionLocal() as db:
        assert export_chemicals.run(["-o", str(out)], db=db) == 0
    records = json.loads(out.read_text())
    assert len(records) == 3
    assert [r["chemical_id"] for r in records] == sorted(r["chemical_id"] for r in records)
    assert records[0]["created_at"]  # the export is the full document

    client.delete("/api/chemicals/all/clear")
    assert client.get("/api/stats").json()["chemicals"]["total"] == 0
    with SessionLocal() as db:
        assert import_file.run(["chemicals", str(out)], db=db) == 0
    again = client.get("/api/chemicals/CHEM-J-001").json()
    assert again["pubchem_cid"] == 2519  # every field survives the round trip
    assert again["cas_number"] == "58-08-2"
    assert client.get("/api/chemicals/CHEM-J-002").json()["cas_number"] is None
    assert client.get("/api/stats").json()["chemicals"]["total"] == 3
