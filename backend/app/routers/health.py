"""/api/health -- the one route that stays open on every rung (phase SH-3a).

The container's HEALTHCHECK, the cron monitor and ``container-py.sh`` used
to probe ``/api/stats``. Once the login is on, that route answers 401 to a
probe with no token, which a monitor would read as "dead" and restart a
healthy application every five minutes. So the probes moved here.

Rule 3 of docs/13-authentication.md: this route says *ok* and nothing
else -- no counts, no versions, nothing worth reading without a login. It
does touch the database with the cheapest possible statement, because an
application whose database is unreachable is not healthy, whatever its
process says.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    """GET /api/health -- {"status": "ok"}, or 503 when the database is not reachable."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database not reachable") from exc
    return {"status": "ok"}
