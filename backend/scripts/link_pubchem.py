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

from sqlalchemy.exc import OperationalError  # noqa: E402

from app.compat import now_iso  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Chemical, Screening  # noqa: E402
from app.store import (  # noqa: E402
    all_docs,
    all_rows,
    insert_docs_bulk,
    next_chemical_id,
)
from app.utils.cleaning import collapse_whitespace, parse_cas_numbers  # noqa: E402
from app.utils.pubchem import PubChemClient  # noqa: E402

import uuid  # noqa: E402


def commit(db, attempts: int = 5) -> None:
    """Commit, waiting out a busy database rather than dying on it.

    SQLite blocks writers while a reader holds the file. A long read in the
    application — and until recently the column endpoint could scan every
    document on a request — can outlast the connection's busy timeout, which
    surfaces as `database is locked`. Unhandled, that ends a run that has been
    going for an hour, and because the failure happens at a commit the run also
    loses whatever it had not yet written.

    Retrying costs nothing and turns a fatal error into a pause.
    """
    for attempt in range(attempts):
        try:
            db.commit()
            return
        except OperationalError as err:
            if "locked" not in str(err).lower() and "busy" not in str(err).lower():
                raise
            db.rollback()
            wait = 2.0 * (attempt + 1)
            print(f"  database busy, retrying commit in {wait:.0f}s", flush=True)
            time.sleep(wait)
    # Out of attempts: raise, so the caller sees a real failure rather than
    # silently continuing with uncommitted work.
    db.commit()


def _note(handle, collected, name: str, cas: str, reason: str) -> None:
    """Record an unlinked compound, to memory and to the report file at once."""
    collected.append((name, cas, reason))
    if handle is not None:
        handle.write(f'"{name}","{cas}","{reason}"\n')


def main() -> int:
    try:
        return _run()
    except Exception:  # noqa: BLE001 - a long run must explain how it ended
        import traceback

        print("\nRun ended early:", flush=True)
        traceback.print_exc()
        print(
            "\nWork already committed is kept. Re-running resumes from there.",
            flush=True,
        )
        return 1


