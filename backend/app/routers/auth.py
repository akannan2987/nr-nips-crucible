"""/api/auth -- who am I, log in, log out, change my password (phases SH-3a and SH-3b).

These routes are the door itself, so they are never behind the guard:

* ``GET  /api/auth/me``        -- open; says which mode is on and whether this
                                 caller is signed in. The page calls it once
                                 on load to decide whether to show the login.
* ``POST /api/auth/login``     -- the token rung: ``{"token": …}``, checked in
                                 constant time; the local rung: ``{"username",
                                 "password"}``, checked against the Argon2 hash.
                                 On success a session cookie the browser sends
                                 on every later request (including downloads,
                                 which a header could not cover). A wrong
                                 credential answers 401 with the same words as
                                 a missing one, after a short fixed pause.
* ``POST /api/auth/logout``    -- clears the cookie.
* ``POST /api/auth/password``  -- the local rung only: a signed-in person
                                 changes their own password; every other
                                 browser of theirs is signed out.

The answer shape is the same on every rung: ``{mode, authenticated, user}``.
"""

import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from .. import accounts, config
from ..auth import (
    ANYONE,
    COOKIE_NAME,
    NOT_AUTHENTICATED,
    TOKEN_HOLDER,
    identify,
    identity_of,
    issue_session,
    session_value,
    set_session_cookie,
    token_matches,
)
from ..database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

# A small, constant cost per wrong guess. A 64-character random token is
# not guessable in any case; this keeps a mistaken script from hammering,
# and with passwords it is one of three brakes (with Argon2's own cost and
# the per-account lockout).
FAILED_LOGIN_PAUSE_SECONDS = 0.25


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    token: str = ""
    username: str = ""
    password: str = ""


class PasswordIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    current: str = ""
    new: str = ""


def _answer(request: Request, db: Session) -> dict:
    who = identify(request, db)
    return {
        "mode": config.AUTH_MODE,
        "authenticated": who is not None,
        "user": who.as_dict() if who else None,
    }


def _refused() -> HTTPException:
    time.sleep(FAILED_LOGIN_PAUSE_SECONDS)
    return HTTPException(status_code=401, detail=NOT_AUTHENTICATED, headers={"WWW-Authenticate": "Bearer"})


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)) -> dict:
    """GET /api/auth/me -- mode, and whether this caller is signed in. Always 200."""
    return _answer(request, db)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    """POST /api/auth/login -- set the session cookie, or 401.

    Token rung: ``{"token": "..."}``. Local rung: ``{"username": "...", "password": "..."}``.
    """
    mode = config.AUTH_MODE
    if mode == "off":
        raise HTTPException(status_code=400, detail="AUTH_MODE is off: no login is needed")
    if mode == "token":
        if not token_matches(body.token):
            raise _refused()
        set_session_cookie(response, request, session_value(config.CRUCIBLE_TOKEN))
        return {"mode": "token", "authenticated": True, "user": TOKEN_HOLDER.as_dict()}
    if mode == "local":
        user = accounts.authenticate_password(db, body.username.strip().lower(), body.password)
        if user is None:
            raise _refused()
        set_session_cookie(response, request, issue_session(user))
        return {"mode": "local", "authenticated": True, "user": identity_of(user, "local").as_dict()}
    raise HTTPException(status_code=400, detail=f"AUTH_MODE={mode!r} does not log in here")


@router.post("/logout")
def logout(response: Response) -> dict:
    """POST /api/auth/logout -- forget this browser. Harmless when already out."""
    response.delete_cookie(COOKIE_NAME, path="/")
    off = config.AUTH_MODE == "off"
    return {"mode": config.AUTH_MODE, "authenticated": off, "user": ANYONE.as_dict() if off else None}


@router.post("/password")
def change_password(body: PasswordIn, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    """POST /api/auth/password {"current", "new"} -- the local rung: change my own password.

    Needs a signed-in person (401 otherwise); the current password must be
    right (400 with a plain reason: the caller is known, so the reason is
    help, not a leak); the new one must meet the rules. Every other browser
    of this person is signed out (the password version moves); this one gets
    a fresh cookie so it stays in.
    """
    if config.AUTH_MODE != "local":
        raise HTTPException(status_code=400, detail=f"AUTH_MODE={config.AUTH_MODE!r} has no passwords to change")
    who = identify(request, db)
    if who is None or who.via != "local":
        raise HTTPException(status_code=401, detail=NOT_AUTHENTICATED, headers={"WWW-Authenticate": "Bearer"})
    row = accounts.get_user(db, who.subject)
    if row is None or not accounts.verify_password(row.doc.get("password_hash"), body.current):
        time.sleep(FAILED_LOGIN_PAUSE_SECONDS)
        raise HTTPException(status_code=400, detail="The current password is not right")
    reason = accounts.check_password_rules(body.new)
    if reason:
        raise HTTPException(status_code=400, detail=reason.capitalize())
    accounts.set_password(db, who.subject, body.new)
    user = accounts.get_user(db, who.subject).doc
    set_session_cookie(response, request, issue_session(user))
    return {"mode": "local", "authenticated": True, "user": identity_of(user, "local").as_dict()}
