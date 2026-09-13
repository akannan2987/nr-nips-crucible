"""CR-10 — the attention page: every flag in the browser, with the actions a person takes.

* `GET /api/chemicals/audit` lists shared identifiers as groups (derived from
  the data, so an entry created by any route is seen), batch conflicts with
  each batch's value, pending identifiers, and the formula findings, each
  with its review mark and its count of linked rows;
* `POST /api/chemicals/audit/review` leaves or lifts a mark; a reviewed item
  stays listed but no longer counts on the banner;
* `POST /api/chemicals/merge` folds entries into a survivor: fields the
  survivor lacked are carried over, every row is repointed FIRST, the flags
  naming the removed entries are cleaned, and only then are they deleted;
* `POST /api/chemicals/:id/identifier` fills in a pending identifier;
* the terminal script prints the same audit, and merges through the same
  module.
"""
from __future__ import annotations

import sys
from pathlib import Path

from app.database import SessionLocal
from app.models import Chemical, Sample, Screening
from app.store import insert_doc

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audit_chemicals  # noqa: E402
import merge_duplicate_chemicals  # noqa: E402

TWIN_A = {"chemical_id": "CHEM-000010", "name": "Vanillin", "cas_number": "121-33-5", "dtx_id": "DTXSID0021976", "molecular_formula": "C8H8O3"}
TWIN_B = {"chemical_id": "CHEM-000011", "name": "Vanillin (repeat registration)", "cas_number": "121-33-5", "supplier": "ACME", "molecular_formula": "C8H8O3"}
LONE = {"chemical_id": "CHEM-000012", "name": "Pentacosane", "cas_number": "629-99-2", "molecular_formula": "C25H52"}


def _seed(client, *docs):
    for doc in docs:
        assert client.post("/api/chemicals", json=doc).status_code == 201


def _link(client, chemical_id: str, n: int) -> None:
    for i in range(n):
        assert client.post("/api/screening", json={"chemical_id": chemical_id, "assay_name": f"assay {i}"}).status_code == 201


def test_audit_groups_shared_identifiers_from_the_data(client):
    _seed(client, TWIN_A, TWIN_B, LONE)
    _link(client, "CHEM-000011", 2)
    audit = client.get("/api/chemicals/audit").json()
    assert audit["counts"]["shared_groups"] == 1 and audit["counts"]["shared_entries"] == 2
    group = audit["shared"][0]
    assert (group["kind"], group["value"], group["key"], group["reviewed"]) == ("cas", "121-33-5", "shared:cas:121-33-5", False)
    assert [e["chemical_id"] for e in group["entries"]] == ["CHEM-000010", "CHEM-000011"]
    assert [e["linked_rows"] for e in group["entries"]] == [0, 2]     # side by side, with what points at each
    assert audit["batch_conflicts"] == [] and audit["pending"] == []
    assert audit["counts"]["attention"] == 1 + audit["counts"]["formula"]
    # the banner sees the same numbers
    summary = client.get("/api/chemicals/notices/summary").json()
    assert summary["cas_shared"] == 2 and summary["attention"] == audit["counts"]["attention"]


def test_review_mark_keeps_the_item_listed_but_off_the_banner(client):
    _seed(client, TWIN_A, TWIN_B)
    res = client.post("/api/chemicals/audit/review", json={"chemical_ids": ["CHEM-000010", "CHEM-000011"], "key": "shared:cas:121-33-5", "reviewed": True})
    assert res.status_code == 200 and res.json() == {"updated": 2, "key": "shared:cas:121-33-5", "reviewed": True}
    audit = client.get("/api/chemicals/audit").json()
    assert audit["shared"][0]["reviewed"] is True                        # still listed
    assert audit["counts"]["shared_groups"] == 0 and audit["counts"]["reviewed"] == 1
    assert client.get("/api/chemicals/notices/summary").json()["cas_shared"] == 0
    assert "shared:cas:121-33-5" in client.get("/api/chemicals/CHEM-000010").json()["reviewed"]   # the mark is data on the entry
    # lifting it: the mark is removed, not set to false
    res = client.post("/api/chemicals/audit/review", json={"chemical_ids": ["CHEM-000010"], "key": "shared:cas:121-33-5", "reviewed": False})
    assert res.json()["updated"] == 1
    assert "reviewed" not in client.get("/api/chemicals/CHEM-000010").json()
    assert client.get("/api/chemicals/audit").json()["shared"][0]["reviewed"] is False   # one of two lifted → open again
    # nothing is written when an id is unknown
    res = client.post("/api/chemicals/audit/review", json={"chemical_ids": ["CHEM-000011", "CHEM-999999"], "key": "formula"})
    assert res.status_code == 404
    assert "reviewed" not in client.get("/api/chemicals/CHEM-000011").json() or "formula" not in client.get("/api/chemicals/CHEM-000011").json()["reviewed"]


