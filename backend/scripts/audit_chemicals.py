#!/usr/bin/env python3
"""List everything in the registry that needs a person's eye.

The same audit the browser's attention page shows (Chemical Registry →
Needs attention) and the API answers at `GET /api/chemicals/audit`: all
three call `app.audit`, so a mark left in the browser is seen here and the
terminal never lists something the page does not.

Five kinds of thing, in this order:

* entries sharing a CAS number, DTXSID or PubChem compound id with another;
* compounds whose batches disagree on a column, each batch's value shown;
* entries still waiting for their identifier from the screening data;
* entries whose formula contradicts their own name — a name saying
  *hexadecanoate* claims sixteen carbons; a formula with seven disagrees,
  and no naming convention explains it. (Comparing the two *names* does not
  work: `Monostearin` and `Glycerol, 1-monooctadecanoate` share no words
  and are one substance.);
* entries whose derived structure disagrees with the formula, weight or
  InChI the source recorded beside it (CR-12; derived on request by
  `derive_structures.py`, listed here).

It decides nothing — it sorts, so somebody reviewing hundreds of entries
meets the doubtful ones first. Items a person has marked reviewed are shown
last, greyed with the word *reviewed*, and do not count on the banner.

    .venv/bin/python scripts/audit_chemicals.py              # what needs attention
    .venv/bin/python scripts/audit_chemicals.py --all        # plus every entry the formula check passed, ranked
    .venv/bin/python scripts/audit_chemicals.py --json       # the endpoint's answer, as JSON
    .venv/bin/python scripts/audit_chemicals.py -o ids.txt   # doubtful-formula ids for remove_chemicals.py
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("AUTO_INIT_DB", "false")

# Re-exported so anything that imported the checks from here still works.
from app.audit import (  # noqa: E402, F401
    CHAIN_CARBONS,
    HETEROATOMS,
    audit_registry,
    formula_carbons,
    formula_elements,
    implied_carbons,
    unexplained_heteroatoms,
)
from app.database import SessionLocal  # noqa: E402

KIND_LABEL = {"cas": "CAS", "dtxsid": "DTXSID", "pubchem": "PubChem"}


def _entry_line(e: dict) -> str:
    rows = e.get("linked_rows")
    tail = f"  {rows} row{'' if rows == 1 else 's'} linked" if rows else ""
    return (f"{e['chemical_id']}  {str(e.get('name'))[:48]:<48}  cas={e.get('cas_number') or '-'}"
            f"  dtx={e.get('dtx_id') or '-'}  cid={e.get('pubchem_cid') or '-'}  formula={e.get('molecular_formula') or '-'}{tail}")


def print_report(result: dict, show_all: bool) -> None:
    c = result["counts"]
    print(f"{c['attention']} thing{'' if c['attention'] == 1 else 's'} need attention"
          f" ({c['shared_groups']} shared identifiers, {c['batch_conflicts']} batch conflicts,"
          f" {c['pending']} pending identifiers, {c['formula']} doubtful formulas, {c.get('structure', 0)} doubtful structures); {c['reviewed']} reviewed.\n")

    if result["shared"]:
        print("Shared identifiers — two or more entries with one identifier (kept on purpose; a person decides):")
        for g in result["shared"]:
            mark = "  reviewed" if g["reviewed"] else ""
            print(f"  {KIND_LABEL[g['kind']]} {g['value']}  shared by {len(g['entries'])}{mark}")
            for e in g["entries"]:
                print(f"      {_entry_line(e)}")
        print()

    if result["batch_conflicts"]:
        print("Batch conflicts — the batches of one compound disagree on a column:")
        for item in result["batch_conflicts"]:
            mark = "  reviewed" if item["reviewed"] else ""
            print(f"  {item['chemical_id']}  {item.get('name')}{mark}")
            for col in item["columns"]:
                values = "; ".join(f"batch {v['batch']}: {v['value'] if v['value'] not in (None, '') else '(blank)'}" for v in col["values"])
                print(f"      {col['column']}: {values}")
        print()

    if result["pending"]:
        print("Pending identifiers — to come from the screening data, or set by hand:")
        for item in result["pending"]:
            print(f"  {item['chemical_id']}  {str(item.get('name'))[:48]}  supplier={item.get('supplier') or '-'}")
        print()

    print(f"{result['checked']} entries checked for chemistry ({result['skipped']} skipped for having no formula).")
    doubtful = result["formula"]
    print(f"{len(doubtful)} look{'s' if len(doubtful) == 1 else ''} doubtful.\n")
    shown = doubtful + (result.get("passed") or [] if show_all else [])
    for item in shown:
        if item.get("reasons"):
            mark = "  ??" if not item.get("reviewed") else "  ..  reviewed"
        else:
            mark = "  ok"
        print(f"{mark}  {item['chemical_id']}")
        print(f"        yours   : {item.get('name')}")
        print(f"        pubchem : {item.get('pubchem_name') or '(none recorded)'}")
        print(f"        cas={item.get('cas_number')}  formula={item.get('molecular_formula')}  mw={item.get('molecular_weight')}")
        for reason in item.get("reasons") or []:
            print(f"        -> {reason}")
        print()

    structures = result.get("structures") or []
    ss = result.get("structures_summary") or {}
    if ss:
        print(f"Structures: {ss.get('with_source', 0)} entries carry a structure source, {ss.get('derived', 0)} derived, "
              f"{ss.get('to_derive', 0)} still to derive (scripts/derive_structures.py --apply), {ss.get('findings', 0)} with a finding.")
    if structures:
        print("Doubtful structures — the derived structure disagrees with the formula, weight or InChI the source recorded beside it:")
        for item in structures:
            mark = "  reviewed" if item["reviewed"] else ""
            s = item.get("structure") or {}
            print(f"  {item['chemical_id']}  {str(item.get('name'))[:44]}{mark}")
            print(f"        laboratory : formula={item.get('molecular_formula') or '-'}  weight={item.get('molecular_weight') if item.get('molecular_weight') is not None else '-'}")
            if s.get("source"):
                print(f"        structure  : from {s.get('source')}  formula={s.get('formula')}  weight={s.get('weight')}  exact={s.get('exact_mass')}  inchikey={s.get('inchikey')}")
            for reason in item.get("reasons") or []:
                print(f"        -> {reason}")
        print()

    print(
        "This flags contradictions it can measure, not everything that is wrong.\n"
        "An entry it passes may still be mismatched — a wrong CAS pointing at a\n"
        "compound of similar size will not show up here. Read the pairs.\n"
        "The same list, with buttons: Chemical Registry → Needs attention in the browser."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="also show every entry the formula check passed, ranked")
    parser.add_argument("--json", action="store_true", help="print the audit as JSON (what GET /api/chemicals/audit answers)")
    parser.add_argument("-o", "--out", help="write the doubtful-formula identifiers to a file")
    args = parser.parse_args(argv)

    db = SessionLocal()
    result = audit_registry(db, with_links=True, everything=args.all)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print_report(result, args.all)

    flagged = [f for f in result["formula"] if not f["reviewed"]]
    if args.out and flagged:
        Path(args.out).write_text("".join(f"{f['chemical_id']}\n" for f in flagged))
        print(f"\n{len(flagged)} identifiers written to {args.out}")
        print("Review them, delete the lines you want to KEEP, then:")
        print(f"  scripts/remove_chemicals.py --from-file {args.out} --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
