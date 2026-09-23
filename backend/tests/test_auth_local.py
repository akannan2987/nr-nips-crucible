"""Phase SH-3b: local accounts (docs/13-authentication.md, rung 2).

The suite runs with AUTH_MODE=off, so every contract test is unchanged.
These tests switch the mode to ``local`` around one application and prove
the plan's promises: a username and a password sign a person in, a wrong
credential of any kind gets the same 401 as a missing one, the cookie is
signed and slides, a disabled account or a reset password is refused at
once, ten wrong passwords lock the account, each role may do what the rule
says and no more, a personal token lets a script in and is revoked by
name, the password hash never leaves the database (not through the API,
not through the query console), the management script does what the
route does, and the migration creates the table the model describes.
"""

import importlib.util
import io
import time
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from alembic import command
from app import accounts, auth, config
from app.database import Base, SessionLocal
from app.main import app
from app.routers import auth as auth_router

BACKEND = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("manage_users", BACKEND / "scripts" / "manage_users.py")
manage_users = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(manage_users)

SECRET = "s3ssion-" + "k" * 40  # 48 characters, above the minimum
NOT_AUTH = {"error": "Not authenticated"}
PEOPLE = {
    # username: (password, role, display name)
    "vera": ("viewer-pass-1", "viewer", "Vera Viewer"),
    "ed": ("editor-pass-1", "editor", "Ed Editor"),
    "ada": ("admin-pass-1", "admin", "Ada Admin"),
}


@pytest.fixture()
def local_mode(monkeypatch):
    """The local rung, switched on for one test; the pauses and the hashing cost turned down."""
    monkeypatch.setattr(config, "AUTH_MODE", "local")
    monkeypatch.setattr(config, "SESSION_SECRET", SECRET)
    monkeypatch.setattr(auth_router, "FAILED_LOGIN_PAUSE_SECONDS", 0)
    # Argon2's real cost is the point in production and a tax in a test
    # suite: the same algorithm, cheaper parameters, for the tests only.
    monkeypatch.setattr(accounts, "_hasher", PasswordHasher(time_cost=1, memory_cost=8 * 1024, parallelism=1))


@pytest.fixture()
def users(client, local_mode):
    """One account per role, created the way the script creates them."""
    db = SessionLocal()
    try:
        for name, (password, role, display) in PEOPLE.items():
            accounts.add_user(db, name, password, role=role, display_name=display)
    finally:
        db.close()
    return client


def sign_in(client, username, password=None):
    password = password or PEOPLE[username][0]
    return client.post("/api/auth/login", json={"username": username, "password": password})


def fresh() -> TestClient:
    """A second browser: no cookies shared with the first."""
    return TestClient(app, raise_server_exceptions=False)


def with_db(fn):
    db = SessionLocal()
    try:
        return fn(db)
    finally:
        db.close()


# ── settings and primitives ──────────────────────────────────────────


def test_startup_refuses_a_local_login_without_a_usable_secret(monkeypatch):
    monkeypatch.setattr(config, "AUTH_MODE", "local")
    monkeypatch.setattr(config, "SESSION_SECRET", "")
    with pytest.raises(RuntimeError, match="SESSION_SECRET is empty"):
        auth.check_settings()
    monkeypatch.setattr(config, "SESSION_SECRET", "short")
    with pytest.raises(RuntimeError, match="at least 32"):
        auth.check_settings()
    monkeypatch.setattr(config, "SESSION_SECRET", SECRET)
    auth.check_settings()


def test_the_password_hash_is_one_way_and_verifies(local_mode):
    h = accounts.hash_password("correct horse battery")
    assert "correct horse" not in h and h.startswith("$argon2id$")
    assert accounts.verify_password(h, "correct horse battery")
    assert not accounts.verify_password(h, "correct horse batter")
    assert not accounts.verify_password(None, "anything")
    assert not accounts.verify_password("not a hash at all", "anything")
    assert accounts.hash_password("same") != accounts.hash_password("same")  # salted


