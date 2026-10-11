from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import Tournament
from app.services.clock_service import serialize_clock_state
from app.services.buyin_undo import BuyinUndoError, undo_last_buyin
from app.services.reentry_service import (
    ReentryError,
    register_reentry,
)


reentry_api_bp = Blueprint(
    "reentry_api",
    __name__,
    url_prefix="/api",
)


@reentry_api_bp.post("/tournaments/<int:tournament_id>/undo-buyin")
def undo_buyin(tournament_id: int):
    tournament = db.get_or_404(Tournament, tournament_id)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("action_id"), str):
        return jsonify({"ok": False, "error": "Välj inköpet som ska ångras."}), 400
    try:
        undo_last_buyin(tournament, action_id=payload["action_id"])
    except BuyinUndoError as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify(serialize_clock_state(tournament))


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
