"""CR-12, step A: one derived structure per entry, checked against what the source recorded.

* `derive_one` reads the MOL block, then the SMILES, then the InChI (S5),
  computes the canonical SMILES, InChI, InChIKey, formula, weights and
  counts, and compares the laboratory's formula, weight and InChI with them;
* a formula is accepted when it is the whole structure's or any fragment's
  (a salt's parent); a weight when it is the average or the exact mass; an
  InChI that names another skeleton, or differs in stereo only, is a finding;
* a SMILES the source wrapped in brackets is repaired and recorded; a source
  nothing can read is a finding of its own;
* the endpoint reports without writing, writes on `apply`, refuses an
  unknown id without writing, and a re-run rewrites nothing; the audit lists
  the findings as the fifth kind, the notices count them, the review mark
  works, and the derived fields become columns; the script is a caller.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from rdkit import Chem

from app import structures
from app.database import SessionLocal

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import derive_structures  # noqa: E402

CAFFEINE = {"chemical_id": "CHEM-000001", "name": "Caffeine", "smiles": "Cn1cnc2c1c(=O)n(C)c(=O)n2C", "molecular_formula": "C8H10N4O2", "molecular_weight": 194.0804}
ACETATE = {"chemical_id": "CHEM-000002", "name": "Sodium acetate", "smiles": "CC(=O)[O-].[Na+]", "molecular_formula": "C2H3O2", "molecular_weight": 82.03}
WRONG = {"chemical_id": "CHEM-000003", "name": "Mislabelled", "smiles": "CCO", "molecular_formula": "C5H10", "molecular_weight": 250.0}
BROKEN = {"chemical_id": "CHEM-000004", "name": "Unreadable", "smiles": "not a smiles", "inchi": "nope"}
PLAIN = {"chemical_id": "CHEM-000005", "name": "No structure", "cas_number": "1-2-3"}


def test_derive_from_smiles_computes_the_facts_and_agrees_with_the_laboratory():
    s = structures.derive_one(CAFFEINE)
    assert s["source"] == "smiles" and "repaired" not in s
    assert (s["formula"], s["weight"], s["exact_mass"]) == ("C8H10N4O2", 194.194, 194.0804)
    assert s["inchikey"] == "RYYVLZVUVIJVGH-UHFFFAOYSA-N" and s["inchi"].startswith("InChI=1S/C8H10N4O2/")
    assert (s["atoms"], s["bonds"], s["rings"], s["charge"], s["fragments"]) == (14, 15, 2, 0, 1)
    assert s["checks"] == {"formula": "agrees", "weight": "agrees", "inchi": "none"} and s["findings"] == []
    assert s["derived_at"].endswith("Z")
    assert structures.derive_one(PLAIN) is None


def test_the_source_order_is_mol_block_then_smiles_then_inchi():
    ethanol_block = Chem.MolToMolBlock(Chem.MolFromSmiles("CCO"))
    methanol_inchi = Chem.MolToInchi(Chem.MolFromSmiles("CO"))
    both = {"chemical_id": "X", "mol_block": ethanol_block, "smiles": "CO"}
    assert (structures.derive_one(both)["source"], structures.derive_one(both)["formula"]) == ("mol_block", "C2H6O")
    smiles_first = {"chemical_id": "X", "smiles": "CCO", "inchi": methanol_inchi}
    s = structures.derive_one(smiles_first)
    assert s["source"] == "smiles" and s["formula"] == "C2H6O"
    inchi_only = {"chemical_id": "X", "inchi": methanol_inchi}
    s = structures.derive_one(inchi_only)
    assert (s["source"], s["formula"], s["checks"]["inchi"]) == ("inchi", "CH4O", "same source")
    # a MOL block nothing can read falls through to the SMILES, and says so
    fallen = {"chemical_id": "X", "mol_block": "garbage", "smiles": "CCO"}
    s = structures.derive_one(fallen)
    assert s["source"] == "smiles" and s["unreadable"] == ["mol_block"] and s["findings"] == []


def test_a_bracketed_smiles_is_repaired_and_an_unreadable_source_is_a_finding():
    s = structures.derive_one({"chemical_id": "X", "smiles": "[CCO]"})
    assert (s["source"], s["repaired"], s["formula"]) == ("smiles", "outer brackets removed", "C2H6O")
    s = structures.derive_one(BROKEN)
    assert s["source"] is None and s["unreadable"] == ["smiles", "inchi"] and s["checks"] == {}
    assert s["findings"] == [{"kind": "unreadable", "reason": "no structure could be read from the SMILES or the InChI the source carries"}]


def test_the_formula_check_accepts_a_fragment_and_the_weight_check_accepts_either_mass():
    s = structures.derive_one(ACETATE)
    assert s["formula"] == "C2H3NaO2" and s["fragments"] == 2 and s["largest_fragment"]["formula"] == "C2H3O2-"
    assert s["checks"]["formula"] == "agrees" and s["checks"]["weight"] == "agrees" and s["findings"] == []
    assert structures.normalise_formula("C2 H3 O2 -") == "C2H3O2" and structures.normalise_formula("O3Si-2") == "O3Si"
    average = structures.derive_one({**CAFFEINE, "molecular_weight": 194.19})
    assert average["checks"]["weight"] == "agrees"
    s = structures.derive_one(WRONG)
    assert s["checks"] == {"formula": "differs", "weight": "differs", "inchi": "none"}
    assert [f["kind"] for f in s["findings"]] == ["formula", "weight"]
    assert s["findings"][0]["reason"] == "the laboratory's formula C5H10 is not the formula of the structure (C2H6O)"
    assert "neither the average weight (46.069) nor the exact mass (46.0419)" in s["findings"][1]["reason"]


def test_the_inchi_check_tells_a_skeleton_from_a_stereo_layer():
    methanol_inchi = Chem.MolToInchi(Chem.MolFromSmiles("CO"))
    s = structures.derive_one({"chemical_id": "X", "smiles": "CCO", "inchi": methanol_inchi})
    assert s["checks"]["inchi"] == "differs" and "different skeleton" in s["findings"][0]["reason"]
    l_alanine, d_alanine = "C[C@@H](C(=O)O)N", "C[C@H](C(=O)O)N"
    s = structures.derive_one({"chemical_id": "X", "smiles": l_alanine, "inchi": Chem.MolToInchi(Chem.MolFromSmiles(d_alanine))})
    assert s["findings"] == [{"kind": "inchi", "reason": "the InChI the source carries differs from the structure in the stereo or charge layer only"}]
    agreed = structures.derive_one({"chemical_id": "X", "smiles": "CCO", "inchi": Chem.MolToInchi(Chem.MolFromSmiles("OCC"))})
    assert agreed["checks"]["inchi"] == "agrees" and agreed["findings"] == []
    unreadable = structures.derive_one({"chemical_id": "X", "smiles": "CCO", "inchi": "InChI=1S/garbage"})
    assert unreadable["checks"]["inchi"] == "unreadable" and unreadable["findings"][0]["kind"] == "inchi"
    # a polymer written with placeholder atoms has no InChI of its own: nothing to compare, and it says so
    polymer = structures.derive_one({"chemical_id": "X", "smiles": "*CC(*)C", "inchi": Chem.MolToInchi(Chem.MolFromSmiles("CCC"))})
    assert polymer["inchikey"] == "" and polymer["checks"]["inchi"] == "not computable" and "could not be computed" in polymer["findings"][0]["reason"]
    # the largest fragment of a hydrated salt of single atoms is the heaviest atom, not a water
    hydrate = structures.derive_one({"chemical_id": "X", "smiles": "O.O.[Cl-].[Na+]"})
    assert hydrate["largest_fragment"]["formula"] == "Cl-"


def _seed(client, *docs):
    for doc in docs:
        assert client.post("/api/chemicals", json=doc).status_code == 201


def test_the_endpoint_reports_then_writes_and_the_audit_lists_the_findings(client):
    _seed(client, CAFFEINE, ACETATE, WRONG, BROKEN, PLAIN)
    # a report writes nothing
    res = client.post("/api/chemicals/structures/derive", json={})
    assert res.status_code == 200
    r = res.json()
    assert (r["entries"], r["with_source"], r["derived"], r["unreadable"], r["applied"], r["written"]) == (5, 4, 3, 1, False, 0)
    assert r["from"] == {"mol_block": 0, "smiles": 3, "inchi": 0}
    assert r["findings"] == {"entries": 2, "formula": 1, "weight": 1, "inchi": 0, "unreadable": 1}
    assert [i["chemical_id"] for i in r["items"]] == ["CHEM-000003", "CHEM-000004"]
    assert r["items"][0]["kinds"] == ["formula", "weight"] and r["items"][1]["kinds"] == ["unreadable"]
    assert "structure" not in client.get("/api/chemicals/CHEM-000001").json()
    audit = client.get("/api/chemicals/audit").json()
    assert audit["structures"] == [] and audit["counts"]["structure"] == 0
    assert audit["structures_summary"] == {"with_source": 4, "derived": 0, "to_derive": 4, "findings": 0}
    # apply writes the structure beside the laboratory's fields, and leaves updated_at alone
    before = client.get("/api/chemicals/CHEM-000001").json()["updated_at"]
    r = client.post("/api/chemicals/structures/derive", json={"apply": True}).json()
    assert (r["applied"], r["written"], r["unchanged"]) == (True, 4, 0)
    doc = client.get("/api/chemicals/CHEM-000001").json()
    assert doc["structure"]["inchikey"] == "RYYVLZVUVIJVGH-UHFFFAOYSA-N" and doc["molecular_formula"] == "C8H10N4O2"
    assert doc["updated_at"] == before
    assert "structure" not in client.get("/api/chemicals/CHEM-000005").json()
    # the audit's fifth kind, the notices, the banner total
    audit = client.get("/api/chemicals/audit").json()
    assert [s["chemical_id"] for s in audit["structures"]] == ["CHEM-000003", "CHEM-000004"]
    item = audit["structures"][0]
    assert (item["key"], item["reviewed"], item["kinds"]) == ("structure", False, ["formula", "weight"])
    assert (item["molecular_formula"], item["structure"]["formula"], item["structure"]["source"]) == ("C5H10", "C2H6O", "smiles")
    assert len(item["reasons"]) == 2
    assert audit["counts"]["structure"] == 2 and audit["counts"]["attention"] == 2 + audit["counts"]["formula"]
    assert audit["structures_summary"] == {"with_source": 4, "derived": 3, "to_derive": 0, "findings": 2}
    notices = client.get("/api/chemicals/notices/summary").json()
    assert notices["structure"] == 2 and notices["attention"] == audit["counts"]["attention"]
    # the review mark, the same as for every other kind
    res = client.post("/api/chemicals/audit/review", json={"chemical_ids": ["CHEM-000003"], "key": "structure"})
    assert res.json()["updated"] == 1
    audit = client.get("/api/chemicals/audit").json()
    assert audit["counts"]["structure"] == 1 and audit["structures"][-1]["chemical_id"] == "CHEM-000003" and audit["structures"][-1]["reviewed"]
    # a re-run rewrites nothing; a subset works; an unknown id writes nothing
    r = client.post("/api/chemicals/structures/derive", json={"apply": True}).json()
    assert (r["written"], r["unchanged"]) == (0, 4)
    r = client.post("/api/chemicals/structures/derive", json={"chemical_ids": ["CHEM-000002"], "apply": True}).json()
    assert (r["entries"], r["with_source"], r["unchanged"]) == (1, 1, 1)
    res = client.post("/api/chemicals/structures/derive", json={"chemical_ids": ["CHEM-000002", "CHEM-999999"], "apply": True})
    assert res.status_code == 404 and "CHEM-999999" in res.json()["error"]


def test_the_derived_fields_become_columns_and_sort(client):
    _seed(client, CAFFEINE, ACETATE, PLAIN)
    keys = [c["key"] for c in client.get("/api/chemicals/columns").json()["columns"]]
    assert "structure.formula" not in keys and "structure" not in keys          # nothing derived yet
    client.post("/api/chemicals/structures/derive", json={"apply": True})
    columns = {c["key"]: c for c in client.get("/api/chemicals/columns").json()["columns"]}
    assert columns["structure.formula"] == {"key": "structure.formula", "label": "derived formula", "group": "structure", "filled": 2, "coverage": round(2 / 3, 4)}
    assert "structure" not in columns and "structure.inchikey" in columns
    rows = client.get("/api/chemicals?sort=structure.formula&order=asc&limit=10").json()["data"]
    assert [r.get("structure", {}).get("formula") for r in rows][:2] == ["C2H3NaO2", "C8H10N4O2"]
    rows = client.get("/api/chemicals", params={"filters": json.dumps({"structure.source": "smiles"})}).json()["data"]
    assert {r["chemical_id"] for r in rows} == {"CHEM-000001", "CHEM-000002"}


def test_the_script_is_a_caller_of_the_same_module(client, capsys):
    _seed(client, CAFFEINE, WRONG)
    db = SessionLocal()
    try:
        assert derive_structures.main([], db) == 0
        out = capsys.readouterr().out
        assert "2 of 2 entries carry a structure source." in out and "Derived 2: 0 from a MOL block, 2 from a SMILES, 0 from an InChI; 0 could not be read." in out
        assert "Findings on 1 entries: formula 1, weight 1, InChI 0, unreadable 0." in out and "Report only" in out
        assert derive_structures.main(["--ids", "CHEM-000001", "--apply"], db) == 0
        assert "Applied: 1 entries written, 0 unchanged" in capsys.readouterr().out
        assert derive_structures.main(["--ids", "CHEM-404"], db) == 1
        assert "Unknown identifier: CHEM-404" in capsys.readouterr().out
        assert derive_structures.main(["--json"], db) == 0
        assert '"applied": false' in capsys.readouterr().out
    finally:
        db.close()
    assert "structure" in client.get("/api/chemicals/CHEM-000001").json() and "structure" not in client.get("/api/chemicals/CHEM-000003").json()
