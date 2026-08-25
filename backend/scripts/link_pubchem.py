#!/usr/bin/env python3
"""Register unidentified screening compounds, but only when PubChem is certain.

Importing links a screening row to a chemical only when that compound is
already registered. This is the second step: for everything still unlinked, ask
PubChem, and register the compound **only when the name and the CAS number both
resolve to the same PubChem compound**.

That 1:1 rule is the whole point. A CAS number alone is not enough — what was
measured is often a salt, hydrate or complex whose CAS belongs to a different
substance than the name suggests — and a name alone is not enough either,
because laboratory names are ambiguous. Requiring both to agree means a link is
only made when there is no realistic doubt.

Compounds that fail the test are left unlinked rather than guessed at. An
unidentified peak is a real observation; inventing an identity for it would be
worse than leaving it as it is.

    .venv/bin/python scripts/link_pubchem.py            # dry run, reports only
    .venv/bin/python scripts/link_pubchem.py --apply    # register and link
"""

import argparse
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("AUTO_INIT_DB", "false")

from app.compat import now_iso  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Chemical, Screening  # noqa: E402
from app.store import (  # noqa: E402
    all_docs,
    all_rows,
    insert_docs_bulk,
    next_chemical_id,
    replace_doc,
)
from app.utils.cleaning import collapse_whitespace, parse_cas_numbers  # noqa: E402
from app.utils.pubchem import PubChemClient  # noqa: E402

import uuid  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    parser.add_argument("--limit", type=int, default=0, help="stop after N compounds")
    parser.add_argument("--ca-bundle", default=None)
    parser.add_argument("--batch", type=int, default=20, help="write every N confirmed compounds")
    args = parser.parse_args()

    db = SessionLocal()
    client = PubChemClient(ca_bundle=args.ca_bundle)

    # Group the unlinked rows by the compound they describe, so each distinct
    # compound is looked up once rather than once per row.
    # Already-registered compounds are skipped, so a re-run continues rather
    # than repeating work.
    # CAS number -> the identifier this application gave that compound.
    cas_to_id = {
        d["cas_number"]: d["chemical_id"]
        for d in all_docs(db, Chemical)
        if d.get("cas_number") and d.get("chemical_id")
    }
    known = set(cas_to_id.values())

    rows = all_rows(db, Screening)
    pending: dict[tuple[str, str], list] = defaultdict(list)
    for row in rows:
        if row.doc.get("chemical_id"):
            continue
        name = collapse_whitespace(row.doc.get("compound_name"))
        cas_values = parse_cas_numbers(row.doc.get("cas"))
        cas = cas_values[0] if cas_values else ""
        if cas and cas in cas_to_id:
            # Registered by an earlier run; link without asking PubChem again.
            doc = dict(row.doc)
            doc["chemical_id"] = cas_to_id[cas]
            replace_doc(db, row, doc)
            continue
        if name or cas:
            pending[(name, cas)].append(row)

    compounds = list(pending.items())
    if args.limit:
        compounds = compounds[: args.limit]

    print(f"{sum(len(v) for _, v in compounds)} unlinked rows across {len(compounds)} compounds")
    print("Registering only where the name and the CAS agree in PubChem.\n")

    linked_rows = confirmed = rejected = no_cas = not_found = 0
    new_chemicals: list[dict] = []
    started = time.time()

    for index, ((name, cas), members) in enumerate(compounds, start=1):
        if not cas:
            # Without a CAS there is nothing to corroborate the name against,
            # so the 1:1 test cannot be satisfied.
            no_cas += 1
        else:
            by_cas = client.lookup(None, cas)
            by_name = client.lookup(name, None) if name else None
            if by_cas is None or by_name is None:
                not_found += 1
            elif by_cas.cid != by_name.cid:
                # The name and the CAS describe different substances — exactly
                # the salt/complex case this rule exists to catch.
                rejected += 1
            else:
                confirmed += 1
                chemical_id = cas_to_id.get(cas)
                if chemical_id is None:
                    chemical_id = next_chemical_id(db, len(new_chemicals))
                    cas_to_id[cas] = chemical_id
                # The same CAS can arrive under several spellings of the name
                # ("Hexadecane (posh)" and "hexadecane"). They are one
                # substance, so it is registered once and every spelling links
                # to it — registering twice would violate the unique key.
                already = chemical_id in known
                fields = by_cas.as_chemical_fields()
                stamp = now_iso()
                known.add(chemical_id)
                if not already:
                    new_chemicals.append(
                        {
                            "id": str(uuid.uuid4()),
                            "chemical_id": chemical_id,
                            "name": name or fields.get("pubchem_title") or "Unknown",
                            "cas_number": cas,
                            **fields,
                            "pubchem_status": "found",
                            "identification": "pubchem name+cas agree",
                            "created_at": stamp,
                            "updated_at": stamp,
                        }
                    )
                for row in members:
                    doc = dict(row.doc)
                    doc["chemical_id"] = chemical_id
                    # `replace_doc` rather than assigning `row.doc`: the
                    # indexed `chemical_id` column has to be kept in step with
                    # the document, and that column is what "screening for this
                    # chemical" queries. Writing only the document leaves the
                    # link invisible to every lookup.
                    replace_doc(db, row, doc)
                    linked_rows += 1

        # Write as we go. A run over several thousand compounds takes more than
        # an hour, and holding it all in one transaction means a single network
        # fault throws the whole thing away — which has already happened once.
        if args.apply and len(new_chemicals) >= args.batch:
            insert_docs_bulk(db, Chemical, new_chemicals)
            db.commit()
            new_chemicals = []

        if index % 25 == 0 or index == len(compounds):
            rate = index / max(time.time() - started, 1e-6)
            print(
                f"  {index}/{len(compounds)}  confirmed={confirmed} "
                f"rejected={rejected} no_cas={no_cas} not_found={not_found} "
                f"~{(len(compounds) - index) / rate / 60:.0f} min left",
                flush=True,
            )

    print(
        f"\nConfirmed {confirmed} compounds ({linked_rows} rows).\n"
        f"  rejected (name and CAS disagree): {rejected}\n"
        f"  no CAS to corroborate the name:   {no_cas}\n"
        f"  not in PubChem:                   {not_found}"
    )

    if args.apply:
        insert_docs_bulk(db, Chemical, new_chemicals)
        db.commit()
        print(f"\nApplied: {confirmed} chemicals registered, {linked_rows} rows linked.")
    else:
        db.rollback()
        print("\nDry run — nothing written. Re-run with --apply.")
    if client.failures:
        print(f"{client.failures} lookups gave up after retries; re-run to retry them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
