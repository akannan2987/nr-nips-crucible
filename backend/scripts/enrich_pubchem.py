#!/usr/bin/env python3
"""Fill in missing chemical metadata from PubChem.

Screening imports create a chemical for every compound they mention, but those
entries carry only a name and (less than half the time) a CAS number. This
looks each one up in PubChem and adds formula, molecular weight, SMILES,
InChI/InChIKey and the IUPAC name.

Run it from the `backend/` directory:

    .venv/bin/python scripts/enrich_pubchem.py                 # everything unenriched
    .venv/bin/python scripts/enrich_pubchem.py --limit 200     # a first taste
    .venv/bin/python scripts/enrich_pubchem.py --retry-misses  # re-try past failures

**Resumable.** Every chemical records the outcome of its lookup, so re-running
skips what has already been tried. Interrupt it whenever you like; nothing is
lost and the next run continues where this one stopped.

**Rate.** PubChem asks for at most five requests a second, so roughly 25
minutes for 3,000 compounds. That is a property of being a polite client, not
of this script being slow.

Note this sends compound names and CAS numbers to an external service (the US
National Library of Medicine).
"""

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("AUTO_INIT_DB", "false")

from app.database import SessionLocal  # noqa: E402
from app.models import Chemical  # noqa: E402
from app.store import all_rows  # noqa: E402
from app.utils.pubchem import PubChemClient  # noqa: E402


def needs_lookup(doc: dict, retry_misses: bool) -> bool:
    """True when this chemical has not been looked up yet.

    `pubchem_status` records the outcome so a second run does not repeat work:
    `found` is done, `not_found` is skipped unless `--retry-misses` is given.
    """
    status = doc.get("pubchem_status")
    if status is None:
        return True
    if status == "not_found" and retry_misses:
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="stop after N lookups")
    parser.add_argument(
        "--retry-misses", action="store_true", help="try compounds that previously found nothing"
    )
    parser.add_argument(
        "--ca-bundle", default=None, help="PEM of trusted roots (corporate proxy networks)"
    )
    parser.add_argument("--batch", type=int, default=25, help="commit every N updates")
    args = parser.parse_args()

    db = SessionLocal()
    client = PubChemClient(ca_bundle=args.ca_bundle)

    rows = [r for r in all_rows(db, Chemical) if needs_lookup(r.doc, args.retry_misses)]
    if args.limit:
        rows = rows[: args.limit]

    total = len(rows)
    if not total:
        print("Nothing to enrich — every chemical has been looked up.")
        return 0

    print(f"Looking up {total} chemicals in PubChem (~{total * 0.5 / 60:.0f} min)…\n")
    found = missed = 0
    started = time.time()

    for index, row in enumerate(rows, start=1):
        doc = dict(row.doc)
        name = doc.get("name")
        cas = doc.get("cas_number")

        result = client.lookup(name, cas)
        if result:
            doc.update(result.as_chemical_fields())
            doc["pubchem_status"] = "found"
            found += 1
        else:
            # Left as-is on purpose: an unidentified peak is a real observation,
            # and inventing metadata for it would be worse than having none.
            doc["pubchem_status"] = "not_found"
            missed += 1

        row.doc = doc  # a NEW dict, so SQLAlchemy notices the JSON changed
        if index % args.batch == 0 or index == total:
            db.commit()
            rate = index / max(time.time() - started, 1e-6)
            remaining = (total - index) / rate if rate else 0
            print(
                f"  {index}/{total}  found={found} missed={missed}  "
                f"{rate:.1f}/s  ~{remaining / 60:.0f} min left",
                flush=True,
            )

    db.commit()
    print(f"\nDone. {found} enriched, {missed} not in PubChem, {client.requests_made} requests.")
    if client.last_error:
        print(f"Last transport error seen: {client.last_error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
