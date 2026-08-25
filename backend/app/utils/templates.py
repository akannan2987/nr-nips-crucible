"""Declarative descriptions of the laboratory templates we can ingest.

Each source template is a `TemplateSpec` — data, not code. A spec says how to
recognise the file, where its header row is, what its columns mean, and which
cleaner applies to each. Adding a new template should mean **adding a spec**,
not writing another parser; if a template needs new code, this design has
failed and is worth revisiting rather than working around.

The one function that does real work is `parse_with_spec`, and it is shared by
every template.

Reading order:
  1. `TemplateSpec`      — what a template description contains
  2. `CERGY_SCREENING`   — the first real one
  3. `detect_template`   — pick a spec for an uploaded file
  4. `parse_with_spec`   — turn bytes into cleaned records + a report
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .cleaning import (
    Measurement,
    clean_text,
    collapse_whitespace,
    looks_like_header_echo,
    parse_cas_numbers,
    parse_date,
    parse_measurement,
    stable_hash,
)


@dataclass(frozen=True)
class TemplateSpec:
    """Everything needed to read one shape of source file."""

    key: str
    """Stable identifier, e.g. `cergy_screening`. Recorded on every record."""

    label: str
    """Human-readable name shown in the upload report."""

    tag: str
    """Provenance tag written to every record, e.g. `Cergy_data`."""

    module: str
    """Which part of the application the rows belong to (`screening`, …)."""

    fingerprint: tuple[str, ...]
    """Column names that must all be present for this spec to match.

    Chosen to be distinctive rather than exhaustive, so a file with an extra
    column or a renamed unrelated one still matches.
    """

    encodings: tuple[str, ...] = ("utf-8-sig", "cp1252", "latin-1")
    """Text encodings to try, in order. The first that decodes wins.

    Exports from Windows Excel are frequently `cp1252`, not UTF-8 — the Cergy
    file's `°C` is byte 0xB0, which is not valid UTF-8 and makes a naive read
    fail outright.
    """

    dayfirst: bool = False
    """Whether `01/02/2025` means 1 February (True) or January 2nd (False)."""

    text_fields: dict[str, str] = field(default_factory=dict)
    """`source column` → `canonical field`, cleaned as free text."""

    number_fields: dict[str, str] = field(default_factory=dict)
    """`source column` → `canonical field`, cleaned as a measurement."""

    date_fields: dict[str, str] = field(default_factory=dict)
    """`source column` → `canonical field`, normalised to `YYYY-MM-DD`."""

    cas_field: Optional[str] = None
    """Source column holding CAS numbers, if any."""

    name_field: Optional[str] = None
    """Source column naming the compound, if any."""

    identity_fields: tuple[str, ...] = ()
    """Canonical fields that together identify a row, for duplicate detection."""


# --------------------------------------------------------------------------
# Cergy — "Database screening January 2025 to January 2026 (Pack)"
# --------------------------------------------------------------------------
# One row is one compound detected in one sample under one migration
# condition. The file is a concatenation of several exports, so it carries
# copies of its own header row in the middle of the data (handled centrally by
# `looks_like_header_echo`).

CERGY_SCREENING = TemplateSpec(
    key="cergy_screening",
    label="Cergy packaging migration screening",
    tag="Cergy_data",
    module="screening",
    fingerprint=("LIMS", "Simulant", "Retention Indice", "CAS", "mg/kg food"),
    dayfirst=False,  # the file contains 12/24/2025 — month-first
    text_fields={
        "LIMS": "lims_id",
        "Factory": "factory",
        "Zone": "zone",
        "Description\nSample": "sample_description",
        "Category": "category",
        "additionnal information": "additional_information",
        "Migration type": "migration_type",
        "Simulant": "simulant",
        "Name": "compound_name",
        "Comments / Sources": "comments",
        "Restrictions": "restrictions",
        "Extraction/\nMigration": "analysis_type",
        "Retention Indice": "retention_index",
    },
    number_fields={
        "migration time(h)": "migration_time_h",
        "Migration temperature (°C)": "migration_temperature_c",
        "mg/dm2 material": "mg_per_dm2_material",
        "mg/6dm2 material": "mg_per_6dm2_material",
        "mg/kg food": "mg_per_kg_food",
    },
    date_fields={"Date": "analysis_date"},
    cas_field="CAS",
    name_field="Name",
    identity_fields=("lims_id", "compound_name", "simulant", "retention_index"),
)


REGISTRY: tuple[TemplateSpec, ...] = (CERGY_SCREENING,)


def decode_bytes(content: bytes, encodings: tuple[str, ...]) -> tuple[str, str]:
    """Decode using the first encoding that works; return `(text, encoding)`.

    The final fallback decodes with replacement characters rather than raising:
    a single bad byte should not cost you a 49,000-row import.
    """
    for encoding in encodings:
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace"), "utf-8 (with replacements)"


def read_delimited(content: bytes, spec: TemplateSpec) -> tuple[list[dict[str, str]], str]:
    """Read a CSV export into row dicts, honouring quoted newlines.

    Python's `csv` module handles cells containing line breaks (this file's
    headers and comments both have them), which is why the file must not be
    split on newlines by hand — doing so turns 49,069 records into 107,690
    fragments.
    """
    text, encoding = decode_bytes(content, spec.encodings)
    reader = csv.reader(io.StringIO(text, newline=""))
    rows = list(reader)
    if not rows:
        return [], encoding
    headers = [h for h in rows[0]]
    out: list[dict[str, str]] = []
    for values in rows[1:]:
        if not any(collapse_whitespace(v) for v in values):
            continue  # entirely blank line
        out.append({h: (values[i] if i < len(values) else "") for i, h in enumerate(headers)})
    return out, encoding


def detect_template(content: bytes, filename: str = "") -> Optional[TemplateSpec]:
    """Return the spec matching this file, or `None` if nothing recognises it.

    Detection reads only the header row, so it is cheap even on a large file.
    """
    for spec in REGISTRY:
        text, _ = decode_bytes(content[:65536], spec.encodings)
        try:
            headers = next(csv.reader(io.StringIO(text, newline="")))
        except StopIteration:
            continue
        present = {collapse_whitespace(h).lower() for h in headers}
        if all(collapse_whitespace(f).lower() in present for f in spec.fingerprint):
            return spec
    return None


@dataclass
class ParseReport:
    """What happened during a parse — the honest account of an import."""

    template: str = ""
    encoding: str = ""
    rows_read: int = 0
    header_echoes_dropped: int = 0
    records: int = 0
    duplicate_groups: int = 0
    duplicate_rows: int = 0
    below_limit_values: int = 0
    formula_errors: int = 0
    unparsed_numbers: int = 0
    missing_cas: int = 0
    malformed_cas: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


def parse_with_spec(content: bytes, spec: TemplateSpec) -> tuple[list[dict[str, Any]], ParseReport]:
    """Turn an uploaded file into cleaned records, plus a report on the mess.

    Every record carries three things:

    * the cleaned canonical fields, for querying;
    * `source` — provenance: the tag, template, row number and file encoding;
    * `raw` — the original row exactly as read, so nothing is ever lost.

    Rows are **not** dropped for being dirty. The only rows discarded are
    repeated header rows, which are not data at all.
    """
    rows, encoding = read_delimited(content, spec)
    report = ParseReport(template=spec.key, encoding=encoding, rows_read=len(rows))
    headers = list(rows[0].keys()) if rows else []

    records: list[dict[str, Any]] = []
    for line_no, row in enumerate(rows, start=2):  # start=2: row 1 is the header
        if looks_like_header_echo(row, headers):
            report.header_echoes_dropped += 1
            continue

        record: dict[str, Any] = {}

        for source, target in spec.text_fields.items():
            record[target] = clean_text(row.get(source))

        for source, target in spec.date_fields.items():
            record[target] = parse_date(row.get(source), dayfirst=spec.dayfirst)

        below_limit = False
        for source, target in spec.number_fields.items():
            m: Measurement = parse_measurement(row.get(source))
            record[target] = m.value
            if m.status == "error":
                report.formula_errors += 1
            elif m.status == "below_limit":
                below_limit = True
                report.below_limit_values += 1
                # Keep the sentence — it is the result, not noise.
                record[f"{target}_note"] = m.raw
            elif m.status == "text":
                report.unparsed_numbers += 1
                record[f"{target}_note"] = m.raw
        record["below_detection_limit"] = below_limit

        if spec.cas_field:
            cas_list = parse_cas_numbers(row.get(spec.cas_field))
            record["cas"] = cas_list[0] if cas_list else None
            # Extra CAS numbers are kept rather than silently dropped: a cell
            # naming two candidate substances is a real observation.
            record["cas_alternatives"] = cas_list[1:] or None
            if not cas_list:
                raw_cas = collapse_whitespace(row.get(spec.cas_field))
                if raw_cas:
                    report.malformed_cas += 1
                else:
                    report.missing_cas += 1

        record["source"] = {
            "tag": spec.tag,
            "template": spec.key,
            "template_label": spec.label,
            "row_number": line_no,
            "encoding": encoding,
        }
        record["raw"] = {k: v for k, v in row.items() if collapse_whitespace(v)}
        records.append(record)

    _flag_duplicates(records, spec, report)
    report.records = len(records)
    return records, report


def _flag_duplicates(
    records: list[dict[str, Any]], spec: TemplateSpec, report: ParseReport
) -> None:
    """Mark records that share an identity, without removing any of them.

    Repeated measurements may be genuine replicates or an artefact of several
    exports being concatenated. Flagging keeps that decision reversible;
    deleting would not.
    """
    if not spec.identity_fields:
        return
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        key = stable_hash(*(record.get(f) or "" for f in spec.identity_fields))
        groups.setdefault(key, []).append(record)
    for key, members in groups.items():
        if len(members) > 1:
            report.duplicate_groups += 1
            report.duplicate_rows += len(members)
            for member in members:
                member["duplicate_group"] = key
