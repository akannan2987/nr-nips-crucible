"""Where an entry came from, as tags; and the counts the registry page shows.

Phase CR-11. A **tag** is a short label derived from what the entry already
records — it is computed when the entry is read and never stored, so it
cannot go stale and needs no re-import:

| Tag            | The entry carries it when                                      |
|----------------|----------------------------------------------------------------|
| Dotmatics ID   | it has a `dtx_id` (a DTXSID), whatever route it arrived by     |
| Excel upload   | an .xlsx/.xls file loaded or updated it (the export included)  |
| SDF upload     | a structure file did                                           |
| CSV upload     | a .csv or .tsv file did                                        |
| JSON upload    | a .json file, or the JSON-body endpoint, did                   |
| Manual         | it was typed in — POST /api/chemicals, the browser's form —   |
|                | and no file has touched it since                               |

Every file import records the format it came through under `formats` on
the entry (a list, because one entry can arrive by several routes and keep
them all). A typed-in entry records nothing — the v1 contract fixes the
exact keys `POST /api/chemicals` writes — so *Manual* is what an entry
without `formats` and without a file's marks is called. Entries loaded
before `formats` existed have none either; for them the format is inferred
from the recognised source they name (the export and the limited list are
always Excel, the registry SDF always SDF) or, failing that, from what they
hold. The decisions behind the rules — every Excel
file counts, CSV is not Excel, several ticked tags mean *all of them* with
an *any* switch — are recorded in docs/09-registry-sources.md.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .models import Chemical
from .store import all_docs

TAGS = ("Dotmatics ID", "Excel upload", "SDF upload", "CSV upload", "JSON upload", "Manual")

# The token an import records → the tag it earns.
FORMAT_TAGS = {
    "excel": "Excel upload",
    "xlsx": "Excel upload",
    "xls": "Excel upload",
    "sdf": "SDF upload",
    "csv": "CSV upload",
    "tsv": "CSV upload",
    "json": "JSON upload",
    "manual": "Manual",
}

# What each recognised source is always loaded from (for entries recorded
# before `formats` existed).
SPEC_FORMATS = {"dotmatics_export": "excel", "limited_list": "excel", "registry_sdf": "sdf"}


def note_format(doc: dict[str, Any], fmt: str | None, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    """Record on `doc` that it came through `fmt`; keeps what was there (or on `previous`)."""
    if not fmt:
        return doc
    formats = list(doc.get("formats") or (previous or {}).get("formats") or [])
    if fmt not in formats:
        formats.append(fmt)
    doc["formats"] = formats
    return doc


def _inferred_formats(doc: dict[str, Any]) -> list[str]:
    """For an entry without `formats`: the sources it names, else what it holds."""
    found = [SPEC_FORMATS[s] for s in [doc.get("source_template"), *(doc.get("merged_from") or [])] if s in SPEC_FORMATS]
    if found:
        return list(dict.fromkeys(found))
    if doc.get("mol_block") or doc.get("structural"):
        return ["sdf"]
    if doc.get("metadata"):
        return ["excel"]  # the generic spreadsheet route keeps the whole row under metadata
    return ["manual"]


def tags_of(doc: dict[str, Any]) -> list[str]:
    """The tags an entry carries, in the display order of `TAGS`."""
    earned: set[str] = set()
    if doc.get("dtx_id"):
        earned.add("Dotmatics ID")  # the owner's name for "has a DTX identifier" (2026-09-14)
    for fmt in doc.get("formats") or _inferred_formats(doc):
        tag = FORMAT_TAGS.get(str(fmt).lower())
        if tag:
            earned.add(tag)
    return [t for t in TAGS if t in earned]


def batch_count(doc: dict[str, Any]) -> int:
    """How many batches an entry has; an entry with none is one batch row in the Batches view."""
    return max(len(doc.get("batches") or []), 1)


def filter_batches(docs: list[dict[str, Any]], mode: str | None) -> list[dict[str, Any]]:
    """`one` keeps entries with a single batch (or none), `several` those with two or more."""
    if not mode or mode == "all":
        return docs
    if mode == "one":
        return [d for d in docs if batch_count(d) == 1]
    if mode == "several":
        return [d for d in docs if batch_count(d) > 1]
    raise ValueError("batches must be one, several or all")


def parse_tags(tags: str | None) -> list[str]:
    """A comma-separated list of tag names, trimmed; unknown names are kept and match nothing."""
    return [t.strip() for t in (tags or "").split(",") if t.strip()]


def filter_tags(docs: list[dict[str, Any]], tags: str | list[str] | None, match: str | None = None) -> list[dict[str, Any]]:
    """Keep the entries carrying ALL the tags (default) or ANY of them.

    Each doc must already carry its derived `tags` (the list endpoint adds
    them); one without is computed on the spot.
    """
    mode = (match or "all").lower()
    if mode not in ("all", "any"):
        raise ValueError("tags_match must be all or any")
    wanted = parse_tags(tags) if isinstance(tags, str) or tags is None else list(tags)
    if not wanted:
        return docs
    kept = []
    for d in docs:
        have = set(d.get("tags") if "tags" in d else tags_of(d))
        ok = all(t in have for t in wanted) if mode == "all" else any(t in have for t in wanted)
        if ok:
            kept.append(d)
    return kept


def registry_summary(db: Session) -> dict[str, Any]:
    """The counts above the registry table: compounds, batches, and entries per tag."""
    docs = all_docs(db, Chemical)
    one = several = rows = 0
    per_tag = {t: 0 for t in TAGS}
    for d in docs:
        n = batch_count(d)
        rows += n
        if n > 1:
            several += 1
        else:
            one += 1
        for t in tags_of(d):
            per_tag[t] += 1
    return {"total": len(docs), "one_batch": one, "several_batches": several, "batch_rows": rows, "tags": per_tag}
