"""/api/instance — which instance is answering (phase SH-13)."""

from typing import Any

from fastapi import APIRouter

from ..config import CRUCIBLE_INSTANCE, CRUCIBLE_INSTANCE_LABEL, PORT, USE_HTTPS
from ..instance import instance_info

router = APIRouter(prefix="/api/instance", tags=["instance"])


@router.get("")
def get_instance() -> dict[str, Any]:
    """GET /api/instance — name, label, port and scheme of this instance.

    Reads nothing from the database and holds nothing secret, so it stays
    open when the login arrives (docs/13-authentication.md): the login page
    itself has to say which instance it belongs to.
    """
    return instance_info(CRUCIBLE_INSTANCE, CRUCIBLE_INSTANCE_LABEL, PORT, USE_HTTPS)
