"""Tests for the template-driven ingestion of messy laboratory exports.

Every fixture here is **synthetic**. It reproduces the *shapes* of mess found
in the real Cergy export — cp1252 encoding, formula errors, repeated header
rows, multi-value CAS cells, newlines inside quoted fields — without carrying
any real laboratory data, which must never enter this repository.
"""

import io

from app.utils.cleaning import (
    looks_like_header_echo,
    parse_cas_numbers,
    parse_date,
    parse_measurement,
)
from app.utils.templates import CERGY_SCREENING, detect_template, parse_with_spec

# --------------------------------------------------------------------------
# A miniature Cergy-shaped file. Note the deliberate defects, one per row:
#   row 2  a clean baseline record
#   row 3  #DIV/0! in mg/kg food, and NA where a number belongs
#   row 4  a repeated (partial) header row — must be dropped, not parsed
#   row 5  "no compounds found" text instead of a number
#   row 6  two CAS numbers in one cell, and #VALUE!
#   row 7  a duplicate of row 2's identity
# --------------------------------------------------------------------------
HEADER = (
    'LIMS,Date,Factory,Zone,"Description\nSample",Category,additionnal information,'
    "Migration type,Simulant,migration time(h),Migration temperature (\xb0C),"
    'Retention Indice,Name,CAS,Comments / Sources,Restrictions,"Extraction/\nMigration",'
    "mg/dm2 material,mg/6dm2 material,mg/kg food"
)

ROWS = [
    "900000001,1/14/2025,PlantA,EMENA,Bottle sample,Rigid Plastic,note1,inner side,"
    "ethanol 95%,240,60,959,Testanol,100-52-7,A solvent,None,Migration,0.0026,0.0156,0.6434",
    "900000001,2/19/2025,PlantA,EMENA,Bottle sample,Rigid Plastic,note2,inner side,"
    "isooctane,24,60,1025,Testanone,104-76-7,,,Migration,NA,0.3662,#DIV/0!",
    # Partial header echo: real sample context, result columns naming themselves.
    "900000002,3/3/2025,PlantB,AOA,Pouch sample,Flexibles,note3,inner side,"
    "Tenax 2g,240,60,Indice,Name,CAS,Comments / Sources,Restrictions,Migration,"
    'mg/dm2 material,"mg/6dm2 material (in EU Regulation ...)","mg/kg food ratio : 7.74 dm2/kg"',
    "900000002,3/3/2025,PlantB,AOA,Pouch sample,Flexibles,note4,inner side,"
    'Tenax 2g,240,60,1099,Testene,,,,Migration,0.0085,"No compounds found above 0.01 mg/kg",',
    "900000003,12/24/2025,PlantC,AMS,Tub sample,Rigid Plastic,note5,outer side,"
    'ethanol 20%,240,20,1200,Testadiene,"5398-11-8\n\n6386-38-5",,,Migration,0.0512,0.3072,#VALUE!',
    # Same identity as row 2 (LIMS + name + simulant + retention index).
    "900000001,1/14/2025,PlantA,EMENA,Bottle sample,Rigid Plastic,note6,inner side,"
    "ethanol 95%,240,60,959,Testanol,100-52-7,A solvent,None,Migration,0.0027,0.0161,0.6501",
]


def cergy_bytes() -> bytes:
    """The synthetic file, encoded cp1252 exactly as Excel on Windows writes it."""
    return ("\r\n".join([HEADER, *ROWS]) + "\r\n").encode("cp1252")


# --------------------------------------------------------------------------
# Cleaning primitives
# --------------------------------------------------------------------------


def test_formula_errors_become_null_and_are_labelled():
    for token in ("#DIV/0!", "#VALUE!", "#N/A", "#REF!"):
        m = parse_measurement(token)
        assert m.value is None
        assert m.status == "error", token
        assert m.raw == token  # the original is never thrown away


def test_blank_and_na_are_missing_not_errors():
    for token in ("", "   ", "NA", "N/A", "n.d.", "-"):
        m = parse_measurement(token)
        assert m.value is None
        assert m.status == "missing", token


def test_no_compound_found_is_a_result_not_missing_data():
    m = parse_measurement("No compounds found above 0.01 mg/kg")
    assert m.value is None
    assert m.status == "below_limit"
    assert m.below_limit


def test_numbers_parse_with_either_decimal_separator():
    assert parse_measurement("0.0026").value == 0.0026
    assert parse_measurement("0,0026").value == 0.0026
    assert parse_measurement("0.0026 mg").value == 0.0026