def test_username_password_and_role_rules(users):
    def add(name, password="long enough", role="viewer"):
        return with_db(lambda db: accounts.add_user(db, name, password, role=role))

    assert add("  Alice ")["username"] == "alice"  # the door is not case-sensitive: one account, one spelling
    with pytest.raises(ValueError, match="already exists"):
        add("ALICE")
    with pytest.raises(ValueError, match="lowercase"):
        add("a")
    with pytest.raises(ValueError, match="lowercase"):
        add("has space")
    with pytest.raises(ValueError, match="at least 8"):
        add("dan", password="short")
    with pytest.raises(ValueError, match="already exists"):
        add("vera")
    with pytest.raises(ValueError, match="one of viewer, editor, admin"):
        add("dan", role="owner")
    ok = add("dan.o-neil_2")
    assert ok["username"] == "dan.o-neil_2" and ok["role"] == "viewer" and ok["enabled"] is True


def test_the_role_rule_by_verb_and_path():
    r = auth.required_role
    assert r("GET", "/api/chemicals") == "viewer"
    assert r("HEAD", "/api/stats") == "viewer"
    assert r("POST", "/api/query") == "viewer"  # a read that happens to be a POST
    assert r("POST", "/api/chemicals") == "editor"
    assert r("PUT", "/api/chemicals/CHEM-1") == "editor"
    assert r("POST", "/api/screening/link") == "editor"
    assert r("POST", "/api/screening/unlink") == "editor"
    assert r("POST", "/api/chemicals/upload/excel") == "editor"
    assert r("DELETE", "/api/chemicals/CHEM-1") == "admin"
    assert r("DELETE", "/api/chemicals/all/clear") == "admin"
    assert r("POST", "/api/chemicals/bulk/delete") == "admin"
    assert r("POST", "/api/samples/bulk/delete") == "admin"
    assert r("POST", "/api/chemicals/merge") == "admin"
    for held, needed, expect in (("viewer", "viewer", True), ("viewer", "editor", False), ("editor", "viewer", True),
                                 ("editor", "admin", False), ("admin", "viewer", True), ("nobody", "viewer", False)):
        assert accounts.role_includes(held, needed) is expect, (held, needed)


# ── the gate in the local mode ───────────────────────────────────────


def test_no_credential_is_refused_and_me_says_local(users):
    res = users.get("/api/stats")
    assert res.status_code == 401 and res.json() == NOT_AUTH
    assert res.headers["www-authenticate"] == "Bearer"
    assert users.get("/api/auth/me").json() == {"mode": "local", "authenticated": False, "user": None}
    assert users.get("/api/health").json() == {"status": "ok"}
    assert users.get("/api/instance").status_code == 200


def test_every_wrong_login_gets_the_same_answer_and_no_cookie(users):
    attempts = [
        {"username": "nobody", "password": "viewer-pass-1"},  # no such account
        {"username": "vera", "password": "wrong"},  # wrong password
        {"username": "vera", "password": ""},  # empty
        {"username": "", "password": ""},
        {"token": "t3st-" + "x" * 44},  # the token rung's body, on this rung
        {},
    ]
    for body in attempts:
        res = users.post("/api/auth/login", json=body)
        assert res.status_code == 401, body
        assert res.json() == NOT_AUTH, body
        assert "set-cookie" not in res.headers, body
    assert users.get("/api/stats").status_code == 401


def test_the_right_password_sets_a_signed_cookie_that_opens_the_door(users):
    res = sign_in(users, "ed")
    assert res.status_code == 200
    assert res.json() == {
        "mode": "local",
        "authenticated": True,
        "user": {"subject": "ed", "display_name": "Ed Editor", "roles": ["editor"], "via": "local"},
    }
    cookie = res.headers["set-cookie"].lower()
    assert cookie.startswith(auth.COOKIE_NAME + "=") and "httponly" in cookie and "samesite=lax" in cookie
    assert "max-age=36000" in cookie
    # the client keeps the cookie, like a browser: no header needed now
    assert users.get("/api/stats").status_code == 200
    me = users.get("/api/auth/me").json()
    assert me["authenticated"] is True and me["user"]["subject"] == "ed" and me["user"]["via"] == "local"
    # downloads are links, which carry no header; the cookie is what makes them work
    assert users.get("/api/screening/export", params={"format": "csv"}).status_code == 200
    # the username is not case-sensitive at the door; the stored name is lowercase
    other = fresh()
    assert other.post("/api/auth/login", json={"username": "  ED ", "password": PEOPLE["ed"][0]}).status_code == 200


