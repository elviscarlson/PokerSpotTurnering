from __future__ import annotations

from flask import (
    Blueprint,
    jsonify,
    request,
)

from app.extensions import db
from app.models import Tournament
from app.services.clock_service import (
    ClockError,
    adjust_time,
    move_level,
    pause_clock,
    reset_current_level,
    resume_clock,
    serialize_clock_state,
    start_clock,
)
from app.services.player_elimination import (
    EliminationError,
    eliminate_player,
    restore_last_elimination,
)


api_bp = Blueprint(
    "api",
    __name__,
    url_prefix="/api",
)


def get_tournament_or_404(
    tournament_id: int,
) -> Tournament:
    return db.get_or_404(
        Tournament,
        tournament_id,
    )


def error_response(
    exc: Exception,
):
    return (
        jsonify(
            {
                "ok": False,
                "error": str(exc),
            }
        ),
        400,
    )


@api_bp.get(
    "/tournaments/<int:tournament_id>/state"
)
def tournament_state(
    tournament_id: int,
):
    tournament = (
        get_tournament_or_404(
            tournament_id
        )
    )

    try:
        state = serialize_clock_state(
            tournament
        )

    except ClockError as exc:
        return error_response(
            exc
        )

    return jsonify(
        state
    )


@api_bp.post(
    "/tournaments/<int:tournament_id>/start"
)
def tournament_start(
    tournament_id: int,
):
    tournament = (
        get_tournament_or_404(
            tournament_id
        )
    )

    try:
        start_clock(
            tournament
        )

    except ClockError as exc:
        return error_response(
            exc
        )

    return jsonify(
        serialize_clock_state(
            tournament
        )
    )


@api_bp.post(
    "/tournaments/<int:tournament_id>/pause"
)
def tournament_pause(
    tournament_id: int,
):
    tournament = (
        get_tournament_or_404(
            tournament_id
        )
    )

    try:
        pause_clock(
            tournament
        )

    except ClockError as exc:
        return error_response(
            exc
        )

    return jsonify(
        serialize_clock_state(
            tournament
        )
    )


@api_bp.post(
    "/tournaments/<int:tournament_id>/resume"
)
def tournament_resume(
    tournament_id: int,
):
    tournament = (
        get_tournament_or_404(
            tournament_id
        )
    )

    try:
        resume_clock(
            tournament
        )

    except ClockError as exc:
        return error_response(
            exc
        )

    return jsonify(
        serialize_clock_state(
            tournament
        )
    )


@api_bp.post(
    "/tournaments/<int:tournament_id>/next-level"
)
def tournament_next_level(
    tournament_id: int,
):
    tournament = (
        get_tournament_or_404(
            tournament_id
        )
    )

    try:
        move_level(
            tournament,
            direction=1,
        )

    except ClockError as exc:
        return error_response(
            exc
        )

    return jsonify(
        serialize_clock_state(
            tournament
        )
    )


@api_bp.post(
    "/tournaments/<int:tournament_id>/previous-level"
)
def tournament_previous_level(
    tournament_id: int,
):
    tournament = (
        get_tournament_or_404(
            tournament_id
        )
    )

    try:
        move_level(
            tournament,
            direction=-1,
        )

    except ClockError as exc:
        return error_response(
            exc
        )

    return jsonify(
        serialize_clock_state(
            tournament
        )
    )


@api_bp.post(
    "/tournaments/<int:tournament_id>/adjust-time"
)
def tournament_adjust_time(
    tournament_id: int,
):
    tournament = (
        get_tournament_or_404(
            tournament_id
        )
    )

    payload = (
        request.get_json(
            silent=True
        )
        or {}
    )

    try:
        delta_seconds = int(
            payload.get(
                "delta_seconds",
                0,
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        return (
            jsonify(
                {
                    "ok": False,
                    "error": (
                        "delta_seconds måste vara ett heltal."
                    ),
                }
            ),
            400,
        )

    try:
        adjust_time(
            tournament,
            delta_seconds=delta_seconds,
        )

    except ClockError as exc:
        return error_response(
            exc
        )

    return jsonify(
        serialize_clock_state(
            tournament
        )
    )


@api_bp.post(
    "/tournaments/<int:tournament_id>/reset-level"
)
def tournament_reset_level(
    tournament_id: int,
):
    tournament = (
        get_tournament_or_404(
            tournament_id
        )
    )

    try:
        reset_current_level(
            tournament
        )

    except ClockError as exc:
        return error_response(
            exc
        )

    return jsonify(
        serialize_clock_state(
            tournament
        )
    )


@api_bp.post(
    "/tournaments/<int:tournament_id>/players/<int:entry_id>/eliminate"
)
def tournament_eliminate_player(
    tournament_id: int,
    entry_id: int,
):
    tournament = (
        get_tournament_or_404(
            tournament_id
        )
    )

    payload = (
        request.get_json(
            silent=True
        )
        or {}
    )

    raw_eliminator = payload.get(
        "eliminated_by_entry_id"
    )

    eliminated_by_entry_id = None

    if raw_eliminator not in (
        None,
        "",
    ):
        try:
            eliminated_by_entry_id = int(
                raw_eliminator
            )
        except (
            TypeError,
            ValueError,
        ):
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": (
                            "Ogiltig spelare för bounty."
                        ),
                    }
                ),
                400,
            )

    try:
        eliminate_player(
            tournament=tournament,
            entry_id=entry_id,
            eliminated_by_entry_id=(
                eliminated_by_entry_id
            ),
        )

    except EliminationError as exc:
        return error_response(
            exc
        )

    return jsonify(
        serialize_clock_state(
            tournament
        )
    )


@api_bp.post(
    "/tournaments/<int:tournament_id>/players/<int:entry_id>/restore"
)
def tournament_restore_player(
    tournament_id: int,
    entry_id: int,
):
    tournament = (
        get_tournament_or_404(
            tournament_id
        )
    )

    try:
        restore_last_elimination(
            tournament=tournament,
            entry_id=entry_id,
        )

    except EliminationError as exc:
        return error_response(
            exc
        )

    return jsonify(
        serialize_clock_state(
            tournament
        )
    )