def test_merge_repoints_rows_carries_fields_cleans_flags_then_deletes(client):
    _seed(client, {**TWIN_A, "cas_shared_with": ["CHEM-000011"]}, {**TWIN_B, "cas_shared_with": ["CHEM-000010"]})
    _link(client, "CHEM-000011", 3)
    with SessionLocal() as db:
        insert_doc(db, Sample, {"id": "s-1", "sample_id": "SAMP-1", "chemical_ids": ["CHEM-000011", "CHEM-000010"], "name": "vial"})

    res = client.post("/api/chemicals/merge", json={"keep": "CHEM-000010", "remove": ["CHEM-000011"]})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["kept"] == "CHEM-000010" and body["removed"] == ["CHEM-000011"]
    assert body["rows_repointed"] == {"screening": 3, "samples": 1, "total": 4}

    assert client.get("/api/chemicals/CHEM-000011").status_code == 404      # gone
    kept = client.get("/api/chemicals/CHEM-000010").json()
    assert kept["supplier"] == "ACME"                                         # a field only the duplicate had
    assert kept["name"] == "Vanillin"                                          # the survivor's own values win
    assert "cas_shared_with" not in kept                                      # the flag naming the gone entry is cleaned
    assert [m["chemical_id"] for m in kept["merged_entries"]] == ["CHEM-000011"]
    with SessionLocal() as db:
        rows = db.query(Screening).all()
        assert {(r.chemical_id, r.doc["chemical_id"]) for r in rows} == {("CHEM-000010", "CHEM-000010")}   # column AND document
        assert db.query(Sample).one().doc["chemical_ids"] == ["CHEM-000010"]    # no duplicate pointer either
    assert client.get("/api/chemicals/audit").json()["shared"] == []           # nothing shared any more
    # the deploy check's question: no row points at a missing entry
    assert len(client.get("/api/screening/chemical/CHEM-000010").json()) == 3


def test_merge_refuses_nonsense(client):
    _seed(client, TWIN_A, TWIN_B)
    assert client.post("/api/chemicals/merge", json={"keep": "CHEM-000010", "remove": []}).status_code == 400
    assert client.post("/api/chemicals/merge", json={"keep": "CHEM-000010", "remove": ["CHEM-000010"]}).status_code == 400
    assert client.post("/api/chemicals/merge", json={"keep": "CHEM-000010", "remove": ["CHEM-404"]}).status_code == 404
    assert client.get("/api/chemicals/CHEM-000010").status_code == 200        # nothing changed


def test_batch_conflicts_show_each_batch_value_and_pending_identifiers_can_be_set(client):
    with SessionLocal() as db:
        insert_doc(db, Chemical, {
            "id": "c-1", "chemical_id": "CHEM-000020", "name": "Twobatch", "cas_number": "1-1-1",
            "batch_conflicts": ["MOL_FORMULA"], "metadata": {"MOL_FORMULA": "C8H8O3"},
            "batches": [{"BATCH_ID": 1, "MOL_FORMULA": "C8H8O3"}, {"BATCH_ID": 2, "MOL_FORMULA": "C8H8O4"}],
        })
        insert_doc(db, Chemical, {
            "id": "c-2", "chemical_id": "CHEM-000021", "name": "Waiting", "nestle_id_pending": "screening", "supplier": "10001",
        })
    audit = client.get("/api/chemicals/audit").json()
    conflict = audit["batch_conflicts"][0]
    assert conflict["chemical_id"] == "CHEM-000020" and conflict["key"] == "batch_conflicts"
    assert conflict["columns"] == [{"column": "MOL_FORMULA", "promoted": "C8H8O3", "values": [
        {"batch": 1, "batch_id": 1, "value": "C8H8O3"}, {"batch": 2, "batch_id": 2, "value": "C8H8O4"}]}]
    assert audit["pending"][0]["chemical_id"] == "CHEM-000021" and audit["pending"][0]["supplier"] == "10001"
    assert audit["counts"]["batch_conflicts"] == 1 and audit["counts"]["pending"] == 1

    res = client.post("/api/chemicals/CHEM-000021/identifier", json={"nestle_id": "NID-0042"})
    assert res.status_code == 200 and res.json()["nestle_id"] == "NID-0042"
    doc = client.get("/api/chemicals/CHEM-000021").json()
    assert doc["nestle_id"] == "NID-0042" and "nestle_id_pending" not in doc
    assert client.get("/api/chemicals/audit").json()["pending"] == []
    assert client.post("/api/chemicals/CHEM-000021/identifier", json={"nestle_id": "  "}).status_code == 400
    assert client.post("/api/chemicals/CHEM-404/identifier", json={"nestle_id": "x"}).status_code == 404