def test_dates_respect_month_first_versus_day_first():
    # 12/24 can only be December 24th, whichever convention you assume.
    assert parse_date("12/24/2025") == "2025-12-24"
    # 01/02 is ambiguous, so the flag decides.
    assert parse_date("1/2/2025", dayfirst=False) == "2025-01-02"
    assert parse_date("1/2/2025", dayfirst=True) == "2025-02-01"
    assert parse_date("") is None
    assert parse_date("N/A") is None


def test_cas_numbers_are_extracted_and_malformed_ones_rejected():
    assert parse_cas_numbers("100-52-7") == ["100-52-7"]
    assert parse_cas_numbers("5398-11-8\n\n6386-38-5") == ["5398-11-8", "6386-38-5"]
    assert parse_cas_numbers("82304-66-3\n\n+") == ["82304-66-3"]
    for junk in ("-", "-00-0", "N/A", ""):
        assert parse_cas_numbers(junk) == [], junk


def test_partial_header_echo_is_detected():
    headers = ["LIMS", "Name", "CAS", "Comments"]
    echo = {"LIMS": "900000002", "Name": "Name", "CAS": "CAS", "Comments": "Comments"}
    real = {"LIMS": "900000001", "Name": "Testanol", "CAS": "100-52-7", "Comments": "A solvent"}
    assert looks_like_header_echo(echo, headers)
    assert not looks_like_header_echo(real, headers)


def test_a_real_row_naming_one_column_is_not_an_echo():
    """Guards against over-eager dropping of genuine data."""
    headers = ["LIMS", "Name", "Category", "Comments"]
    row = {"LIMS": "1", "Name": "Nameless compound", "Category": "Rigid", "Comments": "ok"}
    assert not looks_like_header_echo(row, headers)


# --------------------------------------------------------------------------
# Template detection and parsing
# --------------------------------------------------------------------------


def test_template_is_detected_from_its_columns():
    assert detect_template(cergy_bytes()) is CERGY_SCREENING


def test_unrelated_file_matches_no_template():
    assert detect_template(b"alpha,beta,gamma\n1,2,3\n") is None


def test_parse_cleans_and_reports_honestly():
    records, report = parse_with_spec(cergy_bytes(), CERGY_SCREENING)

    assert report.encoding == "cp1252"
    assert report.header_echoes_dropped == 1
    assert len(records) == 5  # 6 rows in, 1 header echo dropped
    assert report.formula_errors == 2  # #DIV/0! and #VALUE!
    assert report.below_limit_values == 1
    assert report.duplicate_groups == 1  # rows 2 and 7 share an identity

    first = records[0]
    assert first["lims_id"] == "900000001"
    assert first["compound_name"] == "Testanol"
    assert first["cas"] == "100-52-7"
    assert first["analysis_date"] == "2025-01-14"
    assert first["mg_per_kg_food"] == 0.6434
    assert first["migration_temperature_c"] == 60.0


def test_every_record_carries_its_provenance_tag():
    records, _ = parse_with_spec(cergy_bytes(), CERGY_SCREENING)
    assert records, "expected records"
    for record in records:
        assert record["source"]["tag"] == "Cergy_data"
        assert record["source"]["template"] == "cergy_screening"
        assert record["source"]["row_number"] >= 2


def test_the_original_row_is_preserved_untouched():
    """Cleaning must be additive — `doc` stays the source of truth."""
    records, _ = parse_with_spec(cergy_bytes(), CERGY_SCREENING)
    div_zero = [r for r in records if r["raw"].get("mg/kg food") == "#DIV/0!"]
    assert len(div_zero) == 1
    # cleaned value is null, but the original text survives in `raw`
    assert div_zero[0]["mg_per_kg_food"] is None
    assert div_zero[0]["raw"]["mg/kg food"] == "#DIV/0!"


def test_multi_value_cas_is_shown_exactly_as_the_file_had_it():
    """No honest way to pick one of two candidates, so both are shown."""
    records, _ = parse_with_spec(cergy_bytes(), CERGY_SCREENING)
    multi = [r for r in records if r.get("cas") and "6386-38-5" in r["cas"]]
    assert len(multi) == 1
    assert multi[0]["cas"] == "5398-11-8 6386-38-5"
    # Both are still available for matching against the registry.
    assert multi[0]["_cas_parsed"] == ["5398-11-8", "6386-38-5"]
    assert "cas_alternatives" not in multi[0]


