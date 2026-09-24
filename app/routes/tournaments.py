from __future__ import annotations

from datetime import date, datetime

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
from app.models import Player, Tournament
from app.services.clock_service import (
    ensure_runtime,
)
from app.services.player_elimination import (
    EliminationError,
    restore_last_elimination,
)
from app.services.setup_service import (
    SetupError,
    mark_tournament_ready,
    save_manual_setup,
)
from app.services.tournament_service import (
    InvalidTournamentError,
    create_tournament,
)
from app.services.tournament_structure import (
    ensure_tournament_structure,
    regenerate_tournament_structure,
)


tournaments_bp = Blueprint(
    "tournaments",
    __name__,
    url_prefix="/tournaments",
)


@tournaments_bp.get("/")
def list_tournaments():
    tournaments = db.session.scalars(
        select(Tournament).order_by(
            Tournament.tournament_date.desc(),
            Tournament.created_at.desc(),
        )
    ).all()

    return render_template(
        "tournaments/history.html",
        tournaments=tournaments,
    )


@tournaments_bp.route(
    "/new",
    methods=["GET", "POST"],
)
def new_tournament():
    players = db.session.scalars(
        select(Player)
        .where(
            Player.is_active.is_(True)
        )
        .order_by(
            Player.name.asc()
        )
    ).all()

    if request.method == "POST":
        selected_player_ids = []

        for raw_player_id in request.form.getlist(
            "player_ids"
        ):
            try:
                selected_player_ids.append(
                    int(raw_player_id)
                )
            except ValueError:
                continue

        try:
            tournament_date = datetime.strptime(
                request.form.get(
                    "tournament_date",
                    "",
                ),
                "%Y-%m-%d",
            ).date()

        except ValueError:
            flash(
                "Ange ett giltigt datum.",
                "error",
            )

            return render_template(
                "tournaments/new.html",
                players=players,
                today=date.today().isoformat(),
            )

        try:
            hours = int(
                request.form.get(
                    "duration_hours",
                    "0",
                )
            )

            minutes = int(
                request.form.get(
                    "duration_minutes",
                    "0",
                )
            )

            buy_in = int(
                request.form.get(
                    "buy_in",
                    "0",
                )
            )

            bounty_enabled = (
                request.form.get(
                    "bounty_enabled"
                )
                == "on"
            )

            bounty_amount = int(
                request.form.get(
                    "bounty_amount",
                    "0",
                )
                or 0
            )

        except ValueError:
            flash(
                "Kontrollera att alla belopp och tider är giltiga heltal.",
                "error",
            )

            return render_template(
                "tournaments/new.html",
                players=players,
                today=date.today().isoformat(),
            )

        target_duration_minutes = (
            hours * 60
            + minutes
        )

        try:
            tournament = create_tournament(
                name=request.form.get(
                    "name",
                    "",
                ),
                tournament_date=tournament_date,
                target_duration_minutes=target_duration_minutes,
                buy_in=buy_in,
                bounty_enabled=bounty_enabled,
                bounty_amount=bounty_amount,
                player_ids=selected_player_ids,
            )

        except InvalidTournamentError as exc:
            flash(
                str(exc),
                "error",
            )

        else:
            flash(
                f"{tournament.name} skapades.",
                "success",
            )

            return redirect(
                url_for(
                    "tournaments.setup",
                    tournament_id=tournament.id,
                )
            )

    return render_template(
        "tournaments/new.html",
        players=players,
        today=date.today().isoformat(),
    )


@tournaments_bp.get(
    "/<int:tournament_id>/setup"
)
def setup(
    tournament_id: int,
):
    tournament = db.get_or_404(
        Tournament,
        tournament_id,
    )

    ensure_tournament_structure(
        tournament
    )

    return render_template(
        "tournaments/setup.html",
        tournament=tournament,
    )


@tournaments_bp.post(
    "/<int:tournament_id>/setup/save"
)
def save_setup(
    tournament_id: int,
):
    tournament = db.get_or_404(
        Tournament,
        tournament_id,
    )

    ensure_tournament_structure(
        tournament
    )

    try:
        starting_stack = int(
            request.form.get(
                "starting_stack",
                "0",
            )
        )

        payouts = [
            int(value)
            for value in (
                request.form.getlist(
                    "payout_amount"
                )
            )
        ]

        small_blinds = (
            request.form.getlist(
                "small_blind"
            )
        )

        big_blinds = (
            request.form.getlist(
                "big_blind"
            )
        )

        durations = (
            request.form.getlist(
                "duration_minutes"
            )
        )

        if not (
            len(small_blinds)
            == len(big_blinds)
            == len(durations)
        ):
            raise SetupError(
                "Blindstrukturen kunde inte läsas korrekt."
            )

        blind_levels = [
            (
                int(small),
                int(big),
                int(duration),
            )
            for (
                small,
                big,
                duration,
            ) in zip(
                small_blinds,
                big_blinds,
                durations,
                strict=True,
            )
        ]

        save_manual_setup(
            tournament=tournament,
            starting_stack=starting_stack,
            payouts=payouts,
            blind_levels=blind_levels,
        )

    except (
        ValueError,
        SetupError,
    ) as exc:
        db.session.rollback()

        flash(
            str(exc),
            "error",
        )

    else:
        flash(
            "Turneringsstrukturen sparades.",
            "success",
        )

    return redirect(
        url_for(
            "tournaments.setup",
            tournament_id=tournament.id,
        )
    )