def test_the_cookie_is_signed_and_a_forged_or_foreign_one_is_refused(users, monkeypatch):
    sign_in(users, "vera")
    value = users.cookies.get(auth.COOKIE_NAME)
    payload, _issued = auth.read_session(value)
    assert payload == {"u": "vera", "v": 1}  # readable: it holds no secret, only a signature
    # one changed character breaks the signature
    tampered = value[:-3] + ("AAA" if not value.endswith("AAA") else "BBB")
    assert auth.read_session(tampered) is None
    bad = fresh()
    bad.cookies.set(auth.COOKIE_NAME, tampered)
    assert bad.get("/api/stats").status_code == 401
    # the token rung's cookie (a keyed hash) means nothing here
    old_rung = fresh()
    old_rung.cookies.set(auth.COOKIE_NAME, auth.session_value("some-token"))
    assert old_rung.get("/api/stats").status_code == 401
    # a cookie signed with another instance's secret is refused: one secret, one door
    monkeypatch.setattr(config, "SESSION_SECRET", "0ther-instance-" + "z" * 33)
    assert users.get("/api/stats").status_code == 401


def test_logout_closes_the_door(users):
    sign_in(users, "vera")
    assert users.get("/api/stats").status_code == 200
    out = users.post("/api/auth/logout")
    assert out.status_code == 200 and out.json()["authenticated"] is False
    assert users.get("/api/stats").status_code == 401


def test_a_disabled_account_is_refused_at_once_by_cookie_and_at_the_door(users):
    sign_in(users, "vera")
    assert users.get("/api/stats").status_code == 200
    with_db(lambda db: accounts.set_enabled(db, "vera", False))
    assert users.get("/api/stats").status_code == 401  # the cookie is still there; the account is not
    assert sign_in(fresh(), "vera").status_code == 401
    with_db(lambda db: accounts.set_enabled(db, "vera", True))
    assert sign_in(fresh(), "vera").status_code == 200


def test_a_password_reset_signs_every_browser_of_that_person_out(users, monkeypatch):
    one, two = users, fresh()
    sign_in(one, "ed")
    sign_in(two, "ed")
    assert one.get("/api/stats").status_code == 200 and two.get("/api/stats").status_code == 200
    with_db(lambda db: accounts.set_password(db, "ed", "a brand new password"))
    monkeypatch.setattr(config, "PASSWORD_GRACE_SECONDS", 0)  # the minute is over
    assert one.get("/api/stats").status_code == 401 and two.get("/api/stats").status_code == 401
    assert sign_in(fresh(), "ed", "editor-pass-1").status_code == 401  # the old one
    assert sign_in(fresh(), "ed", "a brand new password").status_code == 200


def test_a_request_in_flight_across_a_password_change_completes_and_gets_the_new_cookie(users, monkeypatch):
    """Lesson 40: the browser that changes its password has requests out with
    the old cookie; a 401 on one of them would sign it out the moment it
    succeeded. For a minute the old version is honoured and upgraded."""
    sign_in(users, "ed")
    old = users.cookies.get(auth.COOKIE_NAME)
    assert auth.read_session(old)[0]["v"] == 1
    with_db(lambda db: accounts.set_password(db, "ed", "a brand new password"))
    # the very next request with the OLD cookie: answered, and handed the new cookie
    res = users.get("/api/stats")
    assert res.status_code == 200 and "set-cookie" in res.headers
    assert auth.read_session(users.cookies.get(auth.COOKIE_NAME))[0]["v"] == 2
    # a cookie two versions behind, or the old one after the grace, is out
    behind = fresh()
    behind.cookies.set(auth.COOKIE_NAME, old)
    monkeypatch.setattr(config, "PASSWORD_GRACE_SECONDS", 0)
    assert behind.get("/api/stats").status_code == 401
    # a disabled account gets no grace at all
    monkeypatch.setattr(config, "PASSWORD_GRACE_SECONDS", 60)
    with_db(lambda db: accounts.set_enabled(db, "ed", False))
    assert users.get("/api/stats").status_code == 401


