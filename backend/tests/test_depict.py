"""CR-12, step B: the derived structure, drawn by the server.

* `depict.svg_for` draws an entry's derived structure as SVG at the size
  asked for, from the MOL block's own coordinates when the structure came
  from it and from the canonical SMILES otherwise; nothing without one;
* `GET /api/chemicals/:id/structure.svg` answers the image with an ETag
  from `derived_at`, 304 when the browser already has it, clamps the size,
  404 for an unknown entry or one not yet derived;
* the picture is offered as a column once anything is derived;
* the script draws the same picture to a file.
"""
from __future__ import annotations

import sys
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import rdDepictor

from app import depict, structures
from app.database import SessionLocal

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import draw_structure  # noqa: E402

CAFFEINE = {"chemical_id": "CHEM-000001", "name": "Caffeine", "smiles": "Cn1cnc2c1c(=O)n(C)c(=O)n2C", "molecular_formula": "C8H10N4O2", "molecular_weight": 194.0804}
PLAIN = {"chemical_id": "CHEM-000002", "name": "No structure", "cas_number": "1-2-3"}


def _derived(doc):
    return {**doc, "structure": structures.derive_one(doc)}


def test_svg_for_draws_the_derived_structure_at_the_size_asked():
    doc = _derived(CAFFEINE)
    svg = depict.svg_for(doc)
    assert svg.startswith("<?xml") and "<svg" in svg and "</svg>" in svg
    assert "width='320px' height='240px'" in svg
    assert "width='96px' height='72px'" in depict.svg_for(doc, 96, 72)
    assert "width='48px'" in depict.svg_for(doc, 10, 10) and "height='1600px'" in depict.svg_for(doc, 5000, 5000)   # clamped
    assert depict.svg_for(PLAIN) is None and depict.svg_for({**PLAIN, "structure": None}) is None
    unreadable = _derived({"chemical_id": "X", "smiles": "not a smiles"})
    assert unreadable["structure"]["source"] is None and depict.svg_for(unreadable) is None
    assert depict.etag_for(doc, None, None) == f'"{doc["structure"]["derived_at"]}-320x240"'


def test_a_mol_block_is_drawn_with_its_own_coordinates_and_a_3d_block_gets_a_layout():
    mol = Chem.MolFromSmiles("CCO")
    rdDepictor.Compute2DCoords(mol)
    conf = mol.GetConformer()
    for i, x in enumerate((0.0, 10.0, 20.0)):
        conf.SetAtomPosition(i, (x, 0.0, 0.0))
    block = Chem.MolToMolBlock(mol)
    doc = _derived({"chemical_id": "X", "mol_block": block})
    assert doc["structure"]["source"] == "mol_block"
    assert depict.drawable(doc) == ("mol_block", block)
    drawn = depict.molecule("mol_block", block)
    pos = [drawn.GetConformer().GetAtomPosition(i).x for i in range(3)]
    assert pos == [0.0, 10.0, 20.0]                       # as drawn, not re-laid out
    assert "<svg" in depict.svg_for(doc)
    three_d = Chem.MolToMolBlock(mol)
    conf.Set3D(True)
    three_d = Chem.MolToMolBlock(mol)
    laid_out = depict.molecule("mol_block", three_d)
    assert not laid_out.GetConformer().Is3D()             # a 3-D block gets a 2-D layout
    # a SMILES source is drawn from the canonical SMILES with computed coordinates
    caffeine = _derived(CAFFEINE)
    assert depict.drawable(caffeine) == ("smiles", caffeine["structure"]["smiles"])   # the canonical form, not what was typed


def test_a_missing_drawing_library_costs_the_picture_only(client, monkeypatch):
    """The drawing module is imported when a picture is asked for, never at start-up:
    an image without the X11 libraries answers 503 on this route and serves everything else."""
    _seed(client, CAFFEINE)
    client.post("/api/chemicals/structures/derive", json={"apply": True})
    depict._svg.cache_clear()

    def broken():
        raise depict.DepictUnavailable("the drawing module could not be loaded (libXrender.so.1 missing)")

    monkeypatch.setattr(depict, "_drawer", broken)
    res = client.get("/api/chemicals/CHEM-000001/structure.svg?w=64&h=64")
    assert res.status_code == 503 and "libXrender" in res.json()["error"]
    assert client.get("/api/chemicals/CHEM-000001").status_code == 200           # the rest of the registry is unaffected
    assert client.get("/api/chemicals/audit").status_code == 200


