"""The login, rung by rung (docs/13-authentication.md; phases SH-3a and SH-3b).

One dependency, ``require_user``, guards every protected router the same
way ``get_db`` supplies a database session: main.py declares it on the
router, FastAPI calls it before any route in that router runs, and the
route sees the caller's identity or is never reached at all, because the
dependency answered 401 (not signed in) or 403 (signed in, but the role
does not allow this) first.

The identity has the same shape on every rung (``Identity``), so nothing
above this module changes when AUTH_MODE moves from ``off`` to ``token``
to ``local`` to ``sso``: only how the identity is established differs.

Rung 1, the token gate (``token``), accepts the shared secret two ways:

* ``Authorization: Bearer <token>`` -- what a script or curl sends on every
  request;
* the session cookie the login page sets after a person pasted the token
  once. Its value is not the token but a keyed hash of it, so a cookie that
  leaks cannot be replayed as a bearer header, and a new token signs every
  browser out at once.

Rung 2, local accounts (``local``, v2.23.0), knows *who*:

* a person logs in with a username and a password; the password is checked
  against an Argon2 hash in the ``users`` table (``accounts.py``); the
  browser gets a **signed** cookie (``itsdangerous``) naming the user and
  the version of their password, timestamped, valid for SESSION_HOURS from
  the last request (a sliding session: an ageing cookie is re-issued);
* a script sends a **personal token**, ``<username>:<secret>``, as the same
  bearer header; only its hash is stored, and it is revoked by name;
* on every request the account is looked up again, so a disabled account
  or a reset password takes effect at once, cookie and token alike;
* each identity carries one **role**, viewer, editor or admin, and the
  guard applies one rule, ``required_role``: reading needs a viewer,
  writing an editor, deleting and merging an admin.

Every comparison is constant-time (``hmac.compare_digest``, Argon2's own
verify, the signer's own check), so the time an answer takes says nothing
about how many characters were right. Nothing in this module logs, prints
or returns a secret.

The settings are read from ``config`` at call time, not copied at import,
so the tests can switch the mode around one application.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import asdict, dataclass, field

from fastapi import Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from . import accounts, config
from .database import get_db

COOKIE_NAME = "crucible_session"
_SESSION_LABEL = b"crucible-session-v1"
_SESSION_SALT = "crucible-session-v2"  # the local rung's signed cookie
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

    def can(self, role: str) -> bool:
        """True when one of this identity's roles includes ``role``."""
        return any(accounts.role_includes(held, role) for held in self.roles)


# With the login off, everyone is this: the behaviour every version before
# v2.22.0 had. With the token rung, everyone who holds the token is the
# second one -- rung 1 knows "someone with the token", never who.
ANYONE = Identity(subject="anyone", display_name="Anyone (login off)", roles=["admin"], via="off")
TOKEN_HOLDER = Identity(subject="token", display_name="Token holder", roles=["admin"], via="token")


def identity_of(user: dict, via: str) -> Identity:
    """The identity of a local account: the username is the subject."""
    return Identity(
        subject=str(user["username"]),
        display_name=str(user.get("display_name") or user["username"]),
        roles=[str(user.get("role") or "viewer")],
        via=via,
    )


def check_settings() -> None:
    """Refuse to start with a login that cannot work.

    Called once by ``create_app``. A mode this version does not know, the
    token rung without a usable token, or the local rung without a usable
    session secret, stops the process with a plain message instead of
    serving an open port that looks closed.
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
    if mode == "local":
        if not config.SESSION_SECRET:
            raise RuntimeError(
                "AUTH_MODE=local but SESSION_SECRET is empty. Generate one with "
                "python3 -c 'import secrets; print(secrets.token_urlsafe(48))' and put it in .env.local"
            )
        if len(config.SESSION_SECRET) < config.TOKEN_MIN_LENGTH:
            raise RuntimeError(
                f"SESSION_SECRET is {len(config.SESSION_SECRET)} characters; at least "
                f"{config.TOKEN_MIN_LENGTH} are required (a guessable key signs nothing)"
            )


# ── rung 1: the shared token ──────────────────────────────────────────


def session_value(secret: str) -> str:
    """The rung-1 cookie's value for this token: a keyed hash of a fixed label.

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


# ── rung 2: the signed, sliding session ──────────────────────────────


def _signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.SESSION_SECRET, salt=_SESSION_SALT)


def issue_session(user: dict) -> str:
    """The cookie value for this account: signed, timestamped, not encrypted.

    It names the user and the version of their password; it holds no
    secret, so it does not need to be. The signature is what a browser
    cannot forge, and the timestamp is what makes the session expire and
    slide. A reset password moves the version, which voids the cookie.
    """
    return _signer().dumps({"u": user["username"], "v": int(user.get("password_version") or 0)})


