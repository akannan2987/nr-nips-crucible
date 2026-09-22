"""The accounts of the local login: rung 2 of docs/13-authentication.md (phase SH-3b).

One module behind three callers, so they cannot disagree: the login route
(``routers/auth.py``), the guard (``auth.py``) and the management script
(``scripts/manage_users.py``). Everything here reads and writes the
``users`` table through ``store``, in the same hybrid document pattern as
every other record: the document is the truth, the ``username`` column is
the index.

What a user's document holds, and what never leaves this module:

* ``password_hash`` -- an **Argon2id** hash (``argon2-cffi``). One-way: the
  database can check a password, never reveal it. Never printed, never
  returned by the API, never readable through the query console.
* ``password_version`` -- bumped on every reset or change; the session
  cookie carries the value it was issued with, so a reset signs every
  browser of that person out at once.
* ``token_hash`` -- the SHA-256 of the personal token, for scripts. The
  token is random and long, so a fast hash is the right one (an attacker
  cannot guess it, and a per-request Argon2 would make every script call
  slow). The token itself is shown once, when issued, and never stored.
* ``role`` -- ``viewer``, ``editor`` or ``admin``; ``enabled`` -- a
  disabled account is refused everywhere, cookie and token included.
* ``failed_attempts`` and ``locked_until`` -- the brute-force lockout.

Rule 5 of the plan holds throughout: a caller learns "not authenticated",
never whether the username exists or which half was wrong.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy.orm import Session

from . import config
from .compat import now_iso
from .models import User
from .store import all_rows, find_row, insert_doc, replace_doc

log = logging.getLogger("crucible.accounts")

ROLES: tuple[str, ...] = ("viewer", "editor", "admin")
# Each role includes the ones before it: an editor may do what a viewer may.
_RANK = {role: i for i, role in enumerate(ROLES)}

# Lowercase letters, digits, dot, hyphen, underscore; starts with a letter or
# digit; 2 to 32 characters. Lowercase on purpose: "Alice" and "alice" being
# two accounts is a support call waiting to happen.
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,31}$")

# A personal token is "<username>:<secret>". The name in front makes the
# lookup direct and tells the operator whose key this is; the secret behind
# it is what is checked. Neither half is ever stored in clear.
TOKEN_SEPARATOR = ":"

_hasher = PasswordHasher()  # Argon2id with the library's current defaults


# ── the primitives ────────────────────────────────────────────────────


def role_includes(held: str, needed: str) -> bool:
    """True when a person with role ``held`` may do what ``needed`` allows."""
    return _RANK.get(held, -1) >= _RANK.get(needed, len(ROLES))


def valid_username(name: str) -> bool:
    return bool(USERNAME_RE.match(name or ""))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Constant-time as far as Argon2 allows; False for any failure, never an exception."""
    if not password_hash or not password:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except VerificationError:
        return False
    except Exception:  # noqa: BLE001 - a corrupt hash is a refusal, not a crash
        return False


def check_password_rules(password: str) -> str | None:
    """The reason a password is not acceptable, or None when it is."""
    if len(password or "") < config.PASSWORD_MIN_LENGTH:
        return f"a password needs at least {config.PASSWORD_MIN_LENGTH} characters"
    return None


def generate_password() -> str:
    """A temporary password: random, 16 characters, readable enough to type once."""
    return secrets.token_urlsafe(12)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


# ── reading ───────────────────────────────────────────────────────────


def get_user(db: Session, username: str):
    """The row for this username, or None. Callers keep the row to write it back."""
    if not username:
        return None
    return find_row(db, User, "username", username.strip().lower())


def public_view(doc: dict[str, Any]) -> dict[str, Any]:
    """What ``manage_users.py list`` prints: never a hash, never a secret."""
    locked_until = _parse(doc.get("locked_until"))
    return {
        "username": doc.get("username"),
        "display_name": doc.get("display_name"),
        "role": doc.get("role"),
        "enabled": bool(doc.get("enabled", True)),
        "has_token": bool(doc.get("token_hash")),
        "token_issued_at": doc.get("token_issued_at"),
        "last_login": doc.get("last_login"),
        "failed_attempts": int(doc.get("failed_attempts") or 0),
        "locked": bool(locked_until and locked_until > _now()),
        "created_at": doc.get("created_at"),
    }


def list_users(db: Session) -> list[dict[str, Any]]:
    return [public_view(row.doc) for row in all_rows(db, User)]


# ── writing (the management script's verbs) ──────────────────────────


def add_user(db: Session, username: str, password: str, role: str = "viewer", display_name: str = "") -> dict[str, Any]:
    """Create an account. Raises ValueError with a plain reason on bad input."""
    username = (username or "").strip().lower()
    if not valid_username(username):
        raise ValueError("a username is 2 to 32 lowercase letters, digits, dots, hyphens or underscores, starting with a letter or digit")
    if role not in ROLES:
        raise ValueError(f"the role must be one of {', '.join(ROLES)}")
    reason = check_password_rules(password)
    if reason:
        raise ValueError(reason)
    if get_user(db, username) is not None:
        raise ValueError(f"a user named {username!r} already exists")
    now = now_iso()
    doc = {
        "id": str(uuid.uuid4()),
        "username": username,
        "display_name": (display_name or "").strip() or username,
        "role": role,
        "enabled": True,
        "password_hash": hash_password(password),
        "password_version": 1,
        "token_hash": None,
        "token_issued_at": None,
        "created_at": now,
        "updated_at": now,
        "last_login": None,
        "failed_attempts": 0,
        "locked_until": None,
    }
    insert_doc(db, User, doc)
    return public_view(doc)


