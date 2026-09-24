from __future__ import annotations

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import select

from app.extensions import db
from app.models import Player
from app.services.player_service import (
    PlayerError,
    create_player,
    set_player_active,
    update_player_name,
)
from app.services.statistics import (
    calculate_player_statistics,
)


players_bp = Blueprint(
    "players",
    __name__,
    url_prefix="/players",
)


@players_bp.get("/")
def list_players():
    players = db.session.scalars(
        select(Player).order_by(
            Player.is_active.desc(),
            Player.name.asc(),
        )
    ).all()

    active_count = sum(
        1
        for player in players
        if player.is_active
    )

    statistics = {
        player.id:
            calculate_player_statistics(
                player
            )
        for player in players
    }

    return render_template(
        "players/list.html",
        players=players,
        active_count=active_count,
        statistics=statistics,
    )


@players_bp.post("/")
def add_player():
    try:
        player = create_player(
            request.form.get(
                "name",
                "",
            )
        )

    except PlayerError as exc:
        flash(
            str(exc),
            "error",
        )

    else:
        flash(
            (
                f"{player.name} "
                f"lades till."
            ),
            "success",
        )

    return redirect(
        url_for(
            "players.list_players"
        )
    )


@players_bp.route(
    "/<int:player_id>/edit",
    methods=[
        "GET",
        "POST",
    ],
)
def edit_player(
    player_id: int,
):
    player = db.get_or_404(
        Player,
        player_id,
    )

    if request.method == "POST":
        try:
            update_player_name(
                player,
                request.form.get(
                    "name",
                    "",
                ),
            )

        except PlayerError as exc:
            flash(
                str(exc),
                "error",
            )

        else:
            flash(
                "Spelaren uppdaterades.",
                "success",
            )

            return redirect(
                url_for(
                    "players.player_detail",
                    player_id=player.id,
                )
            )

    return render_template(
        "players/edit.html",
        player=player,
    )


@players_bp.post(
    "/<int:player_id>/toggle-active"
)
def toggle_active(
    player_id: int,
):
    player = db.get_or_404(
        Player,
        player_id,
    )

    new_state = (
        not player.is_active
    )

    set_player_active(
        player,
        new_state,
    )

    if new_state:
        flash(
            (
                f"{player.name} "
                f"återställdes."
            ),
            "success",
        )
    else:
        flash(
            (
                f"{player.name} "
                f"arkiverades."
            ),
            "success",
        )

    return redirect(
        request.referrer
        or url_for(
            "players.list_players"
        )
    )


@players_bp.get(
    "/<int:player_id>"
)
def player_detail(
    player_id: int,
):
    player = db.get_or_404(
        Player,
        player_id,
    )

    statistics = (
        calculate_player_statistics(
            player
        )
    )

    completed_entries = sorted(
        (
            entry
            for entry
            in player.tournament_entries
            if (
                entry.tournament.status
                == "COMPLETED"
                and entry.placement
                is not None
            )
        ),
        key=lambda entry: (
            (
                entry.tournament
                .result.completed_at
            )
            if (
                entry.tournament.result
                is not None
                and entry.tournament
                .result.completed_at
                is not None
            )
            else entry.tournament.created_at
        ),
        reverse=True,
    )

    return render_template(
        "players/detail.html",
        player=player,
        statistics=statistics,
        entries=completed_entries,
    )