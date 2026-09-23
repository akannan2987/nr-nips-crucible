#!/usr/bin/env python3
"""Derive one structure per registry entry, check it, and say what disagrees (phase CR-12, step A).

The same work the attention page's **Derive structures** button and
`POST /api/chemicals/structures/derive` do: all three call `app.structures`,
so the terminal never reports something the page would not.

For every entry that carries a MOL block, a SMILES or an InChI, RDKit reads
it (in that order, decision S5) and computes the canonical SMILES, the
InChI and InChIKey, the formula, the average weight and the exact mass,
and the counts. The laboratory's own formula, weight and InChI are then
compared with the structure's, and a disagreement is a *structure finding*
for a person to review. Nothing is written without --apply; the entry's
own fields are never changed, the `structure` is stored beside them.

    .venv/bin/python scripts/derive_structures.py                       # report: what would be derived, what disagrees
    .venv/bin/python scripts/derive_structures.py --apply               # write the structure on every entry
    .venv/bin/python scripts/derive_structures.py --ids CHEM-000001 CHEM-000002 --apply
    .venv/bin/python scripts/derive_structures.py --json                # the endpoint's answer, as JSON

On the server, through the shortcut: ./container-py.sh script derive_structures.py [--apply]
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("AUTO_INIT_DB", "false")

from app.database import SessionLocal  # noqa: E402
from app.structures import SOURCE_LABEL, derive_registry  # noqa: E402

SHOWN = 30


def print_report(r: dict) -> None:
    f = r["from"]
    print(f"{r['with_source']:,} of {r['entries']:,} entries carry a structure source.")
    repaired = f" ({r['repaired']} read after removing the outer brackets the source added)" if r["repaired"] else ""
    print(f"Derived {r['derived']:,}: {f['mol_block']:,} from a {SOURCE_LABEL['mol_block']}, {f['smiles']:,} from a {SOURCE_LABEL['smiles']}{repaired}, "
          f"{f['inchi']:,} from an {SOURCE_LABEL['inchi']}; {r['unreadable']:,} could not be read.")
    k = r["findings"]
    print(f"Findings on {k['entries']:,} entries: formula {k['formula']:,}, weight {k['weight']:,}, InChI {k['inchi']:,}, unreadable {k['unreadable']:,}.\n")
    for item in r["items"][:SHOWN]:
        src = item["source"] or "-"
        print(f"  {item['chemical_id']}  {str(item.get('name'))[:44]:<44}  from {src}")
        print(f"        laboratory : formula={item.get('molecular_formula') or '-'}  weight={item.get('molecular_weight') if item.get('molecular_weight') is not None else '-'}")
        if item["source"]:
            print(f"        structure  : formula={item.get('formula')}  weight={item.get('weight')}  exact={item.get('exact_mass')}  fragments={item.get('fragments')}  inchikey={item.get('inchikey')}")
        for reason in item["findings"]:
            print(f"        -> {reason}")
    if len(r["items"]) > SHOWN:
        print(f"  … and {len(r['items']) - SHOWN:,} more (the page lists them all: Chemical Registry -> Needs attention -> Doubtful structures)")
    print()
    if r["applied"]:
        print(f"Applied: {r['written']:,} entries written, {r['unchanged']:,} unchanged, in {r['seconds']} s.")
        print("The findings are on the attention page (Chemical Registry -> Needs attention) and in GET /api/chemicals/audit.")
    else:
        print(f"Report only — nothing written ({r['seconds']} s). Back up (./container-py.sh backup), then re-run with --apply.")


def main(argv: list[str] | None = None, db=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write the derived structure on each entry (report only without it)")
    parser.add_argument("--ids", nargs="+", metavar="CHEM-ID", help="only these entries")
    parser.add_argument("--json", action="store_true", help="print the report as JSON (what the endpoint answers)")
    args = parser.parse_args(argv)

    own = db is None
    db = db or SessionLocal()
    try:
        progress = None if args.json else (lambda n: print(f"  … {n:,} entries read", flush=True))
        report = derive_registry(db, chemical_ids=args.ids, apply=args.apply, progress=progress)
    except KeyError as err:
        print(f"Unknown identifier: {err.args[0]}. Nothing written.")
        return 1
    finally:
        if own:
            db.close()
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
