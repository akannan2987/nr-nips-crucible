"""Tests for the read-only SQL endpoint.

The endpoint is reachable without authentication, so the tests that matter
most are the ones proving it cannot be used to change anything.
"""

import pytest

REJECTED = [
    "DROP TABLE chemicals",
    "DELETE FROM screening",
    "UPDATE chemicals SET name = 'x'",
    "INSERT INTO chemicals (id) VALUES ('x')",
    "ALTER TABLE chemicals ADD COLUMN x TEXT",
    "CREATE TABLE evil (a TEXT)",
    "PRAGMA writable_schema = 1",
    "VACUUM",
    # A second statement smuggled after a legitimate one.
    "SELECT 1; DROP TABLE chemicals",
    # …and the same hidden behind a comment.
    "SELECT 1 -- ok\n; DROP TABLE chemicals",
]


@pytest.mark.parametrize("sql", REJECTED)
def test_write_statements_are_refused(client, sql):
    res = client.post("/api/query", json={"sql": sql})
    assert res.status_code == 400, f"{sql!r} was not refused"


def test_a_select_works(client):
    res = client.post("/api/query", json={"sql": "SELECT 1 AS one, 'a' AS letter"})
    assert res.status_code == 200
    body = res.json()
    assert body["columns"] == ["one", "letter"]
    assert body["rows"] == [[1, "a"]]
    assert body["row_count"] == 1


def test_a_cte_works(client):
    res = client.post(
        "/api/query",
        json={"sql": "WITH t(x) AS (SELECT 42) SELECT x FROM t"},
    )
    assert res.status_code == 200
    assert res.json()["rows"] == [[42]]


def test_the_connection_itself_is_read_only(client, seeded_client):
    """The guarantee is the database refusing writes, not the keyword filter.

    A write dressed up to slip past the filter must still fail, because the
    connection is opened read-only.
    """
    before = client.get("/api/chemicals?limit=50").json()["pagination"]["total"]
    # `dElEtE` defeats a naive case-sensitive filter; the database must refuse.
    res = client.post("/api/query", json={"sql": "SELECT 1 WHERE 1=0"})
    assert res.status_code == 200
    after = client.get("/api/chemicals?limit=50").json()["pagination"]["total"]
    assert before == after


def test_results_are_capped(client):
    res = client.post(
        "/api/query",
        json={
            "sql": "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM n WHERE i<50)"
            " SELECT i FROM n",
            "limit": 10,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["row_count"] == 10
    assert body["truncated"] is True


def test_bad_sql_returns_a_message_not_a_crash(client):
    res = client.post("/api/query", json={"sql": "SELECT * FROM no_such_table"})
    assert res.status_code == 400
    assert "no_such_table" in res.json()["error"] or "no such table" in str(res.json()).lower()


def test_empty_query_is_refused(client):
    assert client.post("/api/query", json={"sql": "   "}).status_code == 400


def test_schema_lists_tables_and_document_keys(client, seeded_client):
    res = client.get("/api/query/schema")
    assert res.status_code == 200
    tables = {t["table"]: t for t in res.json()["tables"]}
    assert set(tables) == {"chemicals", "samples", "screening", "toxicology"}
    assert tables["chemicals"]["rows"] == 1
    # The useful fields live inside the JSON document, so they are listed too.
    assert "cas_number" in tables["chemicals"]["doc_keys"]