def test_ten_wrong_passwords_lock_the_account_until_unlocked(users):
    for _ in range(config.LOGIN_MAX_FAILURES - 1):
        assert sign_in(users, "ada", "wrong").status_code == 401
    state = with_db(lambda db: accounts.public_view(accounts.get_user(db, "ada").doc))
    assert state["failed_attempts"] == config.LOGIN_MAX_FAILURES - 1 and state["locked"] is False
    assert sign_in(users, "ada", "wrong").status_code == 401  # the tenth
    state = with_db(lambda db: accounts.public_view(accounts.get_user(db, "ada").doc))
    assert state["locked"] is True
    assert sign_in(users, "ada").status_code == 401  # the right password is refused while locked
    with_db(lambda db: accounts.unlock(db, "ada"))
    assert sign_in(users, "ada").status_code == 200
    state = with_db(lambda db: accounts.public_view(accounts.get_user(db, "ada").doc))
    assert state["failed_attempts"] == 0 and state["last_login"] is not None
    # an unknown username is never counted anywhere: nothing to lock, nothing to learn
    assert sign_in(users, "nobody", "x").status_code == 401


def test_the_session_slides_with_use_and_expires_without_it(users, monkeypatch):
    real_time = time.time
    start = real_time()
    clock = {"now": start}
    monkeypatch.setattr(time, "time", lambda: clock["now"])
    sign_in(users, "vera")
    first = users.cookies.get(auth.COOKIE_NAME)
    # within the slide interval nothing is re-issued
    clock["now"] = start + config.SESSION_SLIDE_SECONDS - 1
    res = users.get("/api/stats")
    assert res.status_code == 200 and "set-cookie" not in res.headers
    # six hours in: still valid, and a fresh cookie comes back with the answer
    clock["now"] = start + 6 * 3600
    res = users.get("/api/stats")
    assert res.status_code == 200 and "set-cookie" in res.headers
    assert users.cookies.get(auth.COOKIE_NAME) != first
    # twelve hours after the login, six after the last request: still in, because it slid
    clock["now"] = start + 12 * 3600
    assert users.get("/api/stats").status_code == 200
    # eleven idle hours later: out
    clock["now"] = start + 23 * 3600
    assert users.get("/api/stats").status_code == 401
    assert users.get("/api/auth/me").json()["authenticated"] is False


# ── roles ─────────────────────────────────────────────────────────────


CHEM = {"chemical_id": "CHEM-ROLE-1", "name": "Caffeine", "cas_number": "58-08-2"}


def test_a_viewer_reads_and_queries_but_cannot_write_or_delete(users):
    sign_in(users, "vera")
    assert users.get("/api/chemicals").status_code == 200
    assert users.get("/api/screening/export", params={"format": "json"}).status_code == 200
    assert users.post("/api/query", json={"sql": "SELECT 1 AS one"}).status_code == 200
    res = users.post("/api/chemicals", json=CHEM)
    assert res.status_code == 403
    assert res.json() == {"error": "Forbidden: this needs the editor role (yours: viewer)"}
    assert users.put("/api/chemicals/CHEM-ROLE-1", json={"name": "x"}).status_code == 403
    assert users.delete("/api/chemicals/CHEM-ROLE-1").status_code == 403
    assert users.post("/api/screening/unlink", json={"all": True}).status_code == 403
    assert users.get("/api/chemicals", params={"search": "caffeine"}).json()["pagination"]["total"] == 0  # nothing was written


def test_an_editor_writes_and_links_but_cannot_delete_merge_or_clear(users):
    sign_in(users, "ed")
    assert users.post("/api/chemicals", json=CHEM).status_code == 201
    assert users.put("/api/chemicals/CHEM-ROLE-1", json={"name": "Caffeine (edited)"}).status_code == 200
    assert users.post("/api/screening", json={"chemical_id": "CHEM-ROLE-1", "compound_name": "Caffeine"}).status_code == 201
    assert users.post("/api/screening/unlink", json={"all": True}).status_code == 200
    for method, path, body in (
        ("DELETE", "/api/chemicals/CHEM-ROLE-1", None),
        ("POST", "/api/chemicals/bulk/delete", {"chemical_ids": ["CHEM-ROLE-1"]}),
        ("POST", "/api/chemicals/merge", {"keep": "CHEM-ROLE-1", "remove": "CHEM-ROLE-2"}),
        ("DELETE", "/api/chemicals/all/clear", None),
        ("DELETE", "/api/samples/all/clear", None),
    ):
        res = users.request(method, path, json=body)
        assert res.status_code == 403, (method, path)
        assert "admin role" in res.json()["error"]
    assert users.get("/api/chemicals/CHEM-ROLE-1").status_code == 200  # still there


