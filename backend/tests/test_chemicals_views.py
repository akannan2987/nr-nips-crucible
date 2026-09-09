"""CR-2 (with CR-1) — the registry table can show every column, every batch, sorted and filtered.

* `GET /api/chemicals/columns` discovers the columns from the data: the
  entries' own fields, every `metadata.<key>`, every `batch.<key>`;
* `view=batches` answers one row per batch — 12,561 for the real export;
* `sort` orders by any column, numbers as numbers, missing values last;
* `filters` keeps rows whose column contains the text;
* without those parameters the answer is what it always was.
"""
from __future__ import annotations

import io
import json

from openpyxl import Workbook

DM_HEADER = ["FORMATTED_BATCH_ID", "REG_ID", "BATCH_ID", "BATCH_NUMBER", "CAS_NO", "CHEMICAL_NAME", "DTXSID",
             "MOL_WEIGHT_ORIG", "GC_RI_METHOD", "EFSA_OPINIONS"]


def _xlsx(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "browser export"
    ws.append(DM_HEADER)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _seed(client):
    rows = [
        ["R-1-1", 100001, 900001, 1, "58-08-2", "Caffeine", "DTXSID0020232", 194.19, "1810", "Opinion A"],
        ["R-1-2", 100001, 900002, 2, "58-08-2", "Caffeine", "DTXSID0020232", 194.19, "1815", "Opinion A"],
        ["R-2-1", 100002, 900003, 1, "121-33-5", "Vanillin", "DTXSID0021976", 152.15, "", ""],
        ["R-3-1", 100003, 900004, 1, "", "Zeta mixture", "", 10.5, "", ""],
    ]
    res = client.post("/api/chemicals/upload/excel", files={"file": ("x.xlsx", io.BytesIO(_xlsx(rows)), "application/octet-stream")})
    assert res.json()["compounds"] == 3


def test_columns_are_discovered_from_the_data(client):
    _seed(client)
    cols = client.get("/api/chemicals/columns").json()
    keys = [c["key"] for c in cols["columns"]]
    assert "chemical_id" in keys and "name" in keys and "dotmatics_reg_id" in keys
    assert "metadata.EFSA_OPINIONS" in keys and "metadata.CHEMICAL_NAME" in keys
    assert "batches" not in keys and "metadata" not in keys          # nested values are views, not columns
    efsa = next(c for c in cols["columns"] if c["key"] == "metadata.EFSA_OPINIONS")
    assert efsa["label"] == "EFSA_OPINIONS" and efsa["group"] == "metadata" and efsa["filled"] == 1
    assert {"key": "batch.GC_RI_METHOD", "label": "GC_RI_METHOD"} in cols["batch_columns"]
    assert cols["total"] == 3


def test_batches_view_is_one_row_per_batch(client):
    _seed(client)
    res = client.get("/api/chemicals?view=batches&limit=10&sort=chemical_id").json()
    assert res["pagination"]["total"] == 4                             # 3 compounds, 4 batch rows
    caffeine = [r for r in res["data"] if r["name"] == "Caffeine"]
    assert [(r["batch_no"], r["batches_total"], r["batch"]["GC_RI_METHOD"]) for r in caffeine] == [(1, 2, "1810"), (2, 2, "1815")]
    zeta = next(r for r in res["data"] if r["name"] == "Zeta mixture")
    assert (zeta["batch_no"], zeta["batches_total"]) == (1, 1)
    plain = client.get("/api/chemicals?limit=10").json()
    assert plain["pagination"]["total"] == 3 and "batch" not in plain["data"][0]


def test_sort_by_any_column_numbers_as_numbers_missing_last(client):
    _seed(client)
    names = lambda res: [r["name"] for r in res.json()["data"]]  # noqa: E731
    assert names(client.get("/api/chemicals?sort=molecular_weight&order=asc")) == ["Zeta mixture", "Vanillin", "Caffeine"]
    assert names(client.get("/api/chemicals?sort=molecular_weight&order=desc")) == ["Caffeine", "Vanillin", "Zeta mixture"]
    assert names(client.get("/api/chemicals?sort=cas_number&order=asc")) == ["Vanillin", "Caffeine", "Zeta mixture"]  # no CAS last
    assert names(client.get("/api/chemicals?sort=metadata.EFSA_OPINIONS&order=asc"))[0] == "Caffeine"
    assert names(client.get("/api/chemicals?view=batches&sort=batch.GC_RI_METHOD&order=desc"))[:2] == ["Caffeine", "Caffeine"]


def test_filters_keep_rows_whose_column_contains_the_text(client):
    _seed(client)
    f = lambda d: client.get("/api/chemicals", params={"filters": json.dumps(d)}).json()  # noqa: E731
    assert [r["name"] for r in f({"name": "van"})["data"]] == ["Vanillin"]
    assert f({"metadata.EFSA_OPINIONS": "opinion"})["pagination"]["total"] == 1
    assert f({"cas_number": "58-08"})["pagination"]["total"] == 1
    assert f({"name": "van", "cas_number": "999"})["pagination"]["total"] == 0
    res = client.get("/api/chemicals?filters=not-json")
    assert res.status_code == 400 and res.json() == {"error": "filters must be a JSON object of column: text"}


def test_default_answer_is_unchanged(seeded_client):
    res = seeded_client.get("/api/chemicals").json()
    assert set(res) == {"data", "pagination"}
    assert set(res["pagination"]) == {"page", "limit", "total", "totalPages"}
    assert res["data"][0]["chemical_id"] == "CHEM-TEST-001"
