from __future__ import annotations

from flask import Blueprint, jsonify

from app.extensions import db
from app.models import Tournament
from app.services.clock_service import serialize_clock_state
from app.services.reentry_service import (
    ReentryError,
    register_reentry,
)


reentry_api_bp = Blueprint(
    "reentry_api",
    __name__,
    url_prefix="/api",
)


@reentry_api_bp.post(
    "/tournaments/<int:tournament_id>/players/<int:entry_id>/reentry"
)
def reentry_player(
    tournament_id: int,
    entry_id: int,
):
    tournament = db.get_or_404(
        Tournament,
        tournament_id,
    )

    try:
        register_reentry(
            tournament=tournament,
            entry_id=entry_id,
        )

    except ReentryError as exc:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": str(exc),
                }
            ),
            400,
        )

    return jsonify(
        serialize_clock_state(
            tournament
        )
    )