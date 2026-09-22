"""Phase SH-3a: the token gate (docs/13-authentication.md, rung 1).

The suite runs with AUTH_MODE=off, so every contract test is unchanged.
These tests switch the mode to ``token`` around one application and prove
the plan's promises: no credential -> 401, a wrong one -> 401 with the same
words, the right one -> exactly the old answer, health and instance open,
the login page's cookie opens the door and the logout closes it.
"""

import pytest
from fastapi.testclient import TestClient

from app import auth, config
from app.main import app

TOKEN = "t3st-" + "x" * 44  # 49 characters, above the minimum
GUARDED = [
    "/api/stats",
    "/api/chemicals",
    "/api/samples",
    "/api/screening",
    "/api/toxicology",
    "/api/query/schema",
    "/api/chemicals/summary",
    "/api/screening/columns",
]


@pytest.fixture()
def token_mode(monkeypatch):
    """The token rung, switched on for one test."""
    monkeypatch.setattr(config, "AUTH_MODE", "token")
    monkeypatch.setattr(config, "CRUCIBLE_TOKEN", TOKEN)
    return TOKEN


def bearer(token: str = TOKEN) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── mode off: nothing changed ─────────────────────────────────────────


def test_mode_off_answers_everyone_as_before(client):
    assert client.get("/api/stats").status_code == 200
    me = client.get("/api/auth/me").json()
    assert me["mode"] == "off"
    assert me["authenticated"] is True
    assert me["user"]["via"] == "off"


def test_login_is_a_400_when_the_login_is_off(client):
    res = client.post("/api/auth/login", json={"token": TOKEN})
    assert res.status_code == 400
    assert "AUTH_MODE is off" in res.json()["error"]


def test_the_identity_has_the_same_four_fields_on_every_rung():
    for who in (auth.ANYONE, auth.TOKEN_HOLDER):
        assert set(who.as_dict()) == {"subject", "display_name", "roles", "via"}


# ── the gate ──────────────────────────────────────────────────────────


def test_no_credential_is_refused_with_401_and_the_legacy_error_shape(client, token_mode):
    res = client.get("/api/stats")
    assert res.status_code == 401
    assert res.json() == {"error": "Not authenticated"}
    assert res.headers["www-authenticate"] == "Bearer"


def test_a_wrong_credential_gets_exactly_the_same_answer(client, token_mode):
    for headers in (bearer("nope"), {"Authorization": "Basic abc"}, bearer(TOKEN[:-1]), bearer(TOKEN + "x")):
        res = client.get("/api/stats", headers=headers)
        assert res.status_code == 401
        assert res.json() == {"error": "Not authenticated"}


def test_the_right_header_gets_the_old_answer_unchanged(client, token_mode):
    with_token = client.get("/api/stats", headers=bearer())
    assert with_token.status_code == 200
    assert set(with_token.json()) == {"chemicals", "samples", "screening", "toxicology", "counts", "capacities", "lastUpdated"}


def test_every_module_is_behind_the_guard(client, token_mode):
    for path in GUARDED:
        assert client.get(path).status_code == 401, path
        assert client.get(path, headers=bearer()).status_code == 200, path
    # writes too, not only reads
    assert client.post("/api/query", json={"sql": "SELECT 1"}).status_code == 401
    assert client.post("/api/chemicals", json={"chemical_id": "CHEM-X", "name": "x"}).status_code == 401


def test_health_and_instance_stay_open(client, token_mode):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert client.get("/api/instance").status_code == 200


def test_me_is_open_and_says_not_signed_in(client, token_mode):
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == {"mode": "token", "authenticated": False, "user": None}
    signed = client.get("/api/auth/me", headers=bearer()).json()
    assert signed["authenticated"] is True
    assert signed["user"]["via"] == "token"


# ── the login page's cookie ───────────────────────────────────────────