def _seed(client, *docs):
    for doc in docs:
        assert client.post("/api/chemicals", json=doc).status_code == 201


def test_the_route_answers_the_picture_with_an_etag_and_refuses_what_it_cannot_draw(client):
    _seed(client, CAFFEINE, PLAIN)
    res = client.get("/api/chemicals/CHEM-000001/structure.svg")
    assert res.status_code == 404 and "derive it first" in res.json()["error"]        # not derived yet
    client.post("/api/chemicals/structures/derive", json={"apply": True})
    res = client.get("/api/chemicals/CHEM-000001/structure.svg")
    assert res.status_code == 200 and res.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in res.text and "width='320px'" in res.text
    etag = res.headers["etag"]
    stamp = client.get("/api/chemicals/CHEM-000001").json()["structure"]["derived_at"]
    assert etag == f'"{stamp}-320x240"' and res.headers["cache-control"] == "private, max-age=86400"
    again = client.get("/api/chemicals/CHEM-000001/structure.svg", headers={"If-None-Match": etag})
    assert again.status_code == 304 and again.headers["etag"] == etag
    small = client.get("/api/chemicals/CHEM-000001/structure.svg?w=96&h=72")
    assert small.status_code == 200 and "width='96px' height='72px'" in small.text and small.headers["etag"] == f'"{stamp}-96x72"'
    assert "width='48px'" in client.get("/api/chemicals/CHEM-000001/structure.svg?w=3&h=3").text     # clamped, not refused
    assert client.get("/api/chemicals/CHEM-000002/structure.svg").status_code == 404                  # nothing to draw
    assert client.get("/api/chemicals/CHEM-999999/structure.svg").status_code == 404                  # no such entry
    # the picture is a column once anything is derived, counted by derived structures
    columns = {c["key"]: c for c in client.get("/api/chemicals/columns").json()["columns"]}
    assert columns["structure.picture"] == {"key": "structure.picture", "label": "structure (picture)", "group": "structure", "filled": 1, "coverage": 0.5}
    # the audit says whether an entry can be drawn (for the pictures in the shared-identifier groups and the dialogs)
    _seed(client, {**CAFFEINE, "chemical_id": "CHEM-000003", "name": "Caffeine (again)"})
    client.post("/api/chemicals/structures/derive", json={"chemical_ids": ["CHEM-000003"], "apply": True})
    group = client.get("/api/chemicals/audit").json()["shared"]
    assert group == [] or all("structure_source" in e for g in group for e in g["entries"])


def test_the_script_draws_the_same_picture_to_a_file(client, tmp_path, capsys):
    _seed(client, CAFFEINE, PLAIN)
    db = SessionLocal()
    try:
        assert draw_structure.main(["CHEM-000001"], db) == 1                     # not derived yet
        assert "no derived structure" in capsys.readouterr().err
        client.post("/api/chemicals/structures/derive", json={"apply": True})
        out = tmp_path / "caffeine.svg"
        assert draw_structure.main(["CHEM-000001", "-o", str(out), "--width", "200", "--height", "150"], db) == 0
        assert "bytes of SVG written" in capsys.readouterr().out
        text = out.read_text()
        assert text.startswith("<?xml") and "width='200px' height='150px'" in text
        assert text == client.get("/api/chemicals/CHEM-000001/structure.svg?w=200&h=150").text   # one engine, the same picture
        assert draw_structure.main(["CHEM-000001"], db) == 0 and "<svg" in capsys.readouterr().out
        assert draw_structure.main(["CHEM-000002"], db) == 1 and draw_structure.main(["CHEM-404"], db) == 1
    finally:
        db.close()