def _run() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    parser.add_argument("--limit", type=int, default=0, help="stop after N compounds")
    parser.add_argument("--ca-bundle", default=None)
    parser.add_argument("--batch", type=int, default=20, help="write every N confirmed compounds")
    parser.add_argument(
        "--report", default=None, help="write the unlinked compounds and why to a CSV"
    )
    args = parser.parse_args()

    db = SessionLocal()
    client = PubChemClient(ca_bundle=args.ca_bundle)

    # Group the unlinked rows by the compound they describe, so each distinct
    # compound is looked up once rather than once per row.
    # Already-registered compounds are skipped, so a re-run continues rather
    # than repeating work.
    # CAS number -> the identifier this application gave that compound.
    cas_to_id: dict[str, str] = {}
    name_to_id: dict[str, str] = {}
    cas_of: dict[str, str] = {}
    # PubChem's own compound id. Two CAS numbers can legitimately resolve to
    # one compound — a substance and its hydrate, say — so keying only on CAS
    # lets the same substance be registered twice under different numbers.
    # This map is what stops that.
    cid_to_id: dict[int, str] = {}
    for d in all_docs(db, Chemical):
        chemical_id = d.get("chemical_id")
        if not chemical_id:
            continue
        if d.get("cas_number"):
            cas = str(d["cas_number"]).strip()
            cas_to_id.setdefault(cas, chemical_id)
            cas_of.setdefault(chemical_id, cas)
        if d.get("name"):
            name_to_id.setdefault(collapse_whitespace(d["name"]).lower(), chemical_id)
        if d.get("pubchem_cid"):
            cid_to_id.setdefault(int(d["pubchem_cid"]), chemical_id)
    known = set(cas_to_id.values())

    rows = all_rows(db, Screening)
    resumed = 0
    pending: dict[tuple[str, str], list] = defaultdict(list)
    for row in rows:
        if row.doc.get("chemical_id"):
            continue
        name = collapse_whitespace(row.doc.get("compound_name"))
        cas_values = parse_cas_numbers(row.doc.get("cas"))
        cas = cas_values[0] if cas_values else ""
        # Already-registered compounds are linked without asking PubChem, by
        # CAS first and then by name — the same order the upload uses. Matching
        # on CAS alone (an earlier version) left rows unlinked whenever the
        # registered compound had a name but no CAS number, which is exactly
        # the case a manually curated registry produces.
        existing = cas_to_id.get(cas) if cas else None
        if existing is None and name:
            candidate = name_to_id.get(name.lower())
            # Same rule as the upload: a name match is refused when the row's
            # CAS contradicts the one recorded against that compound.
            if candidate is not None:
                known = cas_of.get(candidate)
                if not (cas and known and known != cas):
                    existing = candidate
        if existing is not None:
            doc = dict(row.doc)
            doc["chemical_id"] = existing
            row.doc = doc
            row.chemical_id = existing
            resumed += 1
            continue
        if name or cas:
            pending[(name, cas)].append(row)

    if resumed:
        if args.apply:
            commit(db)
        print(f"Re-linked {resumed} rows to compounds registered by an earlier run.")

    compounds = list(pending.items())
    if args.limit:
        compounds = compounds[: args.limit]

    print(f"{sum(len(v) for _, v in compounds)} unlinked rows across {len(compounds)} compounds")
    print("Registering only where the name and the CAS agree in PubChem.\n", flush=True)

    # The report is written as the run proceeds, not at the end. A run of this
    # length can be interrupted — by a restart, a kill, or a fault — and a
    # report that only exists on clean completion is exactly the report you do
    # not have when you need it most.
    report_handle = None
    if args.report:
        report_handle = open(args.report, "w", buffering=1)
        report_handle.write("compound_name,cas,reason\n")

    linked_rows = confirmed = rejected = no_cas = not_found = 0
    name_unknown = cas_unknown = 0
    pending_writes = 0
    unlinked_detail: list[tuple[str, str, str]] = []
    new_chemicals: list[dict] = []
    started = time.time()

    for index, ((name, cas), members) in enumerate(compounds, start=1):
        if not cas:
            # Without a CAS there is nothing to corroborate the name against,
            # so the 1:1 test cannot be satisfied. Recorded in the report like
            # every other unlinked compound — it is the largest category, and a
            # report that omitted it would understate the work outstanding.
            no_cas += 1
            _note(report_handle, unlinked_detail, name, "", "no CAS to corroborate the name")
        else:
            by_cas = client.lookup(None, cas)
            # Only the CID matters here — it is compared against the CAS's
            # CID and never stored, so the property fetch is skipped.
            by_name = client.lookup(name, None, cid_only=True) if name else None
            if by_cas is not None and by_name is None:
                # The CAS resolves but PubChem does not recognise the name.
                # Usually a house naming style rather than a doubtful identity
                # — 'Phenol, 2,4-di-tertiobutyl' is a real compound written the
                # way this laboratory writes it. Counted separately so the cost
                # of requiring both identifiers stays visible.
                name_unknown += 1
                _note(report_handle, unlinked_detail, name, cas, "name not in PubChem")
            elif by_cas is None and by_name is not None:
                cas_unknown += 1
                _note(report_handle, unlinked_detail, name, cas, "CAS not in PubChem")
            elif by_cas is None and by_name is None:
                not_found += 1
                _note(report_handle, unlinked_detail, name, cas, "neither found")
            elif by_cas.cid != by_name.cid:
                # The name and the CAS describe different substances — exactly
                # the salt/complex case this rule exists to catch.
                rejected += 1
                _note(
                    report_handle,
                    unlinked_detail,
                    name,
                    cas,
                    f"name=CID {by_name.cid} but CAS=CID {by_cas.cid}",
                )
            else:
                confirmed += 1
                # Reuse an existing entry when either the CAS number or the
                # PubChem compound is already registered. Checking the compound
                # as well as the number is what prevents one substance being
                # registered twice under two equivalent CAS numbers.
                chemical_id = cas_to_id.get(cas) or cid_to_id.get(by_cas.cid)
                if chemical_id is None:
                    chemical_id = next_chemical_id(db, len(new_chemicals))
                cas_to_id[cas] = chemical_id
                cid_to_id[by_cas.cid] = chemical_id
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
                    # Both the document and the indexed column, because that
                    # column is what "screening for this chemical" queries —
                    # writing only the document leaves the link invisible.
                    #
                    # Set directly rather than through `replace_doc`, which
                    # commits every call: one commit per row over a 116 MB file
                    # on a bind mount is minutes of disk flushing for a single
                    # compound. The batch commit below writes them together.
                    row.doc = doc
                    row.chemical_id = chemical_id
                    linked_rows += 1
                    pending_writes += 1

        # Write as we go. A run over several thousand compounds takes more than
        # an hour, and holding it all in one transaction means a single network
        # fault throws the whole thing away — which has already happened once.
        # Commit on either counter: a handful of very common compounds can
        # account for thousands of rows before the chemical count moves.
        if args.apply and (len(new_chemicals) >= args.batch or pending_writes >= 2000):
            insert_docs_bulk(db, Chemical, new_chemicals)
            commit(db)
            new_chemicals = []
            pending_writes = 0

        # Report often: with no output a slow network looks like a hang.
        if index % 5 == 0 or index == len(compounds):
            rate = index / max(time.time() - started, 1e-6)
            print(
                f"  {index}/{len(compounds)}  confirmed={confirmed} "
                f"rejected={rejected} name_unknown={name_unknown} "
                f"no_cas={no_cas} not_found={not_found} "
                f"~{(len(compounds) - index) / rate / 60:.0f} min left",
                flush=True,
            )

    print(
        f"\nConfirmed {confirmed} compounds ({linked_rows} rows).\n"
        f"\nLeft unlinked, by reason:\n"
        f"  name and CAS name DIFFERENT compounds: {rejected:5}  <- the check working\n"
        f"  CAS resolves, name unknown to PubChem: {name_unknown:5}  "
        f"<- usually a house naming style\n"
        f"  name resolves, CAS unknown:            {cas_unknown:5}\n"
        f"  no CAS to corroborate the name:        {no_cas:5}\n"
        f"  neither identifier found:              {not_found:5}"
    )
    if report_handle is not None:
        report_handle.close()
        print(f"\nUnlinked compounds written to {args.report}")

    if args.apply:
        insert_docs_bulk(db, Chemical, new_chemicals)
        commit(db)
        print(f"\nApplied: {confirmed} chemicals registered, {linked_rows} rows linked.")
    else:
        # Genuinely nothing written. An earlier version linked rows through
        # `replace_doc`, which commits on every call — so the rows were already
        # on disk by the time this rollback ran, and a "dry run" quietly
        # modified the database. Changes are now held in the session until the
        # batch commit above, which only runs under --apply, so this rollback
        # actually discards them.
        db.rollback()
        print("\nDry run — nothing written. Re-run with --apply.")
    if client.failures:
        print(f"\n{client.failures} lookups gave up after retries; re-run to retry them.")
    if client.throttled:
        print(
            f"PubChem throttled this run {client.throttled} times "
            f"(request spacing ended at {client.min_interval:.2f}s). "
            "Compounds it refused are reported as 'not in PubChem' but were "
            "never actually asked — re-run to retry them."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