def test_an_admin_may_do_everything(users):
    sign_in(users, "ada")
    assert users.post("/api/chemicals", json=CHEM).status_code == 201
    assert users.post("/api/chemicals/bulk/delete", json={"chemical_ids": ["CHEM-ROLE-1"]}).status_code == 200
    assert users.post("/api/chemicals", json=CHEM).status_code == 201
    assert users.delete("/api/chemicals/CHEM-ROLE-1").status_code == 200
    assert users.delete("/api/chemicals/all/clear").status_code == 200


def test_the_token_and_off_rungs_do_not_know_roles(client, monkeypatch):
    """Every holder is an admin there, so the rule never refuses: the contract is unchanged."""
    monkeypatch.setattr(config, "AUTH_MODE", "token")
    monkeypatch.setattr(config, "CRUCIBLE_TOKEN", "t3st-" + "x" * 44)
    headers = {"Authorization": "Bearer t3st-" + "x" * 44}
    assert client.post("/api/chemicals", json=CHEM, headers=headers).status_code == 201
    assert client.delete("/api/chemicals/CHEM-ROLE-1", headers=headers).status_code == 200


# ── personal tokens ──────────────────────────────────────────────────


def test_a_personal_token_lets_a_script_in_and_is_revoked_by_name(users):
    token = with_db(lambda db: accounts.issue_token(db, "ed"))
    assert token.startswith("ed:") and len(token) > 40
    stored = with_db(lambda db: accounts.get_user(db, "ed").doc)
    assert stored["token_hash"] != token and stored["token_hash"] == accounts.token_hash(token)
    bearer = {"Authorization": f"Bearer {token}"}
    assert users.get("/api/stats", headers=bearer).status_code == 200
    me = users.get("/api/auth/me", headers=bearer).json()
    assert me["user"] == {"subject": "ed", "display_name": "Ed Editor", "roles": ["editor"], "via": "token"}
    # the role travels with the token
    assert users.post("/api/chemicals", json=CHEM, headers=bearer).status_code == 201
    assert users.delete("/api/chemicals/CHEM-ROLE-1", headers=bearer).status_code == 403
    # wrong secret, wrong name, no name: 401, the same words
    for bad in (token[:-1] + "x", "vera:" + token.split(":")[1], token.split(":")[1], "nope"):
        res = users.get("/api/stats", headers={"Authorization": f"Bearer {bad}"})
        assert res.status_code == 401 and res.json() == NOT_AUTH, bad
    # a second issue voids the first
    second = with_db(lambda db: accounts.issue_token(db, "ed"))
    assert users.get("/api/stats", headers=bearer).status_code == 401
    assert users.get("/api/stats", headers={"Authorization": f"Bearer {second}"}).status_code == 200
    # a disabled account's token is refused; so is a revoked one
    with_db(lambda db: accounts.set_enabled(db, "ed", False))
    assert users.get("/api/stats", headers={"Authorization": f"Bearer {second}"}).status_code == 401
    with_db(lambda db: accounts.set_enabled(db, "ed", True))
    with_db(lambda db: accounts.revoke_token(db, "ed"))
    assert users.get("/api/stats", headers={"Authorization": f"Bearer {second}"}).status_code == 401
    # the shared token of rung 1 opens nothing on this rung
    assert users.get("/api/stats", headers={"Authorization": "Bearer " + "t3st-" + "x" * 44}).status_code == 401


# ── changing one's own password ──────────────────────────────────────