def read_session(value: str | None) -> tuple[dict, float] | None:
    """The payload and its issue time, when the signature is good and the
    cookie is younger than SESSION_HOURS; else None."""
    if not value:
        return None
    try:
        payload, issued = _signer().loads(value, max_age=config.SESSION_HOURS * 3600, return_timestamp=True)
    except (SignatureExpired, BadSignature):
        return None
    if not isinstance(payload, dict) or "u" not in payload or "v" not in payload:
        return None
    return payload, issued.timestamp()


def set_session_cookie(response: Response, request: Request, value: str) -> None:
    """One place that knows the cookie's flags, for both rungs."""
    response.set_cookie(
        COOKIE_NAME,
        value,
        max_age=config.SESSION_HOURS * 3600,
        httponly=True,  # a script on a page cannot read it
        samesite="lax",  # another site cannot ride on it
        secure=request.url.scheme == "https",  # HTTPS only, except on a plain-HTTP development machine
        path="/",
    )


# ── who is asking ─────────────────────────────────────────────────────


def identify(request: Request, db: Session | None = None) -> Identity | None:
    """Who is asking, or None when nobody acceptable is.

    Used by the open ``/api/auth/me`` route, which must answer 200 either way
    so the page can decide whether to show the login. In the local mode it
    needs the database to look the account up; the age of a session cookie
    is left on ``request.state`` for the guard to decide whether to slide.
    """
    mode = config.AUTH_MODE
    if mode == "off":
        return ANYONE
    if mode == "token":
        if token_matches(bearer_of(request)) or cookie_matches(request.cookies.get(COOKIE_NAME)):
            return TOKEN_HOLDER
        return None
    if mode == "local":
        if db is None:
            return None
        bearer = bearer_of(request)
        if bearer:
            user = accounts.authenticate_token(db, bearer)
            return identity_of(user, "token") if user else None
        session = read_session(request.cookies.get(COOKIE_NAME))
        if session is None:
            return None
        payload, issued = session
        found = accounts.user_for_session(db, str(payload["u"]), int(payload["v"]))
        if found is None:
            return None
        user, stale = found
        request.state.session_issued = issued
        request.state.session_stale = stale
        request.state.session_user = user
        return identity_of(user, "local")
    # check_settings() stops the process before this can happen.
    raise HTTPException(status_code=500, detail=f"AUTH_MODE={mode!r} is not supported by this version")


# ── what each role may do ─────────────────────────────────────────────

# Paths (suffixes) that destroy or reshape records with one call, whatever
# the verb says: an admin's job, like DELETE itself.
_ADMIN_SUFFIXES = ("/bulk/delete", "/merge", "/all/clear")
# Reads that happen to be POSTs: the read-only SQL console.
_VIEWER_POSTS = ("/api/query",)


def required_role(method: str, path: str) -> str:
    """The role a request needs, from its verb and path, in one rule.

    Reading is a viewer's right, writing an editor's, deleting an admin's.
    The rule lives here, once, rather than on each route, for the same
    reason the guard is declared per router: a route added next month is
    covered without anyone remembering to cover it.
    """
    method = method.upper()
    if method in ("GET", "HEAD", "OPTIONS"):
        return "viewer"
    if method == "DELETE":
        return "admin"
    if any(path.endswith(s) for s in _ADMIN_SUFFIXES):
        return "admin"
    if path in _VIEWER_POSTS:
        return "viewer"
    return "editor"


def require_user(request: Request, response: Response, db: Session = Depends(get_db)) -> Identity:
    """The guard: the identity, or 401 and the route never runs; or 403 when
    the identity's role does not allow this verb on this path.

    The 401 is the same for a missing and for a wrong credential (rule 5
    of the plan): a difference would tell a guesser something. The 403
    names the role needed: the caller is known, and that is help, not a leak.
    """
    who = identify(request, db)
    if who is None:
        raise HTTPException(
            status_code=401,
            detail=NOT_AUTHENTICATED,
            headers={"WWW-Authenticate": "Bearer"},
        )
    needed = required_role(request.method, request.url.path)
    if not who.can(needed):
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: this needs the {needed} role (yours: {', '.join(who.roles)})",
        )
    # The sliding session: a cookie that has aged past the slide interval is
    # re-issued with a fresh timestamp, so the ten hours count from the last
    # request rather than from the login. Only cookies slide; a token has no
    # age. A cookie of the previous password version (within the grace) is
    # re-issued too, which moves that browser onto the new version.
    issued = getattr(request.state, "session_issued", None)
    stale = getattr(request.state, "session_stale", False)
    if who.via == "local" and issued is not None and (stale or time.time() - issued > config.SESSION_SLIDE_SECONDS):
        set_session_cookie(response, request, issue_session(request.state.session_user))
    return who
