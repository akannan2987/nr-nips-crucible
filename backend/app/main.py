"""FastAPI application — the Crucible backend entry point.

Run in development:
    cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

Run in production:
    cd backend && python -m app.main          # uvicorn on 0.0.0.0:$PORT (49160)

This app:
  * answers all /api/* routes (chemicals, samples, screening, toxicology, stats),
    every one of them behind the login guard when AUTH_MODE is not off: 401
    without a credential, 403 when the account's role does not allow the verb
    (local accounts, v2.23.0); only /api/health, /api/instance and /api/auth/*
    stay open (docs/13-authentication.md),
  * serves the built React client (client/dist) as static files,
  * serves /architecture (interactive architecture doc),
  * returns index.html for any other path so React Router can take over,
  * returns errors as {"error": "..."} JSON with the same status codes.
"""

import os

import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .auth import check_settings, require_user
from .config import (
    AUTO_INIT_DB,
    CLIENT_DIST,
    CORS_ORIGINS,
    DOCS_DIR,
    PORT,
    SSL_CERT_PATH,
    SSL_KEY_PATH,
    USE_HTTPS,
)
from .database import init_db
from .routers import auth, chemicals, health, instance, query, samples, screening, stats, toxicology


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    application = FastAPI(
        title="Crucible: Pandora Toolbox Enhancement (v2.0)",
        description="Chemical & Sample Management API (Python backend)",
        version="2.0",
    )

    # A login that cannot work (a mode this version does not know, the token
    # rung without a usable token, the local rung without a session secret)
    # stops the process here, with the reason, rather than serving an open
    # port that looks closed.
    check_settings()

    # Cross-origin policy: closed unless CORS_ORIGINS names another site
    # (decision A7 in docs/13-authentication.md). The page is served by this
    # process, so a browser on the same origin never needs it; with a login
    # cookie in play the old wildcard would have been a real hole.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Create tables on startup when Alembic is NOT managing the schema — this
    # is the case for the SQLite default and the test suite. In the container
    # AUTO_INIT_DB=false and `alembic upgrade head` runs at startup instead.
    if AUTO_INIT_DB:
        init_db()

    # ── API routers (must be registered before the SPA catch-all) ──
    # The guard is declared once per router, not once per route: every route
    # in a guarded router runs only after require_user has returned an
    # identity whose role allows the verb, or the caller got 401 or 403
    # (docs/13-authentication.md). With AUTH_MODE=off the guard lets everyone
    # through as an admin, so nothing changes.
    guard = [Depends(require_user)]
    application.include_router(chemicals.router, dependencies=guard)
    application.include_router(samples.router, dependencies=guard)
    application.include_router(screening.router, dependencies=guard)
    application.include_router(toxicology.router, dependencies=guard)
    application.include_router(stats.router, dependencies=guard)
    application.include_router(query.router, dependencies=guard)
    # Open on every rung: the health probe, the instance label, and the door itself.
    application.include_router(health.router)
    application.include_router(instance.router)
    application.include_router(auth.router)

    # ── Error shape parity ──────────────────────────────────────────
    # The v1 API returned {"error": message}; FastAPI's default is
    # {"detail": ...}, so we convert every error to the legacy shape.

    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Keep the exception's own headers: the guard's 401 carries
        # WWW-Authenticate: Bearer, which tells a client how to log in.
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": str(exc.detail)},
            headers=getattr(exc, "headers", None),
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # The v1 API performed no validation, so this only fires for malformed
        # JSON bodies and the like — report as a 400 in the same shape.
        return JSONResponse(status_code=400, content={"error": str(exc)})

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Mirror of the v1 error middleware (res.status(500).json({error})).
        return JSONResponse(status_code=500, content={"error": str(exc)})

    # ── Non-API routes ─────────────────────────────────────────────

    @application.get("/architecture", include_in_schema=False)
    def architecture_page() -> FileResponse:
        """Interactive architecture documentation page."""
        page = DOCS_DIR / "architecture-interactive.html"
        if not page.is_file():
            raise StarletteHTTPException(status_code=404, detail="architecture page not found")
        return FileResponse(page)

    @application.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        """Static files + SPA fallback.

        Serves client/dist, then falls back to index.html for unknown paths
        so React Router can handle client-side routes.
        """
        if full_path:
            candidate = (CLIENT_DIST / full_path).resolve()
            # Path-traversal guard: only serve files inside client/dist.
            if candidate.is_file() and str(candidate).startswith(str(CLIENT_DIST.resolve())):
                return FileResponse(candidate)
        # The shell must never be cached. Its <script> tag names a
        # content-hashed bundle, so a stale index.html pins the browser to an
        # old build no matter how many times the app is rebuilt — the user
        # keeps seeing yesterday's interface and no amount of reloading helps.
        # The hashed assets themselves are safe to cache forever.
        index = CLIENT_DIST / "index.html"
        if index.is_file():
            return FileResponse(
                index,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )
        raise StarletteHTTPException(
            status_code=404,
            detail="Client build not found — run `npm run build` in client/ first",
        )

    return application


app = create_app()


if __name__ == "__main__":
    # Bind 0.0.0.0 so the same container/image works on the development machine and on RHEL8;
    # the port comes from the PORT env var (default 49160).
    host = os.environ.get("HOST", "0.0.0.0")

    if USE_HTTPS and SSL_CERT_PATH.is_file() and SSL_KEY_PATH.is_file():
        print(f"🔒 HTTPS enabled — cert: {SSL_CERT_PATH}")
        uvicorn.run(
            app,
            host=host,
            port=PORT,
            ssl_certfile=str(SSL_CERT_PATH),
            ssl_keyfile=str(SSL_KEY_PATH),
        )
    else:
        # Same graceful fallback the v1 backend had: missing certs
        # must not take the app down.
        if USE_HTTPS:
            print(f"⚠️  USE_HTTPS=true but certificates not found "
                  f"({SSL_CERT_PATH} / {SSL_KEY_PATH}) — starting HTTP instead.")
        uvicorn.run(app, host=host, port=PORT)
