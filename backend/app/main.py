"""FastAPI application — the Crucible backend entry point.

Run in development:
    cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

Run in production:
    cd backend && python -m app.main          # uvicorn on 0.0.0.0:$PORT (49160)

This app:
  * answers all /api/* routes (chemicals, samples, screening, toxicology, stats),
  * serves the built React client (client/dist) as static files,
  * serves /architecture (interactive architecture doc),
  * returns index.html for any other path so React Router can take over,
  * returns errors as {"error": "..."} JSON with the same status codes.
"""

import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import (
    AUTO_INIT_DB,
    CLIENT_DIST,
    DOCS_DIR,
    PORT,
    SSL_CERT_PATH,
    SSL_KEY_PATH,
    USE_HTTPS,
)
from .database import init_db
from .routers import chemicals, samples, screening, stats, toxicology


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    application = FastAPI(
        title="Crucible: Pandora Toolbox Enhancement (v2.0)",
        description="Chemical & Sample Management API (Python backend)",
        version="2.0",
    )

    # Open CORS policy (same permissive default the v1 backend used).
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Create tables on startup when Alembic is NOT managing the schema — this
    # is the case for the SQLite default and the test suite. In the container
    # AUTO_INIT_DB=false and `alembic upgrade head` runs at startup instead.
    if AUTO_INIT_DB:
        init_db()

    # ── API routers (must be registered before the SPA catch-all) ──
    application.include_router(chemicals.router)
    application.include_router(samples.router)
    application.include_router(screening.router)
    application.include_router(toxicology.router)
    application.include_router(stats.router)

    # ── Error shape parity ──────────────────────────────────────────
    # The v1 API returned {"error": message}; FastAPI's default is
    # {"detail": ...}, so we convert every error to the legacy shape.

    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})

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
        index = CLIENT_DIST / "index.html"
        if index.is_file():
            return FileResponse(index)
        raise StarletteHTTPException(
            status_code=404,
            detail="Client build not found — run `npm run build` in client/ first",
        )

    return application


app = create_app()


if __name__ == "__main__":
    # Bind 0.0.0.0 so the same container/image works on macOS and RHEL8;
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