def test_formula_findings_are_the_chemistry_checks_with_a_review_mark(client):
    # a name claiming sixteen carbons over a seven-carbon formula: the 2026-08-25 case
    _seed(client, {"chemical_id": "CHEM-000030", "name": "Glycerol, 2-monohexadecanoate", "cas_number": "23470-00-0", "molecular_formula": "C7H9NO"})
    audit = client.get("/api/chemicals/audit").json()
    item = next(f for f in audit["formula"] if f["chemical_id"] == "CHEM-000030")
    assert item["key"] == "formula" and item["reviewed"] is False
    assert item["reasons"] == ["name says 'hexadec…' (16 carbons) but the formula has 7",
                               "formula has N but nothing in the name accounts for it"]
    assert audit["formula"][0]["chemical_id"] == "CHEM-000030"              # the worst first
    before = client.get("/api/chemicals/notices/summary").json()["formula"]
    client.post("/api/chemicals/audit/review", json={"chemical_ids": ["CHEM-000030"], "key": "formula"})
    assert client.get("/api/chemicals/notices/summary").json()["formula"] == before - 1


def test_the_scripts_print_the_same_audit_and_merge_through_the_same_module(client, capsys):
    _seed(client, TWIN_A, TWIN_B)
    _link(client, "CHEM-000011", 1)
    assert audit_chemicals.main([]) == 0
    out = capsys.readouterr().out
    assert "CAS 121-33-5  shared by 2" in out and "1 row linked" in out
    assert "Needs attention in the browser" in out

    assert merge_duplicate_chemicals.main(["CHEM-000010", "CHEM-000011"]) == 0   # report only
    out = capsys.readouterr().out
    assert "(1 rows point at it)" in out and "Report only" in out
    assert client.get("/api/chemicals/CHEM-000011").status_code == 200           # provably dry

    assert merge_duplicate_chemicals.main(["CHEM-000010", "CHEM-000011", "--apply"]) == 0
    assert "1 entries removed, 1 rows repointed. Applied." in capsys.readouterr().out
    assert client.get("/api/chemicals/CHEM-000011").status_code == 404
    assert len(client.get("/api/screening/chemical/CHEM-000010").json()) == 1


def test_formula_check_reads_every_name_and_halogen_multipliers_are_not_chains(client):
    # DDT: the trivial name says nothing about chlorine; its synonym does → not doubtful
    # (seeded through the store: the v1 create endpoint keeps a fixed field set, without synonyms)
    with SessionLocal() as db:
        insert_doc(db, Chemical, {"id": "c-40", "chemical_id": "CHEM-000040", "name": "DDT", "cas_number": "50-29-3", "molecular_formula": "C14H9Cl5",
                                  "synonyms": ["1,1'-(2,2,2-trichloroethylidene)bis(4-chlorobenzene)"]})
    # 'tridecafluorohexyl' is thirteen fluorines on six carbons, not a thirteen-carbon chain
    _seed(client, {"chemical_id": "CHEM-000041", "name": "Tridecafluorohexanesulfonic acid", "cas_number": "355-46-4", "molecular_formula": "C6HF13O3S"})
    # and a real contradiction still shows
    _seed(client, {"chemical_id": "CHEM-000042", "name": "Ethyl benzoate", "cas_number": "93-89-0", "molecular_formula": "C9H10N2"})
    flagged = [f["chemical_id"] for f in client.get("/api/chemicals/audit").json()["formula"]]
    assert "CHEM-000040" not in flagged and "CHEM-000041" not in flagged
    assert flagged == ["CHEM-000042"]
