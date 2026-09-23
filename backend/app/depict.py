"""Draw a derived structure as a picture (phase CR-12, step B; docs/09-structures.md).

One drawing engine, on the server: `GET /api/chemicals/{id}/structure.svg`
answers an SVG image of the entry's *derived* structure (step A stored it
under `structure`), and the browser shows that image in the detail view,
as a thumbnail column and in the dialogs where a person confirms a
compound. The same picture can be saved from the API or drawn by the
script `draw_structure.py`; the browser holds no chemistry library.

Which coordinates. A MOL block is a drawing: it carries the positions the
chemist gave every atom, so an entry whose structure came from its MOL
block is drawn as drawn (unless the block is 3-D or has no positions, in
which case a 2-D layout is computed). Every other entry is drawn from its
canonical SMILES with a layout computed by RDKit's CoordGen, the layout
engine chemists' drawing programs use, so rings and chains look the way
a chemist expects.

Nothing is stored: the picture is computed on request and kept in a small
in-process cache keyed on what was drawn and at what size; the HTTP answer
carries an ETag made from the structure's `derived_at`, so a browser that
already has the picture asks once and is told 304, and a re-derived entry
gets a new picture at once.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from rdkit import Chem, RDLogger
from rdkit.Chem import rdDepictor

RDLogger.DisableLog("rdApp.*")


class DepictUnavailable(RuntimeError):
    """The drawing module could not be loaded: a system library the image lacks."""


def _drawer():
    """RDKit's drawing module, imported only when a picture is asked for.

    It links against X11 libraries (libXrender, libX11, libXext) and expat
    that a slim image does not carry by default; the Dockerfile installs
    them since v2.25.0 (libxrender1, libx11-6, libxext6, libexpat1).
    Imported at module level, a missing library stopped the whole
    application from starting inside the container (found on the
    development machine's rebuild, lesson 44). Imported here, a missing
    library costs the picture route alone, which answers 503 and says why.
    """
    try:
        from rdkit.Chem.Draw import rdMolDraw2D
    except ImportError as err:  # pragma: no cover - exercised by a test through monkeypatching
        raise DepictUnavailable(f"the drawing module could not be loaded ({err}); the image needs libxrender1, libx11-6, libxext6 and libexpat1, which the Dockerfile installs since v2.25.0") from err
    return rdMolDraw2D

MIN_SIZE, MAX_SIZE = 48, 1600
DEFAULT_WIDTH, DEFAULT_HEIGHT = 320, 240
THUMB_WIDTH, THUMB_HEIGHT = 96, 72

try:  # the layout engine of the chemists' drawing programs; RDKit's own layout if it is missing
    rdDepictor.SetPreferCoordGen(True)
except Exception:  # pragma: no cover
    pass


def clamp(value: Any, default: int) -> int:
    """A requested size, kept between the smallest legible and the largest reasonable."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(MIN_SIZE, min(MAX_SIZE, n))


def drawable(doc: dict[str, Any]) -> tuple[str, str] | None:
    """What to draw for an entry: ('mol_block', the block) or ('smiles', the canonical SMILES); None without a derived structure."""
    structure = doc.get("structure") or {}
    if not structure.get("source"):
        return None
    if structure["source"] == "mol_block" and doc.get("mol_block"):
        return "mol_block", str(doc["mol_block"])
    smiles = structure.get("smiles")
    return ("smiles", str(smiles)) if smiles else None


def molecule(kind: str, text: str) -> Chem.Mol | None:
    """The molecule with 2-D coordinates: the block's own when it has them, computed otherwise."""
    if kind == "mol_block":
        mol = Chem.MolFromMolBlock(text)
        if mol is None:
            return None
        if mol.GetNumConformers() == 0 or mol.GetConformer().Is3D():
            rdDepictor.Compute2DCoords(mol)
        return mol
    mol = Chem.MolFromSmiles(text)
    if mol is None:
        return None
    rdDepictor.Compute2DCoords(mol)
    return mol


def render(mol: Chem.Mol, width: int, height: int) -> str:
    """The SVG text of one molecule at one size; a transparent background, so it sits on any card."""
    rdMolDraw2D = _drawer()
    drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
    drawer.drawOptions().clearBackground = False
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol)
    drawer.FinishDrawing()
    return drawer.GetDrawingText()


@lru_cache(maxsize=4096)
def _svg(kind: str, text: str, width: int, height: int) -> str | None:
    mol = molecule(kind, text)
    return None if mol is None else render(mol, width, height)


def svg_for(doc: dict[str, Any], width: Any = None, height: Any = None) -> str | None:
    """The picture of an entry's derived structure, or None when there is none to draw."""
    what = drawable(doc)
    if what is None:
        return None
    return _svg(what[0], what[1], clamp(width, DEFAULT_WIDTH), clamp(height, DEFAULT_HEIGHT))


def etag_for(doc: dict[str, Any], width: Any, height: Any) -> str:
    """A tag that changes when the structure is re-derived or another size is asked for."""
    stamp = (doc.get("structure") or {}).get("derived_at") or "none"
    return f'"{stamp}-{clamp(width, DEFAULT_WIDTH)}x{clamp(height, DEFAULT_HEIGHT)}"'