def test_duplicates_are_flagged_and_never_dropped():
    records, report = parse_with_spec(cergy_bytes(), CERGY_SCREENING)
    flagged = [r for r in records if r.get("duplicate_group")]
    assert len(flagged) == 2
    assert flagged[0]["duplicate_group"] == flagged[1]["duplicate_group"]
    assert report.duplicate_rows == 2


# --------------------------------------------------------------------------
# End to end, through the real endpoint
# --------------------------------------------------------------------------


def test_identical_rows_and_repeat_measurements_are_told_apart():
    """Conflating them would let a 'remove duplicates' button delete results."""
    records, report = parse_with_spec(cergy_bytes(), CERGY_SCREENING)
    flagged = [r for r in records if r.get("duplicate_group")]
    assert len(flagged) == 2
    # Rows 2 and 7 share an identity but differ in every measurement, so they
    # are repeat measurements, not copies.
    assert all(r["duplicate_kind"] == "repeat_measurement" for r in flagged)
    assert report.repeat_measurements == 2
    assert report.identical_rows == 0
    assert [r["duplicate_rank"] for r in flagged] == [0, 1]


def test_column_headings_are_snake_case_of_the_source_heading():
    from app.utils.templates import label_for

    assert label_for("lims_id") == "lims"
    assert label_for("compound_name") == "name"
    assert label_for("mg_per_kg_food") == "mg_kg_food"
    assert label_for("migration_temperature_c") == "migration_temperature_c"
    # A typo in the file is kept: correcting it would make the table harder to
    # reconcile against the source.
    assert label_for("additional_information") == "additionnal_information"
    # Columns we added keep their own name.
    assert label_for("below_detection_limit") == "below_detection_limit"
    assert label_for("mg_per_kg_food_note") == "mg_kg_food_original_text"


def test_every_record_carries_a_visible_source_tag():
    records, _ = parse_with_spec(cergy_bytes(), CERGY_SCREENING)
    assert all(r["source_tag"] == "Cergy_data" for r in records)


def test_upload_links_only_to_registered_chemicals(client, seeded_client):
    res = client.post(
        "/api/screening/upload/excel",
        files={"file": ("cergy.csv", io.BytesIO(cergy_bytes()), "text/csv")},
    )
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["tag"] == "Cergy_data"
    assert body["template"] == "cergy_screening"
    assert body["inserted"] == 5
    # Importing never invents a chemical; identification is a separate,
    # evidence-based step (scripts/link_pubchem.py).
    assert body["chemicals_created"] == 0
    # The seeded chemical is caffeine, which this file does not mention, so
    # every row is left awaiting identification.
    assert body["records_without_chemical"] == 5

    screening = client.get("/api/screening?limit=100").json()["data"]
    assert len(screening) == 5
    assert all(s["source_tag"] == "Cergy_data" for s in screening)


def test_rows_link_to_a_chemical_already_registered(client):
    """A compound the registry already knows is linked on import, by CAS."""
    client.post(
        "/api/chemicals",
        json={"chemical_id": "CHEM-1", "name": "Anything", "cas_number": "100-52-7"},
    )
    client.post(
        "/api/screening/upload/excel",
        files={"file": ("cergy.csv", io.BytesIO(cergy_bytes()), "text/csv")},
    )
    rows = client.get("/api/screening?limit=100").json()["data"]
    linked = [r for r in rows if r["chemical_id"] == "CHEM-1"]
    # Testanol carries CAS 100-52-7 and appears twice in the fixture.
    assert len(linked) == 2


def test_unique_only_keeps_repeat_measurements(client):
    """Only exact copies are dropped; differing repeats are real results."""
    client.post(
        "/api/screening/upload/excel",
        files={"file": ("cergy.csv", io.BytesIO(cergy_bytes()), "text/csv")},
    )
    everything = client.get("/api/screening?limit=100").json()["pagination"]["total"]
    unique = client.get("/api/screening?limit=100&unique_only=true").json()["pagination"]["total"]
    # The fixture's two flagged rows differ in their measurements, so nothing
    # is removed.
    assert everything == 5
    assert unique == 5


def test_unrecognised_spreadsheet_still_uses_the_original_path(client, seeded_client):
    """The legacy column-mapping upload must keep working unchanged."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["chemical_id", "assay_name", "result"])
    ws.append(["CHEM-TEST-001", "MTT viability", "active"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    res = client.post(
        "/api/screening/upload/excel",
        files={"file": ("legacy.xlsx", buf, "application/vnd.ms-excel")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["inserted"] == 1
    assert "template" not in body  # took the original branch
