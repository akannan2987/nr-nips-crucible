#!/usr/bin/env python3
"""
=============================================================
Crucible — PubChem API Integration Demo
=============================================================

Demonstrates how the Crucible FastAPI backend could enrich chemical
records from PubChem (a free public database — no authentication needed).

RUN:  python docs/api-demo.py

Uses the Python standard library only (urllib), so it runs without
installing anything or activating the backend virtualenv.
=============================================================
"""

import json
import urllib.parse
import urllib.request

PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"


# ─────────────────────────────────────────────────────────────
# HELPER: simple GET returning parsed JSON (stdlib only)
# ─────────────────────────────────────────────────────────────
def http_get_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "Crucible/2.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310 (fixed https host)
        return json.load(resp)


# ═════════════════════════════════════════════════════════════
# 1. PUBCHEM lookups — public, free, no authentication needed
#    Docs: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
# ═════════════════════════════════════════════════════════════
def pubchem_lookup_by_cas(cas: str) -> dict:
    print(f'\n🔬 PubChem: looking up CAS number "{cas}"...')
    url = (
        f"{PUBCHEM}/name/{urllib.parse.quote(cas)}"
        "/property/MolecularFormula,MolecularWeight,IUPACName,InChI,InChIKey,CanonicalSMILES/JSON"
    )
    props = http_get_json(url)["PropertyTable"]["Properties"][0]
    print("  ✅ Found:")
    print(f"     CID:               {props.get('CID')}")
    print(f"     IUPAC Name:        {props.get('IUPACName')}")
    print(f"     Molecular Formula: {props.get('MolecularFormula')}")
    print(f"     Molecular Weight:  {props.get('MolecularWeight')}")
    print(f"     SMILES:            {props.get('CanonicalSMILES')}")
    print(f"     InChIKey:          {props.get('InChIKey')}")
    return props


def pubchem_lookup_by_name(name: str) -> dict:
    print(f'\n🔬 PubChem: looking up compound name "{name}"...')
    url = (
        f"{PUBCHEM}/name/{urllib.parse.quote(name)}"
        "/property/MolecularFormula,MolecularWeight,IUPACName,CanonicalSMILES,InChIKey/JSON"
    )
    props = http_get_json(url)["PropertyTable"]["Properties"][0]
    print("  ✅ Found:")
    print(f"     CID:               {props.get('CID')}")
    print(f"     IUPAC Name:        {props.get('IUPACName')}")
    print(f"     Molecular Formula: {props.get('MolecularFormula')}")
    print(f"     Molecular Weight:  {props.get('MolecularWeight')}")
    print(f"     SMILES:            {props.get('CanonicalSMILES')}")
    return props


def pubchem_get_synonyms(cid: int) -> list[str]:
    print(f"\n🔬 PubChem: getting synonyms for CID {cid}...")
    url = f"{PUBCHEM}/cid/{cid}/synonyms/JSON"
    synonyms = http_get_json(url)["InformationList"]["Information"][0]["Synonym"][:10]
    print("  ✅ First 10 synonyms:")
    for i, s in enumerate(synonyms, start=1):
        print(f"     {i}. {s}")
    return synonyms


def pubchem_search_by_smiles(smiles: str) -> dict:
    print(f'\n🔬 PubChem: searching by SMILES "{smiles}"...')
    url = (
        f"{PUBCHEM}/smiles/{urllib.parse.quote(smiles)}"
        "/property/MolecularFormula,MolecularWeight,IUPACName/JSON"
    )
    props = http_get_json(url)["PropertyTable"]["Properties"][0]
    print("  ✅ Found:")
    print(f"     CID:               {props.get('CID')}")
    print(f"     IUPAC Name:        {props.get('IUPACName')}")
    print(f"     Molecular Formula: {props.get('MolecularFormula')}")
    print(f"     Molecular Weight:  {props.get('MolecularWeight')}")
    return props


# ═════════════════════════════════════════════════════════════
# 2. HOW TO INTEGRATE INTO THE CRUCIBLE FastAPI BACKEND
# ═════════════════════════════════════════════════════════════
def show_integration_example() -> None:
    print(
        r"""
╔═══════════════════════════════════════════════════════════════╗
║  📋 How to add a PubChem lookup route to the FastAPI backend   ║
╚═══════════════════════════════════════════════════════════════╝

Create a new router file: backend/app/routers/external.py

───────────────────────────────────────────────────────────────
import json
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/external", tags=["external"])


@router.get("/pubchem/{identifier}")
def pubchem_lookup(identifier: str) -> dict:
    \"\"\"Look up a compound in PubChem by CAS number or name.\"\"\"
    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
        f"{urllib.parse.quote(identifier)}"
        "/property/MolecularFormula,MolecularWeight,IUPACName,CanonicalSMILES,InChIKey/JSON"
    )
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.load(resp)
        return data["PropertyTable"]["Properties"][0]
    except Exception:
        # Same {"error": ...} shape the rest of the API uses (see main.py)
        raise HTTPException(status_code=404, detail="Compound not found in PubChem")
───────────────────────────────────────────────────────────────

Then register it in backend/app/main.py, next to the other routers:

    from .routers import chemicals, samples, screening, stats, toxicology, external
    ...
    application.include_router(external.router)

(For production use, prefer an async HTTP client such as httpx and add a
short timeout + caching, since PubChem is an external dependency.)
"""
    )


# ═════════════════════════════════════════════════════════════
# MAIN — run the demos
# ═════════════════════════════════════════════════════════════
def main() -> None:
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║  🧪 Crucible — PubChem API Integration Demo                    ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print("\n" + "═" * 60)
    print("  PUBCHEM API DEMOS (live calls — no auth needed)")
    print("═" * 60)

    demos = [
        lambda: pubchem_lookup_by_cas("58-08-2"),   # Caffeine
        lambda: pubchem_lookup_by_name("Aspirin"),
        lambda: pubchem_lookup_by_name("Vanillin"),
        lambda: pubchem_get_synonyms(2519),          # Caffeine CID
        lambda: pubchem_search_by_smiles("CCO"),     # Ethanol
    ]
    for demo in demos:
        try:
            demo()
        except Exception as err:  # network/parse errors shouldn't abort the whole demo
            print(f"  ❌ PubChem error: {err}")

    show_integration_example()
    print("Done.\n")


if __name__ == "__main__":
    main()
