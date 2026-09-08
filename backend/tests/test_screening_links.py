"""Linking and unlinking screening rows from the API — the buttons' backend.

A link is stored twice on a row (document and column); every assertion here
checks both, because the two disagreeing is the failure that would survive a
casual look.
"""

from app.database import SessionLocal
from app.models import Screening

CHEM_B = {"chemical_id": "CHEM-TEST-002", "name": "Aspirin", "cas_number": "50-78-2"}


def _rows(client, n=3):
    ids = []
    for i in range(n):
        res = client.post("/api/screening", json={"chemical_id": "CHEM-TEST-001", "assay_name": f"assay {i}"})
        assert res.status_code == 201
        ids.append(res.json()["id"])
    return ids


def _links():
    db = SessionLocal()
    try:
        return {r.id: (r.chemical_id, r.doc.get("chemical_id")) for r in db.query(Screening).all()}
    finally:
        db.close()


def test_unlink_chosen_rows_clears_document_and_column(seeded_client):
    ids = _rows(seeded_client)
    res = seeded_client.post("/api/screening/unlink", json={"record_ids": ids[:2]})
    assert res.status_code == 200
    assert res.json()["unlinked"] == 2 and res.json()["not_found"] == []
    links = _links()
    assert links[ids[0]] == (None, None) and links[ids[1]] == (None, None)
    assert links[ids[2]] == ("CHEM-TEST-001", "CHEM-TEST-001"), "untouched rows keep their link"
    # the table shows the source name, and the row still exists
    assert seeded_client.get(f"/api/screening/{ids[0]}").json()["chemical_name"] == "Unknown"


def test_unlink_all_detaches_every_linked_row_and_deletes_nothing(seeded_client):
    _rows(seeded_client)
    before = seeded_client.get("/api/stats").json()["screening"]["total"]
    res = seeded_client.post("/api/screening/unlink", json={"all": True})
    assert res.json()["unlinked"] == 3
    assert all(v == (None, None) for v in _links().values())
    assert seeded_client.get("/api/stats").json()["screening"]["total"] == before
    assert seeded_client.get("/api/stats").json()["chemicals"]["total"] == 1, "unlinking never deletes a chemical"
    # a second run finds nothing to do, and says so
    assert seeded_client.post("/api/screening/unlink", json={"all": True}).json()["unlinked"] == 0


def test_link_rows_to_another_registered_chemical(seeded_client):
    assert seeded_client.post("/api/chemicals", json=CHEM_B).status_code == 201
    ids = _rows(seeded_client)
    seeded_client.post("/api/screening/unlink", json={"record_ids": ids})
    res = seeded_client.post("/api/screening/link", json={"record_ids": ids[:2] + ["NOPE"], "chemical_id": "CHEM-TEST-002"})
    assert res.status_code == 200
    assert res.json()["linked"] == 2 and res.json()["not_found"] == ["NOPE"]
    links = _links()
    assert links[ids[0]] == ("CHEM-TEST-002", "CHEM-TEST-002")
    assert links[ids[2]] == (None, None)
    assert seeded_client.get(f"/api/screening/{ids[0]}").json()["chemical_name"] == "Aspirin"


def test_link_refuses_an_unknown_chemical_and_an_empty_selection(seeded_client):
    ids = _rows(seeded_client, 1)
    res = seeded_client.post("/api/screening/link", json={"record_ids": ids, "chemical_id": "CHEM-NOPE"})
    assert res.status_code == 404 and res.json() == {"error": "Chemical not found"}
    res = seeded_client.post("/api/screening/link", json={"record_ids": [], "chemical_id": "CHEM-TEST-001"})
    assert res.status_code == 400
    res = seeded_client.post("/api/screening/unlink", json={"record_ids": []})
    assert res.status_code == 400
    assert _links()[ids[0]] == ("CHEM-TEST-001", "CHEM-TEST-001"), "a refused request changes nothing"


def test_match_selects_every_row_the_table_would_show(seeded_client):
    """A request built from the table's filters acts on ALL matching rows, not one page."""
    for i in range(7):
        assert seeded_client.post("/api/screening", json={"chemical_id": "CHEM-TEST-001", "assay_name": f"cyto {i}"}).status_code == 201
    assert seeded_client.post("/api/screening", json={"chemical_id": "CHEM-TEST-001", "assay_name": "other"}).status_code == 201
    res = seeded_client.post("/api/screening/unlink", json={"match": {"filters": {"assay_name": "cyto"}}})
    assert res.status_code == 200
    assert res.json()["unlinked"] == 7 and res.json()["chemicals"] == 1
    assert res.json()["by_chemical"] == [{"chemical_id": "CHEM-TEST-001", "name": "Caffeine", "rows": 7}]
    left = [v for v in _links().values() if v != (None, None)]
    assert len(left) == 1, "the row that did not match keeps its link"


def test_unlink_summary_names_each_chemical_most_rows_first(seeded_client):
    assert seeded_client.post("/api/chemicals", json=CHEM_B).status_code == 201
    ids = _rows(seeded_client, 2)
    seeded_client.post("/api/screening", json={"chemical_id": "CHEM-TEST-002", "assay_name": "x"})
    res = seeded_client.post("/api/screening/unlink", json={"all": True}).json()
    assert res["chemicals"] == 2
    assert [b["name"] for b in res["by_chemical"]] == ["Caffeine", "Aspirin"]
    assert [b["rows"] for b in res["by_chemical"]] == [2, 1]
    assert res["message"] == "Unlinked 3 screening record(s) from 2 chemical(s)"
    assert ids  # the rows still exist
    assert seeded_client.get("/api/stats").json()["screening"]["total"] == 3


def test_link_by_match_reports_the_chemical_name(seeded_client):
    assert seeded_client.post("/api/chemicals", json=CHEM_B).status_code == 201
    _rows(seeded_client, 3)
    seeded_client.post("/api/screening/unlink", json={"all": True})
    res = seeded_client.post("/api/screening/link", json={"match": {"filters": {"assay_name": "assay 1"}}, "chemical_id": "CHEM-TEST-002"})
    assert res.status_code == 200 and res.json()["linked"] == 1
    assert res.json()["message"] == "Linked 1 screening record(s) to Aspirin (CHEM-TEST-002)"

