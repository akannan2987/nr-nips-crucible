#!/usr/bin/env python3
"""Turn the unlinked report into a chemicals upload you can review.

Identification refuses to register a compound unless its name and its CAS
number agree in PubChem. A large group fails that test with a perfectly good
CAS number, purely because the laboratory writes names in its own style —
`Phenol, 2,4-di-tertiobutyl` for 2,4-di-tert-butylphenol, or `tertiobutyl`
where PubChem expects `tert-butyl`. The compound is not in doubt; only the
spelling is.

This reads those rows, looks each CAS up in PubChem (which does resolve), and
writes a chemicals upload file carrying the laboratory's own name alongside the
retrieved chemistry.

**Nothing is registered by this script.** It produces a file for a person to
look at. Uploading it is the act of vouching for those compounds — which is
exactly the evidence the strict rule was asking for, supplied by someone
qualified to give it rather than inferred from a name.

    .venv/bin/python scripts/propose_chemicals.py unlinked.csv -o proposed.csv
    .venv/bin/python scripts/propose_chemicals.py unlinked.csv -o proposed.xlsx

Review the file, delete anything you disagree with, then upload it through
Chemicals → Upload. Every screening row for those compounds links immediately,
with no further PubChem involvement.
"""

import argparse
import csv
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("AUTO_INIT_DB", "false")

from app.utils.pubchem import PubChemClient  # noqa: E402

# The chemicals upload template's own column names.
HEADER = [
    "DTX_ID",
    "NESTLE_ID",
    "CHEMICAL_NAME",
    "CAS_NO",
    "MOL_WEIGHT_ORIG",
    "MOL_FORMULA",
    "Supplier_ref",
    "SMILES",
    "InChIKey",
    "PUBCHEM_NAME",
]

# Reasons worth proposing. A compound with no CAS cannot be corroborated at
# all, so it is not offered here — there is nothing to look up.
DEFAULT_REASONS = ("name not in PubChem",)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", help="the unlinked.csv written by link_pubchem.py")
    parser.add_argument("-o", "--out", default="proposed-chemicals.csv")
    parser.add_argument(
        "--reason",
        action="append",
        default=None,
        help=f"which reasons to include (default: {DEFAULT_REASONS[0]!r})",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--ca-bundle", default=None)
    args = parser.parse_args()

    reasons = tuple(args.reason or DEFAULT_REASONS)

    with open(args.report, newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("reason") in reasons]

    # One compound per CAS: the same substance appears under several spellings,
    # and proposing it twice would create the duplicate this whole exercise
    # exists to avoid.
    seen: dict[str, str] = {}
    for row in rows:
        cas = (row.get("cas") or "").strip()
        if cas and cas not in seen:
            seen[cas] = (row.get("compound_name") or "").strip()

    items = list(seen.items())
    if args.limit:
        items = items[: args.limit]

    print(f"{len(rows)} rows -> {len(items)} distinct compounds to look up\n")
    client = PubChemClient(ca_bundle=args.ca_bundle)
    proposed: list[list] = []
    missing = 0
    started = time.time()

    for index, (cas, name) in enumerate(items, start=1):
        found = client.lookup(None, cas)
        if found is None:
            missing += 1
        else:
            fields = found.as_chemical_fields()
            proposed.append(
                [
                    "",  # DTX_ID — yours to fill in, left empty on purpose
                    "",  # NESTLE_ID
                    name,  # the laboratory's own name is kept, not replaced
                    cas,
                    fields.get("molecular_weight") or "",
                    fields.get("molecular_formula") or "",
                    "",  # Supplier_ref
                    fields.get("smiles") or "",
                    fields.get("inchi_key") or "",
                    fields.get("pubchem_title") or "",
                ]
            )
        if index % 25 == 0 or index == len(items):
            rate = index / max(time.time() - started, 1e-6)
            print(
                f"  {index}/{len(items)}  resolved={len(proposed)} missing={missing}"
                f"  ~{(len(items) - index) / rate / 60:.0f} min left",
                flush=True,
            )

    out = Path(args.out)
    if out.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import Workbook
        from openpyxl.styles import Font

        wb = Workbook()
        ws = wb.active
        ws.title = "Chemicals"
        ws.append(HEADER)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        ws.freeze_panes = "A2"
        for row in proposed:
            ws.append(row)
        wb.save(out)
    else:
        with open(out, "w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADER)
            writer.writerows(proposed)

    print(f"\n{len(proposed)} compounds written to {out}")
    if missing:
        print(f"{missing} CAS numbers did not resolve and were left out.")
    if client.throttled:
        print(f"PubChem throttled {client.throttled} times — re-run to fill the gaps.")
    print(
        "\nNothing has been registered. Review the file, remove anything you\n"
        "disagree with, then upload it through Chemicals -> Upload.\n"
        "PUBCHEM_NAME is there so you can compare what PubChem calls each\n"
        "compound against your own name; the upload ignores that column."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
