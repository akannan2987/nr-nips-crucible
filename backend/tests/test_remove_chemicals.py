"""The removal script deletes data, so it is the one script that most needs a test.

Every case runs the script in-process against the throwaway test database the
`client` fixture creates, seeded through the real API so the rows look exactly
like production rows: a link lives in the `chemical_id` column AND in the
stored document.

The properties checked, in order of how expensive it would be to learn them on
production:

1. A report (no --apply) writes nothing — lesson 17 is a "dry run" that wrote.
2. Removing one chemical unlinks only its rows and touches no other chemical.
3. --unlink-all clears every link, column and document, and keeps every chemical.
4. --all unlinks everything and leaves the registry empty.
5. Nothing matching is an error, not a silent no-op.
"""

import importlib.util
import uuid
from pathlib import Path

from app.database import SessionLocal
from app.models import Chemical, Sample, Screening
from app.store import insert_doc

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "remove_chemicals.py"
spec = importlib.util.spec_from_file_location("remove_chemicals", SCRIPT)
remove_chemicals = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remove_chemicals)

CHEM_A = {"chemical_id": "CHEM-A", "name": "Caffeine", "cas_number": "58-08-2"}
CHEM_B = {"chemical_id": "CHEM-B", "name": "Aspirin", "cas_number": "50-78-2", "identification": "pubchem name+cas agree"}


def seed(client):
    """Two chemicals; three screening rows (two linked, one not); one sample linked to A."""
    assert client.post("/api/chemicals", json=CHEM_A).status_code == 201
    # CHEM_B is what the identification job creates: it inserts through the
    # store with its own tag, not through the API, which stamps its own.
    db = SessionLocal()
    try:
        insert_doc(db, Chemical, {"id": str(uuid.uuid4()), **CHEM_B})
        db.commit()
    finally:
        db.close()
    for r in [
        {"chemical_id": "CHEM-A", "compound_name": "Caffeine", "assay": "x"},
        {"chemical_id": "CHEM-B", "compound_name": "Aspirin", "assay": "x"},
    ]:
        assert client.post("/api/screening", json=r).status_code == 201
    # The API refuses a screening row that names no existing chemical (the
    # import-order rule). A never-identified row from a laboratory export is
    # exactly that, and arrives through the template loader, so seed it the
    # way the loader does: straight into the store.
    db = SessionLocal()
    try:
        insert_doc(db, Screening, {"id": str(uuid.uuid4()), "compound_name": "Unknown thing", "assay": "x"})
        db.commit()
    finally:
        db.close()
    assert client.post("/api/samples", json={"sample_id": "S-1", "chemical_ids": ["CHEM-A"]}).status_code == 201


def state():
    db = SessionLocal()
    try:
        chems = sorted(r.doc["chemical_id"] for r in db.query(Chemical).all())
        links = sorted(((r.chemical_id, r.doc.get("chemical_id")) for r in db.query(Screening).all()), key=lambda t: (t[0] or "", t[1] or ""))
        samples = [tuple(r.doc.get("chemical_ids") or []) for r in db.query(Sample).all()]  # a sample links through a list, no column
        return chems, links, samples
    finally:
        db.close()


def run(*argv):
    db = SessionLocal()
    try:
        return remove_chemicals.run(list(argv), db=db)
    finally:
        db.close()


def test_report_mode_writes_nothing(client):
    seed(client)
    before = state()
    assert run("CHEM-A") == 0
    assert run("--unlink-all") == 0
    assert run("--all") == 0
    assert state() == before, "a report must be provably dry (lesson 17)"


def test_remove_one_unlinks_only_its_rows(client):
    seed(client)
    assert run("CHEM-A", "--apply") == 0
    chems, links, samples = state()
    assert chems == ["CHEM-B"]
    assert (None, None) in links and ("CHEM-B", "CHEM-B") in links
    assert all(link != ("CHEM-A", "CHEM-A") for link in links)
    assert samples == [()]


def test_unlink_all_clears_column_and_document_but_keeps_chemicals(client):
    seed(client)
    assert run("--unlink-all", "--apply") == 0
    chems, links, samples = state()
    assert chems == ["CHEM-A", "CHEM-B"], "unlink-all must not delete any chemical"
    assert links == [(None, None)] * 3, "every link cleared in BOTH the column and the document"
    assert samples == [()]


def test_all_empties_the_registry_after_unlinking(client):
    seed(client)
    assert run("--all", "--apply") == 0
    chems, links, samples = state()
    assert chems == []
    assert links == [(None, None)] * 3
    assert samples == [()]
    # and the rows themselves survive, carrying every value they had — the
    # loader-style row still has the name its source file recorded
    db = SessionLocal()
    try:
        rows = db.query(Screening).all()
        names = [r.doc.get("compound_name") for r in rows]
    finally:
        db.close()
    assert len(rows) == 3
    assert "Unknown thing" in names


def test_pubchem_registered_selects_only_the_job_s_entries(client):
    seed(client)
    assert run("--pubchem-registered", "--apply") == 0
    chems, links, _ = state()
    assert chems == ["CHEM-A"]
    assert ("CHEM-A", "CHEM-A") in links


def test_nothing_matching_is_an_error(client):
    seed(client)
    assert run("CHEM-NOPE") == 1
    assert run("CHEM-NOPE", "--apply") == 1


def test_unlink_only_detaches_one_chemical_s_rows_and_keeps_every_entry(client):
    seed(client)
    assert run("CHEM-A", "--unlink-only", "--apply") == 0
    chems, links, samples = state()
    assert chems == ["CHEM-A", "CHEM-B"], "unlink-only never deletes"
    assert (None, None) in links and ("CHEM-B", "CHEM-B") in links
    assert all(link != ("CHEM-A", "CHEM-A") for link in links)


def test_every_mode_says_which_chemicals_and_how_many_rows(client, capsys):
    seed(client)
    run("--unlink-all")
    out = capsys.readouterr().out
    assert "rows per chemical (2 chemicals), most first:" in out
    assert "Caffeine" in out and "Aspirin" in out
    line = next(line for line in out.splitlines() if "CHEM-A" in line and "Caffeine" in line)
    assert line.split()[0] == "2", "CHEM-A has two linked rows: one screening row and one sample"



def test_all_on_an_empty_registry_says_so_and_succeeds(client, capsys):
    """CR-3 fix: --all with nothing registered is not an error — the reset has already happened."""
    assert run("--all") == 0
    assert "already empty" in capsys.readouterr().out