def test_a_person_changes_their_own_password(users, monkeypatch):
    body = {"current": "viewer-pass-1", "new": "a much longer passphrase"}
    assert users.post("/api/auth/password", json=body).status_code == 401  # not signed in
    one, two = users, fresh()
    sign_in(one, "vera")
    sign_in(two, "vera")
    res = one.post("/api/auth/password", json={"current": "wrong", "new": "a much longer passphrase"})
    assert res.status_code == 400 and res.json() == {"error": "The current password is not right"}
    res = one.post("/api/auth/password", json={"current": "viewer-pass-1", "new": "short"})
    assert res.status_code == 400 and "at least 8" in res.json()["error"]
    res = one.post("/api/auth/password", json=body)
    assert res.status_code == 200 and res.json()["user"]["subject"] == "vera"
    assert one.get("/api/stats").status_code == 200  # this browser got a fresh cookie
    monkeypatch.setattr(config, "PASSWORD_GRACE_SECONDS", 0)
    assert two.get("/api/stats").status_code == 401  # the other one is out, once the minute is over
    assert sign_in(fresh(), "vera", "viewer-pass-1").status_code == 401
    assert sign_in(fresh(), "vera", "a much longer passphrase").status_code == 200
    # a script's token is not a person: it cannot change a password
    token = with_db(lambda db: accounts.issue_token(db, "vera"))
    res = fresh().post("/api/auth/password", json=body, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    # and there are no passwords to change on the other rungs
    monkeypatch.setattr(config, "AUTH_MODE", "off")
    assert users.post("/api/auth/password", json=body).status_code == 400


# ── nothing secret leaves ─────────────────────────────────────────────


def test_the_hashes_never_leave_the_database(users):
    sign_in(users, "ada")
    me = users.get("/api/auth/me").json()["user"]
    assert set(me) == {"subject", "display_name", "roles", "via"}
    view = with_db(lambda db: accounts.list_users(db))
    for user in view:
        assert not any("hash" in key for key in user), user
    # the read-only SQL console refuses the table by name, however it is spelled
    for sql in ("SELECT * FROM users", "select doc from USERS", "SELECT username FROM main.users", 'SELECT * FROM "users"'):
        res = users.post("/api/query", json={"sql": sql})
        assert res.status_code == 400 and "accounts" in res.json()["error"], sql
    assert users.post("/api/query", json={"sql": "SELECT 1 AS users_note"}).status_code == 200  # a mere resemblance is fine
    tables = [t["table"] for t in users.get("/api/query/schema").json()["tables"]]
    assert "users" not in tables


# ── the two moments of the switch (tutorial Step 10a and 10b) ────────


def test_accounts_created_on_the_token_rung_wait_for_the_switch(client, monkeypatch, capsys):
    """Step 10 in two moments: the accounts are created while the door still
    takes the shared token (10a) and are ignored by it; at the switch (10b)
    the same rows are used and the shared token retires. Nothing is lost
    between the two, however long the wait."""
    shared = "t" * 64
    monkeypatch.setattr(config, "AUTH_MODE", "token")
    monkeypatch.setattr(config, "CRUCIBLE_TOKEN", shared)
    monkeypatch.setattr(auth_router, "FAILED_LOGIN_PAUSE_SECONDS", 0)
    monkeypatch.setattr(accounts, "_hasher", PasswordHasher(time_cost=1, memory_cost=8 * 1024, parallelism=1))
    # moment 1: the script writes to the table whatever the mode says
    monkeypatch.setattr("sys.stdin", io.StringIO("alice's long password\n"))
    assert with_db(lambda db: manage_users.main(["add", "alice", "--role", "admin", "--password-stdin"], db)) == 0
    assert with_db(lambda db: manage_users.main(["token", "alice"], db)) == 0
    assert with_db(lambda db: manage_users.main(["list"], db)) == 0
    out = capsys.readouterr().out
    personal = [w for w in out.split() if w.startswith("alice:")][0]
    assert "1 account" in out and "$argon2" not in out
    # the door has not changed: only the shared token opens it
    assert client.get("/api/auth/me").json() == {"mode": "token", "authenticated": False, "user": None}
    assert sign_in(client, "alice", "alice's long password").status_code == 401
    assert fresh().get("/api/stats", headers={"Authorization": f"Bearer {personal}"}).status_code == 401
    assert fresh().get("/api/stats", headers={"Authorization": f"Bearer {shared}"}).status_code == 200
    r = client.post("/api/auth/password", json={"current": "x", "new": "y" * 9}, headers={"Authorization": f"Bearer {shared}"})
    assert r.status_code == 400 and "no passwords to change" in r.json()["error"]
    # moment 2: the switch; the same rows are used and the shared token retires
    monkeypatch.setattr(config, "AUTH_MODE", "local")
    monkeypatch.setattr(config, "SESSION_SECRET", SECRET)
    assert fresh().get("/api/stats", headers={"Authorization": f"Bearer {shared}"}).status_code == 401
    assert fresh().get("/api/stats", headers={"Authorization": f"Bearer {personal}"}).status_code == 200
    r = sign_in(fresh(), "alice", "alice's long password")
    assert r.status_code == 200
    assert (r.json()["user"]["subject"], r.json()["user"]["roles"], r.json()["user"]["via"]) == ("alice", ["admin"], "local")


# ── the management script ────────────────────────────────────────────


def test_manage_users_does_what_the_route_does(users, capsys, monkeypatch):
    def run(*argv, stdin=""):
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
        rc = with_db(lambda db: manage_users.main(list(argv), db))
        out = capsys.readouterr()
        return rc, out.out + out.err

    rc, out = run("add", "dan", "--role", "editor", "--name", "Dan Ops", "--password-stdin", stdin="dan's long password\n")
    assert rc == 0 and "Added dan (editor)" in out and "temporary" not in out
    assert sign_in(fresh(), "dan", "dan's long password").status_code == 200
    rc, out = run("add", "dan", "--password-stdin", stdin="another long one\n")
    assert rc == 1 and "already exists" in out
    rc, out = run("add", "eve")  # the default: a generated temporary password, shown once
    assert rc == 0 and "temporary password: " in out
    temp = out.split("temporary password: ")[1].split()[0]
    assert sign_in(fresh(), "eve", temp).status_code == 200
    rc, out = run("list")
    assert rc == 0 and "5 accounts" in out and "dan" in out and "Dan Ops" in out and "$argon2" not in out
    rc, out = run("list", "--json")
    assert rc == 0 and '"password_hash"' not in out and '"username": "eve"' in out
    rc, out = run("reset", "dan")
    assert rc == 0 and "temporary password: " in out
    new_temp = out.split("temporary password: ")[1].split()[0]
    assert sign_in(fresh(), "dan", "dan's long password").status_code == 401
    assert sign_in(fresh(), "dan", new_temp).status_code == 200
    rc, out = run("role", "dan", "admin")
    assert rc == 0 and "now admin" in out
    rc, out = run("disable", "dan")
    assert rc == 0 and sign_in(fresh(), "dan", new_temp).status_code == 401
    rc, out = run("enable", "dan")
    assert rc == 0 and sign_in(fresh(), "dan", new_temp).status_code == 200
    rc, out = run("token", "dan")
    assert rc == 0 and "dan:" in out
    token = [w for w in out.split() if w.startswith("dan:")][0]
    assert fresh().get("/api/stats", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    rc, out = run("token", "dan", "--revoke")
    assert rc == 0 and fresh().get("/api/stats", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    rc, out = run("unlock", "dan")
    assert rc == 0
    rc, out = run("remove", "eve")
    assert rc == 0 and "Would remove" in out and with_db(lambda db: accounts.get_user(db, "eve")) is not None
    rc, out = run("remove", "eve", "--apply")
    assert rc == 0 and with_db(lambda db: accounts.get_user(db, "eve")) is None
    rc, out = run("role", "nobody", "admin")
    assert rc == 1 and "no user named" in out


# ── the migration ────────────────────────────────────────────────────


def test_the_migration_creates_the_users_table_the_model_describes(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    monkeypatch.setattr(config, "DATABASE_URL", url)  # alembic/env.py reads it at run time
    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    insp = inspect(engine)
    assert {"chemicals", "samples", "screening", "toxicology", "users"} <= set(insp.get_table_names())
    indexes = {i["name"]: i for i in insp.get_indexes("users")}
    assert indexes["ix_users_username"]["unique"] and "ix_users_seq" in indexes
    # what the migrations built is what the models describe: no drift
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        assert compare_metadata(ctx, Base.metadata) == []
    command.downgrade(cfg, "0001_initial")
    assert "users" not in set(inspect(engine).get_table_names())
    engine.dispose()
