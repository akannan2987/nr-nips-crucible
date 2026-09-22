"""The login, rung by rung (docs/13-authentication.md; phase SH-3a).

One dependency, ``require_user``, guards every protected router the same
way ``get_db`` supplies a database session: main.py declares it on the
router, FastAPI calls it before any route in that router runs, and the
route sees the caller's identity or is never reached at all, because the
dependency answered 401 first.

The identity has the same shape on every rung (``Identity``), so nothing
above this module changes when AUTH_MODE moves from ``off`` to ``token``
to ``local`` to ``sso``: only how the identity is established differs.

Rung 1, the token gate, accepts the shared secret two ways:

* ``Authorization: Bearer <token>`` -- what a script or curl sends on every
  request;
* the session cookie the login page sets after a person pasted the token
  once. Its value is not the token but a keyed hash of it, so a cookie that
  leaks cannot be replayed as a bearer header, and a new token signs every
  browser out at once.

Every comparison is constant-time (``hmac.compare_digest``), so the time an
answer takes says nothing about how many characters were right. Nothing in
this module logs, prints or returns the token.

The settings are read from ``config`` at call time, not copied at import,
so the tests can switch the mode on and off around one application.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import asdict, dataclass, field

from fastapi import HTTPException, Request

from . import config

COOKIE_NAME = "crucible_session"
_SESSION_LABEL = b"crucible-session-v1"
NOT_AUTHENTICATED = "Not authenticated"


@dataclass(frozen=True)
class Identity:
    """Who is asking. The same four fields on every rung of the ladder."""

    subject: str
    display_name: str
    roles: list[str] = field(default_factory=list)
    via: str = "off"

    def as_dict(self) -> dict:
        return asdict(self)


# With the login off, everyone is this: the behaviour every version before
# v2.22.0 had. With the token rung, everyone who holds the token is the
# second one -- rung 1 knows "someone with the token", never who.
ANYONE = Identity(subject="anyone", display_name="Anyone (login off)", roles=["admin"], via="off")
TOKEN_HOLDER = Identity(subject="token", display_name="Token holder", roles=["admin"], via="token")


def check_settings() -> None:
    """Refuse to start with a login that cannot work.

    Called once by ``create_app``. A mode this version does not know, or the
    token rung without a usable token, stops the process with a plain
    message instead of serving an open port that looks closed.
    """
    mode = config.AUTH_MODE
    if mode not in config.AUTH_MODES:
        raise RuntimeError(
            f"AUTH_MODE={mode!r} is not one of {', '.join(config.AUTH_MODES)} (docs/13-authentication.md)"
        )
    if mode == "token":
        if not config.CRUCIBLE_TOKEN:
            raise RuntimeError(
                "AUTH_MODE=token but CRUCIBLE_TOKEN is empty. Generate one with "
                "python3 -c 'import secrets; print(secrets.token_urlsafe(48))' and put it in .env.local"
            )
        if len(config.CRUCIBLE_TOKEN) < config.TOKEN_MIN_LENGTH:
            raise RuntimeError(
                f"CRUCIBLE_TOKEN is {len(config.CRUCIBLE_TOKEN)} characters; at least "
                f"{config.TOKEN_MIN_LENGTH} are required (a guessable token is no gate)"
            )


def session_value(secret: str) -> str:
    """The cookie's value for this token: a keyed hash of a fixed label.

    Recomputed on every request and compared in constant time; rotating the
    token changes it, which is how a new token signs every browser out.
    """
    return hmac.new(secret.encode("utf-8"), _SESSION_LABEL, hashlib.sha256).hexdigest()


def token_matches(presented: str | None) -> bool:
    secret = config.CRUCIBLE_TOKEN
    if not presented or not secret:
        return False
    return hmac.compare_digest(presented.encode("utf-8"), secret.encode("utf-8"))


def cookie_matches(presented: str | None) -> bool:
    secret = config.CRUCIBLE_TOKEN
    if not presented or not secret:
        return False
    return hmac.compare_digest(presented.encode("utf-8"), session_value(secret).encode("utf-8"))


def bearer_of(request: Request) -> str | None:
    """The token from ``Authorization: Bearer <token>``, or None."""
    scheme, _, value = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return None


def identify(request: Request) -> Identity | None:
    """Who is asking, or None when nobody acceptable is.

    Used by the open ``/api/auth/me`` route, which must answer 200 either way
    so the page can decide whether to show the login.
    """
    mode = config.AUTH_MODE
    if mode == "off":
        return ANYONE
    if mode == "token":
        if token_matches(bearer_of(request)) or cookie_matches(request.cookies.get(COOKIE_NAME)):
            return TOKEN_HOLDER
        return None
    # check_settings() stops the process before this can happen.
    raise HTTPException(status_code=500, detail=f"AUTH_MODE={mode!r} is not supported by this version")


def require_user(request: Request) -> Identity:
    """The guard: the identity, or 401 and the route never runs.

    The answer is the same for a missing and for a wrong credential (rule 5
    of the plan): a difference would tell a guesser something.
    """
    who = identify(request)
    if who is None:
        raise HTTPException(
            status_code=401,
            detail=NOT_AUTHENTICATED,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return who
