"""CR-6 — deleting a chemical refuses while rows are linked, or unlinks first when forced.

The rule, from the owner's description (docs/09-chemical-identification.md,
"How deletion will work after CR-6"):

1. a plain delete — the browser's route — is refused with 409 while any row
   points at the chemical, and the message says how many and what to do;
2. with `force` the rows are unlinked first and the entry deleted second,
   and the answer carries both counts;
3. with nothing linked, the plain delete answers exactly as it always has
   (the contract tests in test_parity_chemicals.py keep proving that);
4. every link location counts: the screening column and document, and a
   sample's `chemical_ids` list, which has no column.
"""
from __future__ import annotations

from app.database import SessionLocal
from app.models import Sample, Screening
from app.store import insert_doc

CHEM_B = {"chemical_id": "CHEM-TEST-002", "name": "Aspirin", "cas_number": "50-78-2"}


def _seed_links(client, chemical_id: str = "CHEM-TEST-001", screening: int = 3, sample: bool = False) -> None:
    for i in range(screening):
        res = client.post("/api/screening", json={"chemical_id": chemical_id, "assay_name": f"assay {i}"})
        assert res.status_code == 201
    if sample:
        with SessionLocal() as db:
            insert_doc(db, Sample, {"id": "s-1", "sample_id": "SAMP-1", "chemical_ids": [chemical_id], "name": "vial"})


def _links():
    with SessionLocal() as db:
        screening = [(r.chemical_id, r.doc.get("chemical_id")) for r in db.query(Screening).all()]
        samples = [r.doc.get("chemical_ids") for r in db.query(Sample).all()]
    return screening, samples


def test_plain_delete_is_refused_while_rows_are_linked(seeded_client):
    _seed_links(seeded_client)
    res = seeded_client.delete("/api/chemicals/CHEM-TEST-001")
    assert res.status_code == 409
    body = res.json()
    assert set(body) == {"error"}
    assert body["error"].startswith("3 screening rows linked to CHEM-TEST-001; unlink them first")
    assert "force=true" in body["error"]
    # nothing changed: the entry is still there and the rows still point at it
    assert seeded_client.get("/api/chemicals/CHEM-TEST-001").status_code == 200
    screening, _ = _links()
    assert screening == [("CHEM-TEST-001", "CHEM-TEST-001")] * 3


def test_forced_delete_unlinks_first_then_deletes(seeded_client):
    _seed_links(seeded_client, sample=True)
    res = seeded_client.delete("/api/chemicals/CHEM-TEST-001?force=true")
    assert res.status_code == 200
    assert res.json() == {
        "message": "Chemical deleted successfully",
        "unlinked": {"screening": 3, "samples": 1, "total": 4},
    }
    assert seeded_client.get("/api/chemicals/CHEM-TEST-001").status_code == 404
    screening, samples = _links()
    assert screening == [(None, None)] * 3  # column AND document cleared
    assert samples == [[]]  # the sample's list emptied, the sample kept


def test_plain_delete_with_nothing_linked_is_unchanged(seeded_client):
    res = seeded_client.delete("/api/chemicals/CHEM-TEST-001")
    assert res.status_code == 200
    assert res.json() == {"message": "Chemical deleted successfully"}


def test_a_sample_link_alone_is_enough_to_refuse(seeded_client):
    _seed_links(seeded_client, screening=0, sample=True)
    res = seeded_client.delete("/api/chemicals/CHEM-TEST-001")
    assert res.status_code == 409
    assert res.json()["error"].startswith("1 sample linked to CHEM-TEST-001")


def test_bulk_delete_refuses_and_forces(seeded_client):
    seeded_client.post("/api/chemicals", json=CHEM_B)
    _seed_links(seeded_client, "CHEM-TEST-002", screening=2)
    ids = ["CHEM-TEST-001", "CHEM-TEST-002", "MISSING"]

    res = seeded_client.post("/api/chemicals/bulk/delete", json={"chemical_ids": ids})
    assert res.status_code == 409
    assert res.json()["error"].startswith("2 screening rows linked to 2 of the 3 chemicals")
    assert seeded_client.get("/api/chemicals/CHEM-TEST-002").status_code == 200

    res = seeded_client.post("/api/chemicals/bulk/delete", json={"chemical_ids": ids, "force": True})
    assert res.status_code == 200
    assert res.json() == {
        "message": "Successfully deleted 2 chemicals",
        "deleted": 2,
        "requested": 3,
        "unlinked": {"screening": 2, "total": 2},
    }
    screening, _ = _links()
    assert screening == [(None, None)] * 2


def test_clear_all_refuses_and_forces(seeded_client):
    _seed_links(seeded_client, screening=2)
    res = seeded_client.delete("/api/chemicals/all/clear")
    assert res.status_code == 409
    assert res.json()["error"].startswith("2 screening rows linked to chemicals; unlink them first")
    assert seeded_client.get("/api/stats").json()["chemicals"]["total"] == 1

    res = seeded_client.delete("/api/chemicals/all/clear?force=true")
    assert res.status_code == 200
    assert res.json() == {
        "message": "Successfully deleted all 1 chemicals",
        "deleted": 1,
        "unlinked": {"screening": 2, "total": 2},
    }
    assert seeded_client.get("/api/stats").json()["chemicals"]["total"] == 0