@tournaments_bp.post(
    "/<int:tournament_id>/setup/regenerate"
)
def regenerate_setup(
    tournament_id: int,
):
    tournament = db.get_or_404(
        Tournament,
        tournament_id,
    )

    regenerate_tournament_structure(
        tournament
    )

    flash(
        "Startstack och blindstruktur genererades på nytt.",
        "success",
    )

    return redirect(
        url_for(
            "tournaments.setup",
            tournament_id=tournament.id,
        )
    )


@tournaments_bp.post(
    "/<int:tournament_id>/setup/ready"
)
def ready_tournament(
    tournament_id: int,
):
    tournament = db.get_or_404(
        Tournament,
        tournament_id,
    )

    try:
        mark_tournament_ready(
            tournament
        )

    except SetupError as exc:
        db.session.rollback()

        flash(
            str(exc),
            "error",
        )

        return redirect(
            url_for(
                "tournaments.setup",
                tournament_id=tournament.id,
            )
        )

    flash(
        "Turneringen är redo att startas.",
        "success",
    )

    return redirect(
        url_for(
            "tournaments.admin",
            tournament_id=tournament.id,
        )
    )


@tournaments_bp.get(
    "/<int:tournament_id>/admin"
)
def admin(
    tournament_id: int,
):
    tournament = db.get_or_404(
        Tournament,
        tournament_id,
    )

    if tournament.status == "DRAFT":
        flash(
            "Slutför setupen innan turneringen startas.",
            "error",
        )

        return redirect(
            url_for(
                "tournaments.setup",
                tournament_id=tournament.id,
            )
        )

    if tournament.status == "COMPLETED":
        return redirect(
            url_for(
                "tournaments.result",
                tournament_id=tournament.id,
            )
        )

    ensure_tournament_structure(
        tournament
    )

    ensure_runtime(
        tournament
    )

    return render_template(
        "tournaments/admin.html",
        tournament=tournament,
    )


@tournaments_bp.get(
    "/<int:tournament_id>/display"
)
def display(
    tournament_id: int,
):
    tournament = db.get_or_404(
        Tournament,
        tournament_id,
    )

    if tournament.status == "DRAFT":
        flash(
            "Turneringen måste vara READY innan displayen kan öppnas.",
            "error",
        )

        return redirect(
            url_for(
                "tournaments.setup",
                tournament_id=tournament.id,
            )
        )

    ensure_tournament_structure(
        tournament
    )

    ensure_runtime(
        tournament
    )

    return render_template(
        "tournaments/display.html",
        tournament=tournament,
    )


@tournaments_bp.get(
    "/<int:tournament_id>/result"
)
def result(
    tournament_id: int,
):
    tournament = db.get_or_404(
        Tournament,
        tournament_id,
    )

    if (
        tournament.status != "COMPLETED"
        or tournament.result is None
    ):
        flash(
            "Turneringen är inte avslutad ännu.",
            "error",
        )

        return redirect(
            url_for(
                "tournaments.admin",
                tournament_id=tournament.id,
            )
        )

    standings = sorted(
        tournament.players,
        key=lambda entry: (
            entry.placement
            if entry.placement is not None
            else 999999
        ),
    )

    bounty_leaders = sorted(
        (
            entry
            for entry in tournament.players
            if entry.bounty_winnings > 0
        ),
        key=lambda entry: (
            entry.bounty_winnings
        ),
        reverse=True,
    )

    return render_template(
        "tournaments/result.html",
        tournament=tournament,
        standings=standings,
        bounty_leaders=bounty_leaders,
    )


@tournaments_bp.post(
    "/<int:tournament_id>/result/undo-last"
)
def undo_last_result(
    tournament_id: int,
):
    tournament = db.get_or_404(
        Tournament,
        tournament_id,
    )

    runner_up = next(
        (
            entry
            for entry in tournament.players
            if entry.placement == 2
        ),
        None,
    )

    if runner_up is None:
        flash(
            "Ingen sista eliminering kunde hittas.",
            "error",
        )

        return redirect(
            url_for(
                "tournaments.result",
                tournament_id=tournament.id,
            )
        )

    try:
        restore_last_elimination(
            tournament=tournament,
            entry_id=runner_up.id,
        )

    except EliminationError as exc:
        db.session.rollback()

        flash(
            str(exc),
            "error",
        )

        return redirect(
            url_for(
                "tournaments.result",
                tournament_id=tournament.id,
            )
        )

    flash(
        "Den sista elimineringen ångrades.",
        "success",
    )

    return redirect(
        url_for(
            "tournaments.admin",
            tournament_id=tournament.id,
        )
    )