def _update(db: Session, username: str, **changes: Any) -> dict[str, Any]:
    row = get_user(db, username)
    if row is None:
        raise ValueError(f"no user named {username!r}")
    doc = dict(row.doc)
    doc.update(changes)
    doc["updated_at"] = now_iso()
    replace_doc(db, row, doc)
    return public_view(doc)


def set_password(db: Session, username: str, password: str) -> dict[str, Any]:
    """A new password; every session of this person is signed out (the version moves)."""
    reason = check_password_rules(password)
    if reason:
        raise ValueError(reason)
    row = get_user(db, username)
    if row is None:
        raise ValueError(f"no user named {username!r}")
    return _update(
        db,
        username,
        password_hash=hash_password(password),
        password_version=int(row.doc.get("password_version") or 0) + 1,
        password_changed_at=now_iso(),
        failed_attempts=0,
        locked_until=None,
    )


def set_enabled(db: Session, username: str, enabled: bool) -> dict[str, Any]:
    """Disable a leaver, or enable again. Disabling refuses cookie and token at once."""
    changes: dict[str, Any] = {"enabled": bool(enabled)}
    if enabled:
        changes.update(failed_attempts=0, locked_until=None)
    return _update(db, username, **changes)


def set_role(db: Session, username: str, role: str) -> dict[str, Any]:
    if role not in ROLES:
        raise ValueError(f"the role must be one of {', '.join(ROLES)}")
    return _update(db, username, role=role)


def unlock(db: Session, username: str) -> dict[str, Any]:
    return _update(db, username, failed_attempts=0, locked_until=None)


def issue_token(db: Session, username: str) -> str:
    """A new personal token, returned ONCE; only its hash is stored. Replaces any older one."""
    row = get_user(db, username)
    if row is None:
        raise ValueError(f"no user named {username!r}")
    token = f"{row.doc['username']}{TOKEN_SEPARATOR}{secrets.token_urlsafe(36)}"
    _update(db, username, token_hash=token_hash(token), token_issued_at=now_iso())
    return token


def revoke_token(db: Session, username: str) -> dict[str, Any]:
    return _update(db, username, token_hash=None, token_issued_at=None)


# ── authenticating (the login route and the guard) ───────────────────


def is_locked(doc: dict[str, Any]) -> bool:
    until = _parse(doc.get("locked_until"))
    return bool(until and until > _now())


def authenticate_password(db: Session, username: str, password: str) -> dict[str, Any] | None:
    """The user's document when the username and password are right and the
    account is enabled and not locked; None otherwise, for every reason alike.

    Failures are counted on the account; the tenth in a row locks it for
    LOGIN_LOCKOUT_MINUTES. A success clears the count and records the time.
    The log line names the user and the count, never the password.
    """
    row = get_user(db, username)
    if row is None:
        # No account: nothing to count, and the caller is told exactly what a
        # wrong password would be told. (The route adds the same pause.)
        return None
    doc = dict(row.doc)
    if not doc.get("enabled", True):
        log.warning("login refused for %r: account disabled", doc["username"])
        return None
    if is_locked(doc):
        log.warning("login refused for %r: locked until %s", doc["username"], doc.get("locked_until"))
        return None
    if not verify_password(doc.get("password_hash"), password):
        doc["failed_attempts"] = int(doc.get("failed_attempts") or 0) + 1
        if doc["failed_attempts"] >= config.LOGIN_MAX_FAILURES:
            doc["locked_until"] = (_now() + timedelta(minutes=config.LOGIN_LOCKOUT_MINUTES)).isoformat()
            log.warning("login failed for %r (%d in a row): locked for %d minutes",
                        doc["username"], doc["failed_attempts"], config.LOGIN_LOCKOUT_MINUTES)
        else:
            log.warning("login failed for %r (%d in a row)", doc["username"], doc["failed_attempts"])
        replace_doc(db, row, doc)
        return None
    doc["failed_attempts"] = 0
    doc["locked_until"] = None
    doc["last_login"] = now_iso()
    replace_doc(db, row, doc)
    return doc


def authenticate_token(db: Session, token: str | None) -> dict[str, Any] | None:
    """The user's document for a valid, current personal token of an enabled account; else None."""
    if not token or TOKEN_SEPARATOR not in token:
        return None
    username, _, _secret = token.partition(TOKEN_SEPARATOR)
    row = get_user(db, username)
    if row is None:
        return None
    doc = row.doc
    stored = doc.get("token_hash")
    if not stored or not doc.get("enabled", True):
        return None
    if not hmac.compare_digest(token_hash(token).encode("ascii"), str(stored).encode("ascii")):
        return None
    return doc


def user_for_session(db: Session, username: str, password_version: int) -> tuple[dict[str, Any], bool] | None:
    """The user's document for a session cookie, and whether the cookie is
    stale (issued under the previous password version, still within the
    grace); None when the account is gone, disabled, or has had its password
    reset longer ago than the grace allows.

    The grace exists for one reason: the browser that changes its own
    password has requests in flight with the old cookie, and a 401 on one
    of them would sign it out the moment it succeeded. Within the grace the
    old version is honoured and the caller is handed the new cookie.
    """
    row = get_user(db, username)
    if row is None:
        return None
    doc = row.doc
    if not doc.get("enabled", True):
        return None
    current = int(doc.get("password_version") or 0)
    if current == int(password_version):
        return doc, False
    changed = _parse(doc.get("password_changed_at"))
    if current - 1 == int(password_version) and changed and (_now() - changed) <= timedelta(seconds=config.PASSWORD_GRACE_SECONDS):
        return doc, True
    return None
