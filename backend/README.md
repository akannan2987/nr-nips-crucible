# Crucible Python Backend (FastAPI)

The Crucible backend: FastAPI + SQLAlchemy 2 + Pydantic v2 over SQLite (with
optional PostgreSQL). It implements the frozen v1 API contract (see `../API.md`)
so the React client works unchanged. (It began life as a strangler-fig
replacement for a Node/Express service, which has since been retired.)

## Stack

| Piece | Choice | Where to see it |
|---|---|---|
| Web framework | FastAPI | `app/main.py`, `app/routers/` |
| ASGI server | uvicorn | `app/main.py` (bottom) |
| ORM | SQLAlchemy 2.0 | `app/models.py`, `app/database.py` |
| Validation | Pydantic v2 | `app/schemas.py` |
| Database | SQLite (default) or PostgreSQL | `app/config.py` (`DATABASE_URL`) |
| Migrations | Alembic | `alembic/`, `alembic.ini` |
| Excel | openpyxl (+ pandas available) | `app/utils/excel.py`, `app/utils/samples_excel.py` |
| Structures | RDKit | `app/utils/sdf.py` |
| Tests | pytest | `tests/` |

## Quickstart (macOS)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Run the test suite (contract-parity tests + unit tests)
.venv/bin/pytest

# Start the API (dev, with auto-reload, on a side port)
.venv/bin/uvicorn app.main:app --reload --port 8000

# Start the API (production style: 0.0.0.0:$PORT, default 49160)
.venv/bin/python -m app.main
```

Interactive API docs (FastAPI generates them from the code): http://localhost:8000/docs

## Pointing the React dev server at the backend

`client/vite.config.js` proxies `/api` to `http://localhost:49160` by default.
Override per-run with an env var — no file edits needed:

```bash
# against the default port (49160)
cd client && npm run dev

# against the Python backend running on 8000
cd client && VITE_API_PROXY_TARGET=http://localhost:8000 npm run dev
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `49160` | HTTP port read by the app itself (`python -m app.main`). Note: the container scripts pass this in for you and ignore a shell-inherited `PORT` — use `CRUCIBLE_PORT=<n>` with `container-py.sh` |
| `DATABASE_URL` | `sqlite:///<repo>/data/crucible.db` | SQLAlchemy connection string. PostgreSQL: `postgresql+psycopg://user:pass@host/db` (`psycopg[binary]` already ships in requirements; the `doc` column becomes JSONB) |
| `AUTO_INIT_DB` | `true` | `true` → `create_all()` on startup (SQLite default and tests). The container sets `false` so **Alembic** owns the schema (`alembic upgrade head` runs at start via `scripts/db_bootstrap.py`) |
| `CLIENT_DIST` | `<repo>/client/dist` | Built React app served as static files |
| `USE_HTTPS` | `false` | `true` + cert files present → uvicorn serves TLS directly (falls back to HTTP with a warning if certs are missing) |
| `SSL_CERT_PATH` / `SSL_KEY_PATH` | `/app/certs/server.crt` / `.key` | Certificate/key locations |
| `DOCS_DIR` | `<repo>/docs` | Docs directory (served for the `/architecture` page) |
| `SAMPLE_TEMPLATE_PATH` | `<DOCS_DIR>/excel-templates/samples/Upload_Sample_Template.xlsx` | The SLIMS sample upload template served by `GET /api/samples/template/download` |

## Layout

```
backend/
├── app/
│   ├── main.py          # app factory, static/SPA serving, error shape parity
│   ├── config.py        # env-var configuration (PORT, DATABASE_URL, paths)
│   ├── compat.py        # helpers replicating JS semantics (||, parseInt, toFixed)
│   ├── database.py      # engine, sessions, get_db dependency
│   ├── models.py        # SQLAlchemy models (hybrid document pattern — see docstring)
│   ├── schemas.py       # Pydantic request models (lenient — accepts extra keys)
│   ├── store.py         # document-style data-access verbs over SQLAlchemy
│   ├── routers/         # one file per API resource
│   └── utils/           # SDF (RDKit), SLIMS Excel, generic Excel/CSV
├── alembic/             # migration environment + versions/ (schema history)
├── alembic.ini          # Alembic config (DB URL filled from DATABASE_URL)
├── scripts/
│   ├── healthcheck.py            # container HEALTHCHECK probe (HTTP/HTTPS)
│   ├── entrypoint.sh            # container start: db_bootstrap.py → uvicorn
│   ├── db_bootstrap.py          # adopt-or-upgrade the schema (Alembic) on boot
│   └── migrate_sqlite_to_postgres.py   # copy data SQLite → PostgreSQL
└── tests/               # contract-parity tests + unit tests
```
