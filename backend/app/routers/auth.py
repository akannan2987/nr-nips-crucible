"""/api/auth -- who am I, log in, log out (phase SH-3a).

These three routes are the door itself, so they are never behind the guard:

* ``GET  /api/auth/me``     -- open; says which mode is on and whether this
                              caller is signed in. The page calls it once
                              on load to decide whether to show the login.
* ``POST /api/auth/login``  -- the token rung: the pasted token, checked in
                              constant time; on success a session cookie
                              the browser sends on every later request
                              (including downloads, which a header could
                              not cover). A wrong token answers 401 with
                              the same words as a missing one, after a
                              short fixed pause.
* ``POST /api/auth/logout`` -- clears the cookie.

Later rungs add username-and-password and single sign-on to the same
routes; the answer shape stays.
"""

import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict

from .. import config
from ..auth import ANYONE, COOKIE_NAME, NOT_AUTHENTICATED, TOKEN_HOLDER, identify, session_value, token_matches

router = APIRouter(prefix="/api/auth", tags=["auth"])

# A small, constant cost per wrong guess. A 64-character random token is
# not guessable in any case; this keeps a mistaken script from hammering.
FAILED_LOGIN_PAUSE_SECONDS = 0.25


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    token: str = ""


def _answer(request: Request) -> dict:
    who = identify(request)
    return {
        "mode": config.AUTH_MODE,
        "authenticated": who is not None,
        "user": who.as_dict() if who else None,
    }


@router.get("/me")
def me(request: Request) -> dict:
    """GET /api/auth/me -- mode, and whether this caller is signed in. Always 200."""
    return _answer(request)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response) -> dict:
    """POST /api/auth/login {"token": "..."} -- set the session cookie, or 401."""
    if config.AUTH_MODE == "off":
        raise HTTPException(status_code=400, detail="AUTH_MODE is off: no login is needed")
    if config.AUTH_MODE != "token":
        raise HTTPException(status_code=400, detail=f"AUTH_MODE={config.AUTH_MODE!r} does not log in with a token")
    if not token_matches(body.token):
        time.sleep(FAILED_LOGIN_PAUSE_SECONDS)
        raise HTTPException(status_code=401, detail=NOT_AUTHENTICATED, headers={"WWW-Authenticate": "Bearer"})
    response.set_cookie(
        COOKIE_NAME,
        session_value(config.CRUCIBLE_TOKEN),
        max_age=config.SESSION_HOURS * 3600,
        httponly=True,  # a script on a page cannot read it
        samesite="lax",  # another site cannot ride on it
        secure=request.url.scheme == "https",  # HTTPS only, except on a plain-HTTP development machine
        path="/",
    )
    return {"mode": "token", "authenticated": True, "user": TOKEN_HOLDER.as_dict()}


@router.post("/logout")
def logout(response: Response) -> dict:
    """POST /api/auth/logout -- forget this browser. Harmless when already out."""
    response.delete_cookie(COOKIE_NAME, path="/")
    off = config.AUTH_MODE == "off"
    return {"mode": config.AUTH_MODE, "authenticated": off, "user": ANYONE.as_dict() if off else None}