def test_a_wrong_token_on_the_login_page_is_refused_and_sets_no_cookie(client, token_mode):
    res = client.post("/api/auth/login", json={"token": "nope"})
    assert res.status_code == 401
    assert res.json() == {"error": "Not authenticated"}
    assert "set-cookie" not in res.headers
    assert client.get("/api/stats").status_code == 401


def test_the_right_token_sets_a_cookie_that_opens_the_door(client, token_mode):
    res = client.post("/api/auth/login", json={"token": TOKEN})
    assert res.status_code == 200
    assert res.json()["authenticated"] is True
    cookie = res.headers["set-cookie"]
    assert cookie.startswith(auth.COOKIE_NAME + "=")
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie.lower().replace("samesite=lax", "SameSite=lax")
    # the client keeps the cookie, like a browser: no header needed now
    assert client.get("/api/stats").status_code == 200
    assert client.get("/api/auth/me").json()["authenticated"] is True


def test_the_cookie_is_not_the_token(client, token_mode):
    client.post("/api/auth/login", json={"token": TOKEN})
    value = client.cookies.get(auth.COOKIE_NAME)
    assert value and value != TOKEN
    # a leaked cookie cannot be replayed as a bearer header
    fresh = TestClient(app, raise_server_exceptions=False)
    assert fresh.get("/api/stats", headers=bearer(value)).status_code == 401


def test_a_download_works_with_the_cookie(client, token_mode):
    """A link in the page cannot carry a header; the cookie is what makes downloads work."""
    client.post("/api/auth/login", json={"token": TOKEN})
    res = client.get("/api/screening/export", params={"format": "csv"})
    assert res.status_code == 200


def test_logout_closes_the_door(client, token_mode):
    client.post("/api/auth/login", json={"token": TOKEN})
    assert client.get("/api/stats").status_code == 200
    out = client.post("/api/auth/logout")
    assert out.status_code == 200
    assert out.json()["authenticated"] is False
    assert client.get("/api/stats").status_code == 401


def test_the_secure_flag_follows_the_scheme(token_mode):
    over_http = TestClient(app, raise_server_exceptions=False)
    assert "secure" not in over_http.post("/api/auth/login", json={"token": TOKEN}).headers["set-cookie"].lower()
    over_https = TestClient(app, raise_server_exceptions=False, base_url="https://testserver")
    assert "secure" in over_https.post("/api/auth/login", json={"token": TOKEN}).headers["set-cookie"].lower()


def test_rotating_the_token_signs_every_browser_out(client, token_mode, monkeypatch):
    client.post("/api/auth/login", json={"token": TOKEN})
    assert client.get("/api/stats").status_code == 200
    monkeypatch.setattr(config, "CRUCIBLE_TOKEN", "r0tated-" + "y" * 40)
    assert client.get("/api/stats").status_code == 401


# ── settings that cannot work stop the process ────────────────────────


def test_startup_refuses_a_login_that_cannot_work(monkeypatch):
    monkeypatch.setattr(config, "AUTH_MODE", "token")
    monkeypatch.setattr(config, "CRUCIBLE_TOKEN", "")
    with pytest.raises(RuntimeError, match="CRUCIBLE_TOKEN is empty"):
        auth.check_settings()
    monkeypatch.setattr(config, "CRUCIBLE_TOKEN", "short")
    with pytest.raises(RuntimeError, match="at least 32"):
        auth.check_settings()
    monkeypatch.setattr(config, "AUTH_MODE", "sso")
    with pytest.raises(RuntimeError, match="not one of"):
        auth.check_settings()
    monkeypatch.setattr(config, "AUTH_MODE", "off")
    auth.check_settings()  # the default always works


def test_the_cross_origin_policy_is_closed_by_default(client):
    """Decision A7: the page is served by this process, so no other site is allowed in."""
    res = client.options(
        "/api/stats",
        headers={"Origin": "http://elsewhere.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in res.headers
